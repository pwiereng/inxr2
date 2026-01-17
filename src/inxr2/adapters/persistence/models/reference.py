"""Reference ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .commit import CommitModel
    from .file import FileModel
    from .repository import RepositoryModel
    from .symbol import SymbolModel


class ReferenceModel(Base):
    """SQLAlchemy ORM model for references table."""

    __tablename__ = "references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    commit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commits.id", ondelete="CASCADE"), nullable=False
    )

    # Source location
    source_file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    source_line: Mapped[int] = mapped_column(Integer, nullable=False)
    source_column: Mapped[int] = mapped_column(Integer, nullable=False)
    source_end_column: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_text: Mapped[str] = mapped_column(String(500), nullable=False, index=True)

    # Target symbol
    target_symbol_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("symbols.id", ondelete="SET NULL"), nullable=True
    )
    target_repository_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True
    )

    # Reference metadata
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_definition: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_write: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Resolution metadata
    resolution_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default="now()"
    )

    # Relationships
    repository: Mapped["RepositoryModel"] = relationship(
        "RepositoryModel", back_populates="references", foreign_keys=[repository_id]
    )
    commit: Mapped["CommitModel"] = relationship(
        "CommitModel", back_populates="references"
    )
    source_file: Mapped["FileModel"] = relationship(
        "FileModel", back_populates="references"
    )
    target_symbol: Mapped["SymbolModel | None"] = relationship(
        "SymbolModel", back_populates="references", foreign_keys=[target_symbol_id]
    )
    target_repository: Mapped["RepositoryModel | None"] = relationship(
        "RepositoryModel", foreign_keys=[target_repository_id]
    )

    def __repr__(self) -> str:
        return (
            f"<ReferenceModel(id={self.id}, "
            f"text='{self.reference_text}', type='{self.reference_type}')>"
        )
