"""Index status repository port interface for index status operations."""

from abc import ABC, abstractmethod

from ....domain.entities import IndexStatus


class IndexStatusRepositoryPort(ABC):
    """Port for index status operations."""

    @abstractmethod
    async def save(self, status: IndexStatus) -> IndexStatus:
        """Save or update index status."""
        pass

    @abstractmethod
    async def find_by_repository_and_branch(
        self, repository_id: int, branch: str
    ) -> IndexStatus | None:
        """Find index status for a repository/branch combination."""
        pass

    @abstractmethod
    async def list_by_repository(self, repository_id: int) -> list[IndexStatus]:
        """List all index statuses for a repository (all branches)."""
        pass
