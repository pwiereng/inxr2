"""Get repository statistics use case.

Provides aggregated statistics for a repository including file counts,
symbol counts, reference counts, and language distribution.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ....domain.entities import File, Repository
from ....domain.exceptions import (
    GitOperationError,
    InvalidRepositoryPath,
    RepositoryNotFound,
)
from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    FileVersionPort,
    IndexStatusRepositoryPort,
    ReferenceRepositoryPort,
    RepositoryPort,
    SymbolRepositoryPort,
)
from ...ports.services import GitServicePort

logger = logging.getLogger(__name__)


@dataclass
class RepositoryStats:
    """Aggregated repository statistics.

    Contains counts and distributions computed from indexed data.
    """

    repository_id: int
    name: str
    total_files: int
    total_symbols: int
    total_references: int
    language_distribution: dict[str, int] = field(default_factory=dict)
    total_lines: int = 0
    total_references_resolved: int = 0
    total_references_unresolved: int = 0
    commit_date_earliest: datetime | None = None
    commit_date_latest: datetime | None = None
    last_indexed_at: datetime | None = None
    last_indexed_commit: str | None = None
    last_indexing_duration_seconds: float | None = None
    last_resolving_duration_seconds: float | None = None
    git_head_commit: str | None = None
    is_stale: bool = False


@dataclass(frozen=True)
class StalenessInfo:
    """Index staleness information for a repository."""

    last_indexed_at: datetime | None = None
    last_indexed_commit: str | None = None
    last_indexing_duration_seconds: float | None = None
    last_resolving_duration_seconds: float | None = None
    git_head_commit: str | None = None
    is_stale: bool = False


@dataclass
class GetRepositoryStatsRequest:
    """Request to get repository statistics.

    Can specify repository by ID or name.
    """

    repository_id: int | None = None
    repository_name: str | None = None


class GetRepositoryStatsUseCase:
    """Use case for getting aggregated repository statistics.

    Orchestrates multiple repository calls to build a complete
    statistics response including:
    - Total file count
    - Total symbol count
    - Total reference count
    - Language distribution (files per language)

    This centralizes the aggregation logic that was previously
    scattered across controller endpoints.
    """

    def __init__(
        self,
        repository_repo: RepositoryPort,
        file_repo: FileRepositoryPort,
        symbol_repo: SymbolRepositoryPort,
        reference_repo: ReferenceRepositoryPort,
        file_version_repo: FileVersionPort,
        commit_repo: CommitRepositoryPort | None = None,
        index_status_repo: IndexStatusRepositoryPort | None = None,
        git_service: GitServicePort | None = None,
    ) -> None:
        """Initialize use case with required repositories.

        Args:
            repository_repo: Repository for accessing repositories
            file_repo: Repository for CRUD file operations
            file_version_repo: Repository for file version operations
            symbol_repo: Repository for accessing symbols
            reference_repo: Repository for accessing references
            commit_repo: Repository for accessing commits (used to get HEAD files)
            index_status_repo: Repository for index status (staleness check)
            git_service: Git service for fetching current HEAD (staleness check)
        """
        self._repository_repo = repository_repo
        self._file_repo = file_repo
        self._file_version_repo = file_version_repo
        self._symbol_repo = symbol_repo
        self._reference_repo = reference_repo
        self._commit_repo = commit_repo
        self._index_status_repo = index_status_repo
        self._git_service = git_service

    async def execute(self, request: GetRepositoryStatsRequest) -> RepositoryStats:
        """Execute statistics aggregation.

        Args:
            request: Request with repository ID or name

        Returns:
            RepositoryStats with aggregated counts and distributions

        Raises:
            RepositoryNotFound: If repository doesn't exist
            ValueError: If neither repository_id nor repository_name provided
        """
        # 1. Resolve repository
        repository = await self._resolve_repository(request)

        repository_id = repository.id if repository.id is not None else 0

        # 2. Get counts and date range in parallel
        gather_tasks: list[asyncio.Task[object]] = []
        gather_tasks.append(
            asyncio.ensure_future(self._symbol_repo.count_by_repository(repository_id))
        )
        gather_tasks.append(
            asyncio.ensure_future(
                self._reference_repo.count_by_repository(repository_id)
            )
        )
        gather_tasks.append(
            asyncio.ensure_future(
                self._reference_repo.count_unresolved_references(repository_id)
            )
        )
        if self._commit_repo is not None:
            gather_tasks.append(
                asyncio.ensure_future(
                    self._commit_repo.get_commit_date_range(repository_id)
                )
            )

        results = await asyncio.gather(*gather_tasks)
        symbol_count: int = results[0]  # type: ignore[assignment]
        reference_count: int = results[1]  # type: ignore[assignment]
        unresolved_count: int = results[2]  # type: ignore[assignment]
        date_range: tuple[datetime, datetime] | None = (
            results[3] if len(results) > 3 else None  # type: ignore[assignment]
        )

        # 3. Get files at HEAD commit (preferred) or fall back to deduplication
        unique_files = await self._get_head_files(repository, repository_id)

        # 4. Compute language distribution from deduplicated files
        language_distribution = self._compute_language_distribution(unique_files)

        # 5. Compute total lines from files
        total_lines = sum(f.line_count or 0 for f in unique_files)

        # 6. Compute staleness
        staleness = await self._compute_staleness(repository, repository_id)

        return RepositoryStats(
            repository_id=repository_id,
            name=repository.name,
            total_files=len(unique_files),
            total_symbols=symbol_count,
            total_references=reference_count,
            language_distribution=language_distribution,
            total_lines=total_lines,
            total_references_resolved=reference_count - unresolved_count,
            total_references_unresolved=unresolved_count,
            commit_date_earliest=date_range[0] if date_range else None,
            commit_date_latest=date_range[1] if date_range else None,
            last_indexed_at=staleness.last_indexed_at,
            last_indexed_commit=staleness.last_indexed_commit,
            last_indexing_duration_seconds=staleness.last_indexing_duration_seconds,
            last_resolving_duration_seconds=staleness.last_resolving_duration_seconds,
            git_head_commit=staleness.git_head_commit,
            is_stale=staleness.is_stale,
        )

    async def _resolve_repository(
        self, request: GetRepositoryStatsRequest
    ) -> Repository:
        """Resolve repository from request.

        Args:
            request: Request with repository ID or name

        Returns:
            Repository entity

        Raises:
            RepositoryNotFound: If repository doesn't exist
            ValueError: If neither repository_id nor repository_name provided
        """
        if request.repository_id is not None:
            repository = await self._repository_repo.find_by_id(request.repository_id)
            if not repository:
                raise RepositoryNotFound(f"Repository ID: {request.repository_id}")
            return repository

        if request.repository_name is not None:
            repository = await self._repository_repo.find_by_name(
                request.repository_name
            )
            if not repository:
                raise RepositoryNotFound(request.repository_name)
            return repository

        raise ValueError("Either repository_id or repository_name must be provided")

    async def _get_head_files(
        self, repository: Repository, repository_id: int
    ) -> list[File]:
        """Get files at HEAD commit, falling back to deduplication.

        Prefers using list_by_commit with the HEAD commit for accurate
        results regardless of auto-increment ID ordering. Falls back to
        list_by_repository with deduplication when commit_repo is unavailable.

        Args:
            repository: Repository entity (for default_branch)
            repository_id: Repository database ID

        Returns:
            List of unique files at HEAD
        """
        if self._commit_repo is not None:
            default_branch = repository.default_branch or "main"
            commit = await self._commit_repo.find_latest_by_branch(
                repository_id, default_branch
            )
            if commit and commit.id is not None:
                return await self._file_version_repo.list_by_commit(commit.id)

        # Fallback: list all and deduplicate
        files = await self._file_repo.list_by_repository(repository_id)
        return self._deduplicate_files_by_path(files)

    async def _compute_staleness(
        self, repository: Repository, repository_id: int
    ) -> StalenessInfo:
        """Compute index staleness by comparing last indexed commit with git HEAD."""
        if self._index_status_repo is None or self._git_service is None:
            return StalenessInfo()

        default_branch = repository.default_branch or "main"
        last_indexed_at: datetime | None = None
        last_indexed_commit: str | None = None
        last_indexing_duration_seconds: float | None = None
        last_resolving_duration_seconds: float | None = None

        # Get index status
        index_status = await self._index_status_repo.find_by_repository_and_branch(
            repository_id, default_branch
        )
        if index_status is not None:
            last_indexed_at = index_status.last_indexed_at
            last_indexed_commit = index_status.last_indexed_commit
            last_indexing_duration_seconds = index_status.last_indexing_duration_seconds
            last_resolving_duration_seconds = (
                index_status.last_resolving_duration_seconds
            )

        # Get git HEAD (sync call)
        try:
            git_head_commit = self._git_service.get_current_commit(
                Path(repository.url), default_branch
            )
        except (InvalidRepositoryPath, GitOperationError, OSError, ValueError):
            logger.debug(
                "Could not get git HEAD for %s: graceful degradation",
                repository.name,
                exc_info=True,
            )
            return StalenessInfo(
                last_indexed_at=last_indexed_at,
                last_indexed_commit=last_indexed_commit,
                last_indexing_duration_seconds=last_indexing_duration_seconds,
                last_resolving_duration_seconds=last_resolving_duration_seconds,
            )

        # Compare: stale if index exists and HEAD differs
        is_stale = (
            last_indexed_commit is not None
            and git_head_commit is not None
            and last_indexed_commit != git_head_commit
        )

        return StalenessInfo(
            last_indexed_at=last_indexed_at,
            last_indexed_commit=last_indexed_commit,
            last_indexing_duration_seconds=last_indexing_duration_seconds,
            last_resolving_duration_seconds=last_resolving_duration_seconds,
            git_head_commit=git_head_commit,
            is_stale=is_stale,
        )

    def _deduplicate_files_by_path(self, files: list[File]) -> list[File]:
        """Deduplicate files by path, keeping the latest version.

        In content-addressable repositories, list_by_repository may return
        multiple versions of the same file. This method keeps only the latest
        version of each unique path based on file ID (higher ID = more recent).

        Args:
            files: List of File entities (may contain duplicates)

        Returns:
            List of unique files (one per path, latest version)
        """
        latest_by_path: dict[str, File] = {}
        for file in files:
            existing = latest_by_path.get(file.path)
            if existing is None:
                latest_by_path[file.path] = file
            elif file.id is not None and existing.id is not None:
                # Keep the one with higher id (more recent)
                if file.id > existing.id:
                    latest_by_path[file.path] = file
        return list(latest_by_path.values())

    def _compute_language_distribution(self, files: list[File]) -> dict[str, int]:
        """Compute language distribution from files.

        Args:
            files: List of File entities (should be deduplicated by path)

        Returns:
            Dictionary mapping language name to file count
        """
        distribution: dict[str, int] = {}
        for file in files:
            lang = file.language or "unknown"
            distribution[lang] = distribution.get(lang, 0) + 1
        return distribution
