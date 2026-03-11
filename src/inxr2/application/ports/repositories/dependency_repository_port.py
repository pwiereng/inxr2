"""Dependency repository port interface for dependency entity operations."""

from abc import ABC, abstractmethod

from ....domain.entities import Dependency


class DependencyRepositoryPort(ABC):
    """Port for dependency entity operations."""

    @abstractmethod
    async def save(self, dependency: Dependency) -> Dependency:
        """Save or update a dependency."""
        pass

    @abstractmethod
    async def save_many(self, dependencies: list[Dependency]) -> list[Dependency]:
        """Bulk save dependencies for performance."""
        pass

    @abstractmethod
    async def find_by_id(self, dependency_id: int) -> Dependency | None:
        """Find dependency by ID."""
        pass

    @abstractmethod
    async def find_by_file(
        self,
        file_id: int,
        dependency_type: str | None = None,
        is_direct: bool | None = None,
    ) -> list[Dependency]:
        """Find all dependencies for a manifest file version.

        Args:
            file_id: The manifest/lock file version ID
            dependency_type: Filter by type (runtime, dev, etc.) (optional)
            is_direct: Filter by direct/transitive (optional)
        """
        pass

    @abstractmethod
    async def find_by_commit(
        self,
        commit_id: int,
        repository_id: int,
        language: str | None = None,
        dependency_type: str | None = None,
        is_direct: bool | None = None,
    ) -> list[Dependency]:
        """Find all dependencies at a specific commit via commit_files junction.

        Args:
            commit_id: The commit to query at
            repository_id: Filter by repository
            language: Filter by language ecosystem (optional)
            dependency_type: Filter by type (runtime, dev, etc.) (optional)
            is_direct: Filter by direct/transitive (optional)
        """
        pass

    @abstractmethod
    async def find_by_package_name(
        self,
        package_name: str,
        repository_id: int | None = None,
        language: str | None = None,
    ) -> list[Dependency]:
        """Find all dependencies matching a package name (reverse lookup).

        Useful for answering "which repos use package X?"

        Args:
            package_name: Package name to search for
            repository_id: Filter by repository (optional)
            language: Filter by language ecosystem (optional)
        """
        pass

    @abstractmethod
    async def search_by_package_name(
        self,
        query: str,
        repository_id: int | None = None,
        language: str | None = None,
        dependency_type: str | None = None,
        is_direct: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Dependency], int]:
        """Search dependencies by package name with partial, case-insensitive matching.

        Returns (results, total_count) for pagination.

        Args:
            query: Package name search pattern (partial match)
            repository_id: Filter by repository (optional)
            language: Filter by language ecosystem (optional)
            dependency_type: Filter by type (runtime, dev, etc.) (optional)
            is_direct: Filter by direct/transitive (optional)
            limit: Maximum results to return
            offset: Pagination offset
        """
        pass

    @abstractmethod
    async def count_by_repository(self, repository_id: int) -> int:
        """Count total dependencies in a repository."""
        pass

    @abstractmethod
    async def delete_by_file(self, file_id: int) -> int:
        """Delete all dependencies for a file (for re-indexing). Returns count deleted."""
        pass

    @abstractmethod
    async def delete_by_repository(self, repository_id: int) -> int:
        """Delete all dependencies for a repository. Returns count deleted."""
        pass
