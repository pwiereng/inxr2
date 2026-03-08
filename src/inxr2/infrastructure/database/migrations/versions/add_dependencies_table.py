"""Add dependencies table for package dependency tracking

Revision ID: add_dependencies_001
Revises: 9e60343223f9
Create Date: 2026-03-07 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "add_dependencies_001"
down_revision: str | Sequence[str] | None = "9e60343223f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create dependencies table."""
    op.create_table(
        "dependencies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "file_id",
            sa.Integer(),
            sa.ForeignKey("files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            sa.Integer(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("package_name", sa.Text(), nullable=False),
        sa.Column("version_spec", sa.Text(), nullable=True),
        sa.Column("resolved_version", sa.Text(), nullable=True),
        sa.Column("language", sa.String(50), nullable=False),
        sa.Column(
            "dependency_type", sa.String(50), nullable=False, server_default="runtime"
        ),
        sa.Column("is_direct", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "parent_dependency_id",
            sa.Integer(),
            sa.ForeignKey("dependencies.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("extras", postgresql.JSONB(), nullable=True),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes for common query patterns
    op.create_index(
        "idx_dependencies_package", "dependencies", ["package_name", "language"]
    )
    op.create_index("idx_dependencies_file", "dependencies", ["file_id"])
    op.create_index("idx_dependencies_repo", "dependencies", ["repository_id"])
    op.create_index(
        "idx_dependencies_repo_file_package",
        "dependencies",
        ["repository_id", "file_id", "package_name"],
    )
    op.create_index(
        op.f("ix_dependencies_parent_dependency_id"),
        "dependencies",
        ["parent_dependency_id"],
    )


def downgrade() -> None:
    """Drop dependencies table."""
    op.drop_index(
        op.f("ix_dependencies_parent_dependency_id"), table_name="dependencies"
    )
    op.drop_index("idx_dependencies_repo_file_package", table_name="dependencies")
    op.drop_index("idx_dependencies_repo", table_name="dependencies")
    op.drop_index("idx_dependencies_file", table_name="dependencies")
    op.drop_index("idx_dependencies_package", table_name="dependencies")
    op.drop_table("dependencies")
