"""Add extension column to files table

Revision ID: add_extension_001
Revises: normalize_branch_commits_001
Create Date: 2026-02-21

Adds an indexed `extension` column to the files table for efficient
file-extension filtering in search. Backfills existing rows by extracting
the extension from the path column.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_extension_001"
down_revision = "content_addressable_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add nullable extension column with index
    op.add_column(
        "files",
        sa.Column("extension", sa.String(20), nullable=True),
    )
    op.create_index("ix_files_extension", "files", ["extension"])

    # Backfill: extract last .xxx from path, lowercased
    # e.g., "src/main.py" → ".py", "Makefile" → NULL (no dot)
    op.execute(
        "UPDATE files SET extension = lower(substring(path from '(\\.[^./]+)$'))"
    )


def downgrade() -> None:
    op.drop_index("ix_files_extension", table_name="files")
    op.drop_column("files", "extension")
