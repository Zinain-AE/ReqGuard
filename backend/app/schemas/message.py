from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.common import UtcDatetime


class MessageOut(BaseModel):
    """A message in lists. `raw` is left out to keep pages small."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int | None
    source: str
    external_id: str
    channel: str
    author: str
    sent_at: UtcDatetime
    text: str
    imported_at: UtcDatetime


class MessagePage(BaseModel):
    items: list[MessageOut]
    total: int
    page: int
    page_size: int


class SourceOut(BaseModel):
    """A source. Credentials are never part of it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    display_name: str
    config: dict
    last_synced_at: UtcDatetime | None
    created_at: UtcDatetime
    sync_status: str | None = None
    sync_error: str | None = None
    message_count: int = 0
    # API sources only: true while a Gmail source has no connected Google account
    needs_auth: bool = False


class ConnectorOut(BaseModel):
    """An API connector type. `missing_env` lists variable names only, never values."""

    type: str
    label: str
    configured: bool
    missing_env: list[str]


class SourceCreate(BaseModel):
    type: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    # Connector-specific, non-secret settings (e.g. {"project_key": "ACME"}); checked by the connector
    settings: dict[str, Any] = {}


class SourceStatus(BaseModel):
    id: int
    type: str
    configured: bool
    needs_auth: bool
    sync_status: str | None
    sync_error: str | None
    last_synced_at: UtcDatetime | None
    message_count: int


class SyncResult(BaseModel):
    imported: int
    duplicates: int
    sync_status: str
    last_synced_at: UtcDatetime | None


class AuthorizeUrl(BaseModel):
    url: str


class FileImportResult(BaseModel):
    filename: str
    type: str | None  # detected parser; None when the file is not supported
    imported: int = 0
    duplicates: int = 0
    skipped: int = 0
    error: str | None = None


class UploadResult(BaseModel):
    imported: int
    duplicates: int
    skipped: int
    files: list[FileImportResult]
