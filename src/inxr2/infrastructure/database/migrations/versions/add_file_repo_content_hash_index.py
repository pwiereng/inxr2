"""Add composite index on files(repository_id, content_hash).

Optimizes find_by_content_hash queries that now filter by repository_id,
turning sequential scans into index-only lookups.

Revision ID: add_file_repo_content_hash_001
Revises: add_resolution_indexes_001
Create Date: 2026-02-22
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_file_repo_content_hash_001"
down_revision: str | Sequence[str] | None = "add_resolution_indexes_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_files_repo_content_hash",
        "files",
        ["repository_id", "content_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_files_repo_content_hash", table_name="files")
