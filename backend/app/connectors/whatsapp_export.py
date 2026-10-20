"""Parser for WhatsApp "Export chat" .txt files (no network).

Handles both layouts WhatsApp produces:
    Android: 12/03/24, 14:05 - Sarah Khan: text
    iOS:     [12/03/24, 2:05:12 PM] Sarah Khan: text
with 12h or 24h times, 2- or 4-digit years and messages that continue on the next lines.
System lines (encryption notice, "X added Y") and media placeholders are skipped.
"""

import re
from datetime import datetime
from pathlib import PurePath

from app.connectors.base import (
    FileConnector,
    NormalizedMessage,
    OccurrenceCounter,
    ParseResult,
    as_utc,
    decode_text,
    stable_id,
)

SOURCE = "whatsapp"

_DATE = r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}"
_TIME = r"\d{1,2}[:.]\d{2}(?:[:.]\d{2})?(?: ?[AaPp]\.? ?[Mm]\.?)?"
# One regex for both layouts: "[date, time] rest" or "date, time - rest"
HEADER_RE = re.compile(
    rf"^(?:\[(?P<d1>{_DATE}),? (?P<t1>{_TIME})\] |(?P<d2>{_DATE}),? (?P<t2>{_TIME}) - )(?P<rest>.*)$"
)
# "Name: text"; names are short, so a long prefix before ": " is a system line, not an author
AUTHOR_RE = re.compile(r"^(?P<author>[^:\n]{1,60}): (?P<text>.*)$", re.DOTALL)
# iOS marks system messages and attachments with an invisible U+200E right after "Name: "
IOS_SYSTEM_MARK = ": ‎"

# Placeholders WhatsApp writes instead of the real content
SKIP_TEXT_RE = re.compile(
    r"^(?:<media omitted>|<attached: .+>|"
    r"(?:image|video|audio|sticker|gif|document|contact card) omitted|"
    r"this message was deleted\.?|you deleted this message\.?|missed (?:voice|video) call|null)$",
    re.IGNORECASE,
)
EDITED_RE = re.compile(r"\s*<This message was edited>$", re.IGNORECASE)

# Invisible direction marks that iOS exports put before lines and names
_INVISIBLE = dict.fromkeys(map(ord, "‎‏‪‫‬‭‮﻿"), None)
_SPACES = {0x202F: " ", 0x00A0: " "}


def clean_line(line: str) -> str:
    return line.translate(_INVISIBLE).translate(_SPACES).rstrip("\r")


def is_whatsapp_text(text: str, min_lines: int = 3) -> bool:
    """True if at least `min_lines` lines look like WhatsApp message headers."""
    hits = 0
    for line in text.splitlines():
        if HEADER_RE.match(clean_line(line)):
            hits += 1
            if hits >= min_lines:
                return True
    return False


def chat_name_from_filename(filename: str) -> str:
    stem = PurePath(filename).stem
    match = re.match(r"^WhatsApp Chat (?:with|-) (.+)$", stem, re.IGNORECASE)
    return (match.group(1) if match else stem).strip()


def _split_date(value: str) -> tuple[int, int, int]:
    a, b, y = (int(p) for p in re.split(r"[/.-]", value))
    return a, b, y


def _day_first(dates: list[str]) -> bool:
    """dd/mm unless the file proves mm/dd (a second number above 12 and no first number above 12)."""
    parts = [_split_date(d) for d in dates]
    if any(a > 12 for a, _, _ in parts):
        return True
    if any(b > 12 for _, b, _ in parts):
        return False
    return True


def _parse_datetime(date_str: str, time_str: str, day_first: bool) -> datetime:
    a, b, year = _split_date(date_str)
    day, month = (a, b) if day_first else (b, a)
    if year < 100:
        year += 2000

    time_str = time_str.strip()
    ampm = re.search(r"([AaPp])\.? ?[Mm]\.?$", time_str)
    clock = re.split(r"[:.]", re.sub(r" ?[AaPp]\.? ?[Mm]\.?$", "", time_str))
    hour, minute = int(clock[0]), int(clock[1])
    second = int(clock[2]) if len(clock) > 2 else 0
    if ampm:
        is_pm = ampm.group(1).lower() == "p"
        hour = hour % 12 + (12 if is_pm else 0)
    return datetime(year, month, day, hour, minute, second)


def parse_whatsapp(text: str, filename: str) -> ParseResult:
    channel = chat_name_from_filename(filename)

    # First pass: group lines into entries (a header line plus its continuation lines)
    entries: list[dict] = []
    for number, original in enumerate(text.splitlines(), start=1):
        line = clean_line(original)
        match = HEADER_RE.match(line)
        if match:
            entries.append(
                {
                    "date": match["d1"] or match["d2"],
                    "time": match["t1"] or match["t2"],
                    "rest": [match["rest"]],
                    "line": number,
                    "lines": [line],
                    "system": IOS_SYSTEM_MARK in original,
                }
            )
        elif entries:
            entries[-1]["rest"].append(line)
            entries[-1]["lines"].append(line)
        # Text before the first header (rare) has no date or author and is ignored

    day_first = _day_first([e["date"] for e in entries])
    result = ParseResult()
    counter = OccurrenceCounter()

    for entry in entries:
        match = AUTHOR_RE.match("\n".join(entry["rest"]))
        if not match or entry["system"]:  # system line: encryption notice, "X added Y", attachments...
            result.skipped += 1
            continue
        author = match["author"].strip()
        body = EDITED_RE.sub("", match["text"].strip())
        if not body or SKIP_TEXT_RE.match(body):
            result.skipped += 1
            continue

        sent_at = as_utc(_parse_datetime(entry["date"], entry["time"], day_first))
        occurrence = counter.next(sent_at, author, body)
        result.messages.append(
            NormalizedMessage(
                source=SOURCE,
                external_id=stable_id(SOURCE, channel, sent_at.isoformat(), author, body, occurrence),
                channel=channel,
                author=author,
                sent_at=sent_at,
                text=body,
                raw={"filename": filename, "line": entry["line"], "lines": entry["lines"]},
            )
        )
    return result


class WhatsAppExportConnector(FileConnector):
    source = SOURCE

    def parse(self) -> ParseResult:
        return parse_whatsapp(decode_text(self.data), self.filename)
