"""PostgreSQL commit repository adapter."""

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import CommitRepositoryPort
from ....domain.entities import Commit
from ..mappers import CommitMapper
from ..models.branch_commit import BranchCommitModel
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

    async def save_many(self, commits: list[Commit]) -> list[Commit]:
        """Bulk save commits for performance."""
        saved_commits = []
        for commit in commits:
            model = self.mapper.to_model(commit)
            if commit.id is None:
                self.session.add(model)
            else:
                model = await self.session.merge(model)
            saved_commits.append(model)

        await self.session.flush()

        # Refresh all models to get generated IDs
        for model in saved_commits:
            await self.session.refresh(model)

        return [self.mapper.to_domain(model) for model in saved_commits]

    async def find_by_id(self, commit_id: int) -> Commit | None:
        """Find commit by ID."""
        result = await self.session.execute(
            select(CommitModel).where(CommitModel.id == commit_id)
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def find_by_hash(self, repository_id: int, commit_hash: str) -> Commit | None:
        """Find commit by repository and hash.

        Commits are unique per (repository_id, commit_hash).
        """
        result = await self.session.execute(
            select(CommitModel).where(
                CommitModel.repository_id == repository_id,
                CommitModel.commit_hash == commit_hash,
            )
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def link_commit_to_branch(
        self, repository_id: int, commit_id: int, branch: str
    ) -> None:
        """Link an existing commit to a branch.

        Creates an entry in the branch_commits junction table.
        Uses INSERT ... ON CONFLICT DO NOTHING for idempotency.
        """
        stmt = (
            pg_insert(BranchCommitModel)
            .values(repository_id=repository_id, commit_id=commit_id, branch=branch)
            .on_conflict_do_nothing(constraint="uq_branch_commit")
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def link_commit_to_branches(
        self, repository_id: int, commit_id: int, branches: list[str]
    ) -> None:
        """Link an existing commit to multiple branches.

        Bulk version of link_commit_to_branch for efficiency.
        """
        if not branches:
            return

        values = [
            {"repository_id": repository_id, "commit_id": commit_id, "branch": branch}
            for branch in branches
        ]
        stmt = (
            pg_insert(BranchCommitModel)
            .values(values)
            .on_conflict_do_nothing(constraint="uq_branch_commit")
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def get_branches_for_commit(self, commit_id: int) -> list[str]:
        """Get all branches that contain a specific commit."""
        result = await self.session.execute(
            select(BranchCommitModel.branch).where(
                BranchCommitModel.commit_id == commit_id
            )
        )
        return list(result.scalars().all())

    async def list_by_repository(
        self, repository_id: int, branch: str | None = None, limit: int = 100
    ) -> list[Commit]:
        """List commits for a repository, optionally filtered by branch."""
        if branch:
            # Join with branch_commits to filter by branch
            query = (
                select(CommitModel)
                .join(BranchCommitModel, BranchCommitModel.commit_id == CommitModel.id)
                .where(
                    CommitModel.repository_id == repository_id,
                    BranchCommitModel.branch == branch,
                    BranchCommitModel.repository_id == repository_id,
                )
                .order_by(CommitModel.commit_date.desc())
                .limit(limit)
            )
        else:
            # No branch filter - return all commits for repository
            query = (
                select(CommitModel)
                .where(CommitModel.repository_id == repository_id)
                .order_by(CommitModel.commit_date.desc())
                .limit(limit)
            )

        result = await self.session.execute(query)
        models = result.scalars().all()

        return [self.mapper.to_domain(model) for model in models]

    async def find_latest_by_branch(
        self, repository_id: int, branch: str
    ) -> Commit | None:
        """Find the latest indexed commit for a specific branch.

        Queries via the branch_commits junction table.
        """
        result = await self.session.execute(
            select(CommitModel)
            .join(BranchCommitModel, BranchCommitModel.commit_id == CommitModel.id)
            .where(
                CommitModel.repository_id == repository_id,
                BranchCommitModel.branch == branch,
                BranchCommitModel.repository_id == repository_id,
            )
            .order_by(CommitModel.commit_date.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def delete_by_repository(self, repository_id: int) -> int:
        """Delete all commits for a repository. Returns count deleted.

        Note: branch_commits entries are deleted via CASCADE.
        """
        result = await self.session.execute(
            delete(CommitModel).where(CommitModel.repository_id == repository_id)
        )
        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]
