"""sources and messages

Revision ID: b3c1e2d4f5a6
Revises: 598585fc27c6
Create Date: 2026-10-20 10:00:00.000000

Portable on SQLite and PostgreSQL: config and raw are JSON (not JSONB).
Messages are unique per (project_id, source, external_id) so re-imports are skipped.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c1e2d4f5a6"
down_revision: Union[str, Sequence[str], None] = "598585fc27c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_sources_project_id_projects"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sources")),
        sa.UniqueConstraint(
            "project_id", "type", "display_name", name=op.f("uq_sources_project_id_type_display_name")
        ),
    )
    op.create_index(op.f("ix_sources_project_id"), "sources", ["project_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("channel", sa.String(length=200), nullable=False),
        sa.Column("author", sa.String(length=200), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_messages_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name=op.f("fk_messages_source_id_sources"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
        sa.UniqueConstraint(
            "project_id", "source", "external_id", name=op.f("uq_messages_project_id_source_external_id")
        ),
    )
    op.create_index("ix_messages_project_id_sent_at", "messages", ["project_id", "sent_at"])
    op.create_index(op.f("ix_messages_source_id"), "messages", ["source_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_messages_source_id"), table_name="messages")
    op.drop_index("ix_messages_project_id_sent_at", table_name="messages")
    op.drop_table("messages")
    op.drop_index(op.f("ix_sources_project_id"), table_name="sources")
    op.drop_table("sources")
