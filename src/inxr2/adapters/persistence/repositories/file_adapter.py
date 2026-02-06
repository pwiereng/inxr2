"""PostgreSQL file repository adapter."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import FileRepositoryPort
from ....domain.entities import File
from ..mappers import FileMapper
from ..models.branch_commit import BranchCommitModel
from ..models.commit import CommitModel
from ..models.file import FileModel


class PostgresFileRepository(FileRepositoryPort):
    """PostgreSQL implementation of FileRepositoryPort."""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.mapper = FileMapper()

    async def save(self, file: File) -> File:
        """Save or update a file."""
        model = self.mapper.to_model(file)

        if file.id is None:
            self.session.add(model)
        else:
            model = await self.session.merge(model)

        await self.session.flush()
        await self.session.refresh(model)

        return self.mapper.to_domain(model)

    async def save_many(self, files: list[File]) -> list[File]:
        """Bulk save files for performance."""
        models = [self.mapper.to_model(file) for file in files]
        self.session.add_all(models)
        await self.session.flush()

        for model in models:
            await self.session.refresh(model)

        return [self.mapper.to_domain(model) for model in models]

    async def find_by_id(self, file_id: int) -> File | None:
        """Find file by ID."""
        result = await self.session.execute(
            select(FileModel).where(FileModel.id == file_id)
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def find_by_ids(self, file_ids: list[int]) -> dict[int, File]:
        """Find multiple files by IDs in a single query."""
        if not file_ids:
            return {}

        result = await self.session.execute(
            select(FileModel).where(FileModel.id.in_(file_ids))
        )
        models = result.scalars().all()
        return {
            model.id: self.mapper.to_domain(model)
            for model in models
            if model.id is not None
        }

    async def find_by_path(
        self, repository_id: int, commit_id: int, path: str
    ) -> File | None:
        """Find file by repository, commit, and path."""
        result = await self.session.execute(
            select(FileModel).where(
                FileModel.repository_id == repository_id,
                FileModel.commit_id == commit_id,
                FileModel.path == path,
            )
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def list_by_commit(self, commit_id: int) -> list[File]:
        """List all files at a specific commit."""
        result = await self.session.execute(
            select(FileModel)
            .where(FileModel.commit_id == commit_id)
            .order_by(FileModel.path)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def list_at_or_before_commit(
        self, repository_id: int, commit_id: int
    ) -> list[File]:
        """List the latest version of each file at or before a specific commit.

        This returns the full file tree state as it existed at the given commit,
        including files that weren't modified at that commit but existed from
        earlier commits.
        """
        from sqlalchemy import func

        # First get the target commit's date to filter by
        target_commit_result = await self.session.execute(
            select(CommitModel).where(CommitModel.id == commit_id)
        )
        target_commit = target_commit_result.scalar_one_or_none()
        if not target_commit:
            return []

        # Subquery to get all files at or before the target commit date,
        # ranked by commit date (newest first) for each path
        file_with_date = (
            select(
                FileModel.id,
                FileModel.path,
                CommitModel.commit_date,
                func.row_number()
                .over(
                    partition_by=FileModel.path,
                    order_by=(
                        CommitModel.commit_date.desc(),
                        CommitModel.id.desc(),
                    ),
                )
                .label("rn"),
            )
            .join(CommitModel, FileModel.commit_id == CommitModel.id)
            .where(
                FileModel.repository_id == repository_id,
                CommitModel.commit_date <= target_commit.commit_date,
            )
            .subquery()
        )

        # Select only the latest version of each file (rn = 1)
        latest_file_ids = select(file_with_date.c.id).where(file_with_date.c.rn == 1)

        # Get the full file models for those IDs
        result = await self.session.execute(
            select(FileModel)
            .where(FileModel.id.in_(latest_file_ids))
            .order_by(FileModel.path)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def list_by_repository(self, repository_id: int) -> list[File]:
        """List all files for a repository (latest version)."""
        # For now, get all files for the repository
        # TODO: In the future, we might want to get only the latest commit's files
        result = await self.session.execute(
            select(FileModel)
            .where(FileModel.repository_id == repository_id)
            .order_by(FileModel.path)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def find_by_content_hash(self, content_hash: str) -> list[File]:
        """Find files with matching content hash."""
        result = await self.session.execute(
            select(FileModel).where(FileModel.content_hash == content_hash)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def find_by_repository_and_path(
        self, repository_id: int, path: str
    ) -> File | None:
        """Find file by repository and path (latest version).

        Returns the most recently indexed version of the file by ordering
        by commit_id descending (higher commit_id = more recent index).
        """
        result = await self.session.execute(
            select(FileModel)
            .where(
                FileModel.repository_id == repository_id,
                FileModel.path == path,
            )
            .order_by(FileModel.commit_id.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def list_versions_by_path(
        self, repository_id: int, path: str, branch: str | None = None
    ) -> list[File]:
        """List all versions of a file across commits (for time travel).

        Returns files with this path from different commits, ordered by
        commit date descending (newest first). Deduplicates by content_hash
        to only show versions where the file actually changed.

        Args:
            repository_id: The repository ID
            path: The file path
            branch: Optional branch name to filter versions by
        """
        query = (
            select(FileModel)
            .join(CommitModel, FileModel.commit_id == CommitModel.id)
            .where(
                FileModel.repository_id == repository_id,
                FileModel.path == path,
            )
        )

        if branch:
            # Join with branch_commits to filter by branch
            query = query.join(
                BranchCommitModel, BranchCommitModel.commit_id == CommitModel.id
            ).where(
                BranchCommitModel.branch == branch,
                BranchCommitModel.repository_id == repository_id,
            )

        query = query.order_by(CommitModel.commit_date.desc())

        result = await self.session.execute(query)
        models = result.scalars().all()

        # Deduplicate by content_hash - keep first occurrence (newest) of each unique content
        seen_hashes: set[str] = set()
        unique_models = []
        for model in models:
            if model.content_hash not in seen_hashes:
                seen_hashes.add(model.content_hash)
                unique_models.append(model)

        return [self.mapper.to_domain(model) for model in unique_models]

    async def find_by_repository_path_and_commit_hash(
        self, repository_id: int, path: str, commit_hash: str
    ) -> File | None:
        """Find file by repository, path, and commit hash (for time travel).

        With delta indexing, a file may not have a record at every commit.
        This method uses fallback lookup: find the most recent file version
        at or before the target commit.

        The logic is:
        1. First, try exact match (file was modified at this commit)
        2. If not found, find the most recent version where commit_date <= target

        This ensures time-travel works correctly even when files weren't
        modified at the target commit.
        """
        # First, get the target commit's date for fallback lookup
        target_commit_result = await self.session.execute(
            select(CommitModel).where(
                CommitModel.repository_id == repository_id,
                CommitModel.commit_hash == commit_hash,
            )
        )
        target_commit = target_commit_result.scalar_one_or_none()
        if target_commit is None:
            return None

        # Try exact match first (most common case - file was modified at this commit)
        exact_result = await self.session.execute(
            select(FileModel)
            .join(CommitModel, FileModel.commit_id == CommitModel.id)
            .where(
                FileModel.repository_id == repository_id,
                FileModel.path == path,
                CommitModel.commit_hash == commit_hash,
            )
            .limit(1)
        )
        exact_model = exact_result.scalar_one_or_none()
        if exact_model is not None:
            return self.mapper.to_domain(exact_model)

        # Fallback: find the most recent version at or before the target commit
        # This handles delta-indexed files that weren't modified at target commit
        fallback_result = await self.session.execute(
            select(FileModel)
            .join(CommitModel, FileModel.commit_id == CommitModel.id)
            .where(
                FileModel.repository_id == repository_id,
                FileModel.path == path,
                CommitModel.commit_date <= target_commit.commit_date,
            )
            .order_by(CommitModel.commit_date.desc(), CommitModel.id.desc())
            .limit(1)
        )
        fallback_model = fallback_result.scalar_one_or_none()
        return self.mapper.to_domain(fallback_model) if fallback_model else None

    async def list_latest_by_branch(
        self, repository_id: int, branch: str
    ) -> list[File]:
        """List the latest version of each file on a branch.

        For delta-indexed repositories, this aggregates files across all commits
        on the branch, returning only the most recent version of each unique path.

        Uses a window function to rank files by commit date and selects only
        the most recent version of each path.
        """
        from sqlalchemy import func

        # Subquery to get all files on the branch with their commit dates
        file_with_date = (
            select(
                FileModel.id,
                FileModel.path,
                CommitModel.commit_date,
                func.row_number()
                .over(
                    partition_by=FileModel.path,
                    order_by=(
                        CommitModel.commit_date.desc(),
                        CommitModel.id.desc(),
                    ),
                )
                .label("rn"),
            )
            .join(CommitModel, FileModel.commit_id == CommitModel.id)
            .join(BranchCommitModel, BranchCommitModel.commit_id == CommitModel.id)
            .where(
                FileModel.repository_id == repository_id,
                BranchCommitModel.branch == branch,
                BranchCommitModel.repository_id == repository_id,
            )
            .subquery()
        )

        # Select only the latest version of each file (rn = 1)
        latest_file_ids = select(file_with_date.c.id).where(file_with_date.c.rn == 1)

        # Get the full file models for those IDs
        result = await self.session.execute(
            select(FileModel)
            .where(FileModel.id.in_(latest_file_ids))
            .order_by(FileModel.path)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def delete_by_repository(self, repository_id: int) -> int:
        """Delete all files for a repository. Returns count deleted."""
        result = await self.session.execute(
            delete(FileModel).where(FileModel.repository_id == repository_id)
        )
        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def find_one_by_content_hash_in_repo(
        self, repository_id: int, content_hash: str
    ) -> File | None:
        """Find first file with matching content hash within a repository.

        Used for content-hash based symbol/reference reuse optimization.
        """
        result = await self.session.execute(
            select(FileModel)
            .where(
                FileModel.repository_id == repository_id,
                FileModel.content_hash == content_hash,
            )
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def get_content_hash_to_file_id_map(
        self, repository_id: int
    ) -> dict[str, int]:
        """Load all content hashes for a repository into memory.

        Returns a mapping of content_hash -> file_id for fast in-memory lookup.
        Uses the minimum file_id for each unique content_hash (first indexed).
        """
        result = await self.session.execute(
            select(FileModel.content_hash, func.min(FileModel.id).label("file_id"))
            .where(
                FileModel.repository_id == repository_id,
                FileModel.content_hash.isnot(None),
            )
            .group_by(FileModel.content_hash)
        )
        return {row.content_hash: row.file_id for row in result.all()}
