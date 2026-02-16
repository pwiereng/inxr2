"""TextContent ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BIGINT,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .commit import CommitModel
    from .file import FileModel
    from .repository import RepositoryModel


class TextContentModel(Base):
    """SQLAlchemy ORM model for text_contents table.

    Stores searchable text extracted from various sources:
    - Comments and docstrings from code files
    - Commit messages
    - Content from non-code files (markdown, YAML, etc.)
    """

    __tablename__ = "text_contents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    commit_id: Mapped[int | None] = mapped_column(
        BIGINT, ForeignKey("commits.id", ondelete="CASCADE"), nullable=True
    )

    # Source information
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_file_id: Mapped[int | None] = mapped_column(
        BIGINT, ForeignKey("files.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Searchable content (extracted text, NOT raw file content)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Full-text search - excluded from ORM operations
    # This column (content_tsvector) is managed by database triggers
    # The column exists in PostgreSQL but is not mapped in SQLAlchemy

    # Metadata
    language: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    content_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default="now()"
    )

    # Relationships
    repository: Mapped["RepositoryModel"] = relationship(
        "RepositoryModel", back_populates="text_contents"
    )
    commit: Mapped["CommitModel"] = relationship(
        "CommitModel", back_populates="text_contents"
    )
    source_file: Mapped["FileModel | None"] = relationship(
        "FileModel", back_populates="text_contents"
    )

    def __repr__(self) -> str:
        return f"<TextContentModel(id={self.id}, source_type='{self.source_type}')>"
