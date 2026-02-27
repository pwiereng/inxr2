"""Get statistics for all repositories in a single batch.

Avoids N+1 API calls by fetching stats for every repository at once.
"""

import asyncio

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
from .get_repository_stats import (
    GetRepositoryStatsRequest,
    GetRepositoryStatsUseCase,
    RepositoryStats,
)


class GetAllRepositoryStatsUseCase:
    """Fetch stats for every repository in parallel."""

    def __init__(
        self,
        repository_repo: RepositoryPort,
        file_repo: FileRepositoryPort,
        file_version_repo: FileVersionPort,
        symbol_repo: SymbolRepositoryPort,
        reference_repo: ReferenceRepositoryPort,
        commit_repo: CommitRepositoryPort,
        index_status_repo: IndexStatusRepositoryPort | None = None,
        git_service: GitServicePort | None = None,
    ) -> None:
        self._repository_repo = repository_repo
        self._stats_use_case = GetRepositoryStatsUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            file_version_repo=file_version_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            commit_repo=commit_repo,
            index_status_repo=index_status_repo,
            git_service=git_service,
        )

    async def execute(self) -> list[RepositoryStats]:
        """Get stats for all repositories.

        Returns:
            List of RepositoryStats, one per repository.
        """
        repositories = await self._repository_repo.list_all()
        if not repositories:
            return []

        tasks = [
            self._stats_use_case.execute(
                GetRepositoryStatsRequest(repository_id=repo.id)
            )
            for repo in repositories
        ]
        return list(await asyncio.gather(*tasks))
