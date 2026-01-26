"""
Dependency injection providers for FastAPI.

This module provides factory functions that create and wire together
adapters and use cases. Using FastAPI's Depends() system, these
providers eliminate scattered adapter instantiation across route handlers.

Usage in routes:
    @router.get("")
    async def list_repositories(
        use_case: ListRepositoriesUseCase = Depends(get_list_repositories_use_case),
    ) -> list[RepositoryResponse]:
        response = await use_case.execute()

Benefits:
- Centralized dependency wiring (single place to modify)
- Easy to swap implementations (e.g., for testing)
- Clear dependency graph
- Reduced boilerplate in route handlers
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters.external.git_service import GitService
from ..adapters.external.local_filesystem import LocalFileSystem
from ..adapters.persistence.repositories.commit_adapter import PostgresCommitRepository
from ..adapters.persistence.repositories.file_adapter import PostgresFileRepository
from ..adapters.persistence.repositories.index_status_adapter import (
    PostgresIndexStatusRepository,
)
from ..adapters.persistence.repositories.reference_adapter import (
    PostgresReferenceRepository,
)
from ..adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from ..adapters.persistence.repositories.symbol_adapter import PostgresSymbolRepository
from ..application.ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    IndexStatusRepositoryPort,
    ReferenceRepositoryPort,
    RepositoryPort,
    SymbolRepositoryPort,
)
from ..application.ports.services import FileSystemPort
from ..application.use_cases.indexing.index_local_directory import (
    IndexLocalDirectoryUseCase,
)
from ..application.use_cases.repositories.get_repository_files import (
    GetRepositoryFilesUseCase,
)
from ..application.use_cases.repositories.get_repository_tree import (
    GetRepositoryTreeUseCase,
)
from ..application.use_cases.repositories.list_repositories import (
    ListRepositoriesUseCase,
)
from .database import get_db_session

# Type alias for injected session
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


# =============================================================================
# Repository Adapter Providers
# =============================================================================


def get_repository_adapter(session: DbSession) -> RepositoryPort:
    """Provide repository adapter."""
    return PostgresRepositoryAdapter(session)


def get_commit_adapter(session: DbSession) -> CommitRepositoryPort:
    """Provide commit repository adapter."""
    return PostgresCommitRepository(session)


def get_file_adapter(session: DbSession) -> FileRepositoryPort:
    """Provide file repository adapter."""
    return PostgresFileRepository(session)


def get_symbol_adapter(session: DbSession) -> SymbolRepositoryPort:
    """Provide symbol repository adapter."""
    return PostgresSymbolRepository(session)


def get_reference_adapter(session: DbSession) -> ReferenceRepositoryPort:
    """Provide reference repository adapter."""
    return PostgresReferenceRepository(session)


def get_index_status_adapter(session: DbSession) -> IndexStatusRepositoryPort:
    """Provide index status repository adapter."""
    return PostgresIndexStatusRepository(session)


# Type aliases for injected adapters
RepositoryAdapter = Annotated[RepositoryPort, Depends(get_repository_adapter)]
CommitAdapter = Annotated[CommitRepositoryPort, Depends(get_commit_adapter)]
FileAdapter = Annotated[FileRepositoryPort, Depends(get_file_adapter)]
SymbolAdapter = Annotated[SymbolRepositoryPort, Depends(get_symbol_adapter)]
ReferenceAdapter = Annotated[ReferenceRepositoryPort, Depends(get_reference_adapter)]
IndexStatusAdapter = Annotated[
    IndexStatusRepositoryPort, Depends(get_index_status_adapter)
]


# =============================================================================
# External Service Providers
# =============================================================================

# Singleton instance for GitService (stateless, reusable)
_git_service: GitService | None = None


def get_git_service() -> GitService:
    """Provide GitService singleton."""
    global _git_service
    if _git_service is None:
        _git_service = GitService()
    return _git_service


GitServiceDep = Annotated[GitService, Depends(get_git_service)]

# Singleton instance for LocalFileSystem (stateless, reusable)
_local_filesystem: LocalFileSystem | None = None


def get_filesystem() -> FileSystemPort:
    """Provide FileSystemPort singleton (LocalFileSystem implementation)."""
    global _local_filesystem
    if _local_filesystem is None:
        _local_filesystem = LocalFileSystem()
    return _local_filesystem


FileSystemDep = Annotated[FileSystemPort, Depends(get_filesystem)]


# =============================================================================
# Use Case Providers
# =============================================================================


def get_list_repositories_use_case(
    repository_adapter: RepositoryAdapter,
) -> ListRepositoriesUseCase:
    """Provide ListRepositoriesUseCase with dependencies."""
    return ListRepositoriesUseCase(repository_repo=repository_adapter)


def get_repository_files_use_case(
    repository_adapter: RepositoryAdapter,
    file_adapter: FileAdapter,
) -> GetRepositoryFilesUseCase:
    """Provide GetRepositoryFilesUseCase with dependencies."""
    return GetRepositoryFilesUseCase(
        repository_repo=repository_adapter,
        file_repo=file_adapter,
    )


def get_index_local_directory_use_case(
    repository_adapter: RepositoryAdapter,
    commit_adapter: CommitAdapter,
    file_adapter: FileAdapter,
    filesystem: FileSystemDep,
) -> IndexLocalDirectoryUseCase:
    """Provide IndexLocalDirectoryUseCase with dependencies."""
    return IndexLocalDirectoryUseCase(
        repository_repo=repository_adapter,
        commit_repo=commit_adapter,
        file_repo=file_adapter,
        filesystem=filesystem,
    )


def get_repository_tree_use_case(
    repository_adapter: RepositoryAdapter,
    file_adapter: FileAdapter,
    commit_adapter: CommitAdapter,
) -> GetRepositoryTreeUseCase:
    """Provide GetRepositoryTreeUseCase with dependencies."""
    return GetRepositoryTreeUseCase(
        repository_repo=repository_adapter,
        file_repo=file_adapter,
        commit_repo=commit_adapter,
    )


# Type aliases for injected use cases
ListRepositoriesUseCaseDep = Annotated[
    ListRepositoriesUseCase, Depends(get_list_repositories_use_case)
]
GetRepositoryFilesUseCaseDep = Annotated[
    GetRepositoryFilesUseCase, Depends(get_repository_files_use_case)
]
IndexLocalDirectoryUseCaseDep = Annotated[
    IndexLocalDirectoryUseCase, Depends(get_index_local_directory_use_case)
]
GetRepositoryTreeUseCaseDep = Annotated[
    GetRepositoryTreeUseCase, Depends(get_repository_tree_use_case)
]
