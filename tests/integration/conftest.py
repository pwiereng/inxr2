"""Pytest configuration and fixtures for integration tests."""

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from inxr2.adapters.persistence.models.base import Base


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """
    Create an in-memory SQLite database session for testing.

    This fixture creates a fresh database for each test and automatically
    cleans up after the test completes.
    """
    # Create in-memory SQLite database
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    # Cleanup
    await engine.dispose()
