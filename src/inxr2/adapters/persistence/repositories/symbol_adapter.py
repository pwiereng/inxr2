"""PostgreSQL symbol repository adapter."""

from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ....application.ports.repositories import SymbolRepositoryPort
from ....domain.entities import Symbol
from ..mappers import SymbolMapper
from ..models.commit_file import CommitFileModel
from ..models.file import FileModel
from ..models.symbol import SymbolModel
from .base_repository import BaseSQLAlchemyRepository
from .query_utils import build_text_match_filter, split_extension_filter
from .shared_queries import head_file_ids_subquery, latest_file_ids_subquery


class PostgresSymbolRepository(
    BaseSQLAlchemyRepository[Symbol, SymbolModel], SymbolRepositoryPort
):
    """PostgreSQL implementation of SymbolRepositoryPort."""

    _model_class = SymbolModel
    _set_indexed_at_on_save_many = True

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.mapper = SymbolMapper()

    async def search_by_name(
        self,
        name: str,
        repository_id: int | None = None,
        kind: str | None = None,
        limit: int = 50,
        branch: str | None = None,
        language: str | None = None,
        extensions: list[str] | None = None,
        scope: str | None = None,
        mode: str | None = None,
        case_sensitive: bool = True,
        commit_id: int | None = None,
    ) -> list[Symbol]:
        """Search symbols by name (supports autocomplete).

        When commit_id is provided, filters to symbols from files at that
        specific commit (via commit_files junction).
        When repository_id is provided (without commit_id), deduplicates by
        filtering to only the latest file version per (repository_id, path).
        When scope is "latest" and repository_id is None, filters to
        symbols from files at HEAD of each repo's default branch.

        Note: ``branch`` only takes effect when ``repository_id`` is
        provided and ``commit_id`` is not, since branch-scoped dedup
        requires a repository context.
        """
        name_filter = build_text_match_filter(
            SymbolModel.name, name, mode=mode, case_sensitive=case_sensitive
        )
        query = select(SymbolModel).where(name_filter)

        if commit_id is not None:
            # Specific commit: filter via commit_files junction
            if repository_id is not None:
                query = query.where(SymbolModel.repository_id == repository_id)
            query = query.where(
                SymbolModel.file_id.in_(
                    select(CommitFileModel.file_id).where(
                        CommitFileModel.commit_id == commit_id
                    )
                )
            )
        elif repository_id is None and scope == "latest":
            # Global search: only symbols from HEAD of each repo's default branch
            head_fids = head_file_ids_subquery()
            query = query.where(SymbolModel.file_id.in_(select(head_fids.c.file_id)))
        elif repository_id is not None:
            query = query.where(SymbolModel.repository_id == repository_id)
            # Deduplicate: only symbols from latest file version per path.
            # When branch is set, dedup is scoped to that branch.
            latest_sq = latest_file_ids_subquery(repository_id, branch=branch)
            query = query.where(SymbolModel.file_id.in_(select(latest_sq.c.max_id)))

        if kind is not None:
            query = query.where(SymbolModel.kind == kind)

        if language is not None:
            query = query.where(
                SymbolModel.file_id.in_(
                    select(FileModel.id).where(FileModel.language == language)
                )
            )

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
            query = query.where(
                SymbolModel.file_id.in_(select(FileModel.id).where(ext_filter))
            )

        query = query.order_by(SymbolModel.name).limit(limit)

        result = await self.session.execute(query)
        models = result.scalars().all()

        return [self.mapper.to_domain(model) for model in models]

    async def find_by_exact_name(
        self,
        name: str,
        repository_id: int | None = None,
        commit_id: int | None = None,
    ) -> list[Symbol]:
        """Find all symbols with the exact given name.

        Args:
            name: The exact symbol name to match
            repository_id: Filter by repository (optional)
            commit_id: Filter by specific commit via commit_files (optional).
        """
        query = select(SymbolModel).where(SymbolModel.name == name)

        if repository_id is not None:
            query = query.where(SymbolModel.repository_id == repository_id)

        if commit_id is not None:
            # Filter via commit_files junction
            query = query.where(
                SymbolModel.file_id.in_(
                    select(CommitFileModel.file_id).where(
                        CommitFileModel.commit_id == commit_id
                    )
                )
            )
        elif repository_id is not None:
            # Default mode: only latest file version per path
            latest_sq = latest_file_ids_subquery(repository_id)
            query = query.where(SymbolModel.file_id.in_(select(latest_sq.c.max_id)))

        query = query.order_by(SymbolModel.qualified_name, SymbolModel.id)

        result = await self.session.execute(query)
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def find_by_qualified_name(
        self, repository_id: int, qualified_name: str
    ) -> list[Symbol]:
        """Find symbols by fully qualified name.

        Deduplicates by filtering to only latest file version per path.
        """
        latest_sq = latest_file_ids_subquery(repository_id)
        result = await self.session.execute(
            select(SymbolModel).where(
                SymbolModel.repository_id == repository_id,
                SymbolModel.qualified_name == qualified_name,
                SymbolModel.file_id.in_(select(latest_sq.c.max_id)),
            )
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def list_by_file_and_parent(
        self,
        file_id: int,
        parent_symbol_id: int | None,
    ) -> list[Symbol]:
        """List symbols in a file filtered by parent."""
        query = select(SymbolModel).where(SymbolModel.file_id == file_id)
        if parent_symbol_id is None:
            query = query.where(SymbolModel.parent_symbol_id.is_(None))
        else:
            query = query.where(SymbolModel.parent_symbol_id == parent_symbol_id)
        query = query.order_by(SymbolModel.kind, SymbolModel.name)
        result = await self.session.execute(query)
        return [self.mapper.to_domain(m) for m in result.scalars().all()]

    async def list_files_with_symbols(
        self,
        repository_id: int,
        branch: str | None = None,
        commit_id: int | None = None,
        language: str | None = None,
        kinds: list[str] | None = None,
    ) -> list[tuple[int, str, str | None, int]]:
        """List files that contain symbols, with counts."""
        query = (
            select(
                FileModel.id,
                FileModel.path,
                FileModel.language,
                func.count(SymbolModel.id).label("symbol_count"),
            )
            .join(SymbolModel, SymbolModel.file_id == FileModel.id)
            .where(FileModel.repository_id == repository_id)
            .group_by(FileModel.id, FileModel.path, FileModel.language)
        )

        if commit_id is not None:
            query = query.where(
                FileModel.id.in_(
                    select(CommitFileModel.file_id).where(
                        CommitFileModel.commit_id == commit_id
                    )
                )
            )
        else:
            latest_sq = latest_file_ids_subquery(repository_id, branch=branch)
            query = query.where(FileModel.id.in_(select(latest_sq.c.max_id)))

        if language is not None:
            query = query.where(FileModel.language == language)

        if kinds:
            # Only include files that have at least one "effectively top-level"
            # symbol of the requested kind(s). A symbol is effectively top-level
            # if it has no parent OR its parent is a namespace (transparent).
            sym2 = aliased(SymbolModel, flat=True)
            parent_sym = aliased(SymbolModel, flat=True)
            sym2_file = aliased(FileModel, flat=True)
            kinds_subq = (
                select(sym2.file_id)
                .join(sym2_file, sym2.file_id == sym2_file.id)
                .outerjoin(parent_sym, sym2.parent_symbol_id == parent_sym.id)
                .where(
                    sym2_file.repository_id == repository_id,
                    or_(
                        sym2.parent_symbol_id.is_(None),
                        parent_sym.kind == "namespace",
                    ),
                    sym2.kind.in_(kinds),
                )
                .distinct()
            )
            query = query.where(FileModel.id.in_(kinds_subq))

        query = query.order_by(FileModel.path)
        result = await self.session.execute(query)
        return [(row[0], row[1], row[2], row[3]) for row in result.all()]

    async def list_distinct_top_level_kinds(
        self,
        repository_id: int,
        branch: str | None = None,
        commit_id: int | None = None,
        language: str | None = None,
    ) -> list[str]:
        """List distinct symbol kinds for effectively top-level symbols.

        A symbol is effectively top-level if it has no parent or its
        parent is a namespace (namespaces are transparent containers).
        Namespace itself is excluded from the returned kinds.
        """
        parent_sym = aliased(SymbolModel, flat=True)
        query = (
            select(SymbolModel.kind)
            .join(FileModel, SymbolModel.file_id == FileModel.id)
            .outerjoin(parent_sym, SymbolModel.parent_symbol_id == parent_sym.id)
            .where(
                FileModel.repository_id == repository_id,
                or_(
                    SymbolModel.parent_symbol_id.is_(None),
                    parent_sym.kind == "namespace",
                ),
                SymbolModel.kind != "namespace",
            )
            .distinct()
        )

        if commit_id is not None:
            query = query.where(
                FileModel.id.in_(
                    select(CommitFileModel.file_id).where(
                        CommitFileModel.commit_id == commit_id
                    )
                )
            )
        else:
            latest_sq = latest_file_ids_subquery(repository_id, branch=branch)
            query = query.where(FileModel.id.in_(select(latest_sq.c.max_id)))

        if language is not None:
            query = query.where(FileModel.language == language)

        query = query.order_by(SymbolModel.kind)
        result = await self.session.execute(query)
        return [row[0] for row in result.all()]

    async def update_parent_symbol_ids(self, updates: dict[int, int]) -> int:
        """Bulk update parent_symbol_id for multiple symbols."""
        if not updates:
            return 0
        # Use a CASE expression for efficient single-query bulk update
        stmt = (
            update(SymbolModel)
            .where(SymbolModel.id.in_(updates.keys()))
            .values(
                parent_symbol_id=case(
                    *[(SymbolModel.id == sid, pid) for sid, pid in updates.items()],
                )
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def list_by_file(self, file_id: int) -> list[Symbol]:
        """List all symbols in a file."""
        result = await self.session.execute(
            select(SymbolModel)
            .where(SymbolModel.file_id == file_id)
            .order_by(SymbolModel.start_line, SymbolModel.start_column)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def delete_by_file(self, file_id: int) -> int:
        """Delete all symbols for a file (for re-indexing). Returns count deleted."""
        result = await self.session.execute(
            delete(SymbolModel).where(SymbolModel.file_id == file_id)
        )
        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]
