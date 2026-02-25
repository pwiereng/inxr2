"""Symbol repository port interface for symbol entity operations."""

from abc import ABC, abstractmethod

from ....domain.entities import Symbol


class SymbolRepositoryPort(ABC):
    """Port for symbol entity operations."""

    @abstractmethod
    async def save(self, symbol: Symbol) -> Symbol:
        """Save or update a symbol."""
        pass

    @abstractmethod
    async def save_many(self, symbols: list[Symbol]) -> list[Symbol]:
        """Bulk save symbols for performance."""
        pass

    @abstractmethod
    async def find_by_id(self, symbol_id: int) -> Symbol | None:
        """Find symbol by ID."""
        pass

    @abstractmethod
    async def search_by_name(
        self,
        name: str,
        repository_id: int | None = None,
        kind: str | None = None,
        limit: int = 50,
        branch: str | None = None,
        language: str | None = None,
        extensions: list[str] | None = None,
        scope: str | None = None,
        mode: str | None = None,
        case_sensitive: bool = True,
    ) -> list[Symbol]:
        """Search symbols by name (supports autocomplete).

        Args:
            name: Search pattern (substring match or regex when mode="regex")
            repository_id: Filter by repository (optional)
            kind: Filter by symbol kind (optional)
            limit: Maximum results
            branch: Filter by branch name via commit_files -> branch_commits (optional)
            language: Filter by programming language via files (optional)
            extensions: Filter by file extensions (e.g., [".py", ".ts"]) (optional)
            scope: Search scope for global search (e.g. "latest") when no
                repository_id is specified. Ignored when repository_id is set.
            mode: Search mode - "regex" for regex matching on symbol names,
                otherwise substring match (optional)
            case_sensitive: Case-sensitive matching (applies to all modes,
                default True)
        """
        pass

    @abstractmethod
    async def find_by_qualified_name(
        self, repository_id: int, qualified_name: str
    ) -> list[Symbol]:
        """Find symbols by fully qualified name."""
        pass

    @abstractmethod
    async def list_by_file(self, file_id: int) -> list[Symbol]:
        """List all symbols in a file."""
        pass

    @abstractmethod
    async def find_by_exact_name(
        self,
        name: str,
        repository_id: int | None = None,
        commit_id: int | None = None,
    ) -> list[Symbol]:
        """Find all symbols with exact name match.

        Args:
            name: The exact symbol name to match
            repository_id: Filter by repository (optional)
            commit_id: Filter by specific commit via commit_files (optional)
        """
        pass

    @abstractmethod
    async def count_by_repository(self, repository_id: int) -> int:
        """Count total symbols in a repository."""
        pass

    @abstractmethod
    async def delete_by_file(self, file_id: int) -> int:
        """Delete all symbols for a file (for re-indexing). Returns count deleted."""
        pass
