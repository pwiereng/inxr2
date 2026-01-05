"""File ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .commit import CommitModel
    from .reference import ReferenceModel
    from .repository import RepositoryModel
    from .symbol import SymbolModel


class FileModel(Base):
    """SQLAlchemy ORM model for files table."""

    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    commit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commits.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(CHAR(40), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    encoding: Mapped[str] = mapped_column(String(50), nullable=False, default="utf-8")
    is_binary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    line_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default="now()")

    # Relationships
    repository: Mapped["RepositoryModel"] = relationship("RepositoryModel", back_populates="files")
    commit: Mapped["CommitModel"] = relationship("CommitModel", back_populates="files")
    symbols: Mapped[list["SymbolModel"]] = relationship("SymbolModel", back_populates="file", cascade="all, delete-orphan")
    references: Mapped[list["ReferenceModel"]] = relationship("ReferenceModel", back_populates="source_file", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<FileModel(id={self.id}, path='{self.path}')>"
