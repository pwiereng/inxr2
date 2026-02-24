"""Base SQLAlchemy repository with shared CRUD boilerplate."""

from typing import Generic, Protocol, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

TEntity = TypeVar("TEntity")
TModel = TypeVar("TModel")


class MapperProtocol(Protocol[TEntity, TModel]):
    """Protocol for bidirectional entity/model mappers."""

    def to_domain(self, model: TModel) -> TEntity: ...

    def to_model(self, entity: TEntity) -> TModel: ...


class BaseSQLAlchemyRepository(Generic[TEntity, TModel]):
    """Generic base class for SQLAlchemy repository adapters.

    Provides shared ``save()`` and ``find_by_id()`` implementations that are
    identical across most repository adapters.  Subclasses must set
    ``_model_class`` and initialise ``self.mapper`` in their ``__init__``.
    """

    _model_class: type[TModel]
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
