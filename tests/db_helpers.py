"""Shared database test utilities.

Provides helpers used across adapter, integration, and contract test conftest
files for setting up the PostgreSQL test database.
"""

import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from inxr2.adapters.persistence.models import Base

# Default test database URL
_DEFAULT_TEST_DB_URL = (
    "postgresql+asyncpg://inxr2_user:inxr2_dev_password@localhost:5432/inxr2_test"
)


def get_test_database_url() -> str:
    """Return the asyncpg test database URL from the environment."""
    raw = os.getenv("TEST_DATABASE_URL", _DEFAULT_TEST_DB_URL)
    return normalize_asyncpg_url(raw)


def normalize_asyncpg_url(url: str) -> str:
    """Ensure the URL uses the asyncpg driver prefix."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def assert_test_database(url: str) -> None:
    """Safety guard: refuse to operate on a non-test database."""
    db_name = url.rsplit("/", 1)[-1].split("?")[0]
    if not db_name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run tests against database '{db_name}' — "
            "TEST_DATABASE_URL must point to a database ending with '_test'."
        )


async def setup_test_schema(conn: AsyncConnection) -> None:
    """Drop and recreate all tables, then add tsvector column and trigger.

    This mirrors what the Alembic migration does for the tsvector column —
    since ORM create_all doesn't include it, we add it manually here.
    """
    await conn.run_sync(Base.metadata.drop_all)
    await conn.run_sync(Base.metadata.create_all)
    await conn.execute(
        text(
            "ALTER TABLE text_contents "
            "ADD COLUMN IF NOT EXISTS content_tsvector tsvector"
        )
    )
    await conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_text_contents_fts "
            "ON text_contents USING GIN(content_tsvector)"
        )
    )
    await conn.execute(
        text("DROP TRIGGER IF EXISTS text_contents_tsvector_update " "ON text_contents")
    )
    await conn.execute(
        text(
            "CREATE TRIGGER text_contents_tsvector_update "
            "BEFORE INSERT OR UPDATE ON text_contents "
            "FOR EACH ROW EXECUTE FUNCTION "
            "tsvector_update_trigger(content_tsvector, 'pg_catalog.english', content)"
        )
    )
