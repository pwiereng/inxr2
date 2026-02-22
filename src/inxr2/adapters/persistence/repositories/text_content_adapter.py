"""PostgreSQL text content repository adapter."""

from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories import TextContentRepositoryPort
from ....domain.entities import TextContent
from ..mappers import TextContentMapper
from ..models.text_content import TextContentModel


class PostgresTextContentRepository(TextContentRepositoryPort):
    """PostgreSQL implementation of TextContentRepositoryPort."""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.mapper = TextContentMapper()

    async def save(self, text_content: TextContent) -> TextContent:
        """Save or update a text content entry."""
        model = self.mapper.to_model(text_content)

        if text_content.id is None:
            self.session.add(model)
        else:
            model = await self.session.merge(model)

        await self.session.flush()
        await self.session.refresh(model)

        return self.mapper.to_domain(model)

    async def save_batch(self, text_contents: list[TextContent]) -> list[TextContent]:
        """Bulk save text contents for performance.

        Args:
            text_contents: List of text content entities to save

        Returns:
            List of saved text content entities with IDs populated
        """
        now = datetime.utcnow()
        models = [self.mapper.to_model(tc) for tc in text_contents]
        for model in models:
            model.indexed_at = now
        self.session.add_all(models)
        await self.session.flush()

        return [self.mapper.to_domain(model) for model in models]

    async def delete_by_commit(self, commit_id: int) -> int:
        """Delete all text contents for a commit (for re-indexing).

        Args:
            commit_id: The commit ID to delete text contents for

        Returns:
            Number of text contents deleted
        """
        result = await self.session.execute(
            delete(TextContentModel).where(TextContentModel.commit_id == commit_id)
        )
        return result.rowcount if hasattr(result, "rowcount") else 0

    async def delete_by_file(self, file_id: int) -> int:
        """Delete all text contents for a file (for re-indexing).

        Args:
            file_id: The file ID to delete text contents for

        Returns:
            Number of text contents deleted
        """
        result = await self.session.execute(
            delete(TextContentModel).where(TextContentModel.source_file_id == file_id)
        )
        return result.rowcount if hasattr(result, "rowcount") else 0
