"""PostgreSQL index status repository adapter."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import IndexStatusRepositoryPort
from ....domain.entities import IndexStatus
from ..mappers import IndexStatusMapper
from ..models.index_status import IndexStatusModel
from .base_repository import BaseSQLAlchemyRepository


class PostgresIndexStatusRepository(
    BaseSQLAlchemyRepository[IndexStatus, IndexStatusModel], IndexStatusRepositoryPort
):
    """PostgreSQL implementation of IndexStatusRepositoryPort."""

    _model_class = IndexStatusModel

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        super().__init__(session)
        self.mapper = IndexStatusMapper()

    async def save(self, status: IndexStatus) -> IndexStatus:
        """Save or update an index status.

        Uses upsert logic: if an entry already exists for this repository+branch,
        update it instead of creating a duplicate.
        """
        # Check if an entry already exists for this repo+branch
        if status.id is None:
            existing = await self.find_by_repository_and_branch(
                status.repository_id, status.branch
            )
            if existing and existing.id is not None:
                # Update the existing entry instead of creating a new one
                # Preserve original created_at timestamp
                status = IndexStatus(
                    id=existing.id,
                    repository_id=status.repository_id,
                    branch=status.branch,
                    last_indexed_commit=status.last_indexed_commit,
                    oldest_indexed_commit=status.oldest_indexed_commit,
                    last_indexed_at=status.last_indexed_at,
                    indexing_started_at=status.indexing_started_at,
                    indexing_status=status.indexing_status,
                    total_commits_indexed=status.total_commits_indexed,
                    total_files_indexed=status.total_files_indexed,
                    total_symbols_indexed=status.total_symbols_indexed,
                    total_references_indexed=status.total_references_indexed,
                    error_message=status.error_message,
                    error_count=status.error_count,
                    indexer_version=status.indexer_version,
                    metadata=status.metadata,
                    created_at=existing.created_at,
                    updated_at=existing.updated_at,
                )

        return await super().save(status)

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
