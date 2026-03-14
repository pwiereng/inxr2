"""Add source_line column to dependencies table

Revision ID: add_dep_source_line_001
Revises: add_dependencies_001
Create Date: 2026-03-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_dep_source_line_001"
down_revision: str | Sequence[str] | None = "add_dependencies_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add source_line column to dependencies table."""
    op.add_column(
        "dependencies",
        sa.Column("source_line", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_dependencies_source_line_positive",
        "dependencies",
        "source_line IS NULL OR source_line >= 1",
    )


def downgrade() -> None:
    """Remove source_line column from dependencies table."""
    op.drop_constraint(
        "ck_dependencies_source_line_positive", "dependencies", type_="check"
    )
    op.drop_column("dependencies", "source_line")
