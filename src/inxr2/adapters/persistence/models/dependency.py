"""Dependency ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .file import FileModel
    from .repository import RepositoryModel


class DependencyModel(Base):
    """SQLAlchemy ORM model for dependencies table.

    Dependencies belong to a file version (content-addressable manifest/lock file).
    Commit context is provided through the commit_files junction table.
    """

    __tablename__ = "dependencies"
    __table_args__ = (
        Index("idx_dependencies_package", "package_name", "language"),
        Index("idx_dependencies_file", "file_id"),
        Index("idx_dependencies_repo", "repository_id"),
        Index(
            "idx_dependencies_repo_file_package",
            "repository_id",
            "file_id",
            "package_name",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Package identification
    package_name: Mapped[str] = mapped_column(Text, nullable=False)
    version_spec: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(50), nullable=False)

    # Classification
    dependency_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="runtime"
    )
    is_direct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    parent_dependency_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("dependencies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Language-specific metadata
    extras: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Source location in the manifest file (1-based line number)
    source_line: Mapped[int | None] = mapped_column(Integer, nullable=True)

    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default="now()"
    )

    # Relationships
    file: Mapped["FileModel"] = relationship("FileModel", back_populates="dependencies")
    repository: Mapped["RepositoryModel"] = relationship(
        "RepositoryModel", back_populates="dependencies"
    )
    parent_dependency: Mapped["DependencyModel | None"] = relationship(
        "DependencyModel", remote_side=[id], backref="child_dependencies"
    )

    def __repr__(self) -> str:
        return (
            f"<DependencyModel(id={self.id}, package='{self.package_name}', "
            f"language='{self.language}')>"
        )
