"""Commit repository port interface for commit entity operations."""

from abc import ABC, abstractmethod
from datetime import datetime

from ....domain.entities import Commit


class CommitRepositoryPort(ABC):
    """Port for commit entity operations."""

    @abstractmethod
    async def save(self, commit: Commit) -> Commit:
        """Save or update a commit."""
        pass

    @abstractmethod
    async def save_many(self, commits: list[Commit]) -> list[Commit]:
        """Bulk save commits for performance."""
        pass

    @abstractmethod
    async def find_by_id(self, commit_id: int) -> Commit | None:
        """Find commit by ID."""
        pass

    @abstractmethod
    async def find_by_ids(self, commit_ids: list[int]) -> list[Commit]:
        """Find multiple commits by IDs.

        Args:
            commit_ids: List of commit IDs to fetch

        Returns:
            List of commits found (may be fewer than requested if some IDs don't exist)
        """
        pass

    @abstractmethod
    async def find_by_hash(self, repository_id: int, commit_hash: str) -> Commit | None:
        """Find commit by repository and hash.

        Commits are unique per (repository_id, commit_hash) - the same commit
        hash represents the same commit regardless of which branches it's on.
        """
        pass

    @abstractmethod
    async def link_commit_to_branch(
        self, repository_id: int, commit_id: int, branch: str
    ) -> None:
        """Link an existing commit to a branch.

        Creates an entry in the branch_commits junction table.
        Idempotent - if the link already exists, does nothing.

        Args:
            repository_id: The repository ID
            commit_id: The commit database ID
            branch: The branch name to link
        """
        pass

    @abstractmethod
    async def link_commit_to_branches(
        self, repository_id: int, commit_id: int, branches: list[str]
    ) -> None:
        """Link an existing commit to multiple branches.

        Bulk version of link_commit_to_branch for efficiency.
        Idempotent - existing links are ignored.

        Args:
            repository_id: The repository ID
            commit_id: The commit database ID
            branches: List of branch names to link
        """
        pass

    @abstractmethod
    async def get_branches_for_commit(self, commit_id: int) -> list[str]:
        """Get all branches that contain a specific commit.

        Args:
            commit_id: The commit database ID

        Returns:
            List of branch names the commit is on
        """
        pass

    @abstractmethod
    async def get_branches_for_commits(
        self, commit_ids: list[int]
    ) -> dict[int, list[str]]:
        """Get branches for multiple commits in a single query.

        Args:
            commit_ids: List of commit database IDs

        Returns:
            Dict mapping commit_id to list of branch names.
            Commits with no branches will have empty lists.
        """
        pass

    @abstractmethod
    async def list_by_repository(
        self, repository_id: int, branch: str | None = None, limit: int = 100
    ) -> list[Commit]:
        """List commits for a repository, optionally filtered by branch.

        If branch is specified, only returns commits linked to that branch
        via the branch_commits junction table.
        """
        pass

    @abstractmethod
    async def find_indexed_hashes(
        self, repository_id: int, commit_hashes: list[str]
    ) -> set[str]:
        """Check which commit hashes exist in the database.

        Efficiently determines indexed status for a batch of commit hashes
        using a single IN query, rather than fetching full commit objects.

        Args:
            repository_id: The repository ID
            commit_hashes: List of commit hashes to check

        Returns:
            Set of commit hashes that exist in the database
        """
        pass

    @abstractmethod
    async def get_commit_date_range(
        self, repository_id: int
    ) -> tuple[datetime, datetime] | None:
        """Get the earliest and latest author_date for a repository's commits.

        Uses MIN/MAX aggregation for efficiency.

        Args:
            repository_id: The repository ID

        Returns:
            Tuple of (earliest_date, latest_date) or None if no commits exist
        """
        pass

    @abstractmethod
    async def find_latest_by_branch(
        self, repository_id: int, branch: str
    ) -> Commit | None:
        """Find the latest indexed commit for a specific branch.

        Queries via the branch_commits junction table to find commits
        on the specified branch, returning the most recent by commit_date.

        Args:
            repository_id: The repository ID
            branch: The branch name

        Returns:
            The latest commit for the branch, or None if no commits found
        """
        pass
