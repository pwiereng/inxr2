"""Test fixtures for database layer tests."""

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from inxr2.adapters.persistence.models import Base

# Use in-memory SQLite for fast tests (or test PostgreSQL database)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"
)


@pytest_asyncio.fixture
async def test_engine():
    """Create test database engine."""
    # For SQLite, map PostgreSQL ARRAY to JSON (stores as text)
    if "sqlite" in TEST_DATABASE_URL:
        type_annotation_map = {
            list[str]: JSON,  # Map list[str] to JSON for SQLite compatibility
        }
    else:
        type_annotation_map = None

    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()  # Rollback after each test
