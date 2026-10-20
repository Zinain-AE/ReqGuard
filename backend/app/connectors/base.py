"""Shared connector types: the normalised message and the Connector interface.

Every source (chat export, file, or API in Step 4) turns its data into
NormalizedMessage objects. Nothing here touches the database.
"""

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class NormalizedMessage(BaseModel):
    """One message in the unified format (CLAUDE.md rule 1)."""

    source: str
    external_id: str
    channel: str = ""
    author: str = ""
    sent_at: datetime
    text: str
    raw: dict[str, Any] = Field(default_factory=dict)


@dataclass
class ParseResult:
    messages: list[NormalizedMessage] = field(default_factory=list)
    # Lines or records that were recognised but not imported (system lines, media, empty...)
    skipped: int = 0


class Connector(ABC):
    """Anything that can produce messages. `since` limits the result to newer messages."""

    source: str

    @abstractmethod
    def fetch(self, since: datetime | None = None) -> list[NormalizedMessage]: ...


class FileConnector(Connector):
    """A connector over one uploaded file. Subclasses only implement `parse()`."""

    def __init__(self, data: bytes, filename: str):
        self.data = data
        self.filename = filename
        self.skipped = 0

    @abstractmethod
    def parse(self) -> ParseResult: ...

    def fetch(self, since: datetime | None = None) -> list[NormalizedMessage]:
        result = self.parse()
        self.skipped = result.skipped
        if since is None:
            return result.messages
        return [m for m in result.messages if m.sent_at > since]


def decode_text(data: bytes) -> str:
    """Decode an uploaded text file: UTF-8 (with or without BOM), else Windows-1252."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def stable_id(*parts: object) -> str:
    """Deterministic id from the given parts, so re-importing the same message gives the same id."""
    joined = "\x1f".join(str(p) for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


class OccurrenceCounter:
    """Numbers identical keys 0, 1, 2... so two equal messages in one file get different ids."""

    def __init__(self) -> None:
        self._seen: dict[tuple, int] = {}

    def next(self, *key: object) -> int:
        n = self._seen.get(key, 0)
        self._seen[key] = n + 1
        return n


def as_utc(dt: datetime) -> datetime:
    """Naive datetimes (exports without a timezone) are taken as UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
