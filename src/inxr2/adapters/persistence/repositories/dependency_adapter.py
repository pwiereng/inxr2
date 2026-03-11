"""PostgreSQL dependency repository adapter."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import DependencyRepositoryPort
from ....domain.entities import Dependency
from ..mappers import DependencyMapper
from ..models import CommitFileModel, DependencyModel
from .base_repository import BaseSQLAlchemyRepository


class PostgresDependencyRepository(
    BaseSQLAlchemyRepository[Dependency, DependencyModel],
    DependencyRepositoryPort,
):
    """PostgreSQL implementation of DependencyRepositoryPort."""

    _model_class = DependencyModel
    _set_indexed_at_on_save_many = True

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.mapper = DependencyMapper()

    async def find_by_file(
        self,
        file_id: int,
        dependency_type: str | None = None,
        is_direct: bool | None = None,
    ) -> list[Dependency]:
        """Find all dependencies for a manifest file version."""
        query = select(DependencyModel).where(DependencyModel.file_id == file_id)

        if dependency_type is not None:
            query = query.where(DependencyModel.dependency_type == dependency_type)
        if is_direct is not None:
            query = query.where(DependencyModel.is_direct == is_direct)

        query = query.order_by(DependencyModel.package_name)
        result = await self.session.execute(query)
        return [self.mapper.to_domain(m) for m in result.scalars().all()]

    async def find_by_commit(
        self,
        commit_id: int,
        repository_id: int,
        language: str | None = None,
        dependency_type: str | None = None,
        is_direct: bool | None = None,
    ) -> list[Dependency]:
        """Find all dependencies at a specific commit via commit_files junction."""
        query = select(DependencyModel).where(
            DependencyModel.repository_id == repository_id,
            DependencyModel.file_id.in_(
                select(CommitFileModel.file_id).where(
                    CommitFileModel.commit_id == commit_id
                )
            ),
        )

        if language is not None:
            query = query.where(DependencyModel.language == language)
        if dependency_type is not None:
            query = query.where(DependencyModel.dependency_type == dependency_type)
        if is_direct is not None:
            query = query.where(DependencyModel.is_direct == is_direct)

        query = query.order_by(DependencyModel.file_id, DependencyModel.package_name)
        result = await self.session.execute(query)
        return [self.mapper.to_domain(m) for m in result.scalars().all()]

    async def find_by_package_name(
        self,
        package_name: str,
        repository_id: int | None = None,
        language: str | None = None,
    ) -> list[Dependency]:
        """Find all dependencies matching a package name (reverse lookup)."""
        query = select(DependencyModel).where(
            DependencyModel.package_name == package_name
        )

        if repository_id is not None:
            query = query.where(DependencyModel.repository_id == repository_id)
        if language is not None:
            query = query.where(DependencyModel.language == language)

        query = query.order_by(DependencyModel.repository_id, DependencyModel.file_id)
        result = await self.session.execute(query)
        return [self.mapper.to_domain(m) for m in result.scalars().all()]

    async def search_by_package_name(
        self,
        query: str,
        repository_id: int | None = None,
        language: str | None = None,
        dependency_type: str | None = None,
        is_direct: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Dependency], int]:
        """Search dependencies by package name with partial, case-insensitive matching."""
        escaped_query = (
            query.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        )
        base = select(DependencyModel).where(
            DependencyModel.package_name.ilike(f"%{escaped_query}%", escape="\\")
        )

        if repository_id is not None:
            base = base.where(DependencyModel.repository_id == repository_id)
        if language is not None:
            base = base.where(DependencyModel.language == language)
        if dependency_type is not None:
            base = base.where(DependencyModel.dependency_type == dependency_type)
        if is_direct is not None:
            base = base.where(DependencyModel.is_direct == is_direct)

        # Count total
        count_query = select(func.count()).select_from(base.subquery())
        total = (await self.session.execute(count_query)).scalar() or 0

        # Fetch page
        results_query = (
            base.order_by(DependencyModel.package_name, DependencyModel.repository_id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(results_query)
        deps = [self.mapper.to_domain(m) for m in result.scalars().all()]

        return deps, total

    async def delete_by_file(self, file_id: int) -> int:
        """Delete all dependencies for a file. Returns count deleted."""
        result = await self.session.execute(
            delete(DependencyModel).where(DependencyModel.file_id == file_id)
        )
        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]
