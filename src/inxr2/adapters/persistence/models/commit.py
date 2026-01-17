"""Commit ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .types import StringArray

if TYPE_CHECKING:
    from .file import FileModel
    from .reference import ReferenceModel
    from .repository import RepositoryModel
    from .symbol import SymbolModel


class CommitModel(Base):
    """SQLAlchemy ORM model for commits table."""

    __tablename__ = "commits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    commit_hash: Mapped[str] = mapped_column(CHAR(40), nullable=False, index=True)
    short_hash: Mapped[str] = mapped_column(CHAR(7), nullable=False)
    parent_hashes: Mapped[list[str] | None] = mapped_column(StringArray, nullable=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    author_email: Mapped[str] = mapped_column(String(255), nullable=False)
    committer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    committer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    author_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    commit_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default="now()"
    )

    # Relationships
    repository: Mapped["RepositoryModel"] = relationship(
        "RepositoryModel", back_populates="commits"
    )
    files: Mapped[list["FileModel"]] = relationship(
        "FileModel", back_populates="commit", cascade="all, delete-orphan"
    )
    symbols: Mapped[list["SymbolModel"]] = relationship(
        "SymbolModel", back_populates="commit", cascade="all, delete-orphan"
    )
    references: Mapped[list["ReferenceModel"]] = relationship(
        "ReferenceModel", back_populates="commit", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CommitModel(id={self.id}, hash='{self.short_hash}')>"
