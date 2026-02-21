"""Add indexes to foreign key columns

Revision ID: 8c8caa7883cc
Revises: content_addressable_001
Create Date: 2026-02-21 16:15:20.943819

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c8caa7883cc"
down_revision: str | Sequence[str] | None = "content_addressable_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add indexes to foreign key columns for faster joins and lookups."""
    # branch_commits
    op.create_index(
        op.f("ix_branch_commits_commit_id"),
        "branch_commits",
        ["commit_id"],
        unique=False,
    )

    # references
    op.create_index(
        op.f("ix_references_repository_id"),
        "references",
        ["repository_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_references_source_file_id"),
        "references",
        ["source_file_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_references_target_repository_id"),
        "references",
        ["target_repository_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_references_target_symbol_id"),
        "references",
        ["target_symbol_id"],
        unique=False,
    )

    # symbols
    op.create_index(op.f("ix_symbols_file_id"), "symbols", ["file_id"], unique=False)
    op.create_index(
        op.f("ix_symbols_parent_symbol_id"),
        "symbols",
        ["parent_symbol_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_symbols_repository_id"), "symbols", ["repository_id"], unique=False
    )

    # text_contents
    op.create_index(
        op.f("ix_text_contents_commit_id"), "text_contents", ["commit_id"], unique=False
    )
    op.create_index(
        op.f("ix_text_contents_repository_id"),
        "text_contents",
        ["repository_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove foreign key indexes."""
    op.drop_index(op.f("ix_text_contents_repository_id"), table_name="text_contents")
    op.drop_index(op.f("ix_text_contents_commit_id"), table_name="text_contents")
    op.drop_index(op.f("ix_symbols_repository_id"), table_name="symbols")
    op.drop_index(op.f("ix_symbols_parent_symbol_id"), table_name="symbols")
    op.drop_index(op.f("ix_symbols_file_id"), table_name="symbols")
    op.drop_index(op.f("ix_references_target_symbol_id"), table_name="references")
    op.drop_index(op.f("ix_references_target_repository_id"), table_name="references")
    op.drop_index(op.f("ix_references_source_file_id"), table_name="references")
    op.drop_index(op.f("ix_references_repository_id"), table_name="references")
    op.drop_index(op.f("ix_branch_commits_commit_id"), table_name="branch_commits")
