"""PostgreSQL index status repository adapter."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import IndexStatusRepositoryPort
from ....domain.entities import IndexStatus
from ..mappers import IndexStatusMapper
from ..models.index_status import IndexStatusModel


class PostgresIndexStatusRepository(IndexStatusRepositoryPort):
    """PostgreSQL implementation of IndexStatusRepositoryPort."""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.mapper = IndexStatusMapper()

    async def save(self, status: IndexStatus) -> IndexStatus:
        """Save or update an index status."""
        model = self.mapper.to_model(status)

        if status.id is None:
            self.session.add(model)
        else:
            model = await self.session.merge(model)

        await self.session.flush()
        await self.session.refresh(model)

        return self.mapper.to_domain(model)

    async def find_by_repository_and_branch(
        self, repository_id: int, branch: str
    ) -> IndexStatus | None:
        """Find index status for a repository/branch combination."""
        result = await self.session.execute(
            select(IndexStatusModel).where(
                IndexStatusModel.repository_id == repository_id,
                IndexStatusModel.branch == branch,
            )
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def list_by_repository(self, repository_id: int) -> list[IndexStatus]:
        """List all index statuses for a repository (all branches)."""
        result = await self.session.execute(
            select(IndexStatusModel)
            .where(IndexStatusModel.repository_id == repository_id)
            .order_by(IndexStatusModel.branch)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]
