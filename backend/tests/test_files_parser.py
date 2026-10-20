from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.connectors.files import (
    EmailFileConnector,
    MeetingNotesConnector,
    clean_email_body,
    connector_for_upload,
    detect_type,
    find_notes_date,
    html_to_text,
    parse_eml,
    parse_meeting_notes,
)
from app.connectors.messenger_export import MessengerExportConnector
from app.connectors.whatsapp_export import WhatsAppExportConnector

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# ---------- .eml ----------


def test_eml_sender_date_subject():
    msg = parse_eml(fixture("client_email.eml"), "client_email.eml").messages[0]

    assert msg.source == "email"
    assert msg.author == "Sarah Khan"
    assert msg.sent_at == datetime(2024, 3, 19, 8, 41, 7, tzinfo=timezone.utc)  # +01:00 converted to UTC
    assert msg.channel == "Delivery app - notification requirements"  # "Re:" removed
    assert msg.external_id == "CAF1a2b3c4d5e6@mail.acme-logistics.example"
    assert msg.text.startswith("Re: Delivery app - notification requirements\n\nHi Rahim,")


def test_eml_strips_quoted_reply_and_signature():
    text = parse_eml(fixture("client_email.eml"), "client_email.eml").messages[0].text

    assert text.endswith("Also, the tracking page has to work on mobile browsers.")
    assert "at most 5 minutes" in text
    for removed in ("wrote:", "Here is our summary", "Best regards", "Operations Manager", "+44"):
        assert removed not in text


def test_eml_raw_keeps_headers_and_full_body():
    raw = parse_eml(fixture("client_email.eml"), "client_email.eml").messages[0].raw

    assert raw["to"] == "Rahim Uddin <rahim@devteam.example>"
    assert raw["in_reply_to"] == "<A1B2C3@devteam.example>"
    assert "Here is our summary" in raw["body"]


def test_eml_html_only_body():
    msg = parse_eml(fixture("client_email_html.eml"), "client_email_html.eml").messages[0]

    assert msg.author == "tom.becker@acme-logistics.example"  # no display name
    assert msg.channel == "Reporting"
    assert "- number of deliveries per driver" in msg.text
    assert "average delivery time & late deliveries" in msg.text
    assert "Managers need it every Monday at 8:00." in msg.text
    for removed in ("color: #333", "Earlier: can you send", "Thanks,", "<p>"):
        assert removed not in msg.text


def test_eml_without_message_id_gets_stable_id():
    data = b"From: a@example.com\nSubject: Export\nDate: Tue, 19 Mar 2024 09:00:00 +0000\n\nPlease add CSV export.\n"
    first = parse_eml(data, "a.eml").messages[0]
    second = parse_eml(data, "a.eml").messages[0]
    assert first.external_id == second.external_id
    assert len(first.external_id) == 40


def test_eml_without_date_uses_upload_time():
    data = b"From: a@example.com\nSubject: Export\n\nPlease add CSV export.\n"
    assert parse_eml(data, "a.eml", now=NOW).messages[0].sent_at == NOW


def test_empty_eml_is_skipped():
    result = parse_eml(b"From: a@example.com\n\n\n", "empty.eml")
    assert result.messages == []
    assert result.skipped == 1


SEVEN_LINES = "Thanks\n\nline 1\nline 2\nline 3\nline 4\nline 5\nline 6\nline 7"


@pytest.mark.parametrize(
    "body, expected",
    [
        ("Please add export.\n\n-- \nSarah\nAcme", "Please add export."),
        ("Please add export.\n\nSent from my iPhone", "Please add export."),
        ("Please add export.\n> old line\nThanks!", "Please add export."),
        (
            "Please add export.\n\n________________________________\nFrom: Rahim\nSent: Monday\nSubject: x\n\nold",
            "Please add export.",
        ),
        ("Please add export.\n\n-----Original Message-----\nFrom: Rahim\nold", "Please add export."),
        (
            "Please add export.\n\nOn Mon, 18 Mar 2024 at 17:12, Rahim Uddin\n<rahim@x.example> wrote:\n> old",
            "Please add export.",
        ),
        # "Thanks" is the whole message: nothing is removed
        ("Thanks!", "Thanks!"),
        # A sign-off word far from the end is not a signature
        (SEVEN_LINES, SEVEN_LINES),
    ],
)
def test_clean_email_body(body, expected):
    assert clean_email_body(body) == expected


def test_html_to_text_skips_style_and_quotes():
    html = "<style>p{}</style><p>One &amp; two</p><blockquote><p>quoted</p></blockquote><p>Three</p>"
    assert html_to_text(html) == "One & two\n\nThree"


# ---------- meeting notes ----------


def test_meeting_notes_one_message_per_paragraph():
    result = parse_meeting_notes(fixture("meeting_notes.md").decode("utf-8"), "kickoff.md", now=NOW)

    assert len(result.messages) == 4
    # title, Date/Attendees block, ---, and the three "## ..." headings
    assert result.skipped == 6
    assert result.messages[0].text.startswith("Acme wants a mobile app for drivers")
    assert result.messages[1].text == (
        "- Drivers log in with their phone number and a one-time code.\n"
        "- Dispatchers can reassign a delivery to another driver at any time."
    )
    assert result.messages[-1].text == "The system should be easy to use."
    assert all(m.source == "meeting_notes" and m.channel == "kickoff" and m.author == "" for m in result.messages)


def test_meeting_notes_date_from_date_line():
    result = parse_meeting_notes(fixture("meeting_notes.md").decode("utf-8"), "kickoff.md", now=NOW)
    assert {m.sent_at for m in result.messages} == {datetime(2026, 10, 1, tzinfo=timezone.utc)}


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Weekly sync 2026-09-14\n\nNotes", datetime(2026, 9, 14, tzinfo=timezone.utc)),
        ("Date: 3 February 2026\n\nNotes", datetime(2026, 2, 3, tzinfo=timezone.utc)),
        ("Meeting on Tuesday, October 6, 2026\n\nNotes", datetime(2026, 10, 6, tzinfo=timezone.utc)),
        ("No date here\n\nNotes", None),
    ],
)
def test_find_notes_date(text, expected):
    assert find_notes_date(text) == expected


def test_meeting_notes_without_date_use_upload_time():
    result = parse_meeting_notes("First point.\n\nSecond point.", "notes.txt", now=NOW)
    assert [m.sent_at for m in result.messages] == [NOW, NOW]


def test_meeting_notes_heading_inside_paragraph_is_kept_without_hash():
    result = parse_meeting_notes("## Risks\nThe API may be slow.", "notes.md", now=NOW)
    assert result.messages[0].text == "Risks\nThe API may be slow."


def test_meeting_notes_ids_stable_and_unique():
    text = "Same line.\n\nSame line.\n\nOther line."
    ids = [m.external_id for m in parse_meeting_notes(text, "notes.txt", now=NOW).messages]
    assert len(set(ids)) == 3
    assert ids == [m.external_id for m in parse_meeting_notes(text, "notes.txt", now=NOW).messages]


# ---------- detection ----------


@pytest.mark.parametrize(
    "filename, fixture_name, expected",
    [
        ("WhatsApp Chat with Acme.txt", "whatsapp_android.txt", "whatsapp"),
        ("_chat.txt", "whatsapp_ios.txt", "whatsapp"),
        ("message_1.json", "messenger_message_1.json", "messenger"),
        ("reply.EML", "client_email.eml", "email"),
        ("kickoff.md", "meeting_notes.md", "meeting_notes"),
        ("kickoff.txt", "meeting_notes.md", "meeting_notes"),
        ("contract.pdf", "unsupported.pdf", None),
    ],
)
def test_detect_type(filename, fixture_name, expected):
    assert detect_type(filename, fixture(fixture_name)) == expected


def test_detect_type_rejects_other_json():
    assert detect_type("package.json", b'{"name": "x"}') is None
    assert detect_type("broken.json", b"{oops") is None


def test_connector_for_upload_picks_the_right_class():
    assert isinstance(connector_for_upload("a.txt", fixture("whatsapp_android.txt")), WhatsAppExportConnector)
    assert isinstance(connector_for_upload("a.json", fixture("messenger_message_1.json")), MessengerExportConnector)
    assert isinstance(connector_for_upload("a.eml", fixture("client_email.eml")), EmailFileConnector)
    assert isinstance(connector_for_upload("a.md", fixture("meeting_notes.md")), MeetingNotesConnector)
    assert connector_for_upload("a.pdf", fixture("unsupported.pdf")) is None
