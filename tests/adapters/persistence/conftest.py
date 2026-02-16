"""Test fixtures for database layer tests.

Uses a PostgreSQL test database (inxr2_test) with per-test savepoint isolation:
each test runs inside a transaction that is rolled back after the test completes.
"""

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
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

# PostgreSQL test database URL (auto-converted to asyncpg if needed)
_raw_url = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://inxr2_user:inxr2_dev_password@localhost:5432/inxr2_test",
)
if _raw_url.startswith("postgresql://"):
    TEST_DATABASE_URL = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    TEST_DATABASE_URL = _raw_url


def _assert_test_database(url: str) -> None:
    """Safety guard: refuse to drop_all on a non-test database."""
    db_name = url.rsplit("/", 1)[-1].split("?")[0]
    if not db_name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run tests against database '{db_name}' — "
            "TEST_DATABASE_URL must point to a database ending with '_test'."
        )


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine (once per session).

    Drops and recreates all tables at the start of the test session,
    then drops them at the end.
    """
    _assert_test_database(TEST_DATABASE_URL)
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
    """Create a per-test database session with savepoint isolation.

    Opens a transaction, then binds the session with
    join_transaction_mode="create_savepoint" so that session.commit()
    inside test factories releases a SAVEPOINT rather than the real
    transaction. After the test, the outer transaction is rolled back
    so no data persists between tests.
    """
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
    """Create a test file and link it to the test commit."""
    assert test_repository.id is not None
    assert test_commit.id is not None
    adapter = PostgresFileRepository(db_session)
    file = await adapter.save(
        FileFactory.create(
            repository_id=test_repository.id,
            path="src/test.py",
        )
    )
    assert file.id is not None
    await adapter.link_file_to_commit(file.id, test_commit.id)
    await db_session.commit()
    return file
