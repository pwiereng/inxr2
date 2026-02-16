"""Content-addressable file versions schema redesign

Revision ID: content_addressable_001
Revises: add_text_contents_001
Create Date: 2026-02-15

This is a BREAKING migration that requires `inxr2 db reset` before running.

Changes:
- Create commit_files junction table (composite PK: commit_id, file_id)
- Drop commit_id from files, symbols, references tables
- Add UNIQUE(repository_id, path, content_hash) on files
- Make commit_id nullable on text_contents

This enables content-addressable file versioning where symbols and references
belong to file versions, not commits. A file version = (repo, path, content_hash).
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "content_addressable_001"
down_revision = "add_text_contents_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create commit_files junction table
    op.create_table(
        "commit_files",
        sa.Column("commit_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["commit_id"], ["commits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("commit_id", "file_id"),
    )
    op.create_index("ix_commit_files_file_id", "commit_files", ["file_id"])

    # 2. Drop commit_id from files
    op.drop_constraint("files_commit_id_fkey", "files", type_="foreignkey")
    op.drop_column("files", "commit_id")

    # 3. Add unique constraint on files (repository_id, path, content_hash)
    op.create_unique_constraint(
        "uq_file_version", "files", ["repository_id", "path", "content_hash"]
    )

    # 4. Drop commit_id from symbols
    op.drop_constraint("symbols_commit_id_fkey", "symbols", type_="foreignkey")
    op.drop_column("symbols", "commit_id")

    # 5. Drop commit_id from references
    op.drop_constraint("references_commit_id_fkey", "references", type_="foreignkey")
    op.drop_column("references", "commit_id")

    # 6. Make commit_id nullable on text_contents
    op.alter_column(
        "text_contents", "commit_id", existing_type=sa.BIGINT(), nullable=True
    )


def downgrade() -> None:
    # Reverse: make commit_id non-nullable on text_contents
    op.alter_column(
        "text_contents", "commit_id", existing_type=sa.BIGINT(), nullable=False
    )

    # Reverse: add commit_id back to references
    op.add_column(
        "references",
        sa.Column("commit_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "references_commit_id_fkey",
        "references",
        "commits",
        ["commit_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Reverse: add commit_id back to symbols
    op.add_column(
        "symbols",
        sa.Column("commit_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "symbols_commit_id_fkey",
        "symbols",
        "commits",
        ["commit_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Reverse: drop unique constraint and add commit_id back to files
    op.drop_constraint("uq_file_version", "files", type_="unique")
    op.add_column(
        "files",
        sa.Column("commit_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "files_commit_id_fkey",
        "files",
        "commits",
        ["commit_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Reverse: drop commit_files table
    op.drop_index("ix_commit_files_file_id", table_name="commit_files")
    op.drop_table("commit_files")
