"""Get repository statistics use case.

Provides aggregated statistics for a repository including file counts,
symbol counts, reference counts, and language distribution.
"""

from dataclasses import dataclass

from ....domain.entities import Repository
from ....domain.exceptions import RepositoryNotFound
from ...ports.repositories import (
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
    ) -> None:
        """Initialize use case with required repositories.

        Args:
            repository_repo: Repository for accessing repositories
            file_repo: Repository for accessing files
            symbol_repo: Repository for accessing symbols
            reference_repo: Repository for accessing references
        """
        self._repository_repo = repository_repo
        self._file_repo = file_repo
        self._symbol_repo = symbol_repo
        self._reference_repo = reference_repo

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

        # 2. Get counts (these can be done in parallel in async context)
        files = await self._file_repo.list_by_repository(repository_id)
        symbol_count = await self._symbol_repo.count_by_repository(repository_id)
        reference_count = await self._reference_repo.count_by_repository(repository_id)

        # 3. Compute language distribution from files
        language_distribution = self._compute_language_distribution(files)

        return RepositoryStats(
            repository_id=repository_id,
            name=repository.name,
            total_files=len(files),
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
            repository = await self._repository_repo.find_by_name(request.repository_name)
            if not repository:
                raise RepositoryNotFound(request.repository_name)
            return repository

        raise ValueError("Either repository_id or repository_name must be provided")

    def _compute_language_distribution(self, files: list) -> dict[str, int]:
        """Compute language distribution from files.

        Args:
            files: List of File entities

        Returns:
            Dictionary mapping language name to file count
        """
        distribution: dict[str, int] = {}
        for file in files:
            lang = file.language or "unknown"
            distribution[lang] = distribution.get(lang, 0) + 1
        return distribution
