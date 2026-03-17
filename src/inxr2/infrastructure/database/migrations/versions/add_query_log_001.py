"""Add query_log table for activity logging

Revision ID: add_query_log_001
Revises: add_file_renames_001
Create Date: 2026-03-16

Ring-buffer table that stores HTTP request and MCP tool call logs.
Capped at MAX_QUERY_LOG_ENTRIES (default 10000) via application-level cleanup.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "add_query_log_001"
down_revision: str | Sequence[str] | None = "add_file_renames_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create query_log table."""
    op.create_table(
        "query_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "logged_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column("tool_or_path", sa.Text(), nullable=False),
        sa.Column("params", JSONB(), nullable=True),
        sa.Column("repository", sa.Text(), nullable=True),
        sa.Column("status_code", sa.SmallInteger(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_query_log_logged_at", "query_log", ["logged_at"])
    op.create_index("ix_query_log_source", "query_log", ["source"])
    op.create_index("ix_query_log_repository", "query_log", ["repository"])


def downgrade() -> None:
    """Drop query_log table."""
    op.drop_index("ix_query_log_repository", table_name="query_log")
    op.drop_index("ix_query_log_source", table_name="query_log")
    op.drop_index("ix_query_log_logged_at", table_name="query_log")
    op.drop_table("query_log")
