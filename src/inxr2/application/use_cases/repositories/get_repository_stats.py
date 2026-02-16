"""Get repository statistics use case.

Provides aggregated statistics for a repository including file counts,
symbol counts, reference counts, and language distribution.
"""

import asyncio
from dataclasses import dataclass

from ....domain.entities import File, Repository
from ....domain.exceptions import RepositoryNotFound
from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    ReferenceRepositoryPort,
    RepositoryPort,
    SymbolRepositoryPort,
)


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
    language_distribution: dict[str, int]


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
        commit_repo: CommitRepositoryPort | None = None,
    ) -> None:
        """Initialize use case with required repositories.

        Args:
            repository_repo: Repository for accessing repositories
            file_repo: Repository for accessing files
            symbol_repo: Repository for accessing symbols
            reference_repo: Repository for accessing references
            commit_repo: Repository for accessing commits (used to get HEAD files)
        """
        self._repository_repo = repository_repo
        self._file_repo = file_repo
        self._symbol_repo = symbol_repo
        self._reference_repo = reference_repo
        self._commit_repo = commit_repo

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

        # 2. Get counts in parallel
        symbol_count, reference_count = await asyncio.gather(
            self._symbol_repo.count_by_repository(repository_id),
            self._reference_repo.count_by_repository(repository_id),
        )

        # 3. Get files at HEAD commit (preferred) or fall back to deduplication
        unique_files = await self._get_head_files(repository, repository_id)

        # 4. Compute language distribution from deduplicated files
        language_distribution = self._compute_language_distribution(unique_files)

        return RepositoryStats(
            repository_id=repository_id,
            name=repository.name,
            total_files=len(unique_files),
            total_symbols=symbol_count,
            total_references=reference_count,
            language_distribution=language_distribution,
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
                return await self._file_repo.list_by_commit(commit.id)

        # Fallback: list all and deduplicate
        files = await self._file_repo.list_by_repository(repository_id)
        return self._deduplicate_files_by_path(files)

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
