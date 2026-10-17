"""PostgreSQL reference repository adapter."""

from collections.abc import Callable
from typing import Any

from sqlalchemy import Select, and_, delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import (
    ReferenceRepositoryPort,
    UnreferencedSymbolsPage,
)
from ....domain.constants import KIND_ALIASES, QueryDefaults
from ....domain.entities import Reference
from ..mappers import ReferenceMapper, SymbolMapper
from ..models.commit_file import CommitFileModel
from ..models.file import FileModel
from ..models.reference import ReferenceModel
from ..models.symbol import SymbolModel
from .base_repository import BaseSQLAlchemyRepository
from .query_utils import build_text_match_filter, split_extension_filter
from .shared_queries import (
    COMMIT_FILE_IDS_SQL,
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
        # (repository_id, branch, head_commit) the resolution temp tables
        # were built for
        self._resolution_tables_for: tuple[int, str | None, str | None] | None = None

    def _references_to_symbol_query(
        self,
        symbol_id: int,
        commit_id: int | None,
        branch: str | None,
        repository_id: int | None,
    ) -> Select[tuple[ReferenceModel]]:
        """References TO a symbol, in scope, unordered and unlimited.

        With commit_id, the scope is the files at that commit (via
        commit_files). Without it, the scope is the files at the head of
        ``branch`` (the default branch when None); ``repository_id`` scopes
        that head lookup to the correct repository.
        """
        if commit_id is not None:
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
            if repository_id is not None:
                query = query.where(ReferenceModel.repository_id == repository_id)
            return query

        latest_sq = latest_file_ids_subquery(repository_id, branch=branch)
        return select(ReferenceModel).where(
            ReferenceModel.target_symbol_id == symbol_id,
            ReferenceModel.source_file_id.in_(select(latest_sq.c.max_id)),
        )

    def _references_by_text_query(
        self,
        text: str,
        repository_id: int,
        commit_id: int | None,
        branch: str | None,
    ) -> Select[tuple[ReferenceModel]]:
        """References matching text, in scope, unordered and unlimited.

        With commit_id, the scope is the files at that commit (via
        commit_files). Without it, the scope is the files at the head of
        ``branch`` (the default branch when None).
        """
        if commit_id is not None:
            return (
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

        latest_sq = latest_file_ids_subquery(repository_id, branch=branch)
        return select(ReferenceModel).where(
            ReferenceModel.reference_text == text,
            ReferenceModel.repository_id == repository_id,
            ReferenceModel.source_file_id.in_(select(latest_sq.c.max_id)),
        )

    async def _count(self, query: Select[tuple[ReferenceModel]]) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        return int(result.scalar_one())

    async def find_references_to_symbol(
        self,
        symbol_id: int,
        limit: int = QueryDefaults.REFERENCE_LIMIT,
        commit_id: int | None = None,
        branch: str | None = None,
        repository_id: int | None = None,
    ) -> list[Reference]:
        """Find all references TO a symbol (find usages).

        With content-addressable file versions, references belong to file
        versions. When commit_id is provided, we filter via commit_files
        to show only references from files at that commit.

        Note: without commit_id, only references from files at the head of
        ``branch`` (the default branch when None) are returned.
        ``repository_id`` ensures the head lookup is scoped to the
        correct repository.
        """
        query = self._references_to_symbol_query(
            symbol_id, commit_id, branch, repository_id
        )
        result = await self.session.execute(
            query.order_by(ReferenceModel.source_line).limit(limit)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def count_references_to_symbol(
        self,
        symbol_id: int,
        commit_id: int | None = None,
        branch: str | None = None,
        repository_id: int | None = None,
    ) -> int:
        """Count references TO a symbol in find_references_to_symbol's scope."""
        return await self._count(
            self._references_to_symbol_query(
                symbol_id, commit_id, branch, repository_id
            )
        )

    async def find_references_by_text(
        self,
        text: str,
        repository_id: int,
        limit: int = QueryDefaults.REFERENCE_LIMIT,
        commit_id: int | None = None,
        branch: str | None = None,
    ) -> list[Reference]:
        """Find all references matching the given text.

        With content-addressable file versions, each file version has unique
        references. When commit_id is provided, filters via commit_files.

        Note: without commit_id, only references from files at the head of
        ``branch`` (the default branch when None) are returned.
        """
        query = self._references_by_text_query(text, repository_id, commit_id, branch)
        result = await self.session.execute(
            query.order_by(
                ReferenceModel.source_file_id, ReferenceModel.source_line
            ).limit(limit)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def count_references_by_text(
        self,
        text: str,
        repository_id: int,
        commit_id: int | None = None,
        branch: str | None = None,
    ) -> int:
        """Count references matching text in find_references_by_text's scope."""
        return await self._count(
            self._references_by_text_query(text, repository_id, commit_id, branch)
        )

    async def find_unreferenced_symbols(
        self,
        repository_id: int,
        kind: str | None = None,
        branch: str | None = None,
        commit_id: int | None = None,
        limit: int = QueryDefaults.SYMBOL_SEARCH_LIMIT,
        offset: int = 0,
    ) -> UnreferencedSymbolsPage:
        """Find symbols whose name no reference in the same scope uses.

        Set-based, with no per-symbol lookups: one statement for the coverage
        counts and one for the page.
        """
        if commit_id is not None:
            scope_files = (
                select(CommitFileModel.file_id.label("file_id"))
                .where(CommitFileModel.commit_id == commit_id)
                .cte("dead_code_scope_files")
            )
        else:
            latest_sq = latest_file_ids_subquery(repository_id, branch=branch)
            scope_files = select(latest_sq.c.max_id.label("file_id")).cte(
                "dead_code_scope_files"
            )
        scope_file_ids = select(scope_files.c.file_id)

        in_scope = [
            SymbolModel.repository_id == repository_id,
            SymbolModel.file_id.in_(scope_file_ids),
        ]
        if kind is not None:
            in_scope.append(SymbolModel.kind.in_(KIND_ALIASES.get(kind, [kind])))

        # Names referenced in scope, computed once and probed through NOT IN,
        # which Postgres runs as a hashed subplan. A correlated NOT EXISTS is
        # planned as a nested loop (the JSON entry-point filter defeats row
        # estimates) and is 10-100x slower on large repositories.
        # reference_text is NOT NULL, so NOT IN has no NULL pitfall.
        referenced_names = (
            select(ReferenceModel.reference_text.label("name"))
            .where(
                ReferenceModel.repository_id == repository_id,
                ReferenceModel.source_file_id.in_(scope_file_ids),
            )
            .distinct()
            .cte("dead_code_referenced_names")
        )
        unreferenced = and_(
            *in_scope, SymbolModel.name.not_in(select(referenced_names.c.name))
        )
        is_entry_point = (
            SymbolModel.extra_metadata["entry_point"].as_string().is_not(None)
        )

        # One representative per name: its first location by path, then line
        dead = (
            select(SymbolModel.id)
            .join(FileModel, FileModel.id == SymbolModel.file_id)
            .where(unreferenced, ~is_entry_point)
            .distinct(SymbolModel.name)
            .order_by(
                SymbolModel.name,
                FileModel.path,
                SymbolModel.start_line,
                SymbolModel.id,
            )
            .subquery()
        )

        counts = (
            await self.session.execute(
                select(
                    select(func.count())
                    .select_from(SymbolModel)
                    .where(*in_scope)
                    .scalar_subquery(),
                    select(func.count())
                    .select_from(SymbolModel)
                    .where(unreferenced, is_entry_point)
                    .scalar_subquery(),
                    select(func.count()).select_from(dead).scalar_subquery(),
                )
            )
        ).one()
        scanned, entry_points, total = counts

        result = await self.session.execute(
            select(SymbolModel)
            .join(FileModel, FileModel.id == SymbolModel.file_id)
            .where(SymbolModel.id.in_(select(dead.c.id)))
            .order_by(
                FileModel.path,
                SymbolModel.start_line,
                SymbolModel.name,
                SymbolModel.id,
            )
            .limit(limit)
            .offset(offset)
        )
        symbol_mapper = SymbolMapper()
        return UnreferencedSymbolsPage(
            symbols=[symbol_mapper.to_domain(m) for m in result.scalars().all()],
            total=total,
            scanned=scanned,
            entry_points=entry_points,
        )

    async def search_by_text(
        self,
        query: str,
        repository_id: int | None = None,
        branch: str | None = None,
        commit_id: int | None = None,
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
            if commit_id is not None:
                # Commit filter: scope to files present at this specific commit
                base_query = base_query.where(
                    ReferenceModel.source_file_id.in_(
                        select(CommitFileModel.file_id).where(
                            CommitFileModel.commit_id == commit_id
                        )
                    )
                )
            else:
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
            real_exts, has_none = split_extension_filter(extensions)
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
                ReferenceModel.source_file_id.in_(
                    select(FileModel.id).where(ext_filter)
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
        branch: str | None = None,
        head_commit: str | None = None,
    ) -> None:
        """Create temp tables for symbol resolution, restricted to head files.

        Pre-computes name-to-target-ID mappings for the three resolution passes:
        1. Same-file: (name, file_id) -> min symbol ID
        2. Same-language: (name, language) -> min symbol ID
        3. Any-match: (name) -> min symbol ID

        Tables are created once and reused across batch calls within the same
        session. Only symbols from the files of ``head_commit`` — or, when it
        is None, of the head of ``branch`` (the repository's default branch
        when None) — are included, so references never resolve to symbols in
        files deleted before the head (#547), and the O(commits x symbols)
        scan of historical file versions is avoided.
        """
        scope = (repository_id, branch, head_commit)
        if self._resolution_tables_for == scope:
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

        # Step 0: Compute the target file IDs once
        _report("Finding files at branch head...")
        if head_commit is not None:
            pool_sql, pool_params = COMMIT_FILE_IDS_SQL, {
                "repo_id": repository_id,
                "head_commit": head_commit,
            }
        else:
            pool_sql, pool_params = LATEST_FILE_IDS_SQL, {
                "repo_id": repository_id,
                "branch": branch,
            }
        await self.session.execute(
            text(f"""
                CREATE TEMP TABLE _resolve_latest_files AS
                {pool_sql}
            """),
            pool_params,
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

        self._resolution_tables_for = scope

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
        self._resolution_tables_for = None

    async def prepare_resolution(
        self,
        repository_id: int,
        progress_callback: Callable[[str], None] | None = None,
        branch: str | None = None,
        head_commit: str | None = None,
    ) -> None:
        """Pre-compute temp tables for reference resolution.

        Resolution targets are the symbols in the files of ``head_commit``,
        or, when it is None, at the head of ``branch`` (the repository's
        default branch when None). Subsequent resolve_references_batch calls
        reuse these tables.
        """
        await self._ensure_resolution_tables(
            repository_id, progress_callback, branch, head_commit
        )

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
        batch_size: int = 5000,
    ) -> int:
        """Resolve a batch of unlinked references.

        Uses pre-computed temp tables whose target symbols come from the
        scope prepared by prepare_resolution: the files of its
        ``head_commit`` (what indexing always passes), else its branch's
        head. This avoids the O(commits x symbols) scan of all historical
        versions. The GROUP BY aggregations run once (at table creation)
        rather than per batch.

        Resolution priority (deterministic):
        1. Same file - most likely the correct local symbol
        2. Same language - cross-file but same language preferred
        3. Lowest symbol ID - deterministic tiebreaker for consistency

        If prepare_resolution was not called for this repository, builds the
        tables for the default branch's head.
        """
        prepared = self._resolution_tables_for
        if prepared is None or prepared[0] != repository_id:
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
        self,
        repository_id: int,
        branch: str | None = None,
        head_commit: str | None = None,
    ) -> int:
        """Resolve references to their target symbols.

        Uses the same 3-pass priority as resolve_references_batch
        (same-file > same-language > lowest-id) but without batching.
        Only symbols in the files of ``head_commit``, or at the head of
        ``branch`` (the repository's default branch when None), are targets.
        """
        await self._ensure_resolution_tables(
            repository_id, branch=branch, head_commit=head_commit
        )

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
