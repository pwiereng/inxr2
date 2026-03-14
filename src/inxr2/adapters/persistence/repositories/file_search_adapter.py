"""PostgreSQL file search repository adapter."""

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import FileSearchPort
from ....domain.entities import File
from ..mappers import FileMapper
from ..models.branch_commit import BranchCommitModel
from ..models.commit import CommitModel
from ..models.commit_file import CommitFileModel
from ..models.file import FileModel
from .query_utils import NONE_SENTINEL, split_extension_filter
from .shared_queries import head_file_ids_subquery, latest_file_ids_subquery


class PostgresFileSearchRepository(FileSearchPort):
    """PostgreSQL implementation of FileSearchPort."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.mapper = FileMapper()

    async def search_by_name(
        self,
        query: str,
        repository_id: int | None = None,
        commit_id: int | None = None,
        language: str | None = None,
        extensions: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
        scope: str | None = None,
    ) -> tuple[list["File"], int]:
        """Search files by name/path pattern.

        Uses case-insensitive pattern matching. When commit_id is specified,
        filters via commit_files. When commit_id is None, deduplicates by
        returning only the latest version of each path (highest file ID).
        When scope is "latest" and repository_id is None, filters to files
        at HEAD of each repo's default branch.

        Returns:
            Tuple of (matching files, total count of all matches).
        """
        query_lower = query.lower()

        # Build base filter query (without relevance — used for counting)
        base_stmt = select(FileModel.id).where(
            func.lower(FileModel.path).contains(query_lower, autoescape=True)
        )

        if repository_id is not None:
            base_stmt = base_stmt.where(FileModel.repository_id == repository_id)

        if commit_id is not None:
            base_stmt = base_stmt.join(
                CommitFileModel, CommitFileModel.file_id == FileModel.id
            ).where(CommitFileModel.commit_id == commit_id)

        if language is not None:
            base_stmt = base_stmt.where(FileModel.language == language)

        if extensions is not None and len(extensions) > 0:
            real_exts, has_none = split_extension_filter(extensions)
            if real_exts and has_none:
                base_stmt = base_stmt.where(
                    or_(
                        FileModel.extension.in_(real_exts),
                        FileModel.extension.is_(None),
                    )
                )
            elif has_none:
                base_stmt = base_stmt.where(FileModel.extension.is_(None))
            else:
                base_stmt = base_stmt.where(FileModel.extension.in_(real_exts))

        # Deduplicate / scope filtering when no commit_id
        if commit_id is None:
            if repository_id is None and scope == "latest":
                head_fids = head_file_ids_subquery()
                base_stmt = base_stmt.where(
                    FileModel.id.in_(select(head_fids.c.file_id))
                )
            else:
                latest_sq = latest_file_ids_subquery(repository_id)
                base_stmt = base_stmt.where(
                    FileModel.id.in_(select(latest_sq.c.max_id))
                )

        # Count total matches (lightweight — no relevance scoring)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Build result query with relevance scoring for ordering
        filename_expr = func.lower(func.substring(FileModel.path, r"[^/]+$"))
        relevance = case(
            (filename_expr == query_lower, 1),
            (filename_expr.startswith(query_lower, autoescape=True), 2),
            else_=3,
        )

        result_stmt = (
            select(FileModel, relevance.label("relevance"))
            .where(FileModel.id.in_(base_stmt))
            .order_by(relevance, FileModel.path)
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(result_stmt)
        rows = result.all()

        return [self.mapper.to_domain(row[0]) for row in rows], total

    async def get_distinct_extensions(
        self,
        repository_id: int | None = None,
        branch: str | None = None,
        scope: str | None = None,
    ) -> list[str]:
        """Get distinct file extensions across indexed files.

        Returns a sorted list of extensions. If extensionless files exist,
        the sentinel value "(none)" is prepended to the list.
        """
        query_stmt = select(FileModel.extension)

        if repository_id is not None:
            query_stmt = query_stmt.where(FileModel.repository_id == repository_id)

            if branch is not None:
                # Filter to files at the latest commit on this branch
                latest_commit = (
                    select(CommitModel.id)
                    .join(
                        BranchCommitModel,
                        BranchCommitModel.commit_id == CommitModel.id,
                    )
                    .where(
                        CommitModel.repository_id == repository_id,
                        BranchCommitModel.branch == branch,
                        BranchCommitModel.repository_id == repository_id,
                    )
                    .order_by(CommitModel.commit_date.desc(), CommitModel.id.desc())
                    .limit(1)
                    .scalar_subquery()
                )
                query_stmt = query_stmt.where(
                    FileModel.id.in_(
                        select(CommitFileModel.file_id).where(
                            CommitFileModel.commit_id == latest_commit
                        )
                    )
                )
        elif scope == "latest":
            head_fids = head_file_ids_subquery()
            query_stmt = query_stmt.where(FileModel.id.in_(select(head_fids.c.file_id)))

        query_stmt = query_stmt.distinct().order_by(FileModel.extension)

        result = await self.session.execute(query_stmt)
        has_none = False
        extensions: list[str] = []
        for row in result.all():
            if row[0] is None:
                has_none = True
            else:
                extensions.append(row[0])

        if has_none:
            extensions.insert(0, NONE_SENTINEL)

        return extensions
