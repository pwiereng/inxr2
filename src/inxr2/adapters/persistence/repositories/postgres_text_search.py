"""PostgreSQL text search implementation."""

from typing import Any

from sqlalchemy import column, exists, func, or_, select, text
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
from ..models.commit_file import CommitFileModel
from ..models.file import FileModel
from ..models.repository import RepositoryModel
from ..models.text_content import TextContentModel
from .query_utils import build_text_match_filter
from .shared_queries import head_file_ids_subquery


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

        # Apply branch filter
        # File-derived content (comments, docstrings, file_content) has NULL commit_id
        # but has source_file_id — join through commit_files to reach branch_commits.
        # Commit messages have commit_id but NULL source_file_id — join directly.
        if query.branch is not None:
            # File-based: text_contents.source_file_id → commit_files → branch_commits
            file_branch_exists = exists(
                select(1)
                .select_from(CommitFileModel)
                .join(
                    BranchCommitModel,
                    (BranchCommitModel.commit_id == CommitFileModel.commit_id)
                    & (
                        BranchCommitModel.repository_id
                        == TextContentModel.repository_id
                    ),
                )
                .where(CommitFileModel.file_id == TextContentModel.source_file_id)
                .where(BranchCommitModel.branch == query.branch)
            )
            # Commit-based: text_contents.commit_id → branch_commits
            commit_branch_exists = exists(
                select(1)
                .select_from(BranchCommitModel)
                .where(BranchCommitModel.commit_id == TextContentModel.commit_id)
                .where(
                    BranchCommitModel.repository_id == TextContentModel.repository_id
                )
                .where(BranchCommitModel.branch == query.branch)
            )
            base_query = base_query.where(file_branch_exists | commit_branch_exists)

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

        # Apply extension filters via files table
        if query.extensions:
            real_exts = [e for e in query.extensions if e != "(none)"]
            has_none = "(none)" in query.extensions
            if real_exts and has_none:
                ext_filter = or_(
                    FileModel.extension.in_(real_exts),
                    FileModel.extension.is_(None),
                )
            elif has_none:
                ext_filter = FileModel.extension.is_(None)
            else:
                ext_filter = FileModel.extension.in_(real_exts)
            base_query = base_query.where(
                TextContentModel.source_file_id.in_(
                    select(FileModel.id).where(ext_filter)
                )
            )

        # Apply global scope filter (when no repository_id is specified)
        if query.repository_id is None and query.scope == "latest":
            head_fids = head_file_ids_subquery()
            # For file-derived content: source_file_id must be at HEAD
            file_scope = TextContentModel.source_file_id.in_(
                select(head_fids.c.file_id)
            )
            # For commit messages: include all commits on default branches
            # (not just HEAD), since commit messages are inherently tied to
            # specific commits and filtering to only HEAD would return at
            # most one commit message per repo.
            default_commits = self._default_branch_commit_ids_subquery()
            commit_scope = TextContentModel.commit_id.in_(
                select(default_commits.c.commit_id)
            )
            base_query = base_query.where(file_scope | commit_scope)

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
                    func.ts_rank(content_tsvector, tsquery).label("rank"),
                    func.ts_headline(
                        "english",
                        TextContentModel.content,
                        tsquery,
                        "StartSel=<mark>, StopSel=</mark>, "
                        "MaxFragments=3, MaxWords=35, MinWords=15",
                    ).label("headline"),
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
                headline = row[2] if len(row) > 2 else None
                text_content = self.mapper.to_domain(model)
                search_results.append(
                    TextSearchResult(
                        text_content=text_content, rank=rank, headline=headline
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
            regex_filter = build_text_match_filter(
                TextContentModel.content,
                query.query,
                mode="regex",
                case_sensitive=query.case_sensitive,
            )
            return query_builder.where(regex_filter)
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

    def _default_branch_commit_ids_subquery(self) -> Any:
        """All commit IDs on each repo's default branch."""
        return (
            select(BranchCommitModel.commit_id.label("commit_id"))
            .join(
                RepositoryModel,
                (RepositoryModel.id == BranchCommitModel.repository_id)
                & (RepositoryModel.default_branch == BranchCommitModel.branch),
            )
            .subquery()
        )
