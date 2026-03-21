"""Pytest configuration and fixtures for integration tests.

Uses a PostgreSQL test database (inxr2_test) with per-test savepoint isolation.
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from inxr2.adapters.persistence.models import Base
from tests.db_helpers import (
    assert_test_database,
    get_test_database_url,
    setup_test_schema,
)

TEST_DATABASE_URL = get_test_database_url()


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine (once per session)."""
    assert_test_database(TEST_DATABASE_URL)
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await setup_test_schema(conn)

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
