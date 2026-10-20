"""Small reusable field types for request schemas."""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, EmailStr, StringConstraints

# Trimmed, non-empty name
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

# Valid email, stored lower-case so comparisons are case-insensitive
Email = Annotated[EmailStr, AfterValidator(lambda v: v.strip().lower())]


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


# Datetime sent to the frontend always with a timezone (SQLite returns naive UTC values)
UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]
