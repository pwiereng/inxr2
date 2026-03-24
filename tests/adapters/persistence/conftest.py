"""Test fixtures for database layer tests.

Uses a PostgreSQL test database (inxr2_test) with per-test savepoint isolation:
each test runs inside a transaction that is rolled back after the test completes.
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
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
from tests.db_helpers import (
    assert_test_database,
    get_test_database_url,
    setup_test_schema,
)

from .factories import CommitFactory, FileFactory, RepositoryFactory

TEST_DATABASE_URL = get_test_database_url()


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine (once per session).

    Drops and recreates all tables at the start of the test session,
    then drops them at the end.
    """
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
    """Create a test commit, linked to the repository's default branch.

    Linking to the default branch ensures text search deduplication (which
    scopes 'latest' to the default branch) returns this commit's files.
    """
    assert test_repository.id is not None
    adapter = PostgresCommitRepository(db_session)
    commit = await adapter.save(
        CommitFactory.create(
            repository_id=test_repository.id,
            commit_hash="a" * 40,
        )
    )
    assert commit.id is not None
    await adapter.link_commit_to_branch(
        test_repository.id, commit.id, test_repository.default_branch or "main"
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
