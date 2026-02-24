"""PostgreSQL file repository adapter."""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import FileRepositoryPort
from ....domain.entities import File
from ..mappers import FileMapper
from ..models.commit_file import CommitFileModel
from ..models.file import FileModel


class PostgresFileRepository(FileRepositoryPort):
    """PostgreSQL implementation of FileRepositoryPort."""

    def __init__(self, session: AsyncSession):
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

    async def find_or_create_version(
        self,
        repository_id: int,
        path: str,
        content_hash: str,
        size_bytes: int,
        language: str | None = None,
        extension: str | None = None,
        encoding: str = "utf-8",
        is_binary: bool = False,
        line_count: int | None = None,
    ) -> tuple[File, bool]:
        """Find existing file version or create a new one.

        Uses INSERT ... ON CONFLICT DO NOTHING with the unique constraint
        on (repository_id, path, content_hash) for atomicity.
        """
        # Try to find existing
        result = await self.session.execute(
            select(FileModel).where(
                FileModel.repository_id == repository_id,
                FileModel.path == path,
                FileModel.content_hash == content_hash,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return self.mapper.to_domain(existing), False

        # Create new — set indexed_at client-side to avoid a refresh() round-trip
        now = datetime.now(UTC).replace(tzinfo=None)
        model = FileModel(
            repository_id=repository_id,
            path=path,
            content_hash=content_hash,
            size_bytes=size_bytes,
            language=language,
            extension=extension,
            encoding=encoding,
            is_binary=is_binary,
            line_count=line_count,
            indexed_at=now,
        )
        self.session.add(model)
        await self.session.flush()
        return self.mapper.to_domain(model), True

    async def link_file_to_commit(self, file_id: int, commit_id: int) -> None:
        """Link a file version to a commit. Idempotent."""
        stmt = (
            pg_insert(CommitFileModel)
            .values(commit_id=commit_id, file_id=file_id)
            .on_conflict_do_nothing()
        )
        await self.session.execute(stmt)

    async def link_files_to_commit(self, file_ids: list[int], commit_id: int) -> None:
        """Bulk link file versions to a commit. Idempotent."""
        if not file_ids:
            return

        values = [{"commit_id": commit_id, "file_id": file_id} for file_id in file_ids]
        stmt = pg_insert(CommitFileModel).values(values).on_conflict_do_nothing()
        await self.session.execute(stmt)
        await self.session.flush()

    async def find_by_path(
        self, repository_id: int, commit_id: int, path: str
    ) -> File | None:
        """Find file by repository, commit, and path via commit_files."""
        result = await self.session.execute(
            select(FileModel)
            .join(CommitFileModel, CommitFileModel.file_id == FileModel.id)
            .where(
                FileModel.repository_id == repository_id,
                CommitFileModel.commit_id == commit_id,
                FileModel.path == path,
            )
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def list_by_repository(self, repository_id: int) -> list[File]:
        """List all files for a repository (latest version)."""
        result = await self.session.execute(
            select(FileModel)
            .where(FileModel.repository_id == repository_id)
            .order_by(FileModel.path)
        )
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def find_by_content_hash(
        self,
        content_hash: str,
        repository_id: int | None = None,
        path: str | None = None,
    ) -> list[File]:
        """Find files with matching content hash."""
        query = select(FileModel).where(FileModel.content_hash == content_hash)
        if repository_id is not None:
            query = query.where(FileModel.repository_id == repository_id)
        if path is not None:
            query = query.where(FileModel.path == path)
        result = await self.session.execute(query)
        models = result.scalars().all()
        return [self.mapper.to_domain(model) for model in models]

    async def load_file_version_index(
        self, repository_id: int
    ) -> dict[tuple[str, str], int]:
        """Load all file version keys for a repository in a single query."""
        result = await self.session.execute(
            select(FileModel.path, FileModel.content_hash, FileModel.id).where(
                FileModel.repository_id == repository_id
            )
        )
        return {(row[0], row[1]): row[2] for row in result.all()}

    async def find_by_repository_and_path(
        self, repository_id: int, path: str
    ) -> File | None:
        """Find file by repository and path (latest version).

        Returns the most recently indexed version of the file.
        """
        result = await self.session.execute(
            select(FileModel)
            .where(
                FileModel.repository_id == repository_id,
                FileModel.path == path,
            )
            .order_by(FileModel.id.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def delete_by_repository(self, repository_id: int) -> int:
        """Delete all files for a repository. Returns count deleted."""
        result = await self.session.execute(
            delete(FileModel).where(FileModel.repository_id == repository_id)
        )
        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]
