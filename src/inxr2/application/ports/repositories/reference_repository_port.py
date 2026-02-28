"""Reference repository port interface for reference entity operations."""

from abc import ABC, abstractmethod
from collections.abc import Callable

from ....domain.entities import Reference


class ReferenceRepositoryPort(ABC):
    """Port for reference entity operations."""

    @abstractmethod
    async def save(self, reference: Reference) -> Reference:
        """Save or update a reference."""
        pass

    @abstractmethod
    async def save_many(self, references: list[Reference]) -> list[Reference]:
        """Bulk save references for performance."""
        pass

    @abstractmethod
    async def find_by_id(self, reference_id: int) -> Reference | None:
        """Find reference by ID."""
        pass

    @abstractmethod
    async def find_references_to_symbol(
        self,
        symbol_id: int,
        limit: int = 100,
        commit_id: int | None = None,
        branch: str | None = None,
        repository_id: int | None = None,
    ) -> list[Reference]:
        """Find all references TO a symbol (find usages).

        Args:
            symbol_id: The target symbol ID
            limit: Maximum number of results
            commit_id: Filter by specific commit via commit_files (optional).
                       If None, returns from latest version of each file.
            branch: Filter by branch name (only show refs from files on this branch).
            repository_id: Filter by repository (scopes the latest-file dedup).
        """
        pass

    @abstractmethod
    async def list_by_file(self, file_id: int) -> list[Reference]:
        """List all references in a file."""
        pass

    @abstractmethod
    async def find_references_by_text(
        self,
        text: str,
        repository_id: int,
        limit: int = 100,
        commit_id: int | None = None,
        branch: str | None = None,
    ) -> list[Reference]:
        """Find all references matching the given text.

        Args:
            text: The reference text to match
            repository_id: Filter by repository
            limit: Maximum number of results
            commit_id: Filter by specific commit via commit_files (optional).
                       If None, returns from latest version of each file.
            branch: Filter by branch name (only show refs from files on this branch).
        """
        pass

    @abstractmethod
    async def search_by_text(
        self,
        query: str,
        repository_id: int | None = None,
        branch: str | None = None,
        scope: str | None = None,
        extensions: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
        mode: str | None = None,
        case_sensitive: bool = True,
    ) -> tuple[list[Reference], int]:
        """Search references by text match on reference_text.

        Uses substring matching by default, or regex matching when
        mode="regex". Case sensitivity is controlled by case_sensitive.

        Args:
            query: Substring or regex pattern to search for in reference_text
            repository_id: Filter by repository (optional)
            branch: Filter by branch name (optional)
            scope: Search scope for global search (e.g. "latest") when no
                repository_id is specified. Ignored when repository_id is set.
            extensions: Filter by file extensions (e.g. [".py", ".ts"]) (optional)
            limit: Maximum results to return (default 20)
            offset: Pagination offset (default 0)
            mode: Search mode - "regex" for regex matching, otherwise
                substring match (optional)
            case_sensitive: Case-sensitive matching (applies to all modes,
                default True)

        Returns:
            Tuple of (matching references, total count) for pagination
        """
        pass

    @abstractmethod
    async def count_by_repository(self, repository_id: int) -> int:
        """Count total references in a repository."""
        pass

    @abstractmethod
    async def delete_by_file(self, file_id: int) -> int:
        """Delete all references for a file (for re-indexing). Returns count deleted."""
        pass

    @abstractmethod
    async def count_unresolved_references(self, repository_id: int) -> int:
        """Count references that don't have a target_symbol_id set.

        Args:
            repository_id: The repository ID to count for

        Returns:
            Number of unresolved references
        """
        pass

    @abstractmethod
    async def resolve_unlinked_references(
        self, repository_id: int, branch: str | None = None
    ) -> int:
        """Resolve references to their target symbols.

        After indexing, this method matches reference_text to symbol names
        and updates the target_symbol_id for each reference.

        With content-addressable file versions, symbols are unique per file version
        (no commit_id ambiguity), so commit-aware mode is no longer needed.

        Args:
            repository_id: The repository ID to resolve references for
            branch: Accepted for API compatibility but does not affect
                resolution. All references are resolved using repo-wide
                latest symbols.

        Returns:
            Number of references resolved
        """
        pass

    @abstractmethod
    async def prepare_resolution(
        self,
        repository_id: int,
        progress_callback: Callable[[str], None] | None = None,
        branch: str | None = None,
    ) -> None:
        """Pre-compute lookup tables for reference resolution.

        Called once before the batch loop to build any indexes or temp
        tables needed by resolve_references_batch. Implementations that
        don't need preparation can no-op.

        Args:
            repository_id: The repository ID to prepare for
            progress_callback: Optional callback receiving stage descriptions
                (e.g. "Building same-file index...")
            branch: Accepted for API compatibility but does not affect
                resolution.
        """
        pass

    @abstractmethod
    async def resolve_references_batch(
        self,
        repository_id: int,
        batch_size: int = 1000,
    ) -> int:
        """Resolve a batch of unlinked references.

        Processes up to batch_size references at a time. Call repeatedly
        until it returns 0 to resolve all references.

        Args:
            repository_id: The repository ID to resolve references for
            batch_size: Maximum references to resolve in this batch

        Returns:
            Number of references resolved in this batch
        """
        pass
