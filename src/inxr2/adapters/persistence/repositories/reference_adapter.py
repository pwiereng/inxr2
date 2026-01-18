"""PostgreSQL reference repository adapter."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import ReferenceRepositoryPort
from ....domain.entities import Reference
from ..mappers import ReferenceMapper
from ..models.reference import ReferenceModel


class PostgresReferenceRepository(ReferenceRepositoryPort):
    """PostgreSQL implementation of ReferenceRepositoryPort."""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.mapper = ReferenceMapper()

    async def save(self, reference: Reference) -> Reference:
        """Save or update a reference."""
        model = self.mapper.to_model(reference)

        if reference.id is None:
            self.session.add(model)
        else:
            model = await self.session.merge(model)

        await self.session.flush()
        await self.session.refresh(model)

        return self.mapper.to_domain(model)

    async def save_many(self, references: list[Reference]) -> list[Reference]:
        """Bulk save references for performance."""
        if not references:
            return []

        models = [self.mapper.to_model(ref) for ref in references]
        self.session.add_all(models)
        await self.session.flush()

        for model in models:
            await self.session.refresh(model)

        return [self.mapper.to_domain(model) for model in models]

    async def find_by_id(self, reference_id: int) -> Reference | None:
        """Find reference by ID."""
        result = await self.session.execute(
            select(ReferenceModel).where(ReferenceModel.id == reference_id)
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def find_references_to_symbol(
        self, symbol_id: int, limit: int = 100
    ) -> list[Reference]:
        """Find all references TO a symbol (find usages)."""
        result = await self.session.execute(
            select(ReferenceModel)
            .where(ReferenceModel.target_symbol_id == symbol_id)
            .order_by(ReferenceModel.source_line)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def find_references_by_text(
        self, text: str, repository_id: int, limit: int = 100
    ) -> list[Reference]:
        """Find all references matching the given text.

        Useful for finding all calls to a symbol name when multiple
        symbols share the same name (e.g., save() methods in different classes).
        """
        result = await self.session.execute(
            select(ReferenceModel)
            .where(
                ReferenceModel.reference_text == text,
                ReferenceModel.repository_id == repository_id,
            )
            .order_by(ReferenceModel.source_file_id, ReferenceModel.source_line)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

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

    async def count_by_repository(self, repository_id: int) -> int:
        """Count references for a repository."""
        result = await self.session.execute(
            select(func.count(ReferenceModel.id)).where(
                ReferenceModel.repository_id == repository_id
            )
        )
        return result.scalar() or 0
