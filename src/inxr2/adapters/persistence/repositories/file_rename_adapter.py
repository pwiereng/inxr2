"""PostgreSQL file rename repository adapter."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import FileRenameRepositoryPort
from ....domain.entities import FileRename
from ..mappers import FileRenameMapper
from ..models import FileRenameModel
from ..models.branch_commit import BranchCommitModel


class PostgresFileRenameRepository(FileRenameRepositoryPort):
    """PostgreSQL implementation of FileRenameRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.mapper = FileRenameMapper()

    async def save_renames(self, renames: list[FileRename]) -> list[FileRename]:
        """Bulk save file renames detected in a commit."""
        if not renames:
            return []

        models = [self.mapper.to_model(r) for r in renames]
        self.session.add_all(models)
        await self.session.flush()
        return [self.mapper.to_domain(m) for m in models]

    async def get_renames_for_commit(self, commit_id: int) -> list[FileRename]:
        """Get all file renames in a specific commit."""
        query = (
            select(FileRenameModel)
            .where(FileRenameModel.commit_id == commit_id)
            .order_by(FileRenameModel.old_path)
        )
        result = await self.session.execute(query)
        return [self.mapper.to_domain(m) for m in result.scalars().all()]

    async def get_file_history(
        self,
        repository_id: int,
        file_path: str,
        branch: str | None = None,
    ) -> list[FileRename]:
        """Get rename history for a file path."""
        query = select(FileRenameModel).where(
            FileRenameModel.repository_id == repository_id,
            (FileRenameModel.old_path == file_path)
            | (FileRenameModel.new_path == file_path),
        )

        if branch is not None:
            query = query.where(
                FileRenameModel.commit_id.in_(
                    select(BranchCommitModel.commit_id).where(
                        BranchCommitModel.branch == branch,
                        BranchCommitModel.repository_id == repository_id,
                    )
                )
            )

        query = query.order_by(FileRenameModel.id)
        result = await self.session.execute(query)
        return [self.mapper.to_domain(m) for m in result.scalars().all()]

    async def count_by_repository(self, repository_id: int) -> int:
        """Count total file renames in a repository."""
        result = await self.session.execute(
            select(func.count(FileRenameModel.id)).where(
                FileRenameModel.repository_id == repository_id
            )
        )
        return result.scalar() or 0

    async def delete_by_repository(self, repository_id: int) -> int:
        """Delete all file renames for a repository. Returns count deleted."""
        result = await self.session.execute(
            delete(FileRenameModel).where(
                FileRenameModel.repository_id == repository_id
            )
        )
        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]
