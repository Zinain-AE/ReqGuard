"""Parser for Facebook Messenger "Download your information" JSON (message_1.json), no network.

Facebook writes UTF-8 text as if every byte were a Latin-1 character ("donâ\\u0080\\u0099t"
instead of "don't"); `fix_mojibake` undoes that. The newer export layout
(senderName / text / timestamp) is accepted too and is already correctly encoded.
"""

import json
import re
from datetime import datetime, timezone
from typing import Any

from app.connectors.base import FileConnector, NormalizedMessage, OccurrenceCounter, ParseResult, stable_id

SOURCE = "messenger"

# Texts that Messenger generates itself; they are not something the client wrote
GENERATED_RE = re.compile(
    r"^(?:.+ )?(?:reacted .+ to (?:your|a) message|sent an attachment\.|"
    r"sent a (?:photo|video|sticker|GIF|link|voice message)\.|sent \d+ photos\.|unsent a message\.?|"
    r"started (?:a|the) (?:video )?call\.?|joined the (?:video )?call\.?|missed (?:a|your) (?:video )?call\.?)$",
    re.IGNORECASE,
)
SKIP_TYPES = {"Call", "Subscribe", "Unsubscribe"}


def fix_mojibake(value: str) -> str:
    """Reverse Facebook's double encoding. Text that is already correct is returned unchanged."""
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def is_messenger_json(data: Any) -> bool:
    return isinstance(data, dict) and isinstance(data.get("messages"), list) and "participants" in data


def parse_messenger(data: dict[str, Any], filename: str) -> ParseResult:
    title = fix_mojibake(str(data.get("title") or data.get("threadName") or filename))
    thread = str(data.get("thread_path") or title)
    result = ParseResult()
    counter = OccurrenceCounter()
    rows: list[NormalizedMessage] = []

    for record in data["messages"]:
        if not isinstance(record, dict):
            result.skipped += 1
            continue
        author = fix_mojibake(str(record.get("sender_name") or record.get("senderName") or "")).strip()
        content = record.get("content", record.get("text"))
        timestamp_ms = record.get("timestamp_ms", record.get("timestamp"))
        text = fix_mojibake(content).strip() if isinstance(content, str) else ""

        if (
            not text
            or not isinstance(timestamp_ms, (int, float))
            or record.get("is_unsent")
            or record.get("type") in SKIP_TYPES
            or GENERATED_RE.match(text)
        ):
            result.skipped += 1
            continue

        sent_at = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        occurrence = counter.next(timestamp_ms, author, text)
        rows.append(
            NormalizedMessage(
                source=SOURCE,
                external_id=stable_id(SOURCE, thread, timestamp_ms, author, text, occurrence),
                channel=title,
                author=author,
                sent_at=sent_at,
                text=text,
                raw={"filename": filename, "thread": thread, "record": record},
            )
        )

    # The export lists the newest message first
    result.messages = sorted(rows, key=lambda m: m.sent_at)
    return result


class MessengerExportConnector(FileConnector):
    source = SOURCE

    def parse(self) -> ParseResult:
        try:
            data = json.loads(self.data.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Not a valid JSON file: {exc}") from None
        if not is_messenger_json(data):
            raise ValueError("This JSON file is not a Messenger export (no 'participants' and 'messages').")
        return parse_messenger(data, self.filename)
