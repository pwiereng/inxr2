"""PostgreSQL adapter for Repository entity.

Implements RepositoryPort interface using SQLAlchemy and PostgreSQL.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import RepositoryPort
from ....domain.entities import Repository
from ..mappers import RepositoryMapper
from ..models import RepositoryModel


class PostgresRepositoryAdapter(RepositoryPort):
    """PostgreSQL implementation of RepositoryPort."""

    def __init__(self, session: AsyncSession):
        """
        Initialize adapter with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.mapper = RepositoryMapper()

    async def save(self, repository: Repository) -> Repository:
        """Save or update a repository."""
        model = self.mapper.to_model(repository)

        if repository.id is None:
            # New repository - add to session
            self.session.add(model)
        else:
            # Existing repository - merge
            model = await self.session.merge(model)

        await self.session.flush()
        await self.session.refresh(model)

        return self.mapper.to_domain(model)

    async def find_by_id(self, repository_id: int) -> Repository | None:
        """Find repository by ID."""
        result = await self.session.execute(
            select(RepositoryModel).where(RepositoryModel.id == repository_id)
        )
        model = result.scalar_one_or_none()

        return self.mapper.to_domain(model) if model else None

    async def find_by_name(self, name: str) -> Repository | None:
        """Find repository by unique name."""
        result = await self.session.execute(
            select(RepositoryModel).where(RepositoryModel.name == name)
        )
        model = result.scalar_one_or_none()

        return self.mapper.to_domain(model) if model else None

    async def list_all(self) -> list[Repository]:
        """List all repositories."""
        result = await self.session.execute(select(RepositoryModel))
        models = result.scalars().all()

        return [self.mapper.to_domain(model) for model in models]

    async def delete(self, repository_id: int) -> bool:
        """Delete repository and all related data (CASCADE)."""
        model = await self.session.get(RepositoryModel, repository_id)
        if model is None:
            return False

        await self.session.delete(model)
        await self.session.flush()
        return True
