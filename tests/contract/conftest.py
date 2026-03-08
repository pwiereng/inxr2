"""Parametrized fixtures for contract tests (fake vs Postgres)."""

import os
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
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
    PostgresDependencyRepository,
    PostgresFileRepository,
    PostgresFileSearchRepository,
    PostgresFileVersionRepository,
    PostgresReferenceRepository,
    PostgresRepositoryAdapter,
    PostgresSymbolRepository,
)
from inxr2.application.ports.repositories import (
    CommitRepositoryPort,
    DependencyRepositoryPort,
    FileRepositoryPort,
    FileSearchPort,
    FileVersionPort,
    ReferenceRepositoryPort,
    RepositoryPort,
    SymbolRepositoryPort,
)
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryDependencyRepository,
    InMemoryFileRepository,
    InMemoryFileSearchRepository,
    InMemoryFileVersionRepository,
    InMemoryReferenceRepository,
    InMemoryRepositoryRepository,
    InMemorySymbolRepository,
)

# PostgreSQL test database URL
_raw_url = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://inxr2_user:inxr2_dev_password@localhost:5432/inxr2_test",
)
if _raw_url.startswith("postgresql://"):
    TEST_DATABASE_URL = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    TEST_DATABASE_URL = _raw_url


@dataclass
class Repos:
    """Bundle of all repository implementations for contract tests."""

    repository: RepositoryPort
    commit: CommitRepositoryPort
    file: FileRepositoryPort
    file_search: FileSearchPort
    file_version: FileVersionPort
    symbol: SymbolRepositoryPort
    reference: ReferenceRepositoryPort
    dependency: DependencyRepositoryPort


def _assert_test_database(url: str) -> None:
    """Safety guard: refuse to drop_all on a non-test database."""
    db_name = url.rsplit("/", 1)[-1].split("?")[0]
    if not db_name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run tests against database '{db_name}' — "
            "TEST_DATABASE_URL must point to a database ending with '_test'."
        )


@pytest_asyncio.fixture(scope="session")
async def contract_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine for contract tests."""
    _assert_test_database(TEST_DATABASE_URL)
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # Add tsvector column (not in ORM model, managed by migration)
        await conn.execute(
            text(
                "ALTER TABLE text_contents "
                "ADD COLUMN IF NOT EXISTS content_tsvector tsvector"
            )
        )

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    contract_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Per-test database session with savepoint isolation."""
    conn = await contract_engine.connect()
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


@pytest.fixture(params=["fake", "postgres"])
def impl(request: pytest.FixtureRequest) -> str:
    """Parametrize between fake and postgres implementations."""
    return request.param  # type: ignore[no-any-return]


@pytest_asyncio.fixture
async def repos(impl: str, db_session: AsyncSession) -> Repos:
    """Create all repository implementations, wired together."""
    if impl == "fake":
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository(commit_repo=commit_repo)
        file_search_repo = InMemoryFileSearchRepository(file_repo)
        file_version_repo = InMemoryFileVersionRepository(file_repo)
        symbol_repo = InMemorySymbolRepository(file_repo=file_repo)
        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
        )
        dep_repo = InMemoryDependencyRepository(file_repo=file_repo)
        repo_repo = InMemoryRepositoryRepository()
        return Repos(
            repository=repo_repo,
            commit=commit_repo,
            file=file_repo,
            file_search=file_search_repo,
            file_version=file_version_repo,
            symbol=symbol_repo,
            reference=ref_repo,
            dependency=dep_repo,
        )
    else:
        return Repos(
            repository=PostgresRepositoryAdapter(db_session),
            commit=PostgresCommitRepository(db_session),
            file=PostgresFileRepository(db_session),
            file_search=PostgresFileSearchRepository(db_session),
            file_version=PostgresFileVersionRepository(db_session),
            symbol=PostgresSymbolRepository(db_session),
            reference=PostgresReferenceRepository(db_session),
            dependency=PostgresDependencyRepository(db_session),
        )


# Shared test data helpers

BASE_DATE = datetime(2024, 1, 1, tzinfo=UTC).replace(tzinfo=None)


async def create_test_repo(repos: Repos) -> int:
    """Create a test repository and return its ID."""
    from inxr2.domain.entities import Repository

    repo = await repos.repository.save(
        Repository(name="contract-test-repo", url="https://example.com/repo.git")
    )
    assert repo.id is not None
    return repo.id


async def create_test_commit(
    repos: Repos, repo_id: int, hash_str: str, date_offset_days: int = 0
) -> int:
    """Create a test commit and return its ID."""
    from inxr2.domain.entities import Commit
    from inxr2.domain.value_objects import CommitHash

    commit = await repos.commit.save(
        Commit(
            repository_id=repo_id,
            commit_hash=CommitHash(hash_str),
            author_date=BASE_DATE + timedelta(days=date_offset_days),
            commit_date=BASE_DATE + timedelta(days=date_offset_days),
        )
    )
    assert commit.id is not None
    return commit.id


async def create_test_file(
    repos: Repos,
    repo_id: int,
    commit_id: int,
    path: str,
    content_hash: str,
) -> int:
    """Create (or reuse) a test file version, link it to the commit, and return its ID.

    Uses find_or_create_version so that the same (repo_id, path, content_hash)
    can be linked to multiple commits without violating the unique constraint.
    """
    file, _created = await repos.file.find_or_create_version(
        repository_id=repo_id,
        path=path,
        content_hash=content_hash,
        size_bytes=100,
        language="python",
    )
    assert file.id is not None
    await repos.file.link_file_to_commit(file.id, commit_id)
    return file.id


async def create_test_symbol(
    repos: Repos,
    file_id: int,
    repo_id: int,
    commit_id: int,
    name: str,
    qualified_name: str | None = None,
) -> int:
    """Create a test symbol and return its ID."""
    from inxr2.domain.entities import Symbol
    from inxr2.domain.value_objects import SymbolKind

    symbol = await repos.symbol.save(
        Symbol(
            file_id=file_id,
            repository_id=repo_id,
            name=name,
            kind=SymbolKind.FUNCTION,
            start_line=1,
            start_column=0,
            end_line=10,
            end_column=0,
            qualified_name=qualified_name or f"module.{name}",
        )
    )
    assert symbol.id is not None
    return symbol.id


async def create_test_reference(
    repos: Repos,
    repo_id: int,
    commit_id: int,
    source_file_id: int,
    text: str,
    target_symbol_id: int | None = None,
) -> int:
    """Create a test reference and return its ID."""
    from inxr2.domain.entities import Reference
    from inxr2.domain.value_objects import ReferenceType

    ref = await repos.reference.save(
        Reference(
            repository_id=repo_id,
            source_file_id=source_file_id,
            source_line=5,
            source_column=0,
            source_end_column=len(text),
            reference_text=text,
            reference_type=ReferenceType.CALL,
            target_symbol_id=target_symbol_id,
        )
    )
    assert ref.id is not None
    return ref.id
