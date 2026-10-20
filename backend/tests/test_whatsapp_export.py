from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.connectors.whatsapp_export import (
    WhatsAppExportConnector,
    chat_name_from_filename,
    is_whatsapp_text,
    parse_whatsapp,
)

FIXTURES = Path(__file__).parent / "fixtures"
ANDROID = (FIXTURES / "whatsapp_android.txt").read_text(encoding="utf-8")
IOS = (FIXTURES / "whatsapp_ios.txt").read_text(encoding="utf-8")


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_android_messages_authors_and_times():
    result = parse_whatsapp(ANDROID, "WhatsApp Chat with Acme Logistics.txt")

    assert [m.author for m in result.messages] == [
        "Sarah Khan",
        "Sarah Khan",
        "Rahim Uddin",
        "Sarah Khan",
        "Rahim Uddin",
    ]
    assert result.messages[0].sent_at == utc(2024, 3, 12, 9, 20)
    assert result.messages[3].sent_at == utc(2024, 3, 13, 18, 2)
    assert all(m.source == "whatsapp" and m.channel == "Acme Logistics" for m in result.messages)


def test_android_skips_system_lines_media_and_deleted():
    result = parse_whatsapp(ANDROID, "chat.txt")

    # encryption notice, "created group", "added you", <Media omitted>, deleted message
    assert result.skipped == 5
    texts = " ".join(m.text for m in result.messages)
    assert "Media omitted" not in texts
    assert "deleted" not in texts


def test_multi_line_message_is_kept_whole():
    result = parse_whatsapp(ANDROID, "chat.txt")

    text = result.messages[1].text
    assert text.startswith("A few more things:\n- The dispatcher must be able to reassign")
    assert text.endswith("Also the app needs to be fast.")
    assert "\n\nAlso" in text


def test_edited_marker_is_removed():
    result = parse_whatsapp(ANDROID, "chat.txt")
    assert result.messages[-1].text == "Noted. We'll add it to the list."


def test_ios_bracket_format_12h_and_month_first():
    result = parse_whatsapp(IOS, "_chat.txt")

    assert [m.author for m in result.messages] == ["Tom Becker", "Priya Nair", "Tom Becker", "Tom Becker", "Tom Becker"]
    # 3/14/24 is month-first because 14 cannot be a month; PM and the narrow no-break space are handled
    assert result.messages[0].sent_at == utc(2024, 3, 14, 14, 6, 40)
    # 12:01 AM is just after midnight
    assert result.messages[2].sent_at == utc(2024, 3, 15, 0, 1, 30)
    assert result.messages[0].text == (
        "Morning! Quick update from our side.\nThe warehouse team wants to export the daily delivery report as CSV."
    )


def test_ios_skips_marked_system_lines_and_attachments():
    result = parse_whatsapp(IOS, "_chat.txt")

    # encryption notice, "image omitted", "<attached: ...>"
    assert result.skipped == 3
    assert all("‎" not in m.text and "‎" not in m.author for m in result.messages)


def test_identical_messages_get_different_ids():
    result = parse_whatsapp(IOS, "_chat.txt")

    thanks = [m for m in result.messages if m.text == "Thanks!"]
    assert len(thanks) == 2
    assert thanks[0].external_id != thanks[1].external_id


def test_ids_are_stable_across_parses():
    first = parse_whatsapp(ANDROID, "WhatsApp Chat with Acme Logistics.txt")
    second = parse_whatsapp(ANDROID, "WhatsApp Chat with Acme Logistics.txt")
    assert [m.external_id for m in first.messages] == [m.external_id for m in second.messages]


def test_longer_export_keeps_ids_of_old_messages():
    name = "WhatsApp Chat with Acme Logistics.txt"
    longer = ANDROID + "14/03/24, 10:00 - Sarah Khan: One more: drivers need offline mode.\n"

    old_ids = {m.external_id for m in parse_whatsapp(ANDROID, name).messages}
    new_ids = {m.external_id for m in parse_whatsapp(longer, name).messages}

    assert old_ids < new_ids
    assert len(new_ids - old_ids) == 1


def test_day_first_is_default_when_ambiguous():
    text = "01/02/24, 10:00 - Ann: Hello\n01/02/24, 10:01 - Ann: Second\n"
    result = parse_whatsapp(text, "chat.txt")
    assert result.messages[0].sent_at == utc(2024, 2, 1, 10, 0)


def test_four_digit_year_and_lowercase_pm():
    text = "25/12/2023, 3:45 pm - Ann: Please add a holiday calendar.\n"
    result = parse_whatsapp(text, "chat.txt")
    assert result.messages[0].sent_at == utc(2023, 12, 25, 15, 45)


def test_raw_keeps_original_lines():
    result = parse_whatsapp(ANDROID, "chat.txt")
    raw = result.messages[1].raw
    assert raw["filename"] == "chat.txt"
    assert raw["line"] == 5
    assert raw["lines"][0].startswith("12/03/24, 09:21 - Sarah Khan:")


def test_detection():
    assert is_whatsapp_text(ANDROID)
    assert is_whatsapp_text(IOS)
    assert not is_whatsapp_text("Meeting notes\n\nWe discussed the delivery app.\n")


def test_chat_name_from_filename():
    assert chat_name_from_filename("WhatsApp Chat with Acme Logistics.txt") == "Acme Logistics"
    assert chat_name_from_filename("WhatsApp Chat - Acme Logistics.txt") == "Acme Logistics"
    assert chat_name_from_filename("notes.txt") == "notes"


def test_connector_fetch_filters_by_since():
    connector = WhatsAppExportConnector(ANDROID.encode("utf-8"), "chat.txt")

    everything = connector.fetch()
    assert len(everything) == 5
    assert connector.skipped == 5

    since = utc(2024, 3, 13) - timedelta(seconds=1)
    assert [m.sent_at.day for m in connector.fetch(since)] == [13, 13]


def test_connector_reads_utf8_with_bom():
    connector = WhatsAppExportConnector(b"\xef\xbb\xbf" + ANDROID.encode("utf-8"), "chat.txt")
    assert len(connector.fetch()) == 5
