"""Remove redundant git data from commits table

Revision ID: remove_redundant_commit_001
Revises: normalize_branch_001
Create Date: 2026-01-25

This migration removes fields that can be queried from git on-demand:
- author_name, author_email (from git log)
- committer_name, committer_email (from git log)
- message (from git log)
- short_hash (computed from commit_hash[:7])
- parent_hashes (from git log)

This follows the design principle of querying git directly rather than
storing redundant data. See ARCHITECTURAL_REVIEW.md for details.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "remove_redundant_commit_001"
down_revision: str | Sequence[str] | None = "normalize_branch_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop redundant columns from commits table."""
    op.drop_column("commits", "author_name")
    op.drop_column("commits", "author_email")
    op.drop_column("commits", "committer_name")
    op.drop_column("commits", "committer_email")
    op.drop_column("commits", "message")
    op.drop_column("commits", "short_hash")
    op.drop_column("commits", "parent_hashes")


def downgrade() -> None:
    """Restore redundant columns to commits table."""
    op.add_column(
        "commits",
        sa.Column("parent_hashes", postgresql.ARRAY(sa.String(40)), nullable=True),
    )
    op.add_column(
        "commits",
        sa.Column("short_hash", sa.String(7), nullable=True),
    )
    op.add_column(
        "commits",
        sa.Column("message", sa.Text(), nullable=True),
    )
    op.add_column(
        "commits",
        sa.Column("committer_email", sa.String(255), nullable=True),
    )
    op.add_column(
        "commits",
        sa.Column("committer_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "commits",
        sa.Column("author_email", sa.String(255), nullable=True),
    )
    op.add_column(
        "commits",
        sa.Column("author_name", sa.String(255), nullable=True),
    )
