"""PostgreSQL symbol repository adapter."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import SymbolRepositoryPort
from ....domain.entities import Symbol
from ..mappers import SymbolMapper
from ..models.file import FileModel
from ..models.symbol import SymbolModel


class PostgresSymbolRepository(SymbolRepositoryPort):
    """PostgreSQL implementation of SymbolRepositoryPort."""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
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

    async def search_by_name(
        self,
        name: str,
        repository_id: int | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> list[Symbol]:
        """Search symbols by name (supports autocomplete).

        Only returns symbols from the latest version of each file,
        avoiding duplicates from multiple indexed commits.
        """
        # Build base query
        query = select(SymbolModel).where(SymbolModel.name.ilike(f"%{name}%"))

        if repository_id is not None:
            query = query.where(SymbolModel.repository_id == repository_id)

            # Filter to only symbols from latest file versions
            latest_files = (
                select(func.max(FileModel.id).label("latest_id"))
                .where(FileModel.repository_id == repository_id)
                .group_by(FileModel.path)
                .subquery()
            )
            query = query.where(
                SymbolModel.file_id.in_(select(latest_files.c.latest_id))
            )

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

        Useful for disambiguation when multiple symbols have the same name
        (e.g., save() methods in different classes).

        Args:
            name: The exact symbol name to match
            repository_id: Filter by repository (optional)
            commit_id: Filter by specific commit for time travel (optional).
                       If not provided, returns symbols from latest file versions.
        """
        query = select(SymbolModel).where(SymbolModel.name == name)

        if repository_id is not None:
            query = query.where(SymbolModel.repository_id == repository_id)

        if commit_id is not None:
            # Time travel mode: filter to specific commit
            query = query.where(SymbolModel.commit_id == commit_id)
        elif repository_id is not None:
            # Default mode: filter to only symbols from latest file versions
            latest_files = (
                select(func.max(FileModel.id).label("latest_id"))
                .where(FileModel.repository_id == repository_id)
                .group_by(FileModel.path)
                .subquery()
            )
            query = query.where(
                SymbolModel.file_id.in_(select(latest_files.c.latest_id))
            )

        # Order by qualified_name for consistent ordering
        query = query.order_by(SymbolModel.qualified_name, SymbolModel.id)

        result = await self.session.execute(query)
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def find_by_qualified_name(
        self, repository_id: int, qualified_name: str
    ) -> list[Symbol]:
        """Find symbols by fully qualified name.

        Only returns symbols from the latest version of each file,
        avoiding duplicates from multiple indexed commits.
        """
        # Filter to only symbols from latest file versions
        latest_files = (
            select(func.max(FileModel.id).label("latest_id"))
            .where(FileModel.repository_id == repository_id)
            .group_by(FileModel.path)
            .subquery()
        )

        result = await self.session.execute(
            select(SymbolModel).where(
                SymbolModel.repository_id == repository_id,
                SymbolModel.qualified_name == qualified_name,
                SymbolModel.file_id.in_(select(latest_files.c.latest_id)),
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
