"""CommitFile ORM model - junction table linking commits to file versions."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .commit import CommitModel
    from .file import FileModel


class CommitFileModel(Base):
    """
    SQLAlchemy ORM model for commit_files junction table.

    Links commits to file versions, enabling content-addressable file storage.
    A file version (unique by repo_id, path, content_hash) can be linked to
    many commits, and a commit links to all files in its tree.
    """

    __tablename__ = "commit_files"

    commit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("commits.id", ondelete="CASCADE"),
        primary_key=True,
    )
    file_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("files.id", ondelete="CASCADE"),
        primary_key=True,
    )

    __table_args__ = (Index("ix_commit_files_file_id", "file_id"),)

    # Relationships
    commit: Mapped["CommitModel"] = relationship(
        "CommitModel", back_populates="commit_files"
    )
    file: Mapped["FileModel"] = relationship("FileModel", back_populates="commit_files")

    def __repr__(self) -> str:
        return f"<CommitFileModel(commit_id={self.commit_id}, file_id={self.file_id})>"
