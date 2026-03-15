"""File rename repository port interface for file rename entity operations."""

from abc import ABC, abstractmethod

from ....domain.entities import FileRename


class FileRenameRepositoryPort(ABC):
    """Port for file rename entity operations."""

    @abstractmethod
    async def save_renames(self, renames: list[FileRename]) -> list[FileRename]:
        """Bulk save file renames detected in a commit."""
        pass

    @abstractmethod
    async def get_renames_for_commit(self, commit_id: int) -> list[FileRename]:
        """Get all file renames in a specific commit."""
        pass

    @abstractmethod
    async def get_file_history(
        self,
        repository_id: int,
        file_path: str,
        branch: str | None = None,
    ) -> list[FileRename]:
        """Get rename history for a file path, tracing renames forward and backward.

        Returns renames where the file_path appears as either old_path or new_path,
        optionally filtered to commits on a specific branch.

        Args:
            repository_id: Repository to search in
            file_path: File path to trace renames for
            branch: Optional branch filter (via branch_commits junction)
        """
        pass

    @abstractmethod
    async def count_by_repository(self, repository_id: int) -> int:
        """Count total file renames in a repository."""
        pass

    @abstractmethod
    async def delete_by_repository(self, repository_id: int) -> int:
        """Delete all file renames for a repository. Returns count deleted."""
        pass
