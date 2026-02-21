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
from ..adapters.persistence.repositories.postgres_text_search import PostgresTextSearch
from ..adapters.persistence.repositories.reference_adapter import (
    PostgresReferenceRepository,
)
from ..adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from ..adapters.persistence.repositories.symbol_adapter import PostgresSymbolRepository
from ..adapters.persistence.repositories.text_content_adapter import (
    PostgresTextContentRepository,
)
from ..application.ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    IndexStatusRepositoryPort,
    ReferenceRepositoryPort,
    RepositoryPort,
    SymbolRepositoryPort,
    TextContentRepositoryPort,
)
from ..application.ports.services import FileSystemPort, GitServicePort, TextSearchPort
from ..application.use_cases.commits import ListCommitsUseCase
from ..application.use_cases.files import (
    GetFileContentUseCase,
    GetFileHistoryUseCase,
    ResolveFileUseCase,
)
from ..application.use_cases.indexing.index_local_directory import (
    IndexLocalDirectoryUseCase,
)
from ..application.use_cases.repositories.get_all_repository_stats import (
    GetAllRepositoryStatsUseCase,
)
from ..application.use_cases.repositories.get_repository_branches import (
    GetRepositoryBranchesUseCase,
)
from ..application.use_cases.repositories.get_repository_files import (
    GetRepositoryFilesUseCase,
)
from ..application.use_cases.repositories.get_repository_stats import (
    GetRepositoryStatsUseCase,
)
from ..application.use_cases.repositories.get_repository_tree import (
    GetRepositoryTreeUseCase,
)
from ..application.use_cases.repositories.list_repositories import (
    ListRepositoriesUseCase,
)
from ..application.use_cases.search import SearchFilesUseCase, SearchTextUseCase
from ..application.use_cases.symbols import (
    GetSymbolReferencesUseCase,
    SearchSymbolsUseCase,
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


def get_text_content_adapter(session: DbSession) -> TextContentRepositoryPort:
    """Provide text content repository adapter."""
    return PostgresTextContentRepository(session)


def get_text_search(session: DbSession) -> TextSearchPort:
    """Provide text search service."""
    return PostgresTextSearch(session)


# Type aliases for injected adapters
RepositoryAdapter = Annotated[RepositoryPort, Depends(get_repository_adapter)]
CommitAdapter = Annotated[CommitRepositoryPort, Depends(get_commit_adapter)]
FileAdapter = Annotated[FileRepositoryPort, Depends(get_file_adapter)]
SymbolAdapter = Annotated[SymbolRepositoryPort, Depends(get_symbol_adapter)]
ReferenceAdapter = Annotated[ReferenceRepositoryPort, Depends(get_reference_adapter)]
IndexStatusAdapter = Annotated[
    IndexStatusRepositoryPort, Depends(get_index_status_adapter)
]
TextContentAdapter = Annotated[
    TextContentRepositoryPort, Depends(get_text_content_adapter)
]
TextSearchDep = Annotated[TextSearchPort, Depends(get_text_search)]


# =============================================================================
# External Service Providers
# =============================================================================

# Singleton instance for GitService (stateless, reusable)
_git_service: GitServicePort | None = None


def get_git_service() -> GitServicePort:
    """Provide GitService singleton."""
    global _git_service
    if _git_service is None:
        _git_service = GitService()
    return _git_service


GitServiceDep = Annotated[GitServicePort, Depends(get_git_service)]

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
    git_service: GitServiceDep,
) -> GetRepositoryTreeUseCase:
    """Provide GetRepositoryTreeUseCase with dependencies."""
    return GetRepositoryTreeUseCase(
        repository_repo=repository_adapter,
        file_repo=file_adapter,
        commit_repo=commit_adapter,
        git_service=git_service,
    )


def get_resolve_file_use_case(
    repository_adapter: RepositoryAdapter,
    file_adapter: FileAdapter,
    commit_adapter: CommitAdapter,
) -> ResolveFileUseCase:
    """Provide ResolveFileUseCase with dependencies."""
    return ResolveFileUseCase(
        repository_repo=repository_adapter,
        file_repo=file_adapter,
        commit_repo=commit_adapter,
    )


def get_repository_stats_use_case(
    repository_adapter: RepositoryAdapter,
    file_adapter: FileAdapter,
    symbol_adapter: SymbolAdapter,
    reference_adapter: ReferenceAdapter,
    commit_adapter: CommitAdapter,
) -> GetRepositoryStatsUseCase:
    """Provide GetRepositoryStatsUseCase with dependencies."""
    return GetRepositoryStatsUseCase(
        repository_repo=repository_adapter,
        file_repo=file_adapter,
        symbol_repo=symbol_adapter,
        reference_repo=reference_adapter,
        commit_repo=commit_adapter,
    )


def get_all_repository_stats_use_case(
    repository_adapter: RepositoryAdapter,
    file_adapter: FileAdapter,
    symbol_adapter: SymbolAdapter,
    reference_adapter: ReferenceAdapter,
    commit_adapter: CommitAdapter,
) -> GetAllRepositoryStatsUseCase:
    """Provide GetAllRepositoryStatsUseCase with dependencies."""
    return GetAllRepositoryStatsUseCase(
        repository_repo=repository_adapter,
        file_repo=file_adapter,
        symbol_repo=symbol_adapter,
        reference_repo=reference_adapter,
        commit_repo=commit_adapter,
    )


def get_repository_branches_use_case(
    repository_adapter: RepositoryAdapter,
    index_status_adapter: IndexStatusAdapter,
    git_service: GitServiceDep,
) -> GetRepositoryBranchesUseCase:
    """Provide GetRepositoryBranchesUseCase with dependencies."""
    return GetRepositoryBranchesUseCase(
        repository_repo=repository_adapter,
        index_status_repo=index_status_adapter,
        git_service=git_service,
    )


def get_file_content_use_case(
    resolve_file_use_case: Annotated[
        ResolveFileUseCase, Depends(get_resolve_file_use_case)
    ],
    git_service: GitServiceDep,
) -> GetFileContentUseCase:
    """Provide GetFileContentUseCase with dependencies."""
    return GetFileContentUseCase(
        resolve_file_use_case=resolve_file_use_case,
        git_service=git_service,
    )


def get_file_history_use_case(
    repository_adapter: RepositoryAdapter,
    file_adapter: FileAdapter,
    commit_adapter: CommitAdapter,
    git_service: GitServiceDep,
) -> GetFileHistoryUseCase:
    """Provide GetFileHistoryUseCase with dependencies."""
    return GetFileHistoryUseCase(
        repository_repo=repository_adapter,
        file_repo=file_adapter,
        commit_repo=commit_adapter,
        git_service=git_service,
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
ResolveFileUseCaseDep = Annotated[
    ResolveFileUseCase, Depends(get_resolve_file_use_case)
]
GetRepositoryStatsUseCaseDep = Annotated[
    GetRepositoryStatsUseCase, Depends(get_repository_stats_use_case)
]
GetAllRepositoryStatsUseCaseDep = Annotated[
    GetAllRepositoryStatsUseCase, Depends(get_all_repository_stats_use_case)
]
GetRepositoryBranchesUseCaseDep = Annotated[
    GetRepositoryBranchesUseCase, Depends(get_repository_branches_use_case)
]
GetFileContentUseCaseDep = Annotated[
    GetFileContentUseCase, Depends(get_file_content_use_case)
]
GetFileHistoryUseCaseDep = Annotated[
    GetFileHistoryUseCase, Depends(get_file_history_use_case)
]


# Symbol use case providers
def get_search_symbols_use_case(
    symbol_adapter: SymbolAdapter,
    file_adapter: FileAdapter,
    commit_adapter: CommitAdapter,
) -> SearchSymbolsUseCase:
    """Provide SearchSymbolsUseCase with dependencies."""
    return SearchSymbolsUseCase(
        symbol_repo=symbol_adapter,
        file_repo=file_adapter,
        commit_repo=commit_adapter,
    )


def get_symbol_references_use_case(
    symbol_adapter: SymbolAdapter,
    reference_adapter: ReferenceAdapter,
    file_adapter: FileAdapter,
    commit_adapter: CommitAdapter,
) -> GetSymbolReferencesUseCase:
    """Provide GetSymbolReferencesUseCase with dependencies."""
    return GetSymbolReferencesUseCase(
        symbol_repo=symbol_adapter,
        reference_repo=reference_adapter,
        file_repo=file_adapter,
        commit_repo=commit_adapter,
    )


SearchSymbolsUseCaseDep = Annotated[
    SearchSymbolsUseCase, Depends(get_search_symbols_use_case)
]
GetSymbolReferencesUseCaseDep = Annotated[
    GetSymbolReferencesUseCase, Depends(get_symbol_references_use_case)
]


# Commit use case providers
def get_list_commits_use_case(
    repository_adapter: RepositoryAdapter,
    commit_adapter: CommitAdapter,
    git_service: GitServiceDep,
) -> ListCommitsUseCase:
    """Provide ListCommitsUseCase with dependencies."""
    return ListCommitsUseCase(
        repository_repo=repository_adapter,
        commit_repo=commit_adapter,
        git_service=git_service,
    )


ListCommitsUseCaseDep = Annotated[
    ListCommitsUseCase, Depends(get_list_commits_use_case)
]


# Search use case providers
def get_search_text_use_case(
    text_search: TextSearchDep,
    repository_adapter: RepositoryAdapter,
    commit_adapter: CommitAdapter,
    file_adapter: FileAdapter,
    reference_adapter: ReferenceAdapter,
) -> SearchTextUseCase:
    """Provide SearchTextUseCase with dependencies."""
    return SearchTextUseCase(
        text_search=text_search,
        repository_repo=repository_adapter,
        commit_repo=commit_adapter,
        file_repo=file_adapter,
        reference_repo=reference_adapter,
    )


SearchTextUseCaseDep = Annotated[SearchTextUseCase, Depends(get_search_text_use_case)]


def get_search_files_use_case(
    file_adapter: FileAdapter,
    repository_adapter: RepositoryAdapter,
    commit_adapter: CommitAdapter,
) -> SearchFilesUseCase:
    """Provide SearchFilesUseCase with dependencies."""
    return SearchFilesUseCase(
        file_repo=file_adapter,
        repository_repo=repository_adapter,
        commit_repo=commit_adapter,
    )


SearchFilesUseCaseDep = Annotated[
    SearchFilesUseCase, Depends(get_search_files_use_case)
]
