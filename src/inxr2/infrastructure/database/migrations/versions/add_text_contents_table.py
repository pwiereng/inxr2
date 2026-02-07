"""Add text_contents table for full-text search

Revision ID: add_text_contents_001
Revises: bc889896e6d7
Create Date: 2026-02-03 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "add_text_contents_001"
down_revision: str | Sequence[str] | None = "bc889896e6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - create text_contents table."""
    # Create text_contents table
    op.create_table(
        "text_contents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("commit_id", sa.BigInteger(), nullable=False),
        # Source information
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_file_id", sa.BigInteger(), nullable=True),
        sa.Column("source_line", sa.Integer(), nullable=True),
        sa.Column("source_end_line", sa.Integer(), nullable=True),
        # Searchable content
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "content_tsvector",
            postgresql.TSVECTOR(),
            nullable=True,  # NULL in SQLite
        ),
        # Metadata
        sa.Column("language", sa.String(length=50), nullable=True),
        sa.Column("content_type", sa.String(length=50), nullable=True),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Foreign keys
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
        sa.ForeignKeyConstraint(
            ["source_file_id"],
            ["files.id"],
            ondelete="CASCADE",
        ),
        # Constraint: commit messages don't have file/line info
        sa.CheckConstraint(
            "(source_type = 'commit_message' AND source_file_id IS NULL) OR "
            "(source_type != 'commit_message' AND source_file_id IS NOT NULL)",
            name="text_contents_valid_source",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Performance indexes
    op.create_index(
        "idx_text_contents_repo_commit",
        "text_contents",
        ["repository_id", "commit_id"],
        unique=False,
    )
    op.create_index(
        "idx_text_contents_source_file",
        "text_contents",
        ["source_file_id"],
        unique=False,
    )
    op.create_index(
        "idx_text_contents_source_type",
        "text_contents",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        "idx_text_contents_language",
        "text_contents",
        ["language"],
        unique=False,
    )

    # Full-text search index (PostgreSQL GIN) - only if using PostgreSQL
    # Note: This will fail on SQLite, which is handled in tests
    # SQLite tests use in-memory database without tsvector support
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'tsvector'
            ) THEN
                CREATE INDEX idx_text_contents_fts
                ON text_contents USING GIN(content_tsvector);
            END IF;
        END
        $$;
        """)

    # Auto-update tsvector on insert/update (PostgreSQL only)
    # Note: This trigger will only be created if using PostgreSQL
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_proc WHERE proname = 'tsvector_update_trigger'
            ) THEN
                CREATE TRIGGER text_contents_tsvector_update
                BEFORE INSERT OR UPDATE ON text_contents
                FOR EACH ROW EXECUTE FUNCTION
                tsvector_update_trigger(content_tsvector, 'pg_catalog.english', content);
            END IF;
        END
        $$;
        """)


def downgrade() -> None:
    """Downgrade schema - drop text_contents table."""
    # Drop trigger first (PostgreSQL only)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'text_contents_tsvector_update'
            ) THEN
                DROP TRIGGER text_contents_tsvector_update ON text_contents;
            END IF;
        END
        $$;
        """)

    # Drop indexes
    op.drop_index("idx_text_contents_language", table_name="text_contents")
    op.drop_index("idx_text_contents_source_type", table_name="text_contents")
    op.drop_index("idx_text_contents_source_file", table_name="text_contents")
    op.drop_index("idx_text_contents_repo_commit", table_name="text_contents")

    # Drop GIN index if it exists (PostgreSQL only)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE indexname = 'idx_text_contents_fts'
            ) THEN
                DROP INDEX idx_text_contents_fts;
            END IF;
        END
        $$;
        """)

    # Drop table
    op.drop_table("text_contents")
