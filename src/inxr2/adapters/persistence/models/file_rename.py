"""FileRename ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .commit import CommitModel
    from .repository import RepositoryModel


class FileRenameModel(Base):
    """SQLAlchemy ORM model for file_renames table.

    Tracks file renames detected via git diff --find-renames during indexing.
    Each row represents a single rename in a specific commit.
    """

    __tablename__ = "file_renames"
    __table_args__ = (
        UniqueConstraint(
            "commit_id", "old_path", "new_path", name="uq_file_renames_commit_paths"
        ),
        Index("idx_file_renames_repo", "repository_id"),
        Index("idx_file_renames_commit", "commit_id"),
        Index("idx_file_renames_old_path", "repository_id", "old_path"),
        Index("idx_file_renames_new_path", "repository_id", "new_path"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    commit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("commits.id", ondelete="CASCADE"),
        nullable=False,
    )

    old_path: Mapped[str] = mapped_column(Text, nullable=False)
    new_path: Mapped[str] = mapped_column(Text, nullable=False)
    similarity: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default="now()"
    )

    # Relationships
    repository: Mapped["RepositoryModel"] = relationship(
        "RepositoryModel", back_populates="file_renames"
    )
    commit: Mapped["CommitModel"] = relationship(
        "CommitModel", back_populates="file_renames"
    )

    def __repr__(self) -> str:
        return (
            f"<FileRenameModel(id={self.id}, old='{self.old_path}', "
            f"new='{self.new_path}', similarity={self.similarity})>"
        )
