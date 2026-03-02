"""IndexStatus ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CHAR,
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .repository import RepositoryModel


class IndexStatusModel(Base, TimestampMixin):
    """SQLAlchemy ORM model for index_status table."""

    __tablename__ = "index_status"
    __table_args__ = (
        UniqueConstraint("repository_id", "branch", name="uq_index_status_repo_branch"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    branch: Mapped[str] = mapped_column(String(255), nullable=False)

    # Indexing state
    last_indexed_commit: Mapped[str | None] = mapped_column(CHAR(40), nullable=True)
    oldest_indexed_commit: Mapped[str | None] = mapped_column(CHAR(40), nullable=True)
    last_indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    indexing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    indexing_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", index=True
    )

    # Statistics
    total_commits_indexed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_files_indexed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_symbols_indexed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_references_indexed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # Timing
    last_indexing_duration_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    last_resolving_duration_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Metadata
    indexer_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    repository: Mapped["RepositoryModel"] = relationship(
        "RepositoryModel", back_populates="index_statuses"
    )

    def __repr__(self) -> str:
        return (
            f"<IndexStatusModel(id={self.id}, repo_id={self.repository_id}, "
            f"branch='{self.branch}', status='{self.indexing_status}')>"
        )
