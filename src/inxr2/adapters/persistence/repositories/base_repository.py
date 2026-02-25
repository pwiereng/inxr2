"""Base SQLAlchemy repository with shared CRUD boilerplate."""

from datetime import UTC, datetime
from typing import Generic, Protocol, TypeVar

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

TEntity = TypeVar("TEntity")
TModel = TypeVar("TModel")


class MapperProtocol(Protocol[TEntity, TModel]):
    """Protocol for bidirectional entity/model mappers."""

    def to_domain(self, model: TModel) -> TEntity: ...

    def to_model(self, entity: TEntity) -> TModel: ...


class BaseSQLAlchemyRepository(Generic[TEntity, TModel]):
    """Generic base class for SQLAlchemy repository adapters.

    Provides shared ``save()``, ``find_by_id()``, ``save_many()``,
    ``delete_by_repository()``, and ``count_by_repository()``
    implementations that are identical across most repository adapters.
    Subclasses must set ``_model_class`` and initialise ``self.mapper``
    in their ``__init__``.
    """

    _model_class: type[TModel]
    _set_indexed_at_on_save_many: bool = False
    mapper: MapperProtocol[TEntity, TModel]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, entity: TEntity) -> TEntity:
        """Save or update an entity."""
        model = self.mapper.to_model(entity)

        if entity.id is None:  # type: ignore[attr-defined]
            self.session.add(model)
        else:
            model = await self.session.merge(model)

        await self.session.flush()
        await self.session.refresh(model)

        return self.mapper.to_domain(model)

    async def find_by_id(self, entity_id: int) -> TEntity | None:
        """Find an entity by ID."""
        result = await self.session.execute(
            select(self._model_class).where(
                self._model_class.id == entity_id  # type: ignore[attr-defined]
            )
        )
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def save_many(self, entities: list[TEntity]) -> list[TEntity]:
        """Bulk save entities.

        Subclasses that need ``indexed_at`` stamped on every model should set
        the class attribute ``_set_indexed_at_on_save_many = True``.
        """
        if not entities:
            return []

        models = [self.mapper.to_model(entity) for entity in entities]
        if self._set_indexed_at_on_save_many:
            now = datetime.now(UTC).replace(tzinfo=None)
            for model in models:
                model.indexed_at = now  # type: ignore[attr-defined]
        self.session.add_all(models)
        await self.session.flush()
        return [self.mapper.to_domain(model) for model in models]

    async def delete_by_repository(self, repository_id: int) -> int:
        """Delete all rows for a repository. Returns count deleted."""
        result = await self.session.execute(
            delete(self._model_class).where(
                self._model_class.repository_id == repository_id  # type: ignore[attr-defined]
            )
        )
        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def count_by_repository(self, repository_id: int) -> int:
        """Count rows for a repository."""
        result = await self.session.execute(
            select(func.count(self._model_class.id)).where(  # type: ignore[attr-defined]
                self._model_class.repository_id == repository_id  # type: ignore[attr-defined]
            )
        )
        return result.scalar() or 0
