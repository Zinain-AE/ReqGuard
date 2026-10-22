"""Slack connector: channel lookup, history + thread replies, pagination, rate limits, errors."""

from datetime import datetime, timezone

import httpx
import pytest
import respx

from app.connectors.http import ConnectorError
from app.connectors.slack import API, SlackConnector, SlackSettings, slack_to_text
from tests.conftest import api_json


def make_connector(*channels: str) -> SlackConnector:
    return SlackConnector(SlackSettings(channels=list(channels) or ["#client-acme"]), token="xoxb-test-token")


def mock_lists(router: respx.Router):
    route = router.get(f"{API}/conversations.list")
    route.side_effect = [
        httpx.Response(200, json=api_json("slack/conversations_list_page1.json")),
        httpx.Response(200, json=api_json("slack/conversations_list_page2.json")),
    ]
    return route


def mock_channel(router: respx.Router):
    mock_lists(router)
    history = router.get(f"{API}/conversations.history")
    history.side_effect = [
        httpx.Response(200, json=api_json("slack/history_page1.json")),
        httpx.Response(200, json=api_json("slack/history_page2.json")),
    ]
    replies = router.get(f"{API}/conversations.replies").respond(json=api_json("slack/replies.json"))
    return history, replies


def test_slack_markup_to_text():
    assert slack_to_text("Hi <@U1>, see <#C1|general> and <https://x.io|the spec> &lt;3") == (
        "Hi @U1, see #general and the spec <3"
    )
    assert slack_to_text("<!here> mail <mailto:a@b.com>") == "@here mail a@b.com"


def test_settings_strip_hash_and_require_a_channel():
    assert SlackSettings(channels=[" #client-acme", "client-acme", "C0GENERAL1"]).channels == [
        "client-acme",
        "C0GENERAL1",
    ]
    with pytest.raises(ValueError):
        SlackSettings(channels=["#", " "])


@respx.mock
def test_fetch_history_threads_and_pagination():
    history, replies = mock_channel(respx.mock)
    with make_connector() as connector:
        messages = connector.fetch()

    # Join message and bot message are skipped; the two thread replies are added
    assert [m.text for m in messages] == [
        "Hi @U0SARAH001, welcome to #client-acme!",
        "The dashboard must load in under 2 seconds & show our KPIs.",
        "Even on mobile?",
        "Yes, on 4G too.",
    ]
    first = messages[1]
    assert first.source == "slack"
    assert first.external_id == "C0ACME0001:1792656000.000200"
    assert first.channel == "#client-acme"
    assert first.author == "Sarah Client"
    assert first.sent_at == datetime.fromtimestamp(1792656000.0002, tz=timezone.utc)
    assert messages[0].author == "U0TOM00001"  # no profile in the message: user id

    assert history.calls[0].request.url.params["channel"] == "C0ACME0001"
    assert history.calls[1].request.url.params["cursor"] == "bmV4dF90czoxNzkyNjU1ODAw"
    assert replies.calls[0].request.url.params["ts"] == "1792656000.000200"
    assert history.calls[0].request.headers["Authorization"] == "Bearer xoxb-test-token"


@respx.mock
def test_channel_by_id_and_since():
    history, _ = mock_channel(respx.mock)
    with make_connector("C0ACME0001") as connector:
        connector.fetch(since=datetime(2026, 10, 21, 0, 0, tzinfo=timezone.utc))
    # 5 minutes margin before `since`
    assert history.calls[0].request.url.params["oldest"] == f"{1792540800 - 300:.6f}"


@respx.mock
def test_rate_limit_is_retried():
    mock_lists(respx.mock)
    history = respx.get(f"{API}/conversations.history")
    history.side_effect = [
        httpx.Response(429, headers={"Retry-After": "1"}),
        httpx.Response(200, json=api_json("slack/history_page2.json")),
    ]
    with make_connector() as connector:
        messages = connector.fetch()
    assert len(messages) == 1
    assert history.call_count == 2


@respx.mock
def test_unknown_channel():
    mock_lists(respx.mock)
    with make_connector("random") as connector, pytest.raises(ConnectorError, match="#random"):
        connector.fetch()


@respx.mock
def test_bot_not_in_channel():
    mock_lists(respx.mock)
    respx.get(f"{API}/conversations.history").respond(json=api_json("slack/error_not_in_channel.json"))
    with make_connector() as connector, pytest.raises(ConnectorError, match="not a member of #client-acme"):
        connector.fetch()


@respx.mock
def test_invalid_token():
    respx.get(f"{API}/conversations.list").respond(json=api_json("slack/error_invalid_auth.json"))
    with make_connector() as connector, pytest.raises(ConnectorError, match="SLACK_BOT_TOKEN") as exc:
        connector.fetch()
    assert "xoxb-test-token" not in str(exc.value)
