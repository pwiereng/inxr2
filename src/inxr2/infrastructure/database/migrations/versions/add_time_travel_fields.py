"""Add time travel fields to index_status

Revision ID: add_time_travel_001
Revises: edc605da5d0a
Create Date: 2026-01-18

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_time_travel_001"
down_revision: str | Sequence[str] | None = "edc605da5d0a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add oldest_indexed_commit column to index_status table."""
    op.add_column(
        "index_status",
        sa.Column("oldest_indexed_commit", sa.CHAR(length=40), nullable=True),
    )


def downgrade() -> None:
    """Remove oldest_indexed_commit column from index_status table."""
    op.drop_column("index_status", "oldest_indexed_commit")
