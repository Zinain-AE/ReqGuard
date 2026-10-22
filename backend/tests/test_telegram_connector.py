"""Telegram connector: getUpdates offset handling, group filtering, errors. All HTTP is mocked."""

from datetime import datetime, timezone

import pytest
import respx

from app.connectors.http import ConnectorError
from app.connectors.telegram import TelegramConnector, TelegramSettings
from tests.conftest import api_json

TOKEN = "123456:TEST-token"
URL = f"https://api.telegram.org/bot{TOKEN}/getUpdates"


def make_connector(chat_ids: list[int] | None = None, state: dict | None = None) -> TelegramConnector:
    return TelegramConnector(TelegramSettings(chat_ids=chat_ids or []), token=TOKEN, state=state)


@respx.mock
def test_fetch_group_messages_and_remember_last_update():
    route = respx.get(URL).respond(json=api_json("telegram/get_updates.json"))
    with make_connector() as connector:
        messages = connector.fetch()

    # Private chat and the service message (new member) are skipped; photo caption is kept
    assert [m.text for m in messages] == [
        "Users should be able to pay with bKash and cards.",
        "This is the checkout screen they want.",
        "Unrelated group",
    ]
    first = messages[0]
    assert first.source == "telegram"
    assert first.external_id == "-1001234567890:41"
    assert first.channel == "Acme project"
    assert first.author == "Sarah Client"
    assert first.sent_at == datetime.fromtimestamp(1792656000, tz=timezone.utc)
    assert messages[1].author == "@tom_pm"

    # Fewer updates than the page size: one call; state holds the highest update_id
    assert route.call_count == 1
    assert "offset" not in route.calls[0].request.url.params
    assert connector.state == {"last_update_id": 503900005}


@respx.mock
def test_next_sync_continues_after_stored_update_id():
    route = respx.get(URL).respond(json=api_json("telegram/get_updates_empty.json"))
    with make_connector(state={"last_update_id": 503900005}) as connector:
        assert connector.fetch() == []
    assert route.calls[0].request.url.params["offset"] == "503900006"
    assert connector.state == {"last_update_id": 503900005}


@respx.mock
def test_full_page_fetches_the_next_one():
    sample = api_json("telegram/get_updates.json")["result"][0]
    page = [
        {"update_id": 1000 + i, "message": {**sample["message"], "message_id": i, "text": f"message {i}"}}
        for i in range(100)
    ]
    route = respx.get(URL)
    route.side_effect = [
        respx.MockResponse(200, json={"ok": True, "result": page}),
        respx.MockResponse(200, json=api_json("telegram/get_updates_empty.json")),
    ]
    with make_connector() as connector:
        assert len(connector.fetch()) == 100
    assert route.calls[1].request.url.params["offset"] == "1100"
    assert connector.state == {"last_update_id": 1099}


@respx.mock
def test_chat_filter():
    respx.get(URL).respond(json=api_json("telegram/get_updates.json"))
    with make_connector(chat_ids=[-1001234567890]) as connector:
        messages = connector.fetch()
    assert {m.channel for m in messages} == {"Acme project"}


def test_chat_ids_accept_strings_from_the_form():
    assert TelegramSettings(chat_ids=["-1001234567890"]).chat_ids == [-1001234567890]
    with pytest.raises(ValueError):
        TelegramSettings(chat_ids=["acme"])


@respx.mock
def test_webhook_conflict():
    respx.get(URL).respond(409, json=api_json("telegram/error_conflict.json"))
    with make_connector() as connector, pytest.raises(ConnectorError, match="webhook"):
        connector.fetch()


@respx.mock
def test_wrong_token_message_does_not_contain_token():
    respx.get(URL).respond(401, json=api_json("telegram/error_unauthorized.json"))
    with make_connector() as connector, pytest.raises(ConnectorError, match="TELEGRAM_BOT_TOKEN") as exc:
        connector.fetch()
    assert TOKEN not in str(exc.value)
