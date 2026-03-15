"""Add file_renames table for tracking file renames during indexing

Revision ID: add_file_renames_001
Revises: add_dep_source_line_001
Create Date: 2026-03-14

Stores file renames detected via git diff --find-renames during indexing.
Each row represents a single file rename in a specific commit.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_file_renames_001"
down_revision: str | Sequence[str] | None = "add_dep_source_line_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "file_renames",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("commit_id", sa.Integer(), nullable=False),
        sa.Column("old_path", sa.Text(), nullable=False),
        sa.Column("new_path", sa.Text(), nullable=False),
        sa.Column("similarity", sa.SmallInteger(), nullable=False),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["commit_id"],
            ["commits.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "commit_id", "old_path", "new_path", name="uq_file_renames_commit_paths"
        ),
        sa.CheckConstraint(
            "similarity >= 0 AND similarity <= 100",
            name="ck_file_renames_similarity_range",
        ),
    )
    op.create_index("idx_file_renames_repo", "file_renames", ["repository_id"])
    op.create_index("idx_file_renames_commit", "file_renames", ["commit_id"])
    op.create_index(
        "idx_file_renames_old_path", "file_renames", ["repository_id", "old_path"]
    )
    op.create_index(
        "idx_file_renames_new_path", "file_renames", ["repository_id", "new_path"]
    )


def downgrade() -> None:
    op.drop_index("idx_file_renames_new_path", table_name="file_renames")
    op.drop_index("idx_file_renames_old_path", table_name="file_renames")
    op.drop_index("idx_file_renames_commit", table_name="file_renames")
    op.drop_index("idx_file_renames_repo", table_name="file_renames")
    op.drop_table("file_renames")
