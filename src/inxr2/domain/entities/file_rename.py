"""FileRename entity - represents a file rename detected during indexing."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FileRename:
    """
    A file rename detected via git diff --find-renames during indexing.

    Domain entity (framework-agnostic). Separate from SQLAlchemy ORM model.
    File renames belong to a specific commit in a repository.

    Attributes:
        repository_id: Repository where the rename occurred
        commit_id: Commit that introduced the rename
        old_path: Original file path before rename
        new_path: New file path after rename
        similarity: Rename similarity score (0-100), from git's rename detection
        id: Database ID (None for new entities)
        indexed_at: When the rename was indexed
    """

    repository_id: int
    commit_id: int
    old_path: str
    new_path: str
    similarity: int
    id: int | None = None
    indexed_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate file rename entity."""
        if not self.old_path:
            raise ValueError("old_path cannot be empty")
        if not self.new_path:
            raise ValueError("new_path cannot be empty")
        if self.old_path == self.new_path:
            raise ValueError("old_path and new_path must be different")
        if not (0 <= self.similarity <= 100):
            raise ValueError("similarity must be between 0 and 100")
