"""List repositories use case."""

from dataclasses import dataclass

from ....domain.entities import Repository
from ...ports.repositories import RepositoryPort


@dataclass
class ListRepositoriesResponse:
    """Response from listing repositories."""

    repositories: list[Repository]
    total_count: int


class ListRepositoriesUseCase:
    """Use case for listing all repositories."""

    def __init__(self, repository_repo: RepositoryPort) -> None:
        """
        Initialize use case.

        Args:
            repository_repo: Repository for accessing repositories
        """
        self._repository_repo = repository_repo

    async def execute(self) -> ListRepositoriesResponse:
        """
        Execute repository listing.

        Returns:
            List of all repositories
        """
        repositories = await self._repository_repo.list_all()

        return ListRepositoriesResponse(
            repositories=repositories, total_count=len(repositories)
        )
