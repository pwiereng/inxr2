"""Search symbols use case.

Handles symbol search with efficient batch file path enrichment.
"""

from dataclasses import dataclass

from ....domain.constants import QueryDefaults
from ....domain.entities import Symbol
from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    SymbolRepositoryPort,
)


@dataclass
class SymbolWithFilePath:
    """Symbol enriched with file path for display.

    Contains all symbol data plus the file path resolved from file_id.
    """

    symbol: Symbol
    file_path: str | None


@dataclass
class SearchSymbolsRequest:
    """Request to search symbols.

    Args:
        query: Search query for symbol name (empty string matches all)
        repository_id: Optional repository filter. Required when using
            commit_hash.
        kind: Optional symbol kind filter (e.g., "function", "class")
        commit_hash: Optional commit hash for time travel. Requires
            repository_id to be set. Raises ValueError if repository_id
            is not set or if the commit hash cannot be resolved.
        exact_match: If True, match exact name instead of partial
        limit: Maximum results to return
        offset: Offset for pagination
        branch: Optional branch name filter
        language: Optional programming language filter
        extensions: Optional list of file extensions to filter by (e.g. [".py", ".ts"])
        scope: Search scope for cross-repo search (default: "latest").
            Only applies when repository_id is not provided.
        mode: Search mode - "regex" for regex matching, otherwise substring match
        case_sensitive: Case-sensitive matching (applies to all modes, default: True)
    """

    query: str = ""
    repository_id: int | None = None
    kind: str | None = None
    commit_hash: str | None = None
    exact_match: bool = False
    limit: int = QueryDefaults.SYMBOL_SEARCH_LIMIT
    offset: int = 0
    branch: str | None = None
    language: str | None = None
    extensions: list[str] | None = None
    scope: str = "latest"
    mode: str | None = None
    case_sensitive: bool = True
    top_level_only: bool = False


@dataclass
class SearchSymbolsResponse:
    """Response containing search results.

    Args:
        symbols: List of symbols with file paths
        total: Total number of matching symbols across all pages (for pagination)
        limit: Limit used in request
        offset: Offset used in request
    """

    symbols: list[SymbolWithFilePath]
    total: int
    limit: int
    offset: int


class SearchSymbolsUseCase:
    """Use case for searching symbols with file path enrichment.

    Performs symbol search and efficiently enriches results with file paths
    using batch fetching to avoid N+1 queries.

    Handles:
    - Symbol search by name (partial or exact match)
    - Filtering by repository, kind, and commit
    - Pagination with offset/limit
    - Batch file path enrichment
    """

    def __init__(
        self,
        symbol_repo: SymbolRepositoryPort,
        file_repo: FileRepositoryPort,
        commit_repo: CommitRepositoryPort | None = None,
    ) -> None:
        """Initialize use case with dependencies.

        Args:
            symbol_repo: Repository for accessing symbols
            file_repo: Repository for accessing files (for path enrichment)
            commit_repo: Optional repository for commit hash resolution
        """
        self._symbol_repo = symbol_repo
        self._file_repo = file_repo
        self._commit_repo = commit_repo

    async def execute(self, request: SearchSymbolsRequest) -> SearchSymbolsResponse:
        """Execute symbol search.

        Args:
            request: Search parameters

        Returns:
            SearchSymbolsResponse with enriched symbols

        Raises:
            ValueError: If commit_hash is provided but repository_id is
                missing or commit cannot be resolved
        """
        # Resolve commit_id if commit_hash provided
        commit_id: int | None = None
        if request.commit_hash:
            if not request.repository_id or not self._commit_repo:
                raise ValueError("commit_hash requires repository_id to be set")
            commit = await self._commit_repo.find_by_hash(
                request.repository_id, request.commit_hash
            )
            if not commit:
                raise ValueError(
                    f"Commit hash '{request.commit_hash}' not found "
                    f"for repository {request.repository_id}"
                )
            commit_id = commit.id

        # Search symbols
        total: int
        if request.exact_match:
            symbols = await self._symbol_repo.find_by_exact_name(
                name=request.query,
                repository_id=request.repository_id,
                commit_id=commit_id,
            )
            total = len(symbols)
        else:
            symbols, total = await self._symbol_repo.search_by_name(
                name=request.query,
                repository_id=request.repository_id,
                kind=request.kind,
                limit=request.limit,
                offset=request.offset,
                branch=request.branch,
                language=request.language,
                extensions=request.extensions,
                scope=request.scope if request.repository_id is None else None,
                mode=request.mode,
                case_sensitive=request.case_sensitive,
                commit_id=commit_id,
                top_level_only=request.top_level_only,
            )

        # Batch fetch file paths
        enriched_symbols = await self._enrich_with_file_paths(symbols)

        return SearchSymbolsResponse(
            symbols=enriched_symbols,
            total=total,
            limit=request.limit,
            offset=request.offset,
        )

    async def _enrich_with_file_paths(
        self, symbols: list[Symbol]
    ) -> list[SymbolWithFilePath]:
        """Enrich symbols with file paths using batch fetching.

        Args:
            symbols: List of symbols to enrich

        Returns:
            List of symbols with file paths
        """
        # Collect unique file IDs
        file_ids = list({s.file_id for s in symbols if s.file_id})

        # Batch fetch files
        files_by_id = await self._file_repo.find_by_ids(file_ids)

        # Build enriched results
        result = []
        for symbol in symbols:
            file_path = None
            if symbol.file_id:
                file = files_by_id.get(symbol.file_id)
                if file:
                    file_path = file.path
            result.append(SymbolWithFilePath(symbol=symbol, file_path=file_path))
        return result
