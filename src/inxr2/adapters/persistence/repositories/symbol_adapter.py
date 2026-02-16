"""PostgreSQL symbol repository adapter."""

from sqlalchemy import Subquery, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import SymbolRepositoryPort
from ....domain.entities import Symbol
from ..mappers import SymbolMapper
from ..models.commit import CommitModel
from ..models.commit_file import CommitFileModel
from ..models.file import FileModel
from ..models.symbol import SymbolModel


class PostgresSymbolRepository(SymbolRepositoryPort):
    """PostgreSQL implementation of SymbolRepositoryPort."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.mapper = SymbolMapper()

    async def save(self, symbol: Symbol) -> Symbol:
        """Save or update a symbol."""
        model = self.mapper.to_model(symbol)

        if symbol.id is None:
            self.session.add(model)
        else:
            model = await self.session.merge(model)

        await self.session.flush()
        await self.session.refresh(model)

        return self.mapper.to_domain(model)

    async def save_many(self, symbols: list[Symbol]) -> list[Symbol]:
        """Bulk save symbols for performance."""
        if not symbols:
            return []

        models = [self.mapper.to_model(symbol) for symbol in symbols]
        self.session.add_all(models)
        await self.session.flush()

        for model in models:
            await self.session.refresh(model)

        return [self.mapper.to_domain(model) for model in models]

    async def find_by_id(self, symbol_id: int) -> Symbol | None:
        """Find symbol by ID."""
        result = await self.session.execute(
            select(SymbolModel).where(SymbolModel.id == symbol_id)
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    def _latest_file_ids_subquery(self, repository_id: int) -> Subquery:
        """Subquery returning the latest file ID per (repository_id, path).

        Uses commit dates via commit_files junction to determine "latest",
        which is correct even for HEAD-first indexing where newer commits
        may have lower file IDs.
        """
        inner = (
            select(
                FileModel.id.label("file_id"),
                func.row_number()
                .over(
                    partition_by=FileModel.path,
                    order_by=[
                        CommitModel.commit_date.desc(),
                        CommitModel.id.desc(),
                    ],
                )
                .label("rn"),
            )
            .join(CommitFileModel, CommitFileModel.file_id == FileModel.id)
            .join(CommitModel, CommitModel.id == CommitFileModel.commit_id)
            .where(FileModel.repository_id == repository_id)
            .subquery()
        )
        return select(inner.c.file_id.label("max_id")).where(inner.c.rn == 1).subquery()

    async def search_by_name(
        self,
        name: str,
        repository_id: int | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> list[Symbol]:
        """Search symbols by name (supports autocomplete).

        When repository_id is provided, deduplicates by filtering to
        only the latest file version per (repository_id, path).
        """
        query = select(SymbolModel).where(SymbolModel.name.ilike(f"%{name}%"))

        if repository_id is not None:
            query = query.where(SymbolModel.repository_id == repository_id)
            # Deduplicate: only symbols from latest file version per path
            latest_sq = self._latest_file_ids_subquery(repository_id)
            query = query.where(SymbolModel.file_id.in_(select(latest_sq.c.max_id)))

        if kind is not None:
            query = query.where(SymbolModel.kind == kind)

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
            latest_sq = self._latest_file_ids_subquery(repository_id)
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
        latest_sq = self._latest_file_ids_subquery(repository_id)
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

    async def count_by_repository(self, repository_id: int) -> int:
        """Count symbols for a repository."""
        result = await self.session.execute(
            select(func.count(SymbolModel.id)).where(
                SymbolModel.repository_id == repository_id
            )
        )
        return result.scalar() or 0

    async def delete_by_repository(self, repository_id: int) -> int:
        """Delete all symbols for a repository. Returns count deleted."""
        result = await self.session.execute(
            delete(SymbolModel).where(SymbolModel.repository_id == repository_id)
        )
        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]
