"""File entity - represents a source file."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class File:
    """
    A source code file at a specific commit (temporal snapshot).

    Domain entity (framework-agnostic). Separate from SQLAlchemy ORM model.

    Attributes:
        repository_id: Repository this file belongs to
        commit_id: Commit ID where this version exists
        path: File path relative to repository root
        content_hash: Git blob SHA-1 hash (for deduplication)
        size_bytes: File size in bytes
        id: Database ID (None for new entities)
        language: Detected programming language (python, java, etc.)
        encoding: File encoding (default: utf-8)
        is_binary: True if file is binary (skip parsing)
        line_count: Number of lines in file
        indexed_at: When file was indexed
    """

    repository_id: int
    commit_id: int
    path: str
    content_hash: str
    size_bytes: int
    id: int | None = None
    language: str | None = None
    encoding: str = "utf-8"
    is_binary: bool = False
    line_count: int | None = None
    indexed_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate file entity."""
        if not self.path:
            raise ValueError("File path cannot be empty")
        if self.size_bytes < 0:
            raise ValueError(f"File size cannot be negative: {self.size_bytes}")
        if self.line_count is not None and self.line_count < 0:
            raise ValueError(f"Line count cannot be negative: {self.line_count}")

    @property
    def path_obj(self) -> Path:
        """Return path as Path object."""
        return Path(self.path)
