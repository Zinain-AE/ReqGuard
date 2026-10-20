import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.connectors.messenger_export import (
    MessengerExportConnector,
    fix_mojibake,
    is_messenger_json,
    parse_messenger,
)

FIXTURE = Path(__file__).parent / "fixtures" / "messenger_message_1.json"


@pytest.fixture
def export():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fix_mojibake():
    assert fix_mojibake("donâ\u0080\u0099t") == "don’t"
    assert fix_mojibake("â\u0082¬500") == "€500"
    # Already-correct text is not changed
    assert fix_mojibake("café — €") == "café — €"
    assert fix_mojibake("plain ascii") == "plain ascii"


def test_messages_are_parsed_in_time_order(export):
    result = parse_messenger(export, "message_1.json")

    assert [m.author for m in result.messages] == ["Sarah Khan", "Sarah Khan", "Rahim Uddin", "José Martínez"]
    times = [m.sent_at for m in result.messages]
    assert times == sorted(times)
    assert times[0] == datetime(2024, 3, 18, 10, 0, tzinfo=timezone.utc)


def test_text_encoding_is_fixed(export):
    result = parse_messenger(export, "message_1.json")

    assert result.messages[1].text.startswith("Drivers shouldn’t have to log in")
    assert "≤ €500" in result.messages[2].text
    assert all("â\u0080" not in m.text for m in result.messages)


def test_channel_is_fixed_thread_title(export):
    result = parse_messenger(export, "message_1.json")
    assert {m.channel for m in result.messages} == {"Acme Logistics – Delivery App"}
    assert all(m.source == "messenger" for m in result.messages)


def test_photos_reactions_and_unsent_are_skipped(export):
    result = parse_messenger(export, "message_1.json")

    assert result.skipped == 3
    assert not any("reacted" in m.text for m in result.messages)


def test_raw_keeps_original_record(export):
    result = parse_messenger(export, "message_1.json")
    raw = result.messages[0].raw
    assert raw["thread"] == "inbox/acmelogisticsdeliveryapp_10"
    assert raw["record"]["timestamp_ms"] == 1710756000000


def test_ids_are_stable_and_unique(export):
    first = [m.external_id for m in parse_messenger(export, "message_1.json").messages]
    second = [m.external_id for m in parse_messenger(export, "message_1.json").messages]
    assert first == second
    assert len(set(first)) == len(first)


def test_newer_export_layout():
    data = {
        "participants": ["Sarah Khan", "Rahim Uddin"],
        "threadName": "Acme Logistics",
        "messages": [{"senderName": "Sarah Khan", "text": "Add a dark mode, please.", "timestamp": 1710756000000}],
    }
    result = parse_messenger(data, "message_1.json")
    assert result.messages[0].text == "Add a dark mode, please."
    assert result.messages[0].channel == "Acme Logistics"


def test_detection(export):
    assert is_messenger_json(export)
    assert not is_messenger_json({"messages": []})
    assert not is_messenger_json([1, 2])


def test_connector_rejects_other_json():
    connector = MessengerExportConnector(b'{"hello": "world"}', "data.json")
    with pytest.raises(ValueError, match="not a Messenger export"):
        connector.fetch()


def test_connector_rejects_broken_json():
    with pytest.raises(ValueError, match="Not a valid JSON"):
        MessengerExportConnector(b"{oops", "data.json").fetch()


def test_connector_fetch():
    connector = MessengerExportConnector(FIXTURE.read_bytes(), "message_1.json")
    assert len(connector.fetch()) == 4
    assert connector.skipped == 3
