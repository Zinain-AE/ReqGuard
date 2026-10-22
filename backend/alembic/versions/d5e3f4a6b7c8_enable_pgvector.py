"""enable pgvector

Revision ID: d5e3f4a6b7c8
Revises: c4d2f3e5a6b7
Create Date: 2026-10-23 10:00:00.000000

Enables the pgvector extension (used later for requirement/code embeddings).
PostgreSQL only: on SQLite (local tests) this migration does nothing.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e3f4a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c4d2f3e5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # The extension belongs to the whole database (it may also be enabled from the Supabase
    # dashboard), so it is left in place.
    pass
