from pydantic import BaseModel, ConfigDict

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
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    display_name: str
    config: dict
    last_synced_at: UtcDatetime | None
    created_at: UtcDatetime
    message_count: int = 0


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
