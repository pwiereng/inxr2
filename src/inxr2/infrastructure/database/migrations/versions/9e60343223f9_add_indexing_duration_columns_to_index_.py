"""add indexing duration columns to index_status

Revision ID: 9e60343223f9
Revises: add_file_repo_content_hash_001
Create Date: 2026-03-02 03:58:04.337662

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9e60343223f9"
down_revision: str | Sequence[str] | None = "add_file_repo_content_hash_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "index_status",
        sa.Column("last_indexing_duration_seconds", sa.Float(), nullable=True),
    )
    op.add_column(
        "index_status",
        sa.Column("last_resolving_duration_seconds", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("index_status", "last_resolving_duration_seconds")
    op.drop_column("index_status", "last_indexing_duration_seconds")
