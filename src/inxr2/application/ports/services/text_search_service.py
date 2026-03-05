"""Text search service port interface and related data classes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ....domain.entities import TextContent


@dataclass(frozen=True)
class TextSearchResult:
    """Result from a text search query.

    Attributes:
        text_content: The matching text content entity
        rank: Relevance score (higher is better, typically 0.0-1.0)
        headline: Optional highlighted snippet showing match context
    """

    text_content: TextContent
    rank: float
    headline: str | None = None


@dataclass(frozen=True)
class TextSearchQuery:
    """Query parameters for text search.

    Attributes:
        query: Search query string
        mode: Query mode (keyword, phrase, regex) - default: keyword
        repository_id: Optional repository filter
        branch: Optional branch name filter (uses branch_commits table)
        commit_id: Optional commit filter (for time travel)
        source_types: Optional list of source types to filter by
        languages: Optional list of languages to filter by
        extensions: Optional list of file extensions to filter by
        case_sensitive: Whether the search is case sensitive (default: True)
        scope: Search scope for cross-repo search (e.g. "latest").
            Only applies when repository_id is not provided.
        limit: Maximum results to return (default: 20)
        offset: Pagination offset (default: 0)
    """

    query: str
    mode: str = "keyword"  # Use str instead of enum for JSON compatibility
    repository_id: int | None = None
    branch: str | None = None
    commit_id: int | None = None
    source_types: list[str] | None = None
    languages: list[str] | None = None
    extensions: list[str] | None = None
    case_sensitive: bool = True
    scope: str | None = None
    limit: int = 20
    offset: int = 0


class TextSearchPort(ABC):
    """
    Port for full-text search operations.

    This is the key abstraction for database-agnostic text search.
    Implementations can use:
    - PostgreSQL tsvector and GIN indexes
    - Elasticsearch (future)

    The port abstracts away database-specific query syntax and ranking algorithms.
    """

    @abstractmethod
    async def search(
        self, query: TextSearchQuery
    ) -> tuple[list[TextSearchResult], int]:
        """
        Execute full-text search.

        Args:
            query: Search query parameters

        Returns:
            Tuple of (results, total_count) where:
            - results: List of matching results (limited by query.limit/offset)
            - total_count: Total number of matches (for pagination)

        Raises:
            ValueError: If query is empty or invalid
        """
        pass
