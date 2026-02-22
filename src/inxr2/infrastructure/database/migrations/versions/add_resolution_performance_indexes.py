"""Add composite indexes for reference resolution performance.

These indexes optimize the three-pass reference resolution queries:
- idx_symbols_repo_name_file: Helps Pass 1 (same-file resolution) by
  grouping symbols by repository, name, and file.
- idx_references_repo_unresolved: Partial index on unresolved references
  to speed up count_unresolved and all resolution passes.

Revision ID: add_resolution_indexes_001
Revises: add_extension_001
Create Date: 2026-02-21
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "add_resolution_indexes_001"
down_revision: str | Sequence[str] | None = "add_extension_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Composite index for same-file resolution (Pass 1)
    op.create_index(
        "idx_symbols_repo_name_file",
        "symbols",
        ["repository_id", "name", "file_id"],
    )

    # Partial index for finding unresolved references quickly
    op.create_index(
        "idx_references_repo_unresolved",
        "references",
        ["repository_id"],
        postgresql_where=text("target_symbol_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_references_repo_unresolved", table_name="references")
    op.drop_index("idx_symbols_repo_name_file", table_name="symbols")
