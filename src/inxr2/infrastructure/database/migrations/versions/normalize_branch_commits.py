"""Normalize branch handling with junction table

Revision ID: normalize_branch_001
Revises: add_time_travel_001
Create Date: 2026-01-25

This migration:
1. Creates branch_commits junction table
2. Removes branch column from commits table
3. Adds unique constraint on (repository_id, commit_hash)

The junction table properly represents git's model where a commit
is unique by hash and can exist on multiple branches.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "normalize_branch_001"
down_revision: str | Sequence[str] | None = "add_time_travel_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create branch_commits junction table and remove branch from commits."""
    # Create the junction table
    op.create_table(
        "branch_commits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("branch", sa.String(length=255), nullable=False),
        sa.Column("commit_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["commit_id"],
            ["commits.id"],
            name="fk_branch_commits_commit_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name="fk_branch_commits_repository_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id", "branch", "commit_id", name="uq_branch_commit"
        ),
    )
    op.create_index(
        "ix_branch_commits_branch", "branch_commits", ["branch"], unique=False
    )
    op.create_index(
        "ix_branch_commits_repo_branch",
        "branch_commits",
        ["repository_id", "branch"],
        unique=False,
    )

    # Remove branch column from commits table
    op.drop_column("commits", "branch")

    # Add unique constraint on (repository_id, commit_hash) since each commit
    # should only exist once per repository
    op.create_unique_constraint(
        "uq_repo_commit_hash", "commits", ["repository_id", "commit_hash"]
    )


def downgrade() -> None:
    """Restore branch column on commits and drop junction table."""
    # Drop the unique constraint
    op.drop_constraint("uq_repo_commit_hash", "commits", type_="unique")

    # Add back the branch column
    op.add_column(
        "commits",
        sa.Column("branch", sa.String(length=255), nullable=True),
    )

    # Drop indexes first
    op.drop_index("ix_branch_commits_repo_branch", table_name="branch_commits")
    op.drop_index("ix_branch_commits_branch", table_name="branch_commits")

    # Drop the junction table
    op.drop_table("branch_commits")
