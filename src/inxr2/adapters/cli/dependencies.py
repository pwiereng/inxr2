"""CLI dependency injection factory.

Provides repository instances via port types so CLI commands don't need
to import concrete persistence or infrastructure classes directly.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.application.ports.repositories import (
    CommitRepositoryPort,
    DependencyRepositoryPort,
    FileRenameRepositoryPort,
    FileRepositoryPort,
    IndexStatusRepositoryPort,
    ReferenceRepositoryPort,
    RepositoryPort,
    SymbolRepositoryPort,
    TextContentRepositoryPort,
)


@dataclass
class CLIRepositories:
    """Container for all repository instances needed by CLI commands."""

    session: AsyncSession
    repository_repo: RepositoryPort
    commit_repo: CommitRepositoryPort
    file_repo: FileRepositoryPort
    symbol_repo: SymbolRepositoryPort
    reference_repo: ReferenceRepositoryPort
    index_status_repo: IndexStatusRepositoryPort
    text_content_repo: TextContentRepositoryPort
    dependency_repo: DependencyRepositoryPort
    file_rename_repo: FileRenameRepositoryPort


@asynccontextmanager
async def cli_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a database session without repositories.

    For operations that need raw SQL access (e.g., database reset)
    but don't need repository abstractions.
    """
    from inxr2.infrastructure.database.connection import DatabaseConnection

    db = DatabaseConnection()
    try:
        async with db.session() as session:
            yield session
    finally:
        await db.close()


@asynccontextmanager
async def cli_repositories() -> AsyncGenerator[CLIRepositories, None]:
    """Create a database session and all repository instances.

    Yields a CLIRepositories container with typed port references.
    Handles session lifecycle and database connection cleanup.

    Usage:
        async with cli_repositories() as repos:
            orchestrator = DefaultIndexingOrchestrator(
                repository_repo=repos.repository_repo,
                ...
            )
    """
    from inxr2.adapters.persistence.repositories import (
        PostgresCommitRepository,
        PostgresDependencyRepository,
        PostgresFileRenameRepository,
        PostgresFileRepository,
        PostgresIndexStatusRepository,
        PostgresReferenceRepository,
        PostgresRepositoryAdapter,
        PostgresSymbolRepository,
        PostgresTextContentRepository,
    )
    from inxr2.infrastructure.database.connection import DatabaseConnection

    db = DatabaseConnection()
    try:
        async with db.session() as session:
            yield CLIRepositories(
                session=session,
                repository_repo=PostgresRepositoryAdapter(session),
                commit_repo=PostgresCommitRepository(session),
                file_repo=PostgresFileRepository(session),
                symbol_repo=PostgresSymbolRepository(session),
                reference_repo=PostgresReferenceRepository(session),
                index_status_repo=PostgresIndexStatusRepository(session),
                text_content_repo=PostgresTextContentRepository(session),
                dependency_repo=PostgresDependencyRepository(session),
                file_rename_repo=PostgresFileRenameRepository(session),
            )
    finally:
        await db.close()
