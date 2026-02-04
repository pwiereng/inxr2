"""Test fixtures for database layer tests."""

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from inxr2.adapters.persistence.models import Base
from inxr2.adapters.persistence.repositories import (
    PostgresCommitRepository,
    PostgresFileRepository,
    PostgresRepositoryAdapter,
)
from inxr2.domain.entities import Commit, File, Repository

from .factories import CommitFactory, FileFactory, RepositoryFactory

# Use in-memory SQLite for fast tests (or test PostgreSQL database)
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest_asyncio.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine."""
    # For SQLite, map PostgreSQL ARRAY to JSON (stores as text)
    # Note: SQLAlchemy will use our StringArray custom type
    # which handles both PostgreSQL and SQLite automatically

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
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(test_engine, expire_on_commit=False)

    async with async_session() as session:
        yield session
        await session.rollback()  # Rollback after each test


@pytest_asyncio.fixture
async def test_repository(db_session: AsyncSession) -> Repository:
    """Create a test repository."""
    adapter = PostgresRepositoryAdapter(db_session)
    repo = await adapter.save(RepositoryFactory.create(name="test-repo"))
    await db_session.commit()
    return repo


@pytest_asyncio.fixture
async def test_commit(db_session: AsyncSession, test_repository: Repository) -> Commit:
    """Create a test commit."""
    assert test_repository.id is not None
    adapter = PostgresCommitRepository(db_session)
    commit = await adapter.save(
        CommitFactory.create(
            repository_id=test_repository.id,
            commit_hash="a" * 40,
        )
    )
    await db_session.commit()
    return commit


@pytest_asyncio.fixture
async def test_second_commit(
    db_session: AsyncSession, test_repository: Repository
) -> Commit:
    """Create a second test commit."""
    assert test_repository.id is not None
    adapter = PostgresCommitRepository(db_session)
    commit = await adapter.save(
        CommitFactory.create(
            repository_id=test_repository.id,
            commit_hash="b" * 40,
        )
    )
    await db_session.commit()
    return commit


@pytest_asyncio.fixture
async def test_file(
    db_session: AsyncSession, test_repository: Repository, test_commit: Commit
) -> File:
    """Create a test file."""
    assert test_repository.id is not None
    assert test_commit.id is not None
    adapter = PostgresFileRepository(db_session)
    file = await adapter.save(
        FileFactory.create(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            path="src/test.py",
        )
    )
    await db_session.commit()
    return file
