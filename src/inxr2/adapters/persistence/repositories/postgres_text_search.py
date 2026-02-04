"""PostgreSQL text search implementation."""

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


class PostgresTextSearch(TextSearchPort):
    """
    PostgreSQL implementation of TextSearchPort.

    Uses tsvector and GIN indexes for full-text search with support for:
    - Keyword search (to_tsquery)
    - Phrase search (phraseto_tsquery)
    - Regex search (PostgreSQL ~ operator, bypasses tsvector)

    Also supports branch filtering via JOIN with branch_commits table.
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
        # Note: content_tsvector is not mapped in the ORM (SQLite compatibility)
        content_tsvector: Any = column("content_tsvector")

        if query.mode == QueryMode.REGEX.value:
            # Regex mode: no ranking, just order by repository and line
            results_query = base_query.order_by(
                TextContentModel.repository_id,
                TextContentModel.source_file_id,
                TextContentModel.source_line,
            )
        else:
            # Keyword/phrase mode: order by relevance rank
            tsquery = self._build_tsquery(query)
            results_query = (
                select(
                    TextContentModel,
                    func.ts_rank(content_tsvector, tsquery).label("rank"),
                )
                .select_from(base_query.subquery())
                .order_by(text("rank DESC"))
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
        # Note: content_tsvector is not mapped in the ORM (SQLite compatibility)
        # We access it using column() for PostgreSQL queries
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
        """
        if query.mode == QueryMode.PHRASE.value:
            # Use phraseto_tsquery for exact phrase matching
            return func.phraseto_tsquery("english", query.query)
        else:
            # Use to_tsquery for keyword search (default)
            # Replace spaces with & for AND operator
            query_text = " & ".join(query.query.split())
            return func.to_tsquery("english", query_text)
