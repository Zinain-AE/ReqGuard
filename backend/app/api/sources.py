"""Message sources of a project and file/export uploads. Only the project owner can use these."""

import logging
from pathlib import PurePath
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from sqlalchemy import delete, func, select

from app.api.deps import DbSession, OwnedProject
from app.connectors.files import SUPPORTED_EXTENSIONS, connector_for_upload
from app.connectors.importer import get_or_create_source, import_messages
from app.models import Message, Source
from app.schemas.message import FileImportResult, SourceOut, UploadResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}", tags=["sources"])

MAX_FILES = 10
MAX_FILE_BYTES = 10 * 1024 * 1024

# Emails and meeting notes from many files are grouped under one source each
GROUPED_SOURCE_NAMES = {"email": "Email files", "meeting_notes": "Meeting notes"}


@router.get("/sources", response_model=list[SourceOut])
def list_sources(project: OwnedProject, db: DbSession) -> list[SourceOut]:
    counts = dict(
        db.execute(
            select(Message.source_id, func.count())
            .where(Message.project_id == project.id)
            .group_by(Message.source_id)
        ).all()
    )
    return [
        SourceOut.model_validate(source).model_copy(update={"message_count": counts.get(source.id, 0)})
        for source in project.sources
    ]


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: int, project: OwnedProject, db: DbSession) -> Response:
    """Permanently delete a source and every message imported from it (NFR-04)."""
    source = db.get(Source, source_id)
    if source is None or source.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Source not found")
    # messages.source_id is ON DELETE SET NULL, so the messages are removed explicitly (same transaction)
    db.execute(delete(Message).where(Message.project_id == project.id, Message.source_id == source.id))
    db.delete(source)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _import_file(db: DbSession, project_id: int, filename: str, data: bytes) -> FileImportResult:
    connector = connector_for_upload(filename, data)
    if connector is None:
        return FileImportResult(
            filename=filename,
            type=None,
            error=f"Unsupported file. Upload a WhatsApp .txt export, a Messenger .json export, "
            f"an .eml email or .txt/.md meeting notes ({', '.join(SUPPORTED_EXTENSIONS)}).",
        )
    try:
        messages = connector.fetch()
    except ValueError as exc:
        return FileImportResult(filename=filename, type=connector.source, error=str(exc))
    except Exception:
        logger.exception("Could not parse uploaded file %s", filename)
        return FileImportResult(filename=filename, type=connector.source, error="Could not read this file.")

    name = GROUPED_SOURCE_NAMES.get(connector.source) or (messages[0].channel if messages else PurePath(filename).stem)
    source = get_or_create_source(db, project_id, connector.source, name, {"origin": "upload", "last_file": filename})
    counts = import_messages(db, project_id, source, messages)
    return FileImportResult(
        filename=filename,
        type=connector.source,
        imported=counts.imported,
        duplicates=counts.duplicates,
        skipped=connector.skipped,
    )


@router.post("/uploads", response_model=UploadResult)
def upload_files(
    project: OwnedProject,
    db: DbSession,
    files: Annotated[list[UploadFile], File(description="Chat exports, .eml emails or meeting notes")],
) -> UploadResult:
    """Import messages from uploaded files. The type of each file is detected from its name and content."""
    if len(files) > MAX_FILES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Upload at most {MAX_FILES} files at once")

    results: list[FileImportResult] = []
    for upload in files:
        filename = PurePath(upload.filename or "upload").name
        data = upload.file.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            results.append(
                FileImportResult(filename=filename, type=None, error="File is larger than 10 MB.")
            )
            continue
        results.append(_import_file(db, project.id, filename, data))
    db.commit()

    return UploadResult(
        imported=sum(r.imported for r in results),
        duplicates=sum(r.duplicates for r in results),
        skipped=sum(r.skipped for r in results),
        files=results,
    )
