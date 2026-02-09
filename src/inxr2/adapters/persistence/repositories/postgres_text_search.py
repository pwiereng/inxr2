"""PostgreSQL text search implementation."""

import re
from typing import Any

from sqlalchemy import column, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from ....application.ports.services import (
    TextSearchPort,
    TextSearchQuery,
    TextSearchResult,
)
from ....domain.value_objects import QueryMode
from ..mappers import TextContentMapper
from ..models.branch_commit import BranchCommitModel
from ..models.text_content import TextContentModel

# Regex validation constants
MAX_REGEX_LENGTH = 500
# Patterns that can cause catastrophic backtracking (ReDoS)
DANGEROUS_REGEX_PATTERNS = [
    r"\(\.\*\)\+",  # (.*)+
    r"\(\.\+\)\+",  # (.+)+
    r"\([^)]*\+\)\+",  # (x+)+ pattern
    r"\([^)]*\*\)\+",  # (x*)+
    r"\([^)]*\+\)\*",  # (x+)*
    r"\([^)]*\*\)\*",  # (x*)*
]


def _validate_regex_pattern(pattern: str) -> None:
    """
    Validate regex pattern for safety.

    Args:
        pattern: The regex pattern to validate

    Raises:
        ValueError: If pattern is invalid or potentially dangerous
    """
    # Check length
    if len(pattern) > MAX_REGEX_LENGTH:
        raise ValueError(
            f"Regex pattern too long: {len(pattern)} characters "
            f"(max {MAX_REGEX_LENGTH})"
        )

    # Check for dangerous patterns that can cause catastrophic backtracking
    for dangerous in DANGEROUS_REGEX_PATTERNS:
        if re.search(dangerous, pattern):
            raise ValueError(
                "Regex pattern contains potentially dangerous nested quantifiers "
                "that could cause performance issues"
            )

    # Try to compile the regex to catch syntax errors early
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}") from None


class PostgresTextSearch(TextSearchPort):
    """
    PostgreSQL implementation of TextSearchPort.

    Uses tsvector and GIN indexes for full-text search with support for:
    - Keyword search (plainto_tsquery - handles raw user input safely)
    - Phrase search (phraseto_tsquery)
    - Regex search (PostgreSQL ~ operator, bypasses tsvector)

    Also supports branch filtering via JOIN with branch_commits table.

    Security notes:
    - Regex patterns are validated for length and dangerous patterns
    - Keyword queries use plainto_tsquery to safely handle special characters
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize text search.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.mapper = TextContentMapper()

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
        if not query.query or not query.query.strip():
            raise ValueError("Search query cannot be empty")

        # Build base query
        base_query = select(TextContentModel)

        # Apply query mode filter
        base_query = self._apply_query_mode_filter(base_query, query)

        # Apply repository filter
        if query.repository_id is not None:
            base_query = base_query.where(
                TextContentModel.repository_id == query.repository_id
            )

        # Apply branch filter (JOIN with branch_commits)
        if query.branch is not None:
            base_query = base_query.join(
                BranchCommitModel,
                (BranchCommitModel.commit_id == TextContentModel.commit_id)
                & (BranchCommitModel.repository_id == TextContentModel.repository_id),
            ).where(BranchCommitModel.branch == query.branch)

        # Apply commit filter (for time travel)
        if query.commit_id is not None:
            base_query = base_query.where(TextContentModel.commit_id == query.commit_id)

        # Apply source type filters
        if query.source_types:
            base_query = base_query.where(
                TextContentModel.source_type.in_(query.source_types)
            )

        # Apply language filters
        if query.languages:
            base_query = base_query.where(
                TextContentModel.language.in_(query.languages)
            )

        # Get total count (before pagination)
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total_count = count_result.scalar_one()

        # Add ranking and ordering based on query mode
        # content_tsvector is managed by triggers, not mapped in the ORM
        content_tsvector: Any = column("content_tsvector")

        if query.mode == QueryMode.REGEX.value:
            # Regex mode: no ranking, just order by repository and line
            results_query = base_query.order_by(
                TextContentModel.repository_id,
                TextContentModel.source_file_id,
                TextContentModel.source_line,
                TextContentModel.id,
            )
        else:
            # Keyword/phrase mode: order by relevance rank
            # Add ranking to the base query and apply DISTINCT to avoid duplicates
            tsquery = self._build_tsquery(query)
            results_query = (
                base_query.add_columns(
                    func.ts_rank(content_tsvector, tsquery).label("rank")
                )
                .distinct()
                .order_by(text("rank DESC"), TextContentModel.id)
            )

        # Apply pagination
        results_query = results_query.limit(query.limit).offset(query.offset)

        # Execute query
        result = await self.session.execute(results_query)

        # Convert to domain entities and results
        search_results = []
        if query.mode == QueryMode.REGEX.value:
            models = result.scalars().all()
            for model in models:
                text_content = self.mapper.to_domain(model)
                search_results.append(
                    TextSearchResult(text_content=text_content, rank=0.0, headline=None)
                )
        else:
            rows = result.all()
            for row in rows:
                model = row[0]
                rank = row[1] if len(row) > 1 else 0.0
                text_content = self.mapper.to_domain(model)
                # TODO: Add ts_headline support for snippets in future phase
                search_results.append(
                    TextSearchResult(
                        text_content=text_content, rank=rank, headline=None
                    )
                )

        return search_results, total_count

    def _apply_query_mode_filter(
        self, query_builder: Select[Any], query: TextSearchQuery
    ) -> Select[Any]:
        """
        Apply query mode-specific WHERE clause.

        Args:
            query_builder: SQLAlchemy select statement
            query: Search query parameters

        Returns:
            Updated select statement with query mode filter
        """
        # content_tsvector is managed by triggers, not mapped in the ORM
        content_tsvector: Any = column("content_tsvector")

        if query.mode == QueryMode.KEYWORD.value:
            # Keyword search using tsvector
            tsquery = self._build_tsquery(query)
            return query_builder.where(content_tsvector.op("@@")(tsquery))
        elif query.mode == QueryMode.PHRASE.value:
            # Phrase search using tsvector
            tsquery = self._build_tsquery(query)
            return query_builder.where(content_tsvector.op("@@")(tsquery))
        elif query.mode == QueryMode.REGEX.value:
            # Regex search bypasses tsvector, uses PostgreSQL ~ operator
            # Validate pattern for safety before sending to database
            _validate_regex_pattern(query.query)
            return query_builder.where(TextContentModel.content.op("~")(query.query))
        else:
            # Default to keyword search
            tsquery = self._build_tsquery(query)
            return query_builder.where(content_tsvector.op("@@")(tsquery))

    def _build_tsquery(self, query: TextSearchQuery) -> Any:
        """
        Build PostgreSQL tsquery from search query.

        Args:
            query: Search query parameters

        Returns:
            SQLAlchemy text expression for tsquery

        Notes:
            - Uses plainto_tsquery for keyword mode to safely handle user input
              (special characters like :, !, &, |, (, ) are handled automatically)
            - Uses phraseto_tsquery for phrase mode for exact phrase matching
        """
        if query.mode == QueryMode.PHRASE.value:
            # Use phraseto_tsquery for exact phrase matching
            return func.phraseto_tsquery("english", query.query)
        else:
            # Use plainto_tsquery for keyword search (default)
            # This safely handles special characters in user input
            # (e.g., "TODO: fix" works without crashing on the colon)
            return func.plainto_tsquery("english", query.query)
