"""Add unique constraint and cleanup orphaned schema artifacts

Revision ID: bc889896e6d7
Revises: remove_redundant_commit_001
Create Date: 2026-02-02 01:58:41.960900

Changes:
- Add unique constraint on index_status (repository_id, branch)
- Drop orphaned ix_branch_commits_repo_branch index (not in model)
- Drop orphaned symbols.name_tsvector column (excluded from ORM)

Note: This migration assumes a fresh database (full rebuild via DROP SCHEMA +
alembic upgrade head). It does not handle incremental upgrades from databases
with existing duplicates or missing artifacts.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "bc889896e6d7"
down_revision: str | Sequence[str] | None = "remove_redundant_commit_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add unique constraint for index_status
    op.create_unique_constraint(
        "uq_index_status_repo_branch", "index_status", ["repository_id", "branch"]
    )

    # Drop orphaned index (not defined in model)
    op.drop_index("ix_branch_commits_repo_branch", table_name="branch_commits")

    # Drop orphaned column (explicitly excluded from ORM per model comments)
    op.drop_column("symbols", "name_tsvector")


def downgrade() -> None:
    """Downgrade schema."""
    # Restore name_tsvector column
    op.add_column(
        "symbols",
        sa.Column("name_tsvector", postgresql.TSVECTOR(), nullable=True),
    )

    # Restore index
    op.create_index(
        "ix_branch_commits_repo_branch",
        "branch_commits",
        ["repository_id", "branch"],
    )

    # Drop unique constraint
    op.drop_constraint("uq_index_status_repo_branch", "index_status", type_="unique")
