"""Commit ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .branch_commit import BranchCommitModel
    from .commit_file import CommitFileModel
    from .repository import RepositoryModel
    from .text_content import TextContentModel


class CommitModel(Base):
    """
    SQLAlchemy ORM model for commits table.

    Note: Branch information is stored in the branch_commits junction table,
    not directly on this model. A commit can exist on multiple branches.

    Design note: Only essential data is stored. Author info, message, and
    parent hashes are queried from git on-demand. See ARCHITECTURAL_REVIEW.md.
    """

    __tablename__ = "commits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    commit_hash: Mapped[str] = mapped_column(CHAR(40), nullable=False, index=True)
    author_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    commit_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default="now()"
    )

    # Unique constraint: commit hash is unique per repository
    __table_args__ = (
        UniqueConstraint("repository_id", "commit_hash", name="uq_repo_commit_hash"),
    )

    # Relationships
    repository: Mapped["RepositoryModel"] = relationship(
        "RepositoryModel", back_populates="commits"
    )
    commit_files: Mapped[list["CommitFileModel"]] = relationship(
        "CommitFileModel", back_populates="commit", cascade="all, delete-orphan"
    )
    branch_commits: Mapped[list["BranchCommitModel"]] = relationship(
        "BranchCommitModel", back_populates="commit", cascade="all, delete-orphan"
    )
    text_contents: Mapped[list["TextContentModel"]] = relationship(
        "TextContentModel", back_populates="commit", cascade="all, delete-orphan"
    )

    @property
    def short_hash(self) -> str:
        """Return 7-character short hash for display."""
        return self.commit_hash[:7]

    def __repr__(self) -> str:
        return f"<CommitModel(id={self.id}, hash='{self.short_hash}')>"
