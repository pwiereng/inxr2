"""Repository port interface for repository entity operations."""

from abc import ABC, abstractmethod

from ....domain.entities import Repository


class RepositoryPort(ABC):
    """Port for repository entity operations."""

    @abstractmethod
    async def save(self, repository: Repository) -> Repository:
        """Save or update a repository."""
        pass

    @abstractmethod
    async def find_by_id(self, repository_id: int) -> Repository | None:
        """Find repository by ID."""
        pass

    @abstractmethod
    async def find_by_ids(self, repository_ids: list[int]) -> list[Repository]:
        """Find multiple repositories by IDs.

        Args:
            repository_ids: List of repository IDs to fetch

        Returns:
            List of repositories found (may be fewer than requested if some IDs don't exist)
        """
        pass

    @abstractmethod
    async def find_by_name(self, name: str) -> Repository | None:
        """Find repository by unique name."""
        pass

    @abstractmethod
    async def list_all(self) -> list[Repository]:
        """List all repositories."""
        pass

    @abstractmethod
    async def delete(self, repository_id: int) -> bool:
        """Delete repository and all related data (CASCADE)."""
        pass

    @abstractmethod
    async def get_or_create(
        self,
        name: str,
        url: str | None = None,
        description: str | None = None,
        default_branch: str | None = None,
    ) -> tuple["Repository", bool]:
        """Get existing repository by name, or create if not exists.

        Atomically handles race conditions where multiple processes might
        try to create the same repository simultaneously.

        Args:
            name: Unique repository name
            url: Repository URL (local path or remote URL)
            description: Optional description
            default_branch: Default branch name

        Returns:
            Tuple of (Repository, created) where created is True if
            a new repository was created, False if existing was returned.
        """
        pass
