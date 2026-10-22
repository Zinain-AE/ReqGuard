"""source credentials and sync status

Revision ID: c4d2f3e5a6b7
Revises: b3c1e2d4f5a6
Create Date: 2026-10-22 10:00:00.000000

API connectors: an encrypted credentials field (Gmail refresh token) and the result of the last sync.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d2f3e5a6b7"
down_revision: Union[str, Sequence[str], None] = "b3c1e2d4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sources") as batch:
        batch.add_column(sa.Column("credentials_encrypted", sa.Text(), nullable=True))
        batch.add_column(sa.Column("sync_status", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("sync_error", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sources") as batch:
        batch.drop_column("sync_error")
        batch.drop_column("sync_status")
        batch.drop_column("credentials_encrypted")
