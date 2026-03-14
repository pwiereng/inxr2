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
        offset: int = 0,
        branch: str | None = None,
        language: str | None = None,
        extensions: list[str] | None = None,
        scope: str | None = None,
        mode: str | None = None,
        case_sensitive: bool = True,
        commit_id: int | None = None,
        top_level_only: bool = False,
    ) -> tuple[list[Symbol], int]:
        """Search symbols by name (supports autocomplete).

        Args:
            name: Search pattern (substring match or regex when mode="regex")
            repository_id: Filter by repository (optional)
            kind: Filter by symbol kind (optional)
            limit: Maximum results
            offset: Pagination offset (default 0)
            branch: Filter by branch name via commit_files -> branch_commits (optional)
            language: Filter by programming language via files (optional)
            extensions: Filter by file extensions (e.g., [".py", ".ts"]) (optional)
            scope: Search scope for global search (e.g. "latest") when no
                repository_id is specified. Ignored when repository_id is set.
            mode: Search mode - "regex" for regex matching on symbol names,
                otherwise substring match (optional)
            case_sensitive: Case-sensitive matching (applies to all modes,
                default True)
            commit_id: Filter by specific commit via commit_files (optional).
                When set, takes precedence over branch-based dedup.
            top_level_only: If True, only return symbols that are effectively
                top-level (no parent, or parent is a namespace).

        Returns:
            Tuple of (matching symbols, total count of all matches).
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
    async def list_by_file_and_parent(
        self,
        file_id: int,
        parent_symbol_id: int | None,
    ) -> list[Symbol]:
        """List symbols in a file filtered by parent.

        Args:
            file_id: The file to list symbols from
            parent_symbol_id: Parent symbol ID. None returns top-level symbols
                (those with no parent). An integer returns children of that symbol.

        Returns:
            Symbols ordered by kind grouping then name.
        """
        pass

    @abstractmethod
    async def list_files_with_symbols(
        self,
        repository_id: int,
        branch: str | None = None,
        commit_id: int | None = None,
        language: str | None = None,
        kinds: list[str] | None = None,
    ) -> list[tuple[int, str, str | None, int]]:
        """List files that contain symbols, with counts.

        Returns only files that have at least one symbol, scoped to the
        given branch or commit for temporal consistency.

        Args:
            repository_id: Repository to query
            branch: Branch name for latest-file scoping (optional)
            commit_id: Specific commit for time travel (optional, overrides branch)
            language: Filter by programming language (optional)
            kinds: Filter to files containing symbols of these kinds (optional).
                When set, only files with at least one top-level symbol of the
                given kind(s) are returned.

        Returns:
            List of (file_id, path, language, symbol_count) tuples,
            ordered by path.
        """
        pass

    @abstractmethod
    async def list_distinct_kinds(
        self,
        repository_id: int,
        branch: str | None = None,
        commit_id: int | None = None,
        language: str | None = None,
    ) -> list[str]:
        """List all distinct symbol kinds in a repository.

        Returns every kind value present (including nested symbols),
        scoped to the given branch/commit.

        Args:
            repository_id: Repository to query
            branch: Branch name for latest-file scoping (optional)
            commit_id: Specific commit for time travel (optional, overrides branch)
            language: Filter by programming language (optional)

        Returns:
            Sorted list of distinct kind strings.
        """
        pass

    @abstractmethod
    async def count_top_level_kinds_by_file(
        self,
        file_ids: list[int],
    ) -> dict[int, dict[str, int]]:
        """Count effectively top-level symbols by kind for each file.

        A symbol is effectively top-level if it has no parent or its
        parent is a namespace.

        Args:
            file_ids: File IDs to query.

        Returns:
            Mapping of file_id → {kind: count}. Files with no symbols
            are omitted.
        """
        pass

    @abstractmethod
    async def count_kinds_by_file(
        self,
        file_ids: list[int],
    ) -> dict[int, dict[str, int]]:
        """Count all symbols by kind for each file.

        Includes all symbols regardless of nesting level.
        Excludes namespace kind.

        Args:
            file_ids: File IDs to query.

        Returns:
            Mapping of file_id → {kind: count}. Files with no symbols
            are omitted.
        """
        pass

    @abstractmethod
    async def update_parent_symbol_ids(self, updates: dict[int, int]) -> int:
        """Bulk update parent_symbol_id for multiple symbols.

        Args:
            updates: Mapping of {symbol_id: parent_symbol_id} to set.

        Returns:
            Number of symbols updated.
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
