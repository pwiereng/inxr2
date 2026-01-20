"""IndexStatus entity - tracks indexing progress."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class IndexStatus:
    """
    Tracks indexing progress and status for a repository/branch combination.

    Domain entity (framework-agnostic). Separate from SQLAlchemy ORM model.

    Attributes:
        repository_id: Repository being indexed
        branch: Branch being indexed
        indexing_status: Current status (pending, in_progress, completed, failed)
        id: Database ID (None for new entities)
        last_indexed_commit: SHA-1 of most recent (newest) indexed commit
        oldest_indexed_commit: SHA-1 of oldest indexed commit (for time travel)
        last_indexed_at: When indexing completed
        indexing_started_at: When current/last indexing started
        total_commits_indexed: Count of indexed commits
        total_files_indexed: Count of indexed files
        total_symbols_indexed: Count of indexed symbols
        total_references_indexed: Count of indexed references
        error_message: Last error message (if failed)
        error_count: Number of errors encountered
        indexer_version: Version of indexer that ran
        metadata: Additional indexing metadata (JSONB)
        created_at: When record was created
        updated_at: Last update timestamp
    """

    repository_id: int
    branch: str
    indexing_status: str = "pending"
    id: int | None = None
    last_indexed_commit: str | None = None
    oldest_indexed_commit: str | None = None
    last_indexed_at: datetime | None = None
    indexing_started_at: datetime | None = None
    total_commits_indexed: int = 0
    total_files_indexed: int = 0
    total_symbols_indexed: int = 0
    total_references_indexed: int = 0
    error_message: str | None = None
    error_count: int = 0
    indexer_version: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    VALID_STATUSES = {"pending", "in_progress", "completed", "failed"}

    def __post_init__(self) -> None:
        """Validate index status entity."""
        if not self.branch:
            raise ValueError("Branch cannot be empty")
        if self.indexing_status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid indexing status '{self.indexing_status}'. "
                f"Must be one of: {', '.join(self.VALID_STATUSES)}"
            )
        if self.total_commits_indexed < 0:
            raise ValueError(
                f"Total commits cannot be negative: {self.total_commits_indexed}"
            )
        if self.total_files_indexed < 0:
            raise ValueError(
                f"Total files cannot be negative: {self.total_files_indexed}"
            )
        if self.total_symbols_indexed < 0:
            raise ValueError(
                f"Total symbols cannot be negative: {self.total_symbols_indexed}"
            )
        if self.total_references_indexed < 0:
            raise ValueError(
                f"Total references cannot be negative: {self.total_references_indexed}"
            )
        if self.error_count < 0:
            raise ValueError(f"Error count cannot be negative: {self.error_count}")
