"""Pytest configuration and fixtures for integration tests.

Uses a PostgreSQL test database (inxr2_test) with per-test savepoint isolation.
"""

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from inxr2.adapters.persistence.models.base import Base

# PostgreSQL test database URL (auto-converted to asyncpg if needed)
_raw_url = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://inxr2_user:inxr2_dev_password@postgres:5432/inxr2_test",
)
if _raw_url.startswith("postgresql://"):
    TEST_DATABASE_URL = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    TEST_DATABASE_URL = _raw_url


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine (once per session)."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # Add tsvector column and trigger (not in ORM model, managed by migration)
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
            text(
                "DROP TRIGGER IF EXISTS text_contents_tsvector_update "
                "ON text_contents"
            )
        )
        await conn.execute(
            text(
                "CREATE TRIGGER text_contents_tsvector_update "
                "BEFORE INSERT OR UPDATE ON text_contents "
                "FOR EACH ROW EXECUTE FUNCTION "
                "tsvector_update_trigger(content_tsvector, 'pg_catalog.english', content)"
            )
        )

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a per-test database session with savepoint isolation."""
    conn = await test_engine.connect()
    trans = await conn.begin()

    session = AsyncSession(
        bind=conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    yield session

    await session.close()
    await trans.rollback()
    await conn.close()
