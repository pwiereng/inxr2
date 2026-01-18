"""Search symbols use case."""

from dataclasses import dataclass

from ...domain.entities import Symbol
from ..ports.repositories import SymbolRepositoryPort


@dataclass
class SearchSymbolsRequest:
    """
    Request to search for symbols.

    TODO: Add filtering options (repository, language, kind)
    TODO: Add pagination parameters
    """

    query: str
    repository_id: int | None = None
    limit: int = 100


@dataclass
class SearchSymbolsResponse:
    """
    Response from symbol search.

    TODO: Add pagination metadata
    TODO: Add search statistics
    """

    symbols: list[Symbol]
    total_count: int


class SearchSymbolsUseCase:
    """
    Use case for searching symbols.

    This encapsulates the business logic for symbol search.
    Dependencies are injected via constructor.

    TODO: Implement ranking algorithm
    TODO: Add fuzzy matching
    TODO: Add autocomplete support
    """

    def __init__(self, symbol_repository: SymbolRepositoryPort) -> None:
        """
        Initialize use case.

        Args:
            symbol_repository: Repository for accessing symbols
        """
        self._symbol_repository = symbol_repository

    async def execute(self, request: SearchSymbolsRequest) -> SearchSymbolsResponse:
        """
        Execute symbol search.

        Args:
            request: Search request parameters

        Returns:
            Search results

        TODO: Implement search logic
        TODO: Add error handling
        TODO: Add logging
        """
        # TODO: Implement
        # 1. Validate request
        # 2. Query repository with filters
        # 3. Rank results
        # 4. Return response

        # Get all matching symbols (no limit) for total count
        all_symbols = await self._symbol_repository.search_by_name(
            name=request.query,
            repository_id=request.repository_id,
            limit=9999,  # Get all for count
        )

        # Apply limit for response
        limited_symbols = all_symbols[: request.limit]

        return SearchSymbolsResponse(
            symbols=limited_symbols, total_count=len(all_symbols)
        )
