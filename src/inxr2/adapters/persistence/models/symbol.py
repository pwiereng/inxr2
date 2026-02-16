"""Symbol ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .file import FileModel
    from .reference import ReferenceModel
    from .repository import RepositoryModel


class SymbolModel(Base):
    """SQLAlchemy ORM model for symbols table.

    Symbols belong to a file version (content-addressable). Commit context
    is provided through the commit_files junction table.
    """

    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )

    # Symbol identification
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    qualified_name: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Location
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    start_column: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_column: Mapped[int] = mapped_column(Integer, nullable=False)

    # Scope and context
    parent_symbol_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("symbols.id", ondelete="SET NULL"), nullable=True
    )
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Language-specific metadata
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    docstring: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default="now()"
    )

    # Relationships
    file: Mapped["FileModel"] = relationship("FileModel", back_populates="symbols")
    repository: Mapped["RepositoryModel"] = relationship(
        "RepositoryModel", back_populates="symbols"
    )
    parent_symbol: Mapped["SymbolModel | None"] = relationship(
        "SymbolModel", remote_side=[id], backref="child_symbols"
    )
    references: Mapped[list["ReferenceModel"]] = relationship(
        "ReferenceModel",
        back_populates="target_symbol",
        foreign_keys="ReferenceModel.target_symbol_id",
    )

    def __repr__(self) -> str:
        return f"<SymbolModel(id={self.id}, name='{self.name}', kind='{self.kind}')>"
