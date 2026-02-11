"""Commit repository adapter."""

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
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

    async def find_by_ids(self, commit_ids: list[int]) -> list[Commit]:
        """Find multiple commits by IDs in a single query."""
        if not commit_ids:
            return []

        result = await self.session.execute(
            select(CommitModel).where(CommitModel.id.in_(commit_ids))
        )
        models = result.scalars().all()

        return [self.mapper.to_domain(model) for model in models]

    async def find_by_hash(self, repository_id: int, commit_hash: str) -> Commit | None:
        """Find commit by repository and hash.

        Commits are unique per (repository_id, commit_hash).
        Supports short (prefix) commit hashes — when the provided hash
        is shorter than 40 characters, uses prefix matching.
        """
        if len(commit_hash) < 40:
            hash_filter = CommitModel.commit_hash.startswith(commit_hash)
        else:
            hash_filter = CommitModel.commit_hash == commit_hash

        result = await self.session.execute(
            select(CommitModel)
            .where(
                CommitModel.repository_id == repository_id,
                hash_filter,
            )
            .limit(2)
        )
        models = result.scalars().all()
        if len(models) != 1:
            return None
        return self.mapper.to_domain(models[0])

    async def link_commit_to_branch(
        self, repository_id: int, commit_id: int, branch: str
    ) -> None:
        """Link an existing commit to a branch.

        Creates an entry in the branch_commits junction table.
        Idempotent - checks for existing link before inserting.
        Handles concurrent inserts via savepoint rollback (TOCTOU race).
        """
        # Check if link already exists (dialect-agnostic idempotency)
        existing = await self.session.execute(
            select(BranchCommitModel).where(
                BranchCommitModel.repository_id == repository_id,
                BranchCommitModel.commit_id == commit_id,
                BranchCommitModel.branch == branch,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return  # Already linked

        model = BranchCommitModel(
            repository_id=repository_id,
            commit_id=commit_id,
            branch=branch,
        )
        # Use savepoint to isolate potential IntegrityError from main transaction
        try:
            async with self.session.begin_nested():
                self.session.add(model)
        except IntegrityError:
            # Could be duplicate-key (concurrent insert) or FK violation
            # Re-check if link exists - if not, it was a real error
            verify = await self.session.execute(
                select(BranchCommitModel).where(
                    BranchCommitModel.repository_id == repository_id,
                    BranchCommitModel.commit_id == commit_id,
                    BranchCommitModel.branch == branch,
                )
            )
            if verify.scalar_one_or_none() is None:
                raise  # Real failure (e.g., FK violation), not duplicate

    async def link_commit_to_branches(
        self, repository_id: int, commit_id: int, branches: list[str]
    ) -> None:
        """Link an existing commit to multiple branches.

        Bulk version of link_commit_to_branch for efficiency.
        Idempotent - only inserts links that don't already exist.
        Handles concurrent inserts via savepoint rollback (TOCTOU race).
        """
        if not branches:
            return

        # Find which branches are already linked (single query)
        existing = await self.session.execute(
            select(BranchCommitModel.branch).where(
                BranchCommitModel.repository_id == repository_id,
                BranchCommitModel.commit_id == commit_id,
                BranchCommitModel.branch.in_(branches),
            )
        )
        existing_branches = set(existing.scalars().all())

        # Only insert branches that aren't already linked
        new_branches = [b for b in branches if b not in existing_branches]

        # Insert each in a savepoint to handle concurrent races
        for branch in new_branches:
            model = BranchCommitModel(
                repository_id=repository_id,
                commit_id=commit_id,
                branch=branch,
            )
            try:
                async with self.session.begin_nested():
                    self.session.add(model)
            except IntegrityError:
                # Could be duplicate-key (concurrent insert) or FK violation
                # Re-check if link exists - if not, it was a real error
                verify = await self.session.execute(
                    select(BranchCommitModel).where(
                        BranchCommitModel.repository_id == repository_id,
                        BranchCommitModel.commit_id == commit_id,
                        BranchCommitModel.branch == branch,
                    )
                )
                if verify.scalar_one_or_none() is None:
                    raise  # Real failure (e.g., FK violation), not duplicate

    async def get_branches_for_commit(self, commit_id: int) -> list[str]:
        """Get all branches that contain a specific commit."""
        result = await self.session.execute(
            select(BranchCommitModel.branch).where(
                BranchCommitModel.commit_id == commit_id
            )
        )
        return list(result.scalars().all())

    async def get_branches_for_commits(
        self, commit_ids: list[int]
    ) -> dict[int, list[str]]:
        """Get branches for multiple commits in a single query."""
        if not commit_ids:
            return {}

        result = await self.session.execute(
            select(BranchCommitModel.commit_id, BranchCommitModel.branch).where(
                BranchCommitModel.commit_id.in_(commit_ids)
            )
        )
        rows = result.all()

        # Group branches by commit_id
        branches_by_commit: dict[int, list[str]] = {cid: [] for cid in commit_ids}
        for commit_id, branch in rows:
            if commit_id in branches_by_commit:
                branches_by_commit[commit_id].append(branch)

        return branches_by_commit

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
