"""PostgreSQL file version repository adapter."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import FileVersionPort
from ....domain.entities import File
from ..mappers import FileMapper
from ..models.branch_commit import BranchCommitModel
from ..models.commit import CommitModel
from ..models.commit_file import CommitFileModel
from ..models.file import FileModel


class PostgresFileVersionRepository(FileVersionPort):
    """PostgreSQL implementation of FileVersionPort."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.mapper = FileMapper()

    async def list_by_commit(self, commit_id: int) -> list[File]:
        """List all files at a specific commit via commit_files."""
        result = await self.session.execute(
            select(FileModel)
            .join(CommitFileModel, CommitFileModel.file_id == FileModel.id)
            .where(CommitFileModel.commit_id == commit_id)
            .order_by(FileModel.path)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def list_at_or_before_commit(
        self, repository_id: int, commit_id: int
    ) -> list[File]:
        """List all files at or before a commit.

        With full snapshot indexing, every commit has its complete file tree
        in commit_files, so this is equivalent to list_by_commit.
        """
        # Try commit_files first (full snapshot indexing)
        files = await self.list_by_commit(commit_id)
        if files:
            return files

        # Fallback for commits without commit_files entries (shouldn't happen
        # after re-indexing, but handle gracefully)
        return []

    async def list_versions_by_path(
        self, repository_id: int, path: str, branch: str | None = None
    ) -> list[File]:
        """List all versions of a file across commits.

        Returns distinct file versions (unique content_hash), ordered by
        the newest commit that references each version.
        """
        # Get all file versions for this path
        query = select(FileModel).where(
            FileModel.repository_id == repository_id,
            FileModel.path == path,
        )

        if branch:
            # Filter to versions that appear in commits on this branch
            query = (
                query.join(CommitFileModel, CommitFileModel.file_id == FileModel.id)
                .join(CommitModel, CommitModel.id == CommitFileModel.commit_id)
                .join(
                    BranchCommitModel,
                    BranchCommitModel.commit_id == CommitModel.id,
                )
                .where(
                    BranchCommitModel.branch == branch,
                    BranchCommitModel.repository_id == repository_id,
                )
            )
            # Order by commit date (correct for HEAD-first indexing)
            query = query.order_by(
                CommitModel.commit_date.desc(), CommitModel.id.desc()
            )
        else:
            # Order by newest indexed first (fallback when no commit info)
            query = query.order_by(FileModel.id.desc())

        result = await self.session.execute(query)
        models = result.scalars().all()

        # Deduplicate by content_hash - keep first (newest)
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
        """Find file by repository, path, and commit hash via commit_files."""
        # Support short (prefix) commit hashes
        if len(commit_hash) < 40:
            hash_filter = CommitModel.commit_hash.startswith(
                commit_hash, autoescape=True
            )
        else:
            hash_filter = CommitModel.commit_hash == commit_hash

        # Find the commit
        target_commit_result = await self.session.execute(
            select(CommitModel)
            .where(
                CommitModel.repository_id == repository_id,
                hash_filter,
            )
            .limit(2)
        )
        target_commit_matches = target_commit_result.scalars().all()
        target_commit = (
            target_commit_matches[0] if len(target_commit_matches) == 1 else None
        )
        if target_commit is None:
            return None

        # Inline find_by_path query (avoids cross-adapter coupling)
        result = await self.session.execute(
            select(FileModel)
            .join(CommitFileModel, CommitFileModel.file_id == FileModel.id)
            .where(
                FileModel.repository_id == repository_id,
                CommitFileModel.commit_id == target_commit.id,
                FileModel.path == path,
            )
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def list_latest_by_branch(
        self, repository_id: int, branch: str
    ) -> list[File]:
        """List files at the latest commit on a branch.

        Gets the latest commit on the branch, then returns all files
        linked to it via commit_files.
        """
        # Get latest commit on branch
        latest_commit_result = await self.session.execute(
            select(CommitModel)
            .join(BranchCommitModel, BranchCommitModel.commit_id == CommitModel.id)
            .where(
                CommitModel.repository_id == repository_id,
                BranchCommitModel.branch == branch,
                BranchCommitModel.repository_id == repository_id,
            )
            .order_by(CommitModel.commit_date.desc(), CommitModel.id.desc())
            .limit(1)
        )
        latest_commit = latest_commit_result.scalar_one_or_none()
        if latest_commit is None:
            return []

        return await self.list_by_commit(latest_commit.id)

    async def list_changed_at_commit(
        self, repository_id: int, commit_id: int
    ) -> list[File]:
        """List files that changed at a specific commit.

        Compares the commit's file set (via commit_files) with the
        previous commit's file set by comparing content_hash per path.
        """
        # Get files at this commit
        files_at_commit = await self.list_by_commit(commit_id)
        if not files_at_commit:
            return []

        # Get the commit to find the prior commit
        target_commit_result = await self.session.execute(
            select(CommitModel).where(CommitModel.id == commit_id)
        )
        target_commit = target_commit_result.scalar_one_or_none()
        if not target_commit:
            return []

        # Find the most recent prior commit (by date, then id)
        prior_commit_result = await self.session.execute(
            select(CommitModel)
            .where(
                CommitModel.repository_id == repository_id,
                CommitModel.commit_date < target_commit.commit_date,
            )
            .order_by(CommitModel.commit_date.desc(), CommitModel.id.desc())
            .limit(1)
        )
        prior_commit = prior_commit_result.scalar_one_or_none()

        if prior_commit is None:
            # No prior commit — all files are new
            return files_at_commit

        # Get files at prior commit and build path → content_hash map
        prior_files = await self.list_by_commit(prior_commit.id)
        prior_hashes = {f.path: f.content_hash for f in prior_files}

        # Filter to changed/new files
        changed = []
        for f in files_at_commit:
            prior_hash = prior_hashes.get(f.path)
            if prior_hash is None or prior_hash != f.content_hash:
                changed.append(f)

        return changed

    async def get_commit_ids_for_files(
        self, file_ids: list[int]
    ) -> dict[int, list[int]]:
        """Get commit IDs linked to file versions via commit_files."""
        if not file_ids:
            return {}

        query = (
            select(CommitFileModel.file_id, CommitFileModel.commit_id)
            .join(CommitModel, CommitModel.id == CommitFileModel.commit_id)
            .where(CommitFileModel.file_id.in_(file_ids))
            .order_by(
                CommitFileModel.file_id,
                CommitModel.commit_date.desc(),
                CommitModel.id.desc(),
            )
        )
        result = await self.session.execute(query)
        rows = result.all()

        commit_map: dict[int, list[int]] = {}
        for file_id, commit_id in rows:
            commit_map.setdefault(file_id, []).append(commit_id)
        return commit_map
