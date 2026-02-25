"""PostgreSQL reference repository adapter."""

from collections.abc import Callable
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import ReferenceRepositoryPort
from ....domain.entities import Reference
from ..mappers import ReferenceMapper
from ..models.commit_file import CommitFileModel
from ..models.file import FileModel
from ..models.reference import ReferenceModel
from .base_repository import BaseSQLAlchemyRepository
from .query_utils import build_text_match_filter
from .shared_queries import (
    LATEST_FILE_IDS_SQL,
    head_file_ids_subquery,
    latest_file_ids_subquery,
)


class PostgresReferenceRepository(
    BaseSQLAlchemyRepository[Reference, ReferenceModel], ReferenceRepositoryPort
):
    """PostgreSQL implementation of ReferenceRepositoryPort."""

    _model_class = ReferenceModel
    _set_indexed_at_on_save_many = True

    # -- Join clauses for the 3 resolution passes --

    _PASS1_JOIN = """JOIN _resolve_pass1 sub_t
                    ON r.reference_text = sub_t.name
                    AND r.source_file_id = sub_t.file_id"""

    _PASS2_JOIN = """JOIN files rf ON r.source_file_id = rf.id
                    JOIN _resolve_pass2 sub_t
                    ON r.reference_text = sub_t.name
                    AND rf.language = sub_t.language"""

    _PASS3_JOIN = """JOIN _resolve_pass3 sub_t
                    ON r.reference_text = sub_t.name"""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.mapper = ReferenceMapper()
        self._resolution_tables_for_repo_id: int | None = None

    async def find_references_to_symbol(
        self,
        symbol_id: int,
        limit: int = 100,
        commit_id: int | None = None,
        branch: str | None = None,
    ) -> list[Reference]:
        """Find all references TO a symbol (find usages).

        With content-addressable file versions, references belong to file
        versions. When commit_id is provided, we filter via commit_files
        to show only references from files at that commit.

        Note: ``branch`` scopes the latest-file dedup to that branch's
        commits. It requires a repository context (inferred from the
        symbol's references).
        """
        if commit_id is not None:
            # Time travel mode: filter via commit_files junction
            query = (
                select(ReferenceModel)
                .join(
                    CommitFileModel,
                    CommitFileModel.file_id == ReferenceModel.source_file_id,
                )
                .where(
                    ReferenceModel.target_symbol_id == symbol_id,
                    CommitFileModel.commit_id == commit_id,
                )
            )

            result = await self.session.execute(
                query.order_by(ReferenceModel.source_line).limit(limit)
            )
            models = result.scalars().all()
            return [self.mapper.to_domain(model) for model in models]

        # Default: get from latest version of each file.
        # Deduplicate by filtering to only the latest file version per path.
        # When branch is set, dedup is scoped to that branch.
        latest_sq = latest_file_ids_subquery(branch=branch)
        result = await self.session.execute(
            select(ReferenceModel)
            .where(
                ReferenceModel.target_symbol_id == symbol_id,
                ReferenceModel.source_file_id.in_(select(latest_sq.c.max_id)),
            )
            .order_by(ReferenceModel.source_line)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def find_references_by_text(
        self,
        text: str,
        repository_id: int,
        limit: int = 100,
        commit_id: int | None = None,
        branch: str | None = None,
    ) -> list[Reference]:
        """Find all references matching the given text.

        With content-addressable file versions, each file version has unique
        references. When commit_id is provided, filters via commit_files.

        Note: ``branch`` scopes the latest-file dedup to that branch's
        commits. It requires ``repository_id`` to take effect.
        """
        if commit_id is not None:
            # Time travel mode: filter via commit_files junction
            query = (
                select(ReferenceModel)
                .join(
                    CommitFileModel,
                    CommitFileModel.file_id == ReferenceModel.source_file_id,
                )
                .where(
                    ReferenceModel.reference_text == text,
                    ReferenceModel.repository_id == repository_id,
                    CommitFileModel.commit_id == commit_id,
                )
            )

            result = await self.session.execute(
                query.order_by(
                    ReferenceModel.source_file_id, ReferenceModel.source_line
                ).limit(limit)
            )
            models = result.scalars().all()
            return [self.mapper.to_domain(model) for model in models]

        # Default: deduplicate by filtering to latest file version per path.
        # When branch is set, dedup is scoped to that branch.
        latest_sq = latest_file_ids_subquery(repository_id, branch=branch)
        result = await self.session.execute(
            select(ReferenceModel)
            .where(
                ReferenceModel.reference_text == text,
                ReferenceModel.repository_id == repository_id,
                ReferenceModel.source_file_id.in_(select(latest_sq.c.max_id)),
            )
            .order_by(ReferenceModel.source_file_id, ReferenceModel.source_line)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

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
        """Search references by text match on reference_text."""
        text_filter = build_text_match_filter(
            ReferenceModel.reference_text,
            query,
            mode=mode,
            case_sensitive=case_sensitive,
        )
        base_query = select(ReferenceModel).where(text_filter)

        if repository_id is not None:
            base_query = base_query.where(ReferenceModel.repository_id == repository_id)
            # Scope to latest files for this repo/branch
            latest_sq = latest_file_ids_subquery(repository_id, branch=branch)
            base_query = base_query.where(
                ReferenceModel.source_file_id.in_(select(latest_sq.c.max_id))
            )
        elif scope == "latest":
            # Global scope: filter to HEAD files across all repos
            head_fids = head_file_ids_subquery()
            base_query = base_query.where(
                ReferenceModel.source_file_id.in_(select(head_fids.c.file_id))
            )

        # Apply extension filter via files table
        if extensions is not None and len(extensions) > 0:
            base_query = base_query.where(
                ReferenceModel.source_file_id.in_(
                    select(FileModel.id).where(FileModel.extension.in_(extensions))
                )
            )

        # Get total count
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        # Fetch paginated results
        results_query = (
            base_query.order_by(
                ReferenceModel.repository_id,
                ReferenceModel.source_file_id,
                ReferenceModel.source_line,
            )
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(results_query)
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models], total

    async def list_by_file(self, file_id: int) -> list[Reference]:
        """List all references in a file."""
        result = await self.session.execute(
            select(ReferenceModel)
            .where(ReferenceModel.source_file_id == file_id)
            .order_by(ReferenceModel.source_line, ReferenceModel.source_column)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def delete_by_file(self, file_id: int) -> int:
        """Delete all references for a file (for re-indexing). Returns count deleted."""
        result = await self.session.execute(
            delete(ReferenceModel).where(ReferenceModel.source_file_id == file_id)
        )
        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def count_unresolved_references(self, repository_id: int) -> int:
        """Count references that don't have a target_symbol_id set."""
        result = await self.session.execute(
            select(func.count(ReferenceModel.id)).where(
                ReferenceModel.repository_id == repository_id,
                ReferenceModel.target_symbol_id.is_(None),
            )
        )
        return result.scalar() or 0

    async def _ensure_resolution_tables(
        self,
        repository_id: int,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Create temp tables for symbol resolution, restricted to latest files.

        Pre-computes name-to-target-ID mappings for the three resolution passes:
        1. Same-file: (name, file_id) -> min symbol ID
        2. Same-language: (name, language) -> min symbol ID
        3. Any-match: (name) -> min symbol ID

        Tables are created once and reused across batch calls within the same
        session. Only symbols from the latest version of each file path are
        included, avoiding the O(commits x symbols) scan of all historical
        file versions.
        """
        if self._resolution_tables_for_repo_id == repository_id:
            return

        def _report(msg: str) -> None:
            if progress_callback is not None:
                progress_callback(msg)

        # Drop any stale tables from a previous repository
        for table in (
            "_resolve_latest_files",
            "_resolve_pass1",
            "_resolve_pass2",
            "_resolve_pass3",
        ):
            await self.session.execute(
                text(f"DROP TABLE IF EXISTS {table}")  # noqa: S608
            )

        # Step 0: Compute latest file IDs once (expensive window function)
        _report("Finding latest file versions...")
        await self.session.execute(
            text(f"""
                CREATE TEMP TABLE _resolve_latest_files AS
                {LATEST_FILE_IDS_SQL}
            """),
            {"repo_id": repository_id},
        )
        await self.session.execute(
            text("CREATE INDEX ON _resolve_latest_files (file_id)")
        )

        # Pass 1: same-file lookup (name + file_id -> min symbol id)
        _report("Building same-file symbol index...")
        await self.session.execute(
            text("""
                CREATE TEMP TABLE _resolve_pass1 AS
                SELECT s.name, s.file_id, MIN(s.id) AS min_id
                FROM symbols s
                WHERE s.repository_id = :repo_id
                  AND s.file_id IN (
                      SELECT file_id FROM _resolve_latest_files
                  )
                GROUP BY s.name, s.file_id
            """),
            {"repo_id": repository_id},
        )
        await self.session.execute(
            text("CREATE INDEX ON _resolve_pass1 (name, file_id)")
        )

        # Pass 2: same-language lookup (name + language -> min symbol id)
        _report("Building same-language symbol index...")
        await self.session.execute(
            text("""
                CREATE TEMP TABLE _resolve_pass2 AS
                SELECT s.name, f.language, MIN(s.id) AS min_id
                FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE s.repository_id = :repo_id
                  AND s.file_id IN (
                      SELECT file_id FROM _resolve_latest_files
                  )
                GROUP BY s.name, f.language
            """),
            {"repo_id": repository_id},
        )
        await self.session.execute(
            text("CREATE INDEX ON _resolve_pass2 (name, language)")
        )

        # Pass 3: any-match lookup (name -> min symbol id)
        _report("Building global symbol index...")
        await self.session.execute(
            text("""
                CREATE TEMP TABLE _resolve_pass3 AS
                SELECT s.name, MIN(s.id) AS min_id
                FROM symbols s
                WHERE s.repository_id = :repo_id
                  AND s.file_id IN (
                      SELECT file_id FROM _resolve_latest_files
                  )
                GROUP BY s.name
            """),
            {"repo_id": repository_id},
        )
        await self.session.execute(text("CREATE INDEX ON _resolve_pass3 (name)"))

        self._resolution_tables_for_repo_id = repository_id

    async def _drop_resolution_tables(self) -> None:
        """Drop resolution temp tables."""
        for table in (
            "_resolve_latest_files",
            "_resolve_pass1",
            "_resolve_pass2",
            "_resolve_pass3",
        ):
            await self.session.execute(
                text(f"DROP TABLE IF EXISTS {table}")  # noqa: S608
            )
        self._resolution_tables_for_repo_id = None

    async def prepare_resolution(
        self,
        repository_id: int,
        progress_callback: Callable[[str], None] | None = None,
        branch: str | None = None,
    ) -> None:
        """Pre-compute temp tables for reference resolution.

        The branch parameter is accepted for API compatibility but does not
        affect resolution — all references are resolved using repo-wide
        latest symbols.
        """
        await self._ensure_resolution_tables(repository_id, progress_callback)

    async def _execute_resolution_pass(
        self,
        join_clause: str,
        repo_id: int,
        limit: int | None = None,
    ) -> int:
        """Execute one resolution pass and return count of resolved references.

        Args:
            join_clause: The JOIN clause specific to this pass.
            repo_id: Repository ID to scope the update.
            limit: Optional batch size limit for the subquery.
        """
        limit_clause = "LIMIT :batch_size" if limit else ""
        params: dict[str, Any] = {"repo_id": repo_id}
        if limit:
            params["batch_size"] = limit

        sql = text(f"""
            UPDATE "references"
            SET target_symbol_id = sub.target_id
            FROM (
                SELECT r.id AS ref_id, sub_t.min_id AS target_id
                FROM "references" r
                {join_clause}
                WHERE r.repository_id = :repo_id
                  AND r.target_symbol_id IS NULL
                {limit_clause}
            ) sub
            WHERE "references".id = sub.ref_id
        """)

        result = await self.session.execute(sql, params)
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def resolve_references_batch(
        self,
        repository_id: int,
        batch_size: int = 1000,
    ) -> int:
        """Resolve a batch of unlinked references.

        Uses pre-computed temp tables with symbols from latest file versions
        only, avoiding the O(commits x symbols) scan of all historical
        versions. The GROUP BY aggregations run once (at table creation)
        rather than per batch.

        Resolution priority (deterministic):
        1. Same file - most likely the correct local symbol
        2. Same language - cross-file but same language preferred
        3. Lowest symbol ID - deterministic tiebreaker for consistency
        """
        await self._ensure_resolution_tables(repository_id)

        total_resolved = 0

        # Pass 1: Same-file resolution (preferred)
        total_resolved += await self._execute_resolution_pass(
            self._PASS1_JOIN, repository_id, limit=batch_size
        )

        # Pass 2: Same-language cross-file resolution
        remaining = batch_size - total_resolved
        if remaining > 0:
            total_resolved += await self._execute_resolution_pass(
                self._PASS2_JOIN, repository_id, limit=remaining
            )

        # Pass 3: Any-match cross-file resolution (lowest ID fallback)
        remaining = batch_size - total_resolved
        if remaining > 0:
            total_resolved += await self._execute_resolution_pass(
                self._PASS3_JOIN, repository_id, limit=remaining
            )

        return total_resolved

    async def resolve_unlinked_references(
        self, repository_id: int, branch: str | None = None
    ) -> int:
        """Resolve references to their target symbols.

        Uses the same 3-pass priority as resolve_references_batch
        (same-file > same-language > lowest-id) but without batching.
        Only symbols from the latest version of each file path are targets.

        The branch parameter is accepted for API compatibility but does not
        affect resolution.
        """
        await self._ensure_resolution_tables(repository_id)

        total_resolved = 0
        total_resolved += await self._execute_resolution_pass(
            self._PASS1_JOIN, repository_id
        )
        total_resolved += await self._execute_resolution_pass(
            self._PASS2_JOIN, repository_id
        )
        total_resolved += await self._execute_resolution_pass(
            self._PASS3_JOIN, repository_id
        )

        await self.session.flush()
        return total_resolved
