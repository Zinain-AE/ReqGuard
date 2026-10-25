"""requirements

Revision ID: e6f4a5b7c8d9
Revises: d5e3f4a6b7c8
Create Date: 2026-10-25 10:00:00.000000

Requirements with versions (text is never updated in place) and links to their source messages.
Also: when each message was last read by extraction, and a per-project REQ-number counter.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6f4a5b7c8d9"
down_revision: Union[str, Sequence[str], None] = "d5e3f4a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requirements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("origin", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("merged_into_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("origin IN ('ai', 'user')", name=op.f("ck_requirements_origin")),
        sa.CheckConstraint(
            "status IN ('suggested', 'accepted', 'edited', 'rejected', 'merged')", name=op.f("ck_requirements_status")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_requirements_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["merged_into_id"],
            ["requirements.id"],
            name=op.f("fk_requirements_merged_into_id_requirements"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requirements")),
        sa.UniqueConstraint("project_id", "number", name=op.f("uq_requirements_project_id_number")),
    )
    op.create_index(op.f("ix_requirements_project_id"), "requirements", ["project_id"])

    op.create_table(
        "requirement_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("requirement_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("nfr_category", sa.String(length=20), nullable=True),
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("origin", sa.String(length=10), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("origin IN ('ai', 'user')", name=op.f("ck_requirement_versions_origin")),
        sa.CheckConstraint("type IN ('functional', 'non_functional')", name=op.f("ck_requirement_versions_type")),
        sa.CheckConstraint(
            "nfr_category IS NULL OR nfr_category IN ('performance', 'security', 'usability', 'reliability', 'other')",
            name=op.f("ck_requirement_versions_nfr_category"),
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["requirements.id"],
            name=op.f("fk_requirement_versions_requirement_id_requirements"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_requirement_versions_created_by_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requirement_versions")),
        sa.UniqueConstraint("requirement_id", "version", name=op.f("uq_requirement_versions_requirement_id_version")),
    )
    op.create_index(op.f("ix_requirement_versions_requirement_id"), "requirement_versions", ["requirement_id"])

    op.create_table(
        "requirement_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("requirement_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("source_sentence", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["requirements.id"],
            name=op.f("fk_requirement_sources_requirement_id_requirements"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["messages.id"], name=op.f("fk_requirement_sources_message_id_messages"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requirement_sources")),
    )
    op.create_index(op.f("ix_requirement_sources_requirement_id"), "requirement_sources", ["requirement_id"])
    op.create_index(op.f("ix_requirement_sources_message_id"), "requirement_sources", ["message_id"])

    with op.batch_alter_table("messages") as batch:
        batch.add_column(sa.Column("requirements_extracted_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("requirement_counter", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("requirement_counter")
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("requirements_extracted_at")
    op.drop_index(op.f("ix_requirement_sources_message_id"), table_name="requirement_sources")
    op.drop_index(op.f("ix_requirement_sources_requirement_id"), table_name="requirement_sources")
    op.drop_table("requirement_sources")
    op.drop_index(op.f("ix_requirement_versions_requirement_id"), table_name="requirement_versions")
    op.drop_table("requirement_versions")
    op.drop_index(op.f("ix_requirements_project_id"), table_name="requirements")
    op.drop_table("requirements")
