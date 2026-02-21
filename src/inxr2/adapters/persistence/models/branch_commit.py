"""BranchCommit ORM model - junction table linking branches to commits."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .commit import CommitModel
    from .repository import RepositoryModel


class BranchCommitModel(Base):
    """
    SQLAlchemy ORM model for branch_commits junction table.

    This table links branches to commits, allowing a commit to exist on
    multiple branches without duplication. This properly reflects git's
    model where a commit is unique by hash across all branches.
    """

    __tablename__ = "branch_commits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    branch: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    commit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("commits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Unique constraint: a commit can only be linked to a branch once per repo
    __table_args__ = (
        UniqueConstraint(
            "repository_id", "branch", "commit_id", name="uq_branch_commit"
        ),
    )

    # Relationships
    repository: Mapped["RepositoryModel"] = relationship("RepositoryModel")
    commit: Mapped["CommitModel"] = relationship(
        "CommitModel", back_populates="branch_commits"
    )

    def __repr__(self) -> str:
        return (
            f"<BranchCommitModel(branch='{self.branch}', commit_id={self.commit_id})>"
        )
