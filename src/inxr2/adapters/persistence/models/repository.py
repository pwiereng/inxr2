"""Repository ORM model."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .commit import CommitModel
    from .file import FileModel
    from .index_status import IndexStatusModel
    from .reference import ReferenceModel
    from .symbol import SymbolModel


class RepositoryModel(Base, TimestampMixin):
    """
    SQLAlchemy ORM model for repositories table.

    Separate from domain Repository entity (Clean Architecture).
    """

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_branch: Mapped[str] = mapped_column(String(100), nullable=False, default="main")
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    commits: Mapped[list["CommitModel"]] = relationship("CommitModel", back_populates="repository", cascade="all, delete-orphan")
    files: Mapped[list["FileModel"]] = relationship("FileModel", back_populates="repository", cascade="all, delete-orphan")
    symbols: Mapped[list["SymbolModel"]] = relationship("SymbolModel", back_populates="repository", cascade="all, delete-orphan")
    references: Mapped[list["ReferenceModel"]] = relationship("ReferenceModel", back_populates="repository", foreign_keys="ReferenceModel.repository_id", cascade="all, delete-orphan")
    index_statuses: Mapped[list["IndexStatusModel"]] = relationship("IndexStatusModel", back_populates="repository", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<RepositoryModel(id={self.id}, name='{self.name}')>"
