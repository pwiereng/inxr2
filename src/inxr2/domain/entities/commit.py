"""Commit entity - represents a git commit."""

from dataclasses import dataclass
from datetime import datetime

from ..value_objects.commit_hash import CommitHash


@dataclass(frozen=True)
class Commit:
    """
    A git commit snapshot.

    Domain entity (framework-agnostic). Separate from SQLAlchemy ORM model.

    Attributes:
        commit_hash: Full 40-character SHA-1 hash
        repository_id: ID of repository this commit belongs to
        author_name: Name of commit author
        author_email: Email of commit author
        committer_name: Name of committer (may differ from author)
        committer_email: Email of committer
        author_date: When code was authored
        commit_date: When commit was created
        message: Commit message
        id: Database ID (None for new entities)
        short_hash: 7-character short hash for display
        parent_hashes: List of parent commit hashes (for merge commits)
        branch: Branch name (None for detached commits)
        indexed_at: When this commit was indexed
    """

    commit_hash: CommitHash
    repository_id: int
    author_name: str
    author_email: str
    committer_name: str
    committer_email: str
    author_date: datetime
    commit_date: datetime
    message: str
    id: int | None = None
    short_hash: str | None = None
    parent_hashes: list[str] | None = None
    branch: str | None = None
    indexed_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate commit entity."""
        if not self.author_name:
            raise ValueError("Author name cannot be empty")
        if not self.author_email:
            raise ValueError("Author email cannot be empty")
        if not self.message:
            raise ValueError("Commit message cannot be empty")
