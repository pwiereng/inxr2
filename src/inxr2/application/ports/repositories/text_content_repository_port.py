"""Text content repository port interface for text content operations."""

from abc import ABC, abstractmethod

from ....domain.entities import TextContent


class TextContentRepositoryPort(ABC):
    """Port for text content operations.

    Manages searchable text extracted from various sources:
    - Comments and docstrings from code files
    - Commit messages
    - Content from non-code files (markdown, YAML, etc.)
    """

    @abstractmethod
    async def save(self, text_content: TextContent) -> TextContent:
        """Save or update a text content entry."""
        pass

    @abstractmethod
    async def save_batch(self, text_contents: list[TextContent]) -> list[TextContent]:
        """Bulk save text contents for performance.

        Args:
            text_contents: List of text content entities to save

        Returns:
            List of saved text content entities with IDs populated
        """
        pass

    @abstractmethod
    async def delete_by_commit(self, commit_id: int) -> int:
        """Delete all text contents for a commit (for re-indexing).

        Args:
            commit_id: The commit ID to delete text contents for

        Returns:
            Number of text contents deleted
        """
        pass

    @abstractmethod
    async def delete_by_file(self, file_id: int) -> int:
        """Delete all text contents for a file (for re-indexing).

        Args:
            file_id: The file ID to delete text contents for

        Returns:
            Number of text contents deleted
        """
        pass
