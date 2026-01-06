"""PostgreSQL commit repository adapter."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import CommitRepositoryPort
from ....domain.entities import Commit
from ..mappers import CommitMapper
from ..models.commit import CommitModel


class PostgresCommitRepository(CommitRepositoryPort):
    """PostgreSQL implementation of CommitRepositoryPort."""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.mapper = CommitMapper()

    async def save(self, commit: Commit) -> Commit:
        """Save or update a commit."""
        model = self.mapper.to_model(commit)

        if commit.id is None:
            self.session.add(model)
        else:
            model = await self.session.merge(model)

        await self.session.flush()
        await self.session.refresh(model)

        return self.mapper.to_domain(model)

    async def find_by_id(self, commit_id: int) -> Commit | None:
        """Find commit by ID."""
        result = await self.session.execute(
            select(CommitModel).where(CommitModel.id == commit_id)
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def find_by_hash(
        self, repository_id: int, commit_hash: str
    ) -> Commit | None:
        """Find commit by repository and hash."""
        result = await self.session.execute(
            select(CommitModel).where(
                CommitModel.repository_id == repository_id,
                CommitModel.commit_hash == commit_hash,
            )
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def list_by_repository(
        self, repository_id: int, branch: str | None = None, limit: int = 100
    ) -> list[Commit]:
        """List commits for a repository."""
        query = select(CommitModel).where(CommitModel.repository_id == repository_id)

        if branch:
            query = query.where(CommitModel.branch == branch)

        query = query.order_by(CommitModel.commit_date.desc()).limit(limit)

        result = await self.session.execute(query)
        models = result.scalars().all()

        return [self.mapper.to_domain(model) for model in models]
