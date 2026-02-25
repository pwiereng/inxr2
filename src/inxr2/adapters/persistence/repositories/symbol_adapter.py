"""PostgreSQL symbol repository adapter."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import SymbolRepositoryPort
from ....domain.entities import Symbol
from ..mappers import SymbolMapper
from ..models.commit_file import CommitFileModel
from ..models.file import FileModel
from ..models.symbol import SymbolModel
from .base_repository import BaseSQLAlchemyRepository
from .query_utils import build_text_match_filter
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
    ) -> list[Symbol]:
        """Search symbols by name (supports autocomplete).

        When repository_id is provided, deduplicates by filtering to
        only the latest file version per (repository_id, path).
        When scope is "latest" and repository_id is None, filters to
        symbols from files at HEAD of each repo's default branch.

        Note: ``branch`` only takes effect when ``repository_id`` is
        provided, since branch-scoped dedup requires a repository context.
        """
        name_filter = build_text_match_filter(
            SymbolModel.name, name, mode=mode, case_sensitive=case_sensitive
        )
        query = select(SymbolModel).where(name_filter)

        if repository_id is None and scope == "latest":
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
            query = query.where(
                SymbolModel.file_id.in_(
                    select(FileModel.id).where(FileModel.extension.in_(extensions))
                )
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
