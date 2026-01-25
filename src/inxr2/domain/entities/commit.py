"""Commit entity - represents a git commit."""

from dataclasses import dataclass
from datetime import datetime

from ..value_objects.commit_hash import CommitHash


@dataclass(frozen=True)
class Commit:
    """
    A git commit snapshot.

    Domain entity (framework-agnostic). Separate from SQLAlchemy ORM model.

    Note: Branch information is stored separately in the branch_commits table,
    not on the commit itself. A commit can exist on multiple branches.

    Design note: Only essential data is stored in DB. Author info, message,
    and parent hashes are queried from git on-demand to reduce storage and
    avoid data duplication. See ARCHITECTURAL_REVIEW.md for rationale.

    Attributes:
        commit_hash: Full 40-character SHA-1 hash
        repository_id: ID of repository this commit belongs to
        author_date: When code was authored
        commit_date: When commit was created
        id: Database ID (None for new entities)
        indexed_at: When this commit was indexed
    """

    commit_hash: CommitHash
    repository_id: int
    author_date: datetime
    commit_date: datetime
    id: int | None = None
    indexed_at: datetime | None = None

    @property
    def short_hash(self) -> str:
        """Return 7-character short hash for display."""
        return self.commit_hash.short()
