from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Source(Base):
    """Where messages come from: an uploaded chat export, a file, or (Step 4) an API connector.

    `config` holds non-secret settings only (e.g. a channel id or file name). Tokens never go here.
    """

    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("project_id", "type", "display_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    # whatsapp | messenger | email | meeting_notes (Step 4 adds jira, slack, telegram, discord, gmail)
    type: Mapped[str] = mapped_column(String(30))
    display_name: Mapped[str] = mapped_column(String(200))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="sources")  # noqa: F821
