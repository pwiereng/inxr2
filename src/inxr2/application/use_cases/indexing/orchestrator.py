"""
Indexing orchestrator DTOs and enums.

This module defines the request/response objects for the indexing
orchestration port, separating indexing concerns from CLI adapter.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class IndexingStrategy(str, Enum):
    """Strategy for indexing a repository."""

    FULL = "full"  # Index from scratch (optionally with time limits)
    INCREMENTAL = "incremental"  # Only index new commits since last index


@dataclass
class IndexRepositoryRequest:
    """
    Request to index a repository.

    Attributes:
        repository_path: Path to the git repository
        branch: Branch to index (None = current branch)
        languages: List of programming languages to parse
        strategy: Indexing strategy (FULL or INCREMENTAL)
        max_history: Maximum number of commits to index (None = all)
        since_days: Only index commits from last N days (overrides max_history)
        force: If True, clear existing data before indexing (FULL only)
    """

    repository_path: Path
    branch: str | None = None
    languages: list[str] | None = None
    strategy: IndexingStrategy = IndexingStrategy.FULL
    max_history: int | None = 100
    since_days: int | None = None
    force: bool = False


@dataclass
class IncrementalIndexRequest:
    """
    Request for incremental indexing.

    Attributes:
        repository_id: Database ID of repository to update
        repository_path: Path to the git repository
        branch: Branch to index (None = current branch)
        languages: List of programming languages to parse
    """

    repository_id: int
    repository_path: Path
    branch: str | None = None
    languages: list[str] | None = None


@dataclass
class IndexRepositoryResponse:
    """
    Response from indexing operation.

    Contains statistics about what was indexed and any errors encountered.

    Attributes:
        repository_id: Database ID of indexed repository
        repository_name: Human-readable repository name
        branch: Branch that was indexed
        commits_indexed: Number of commits processed
        files_total: Total files found across indexed commits
        files_processed: Files successfully processed
        files_skipped: Files skipped (wrong language, too large, etc.)
        files_failed: Files that failed to process
        symbols_found: Total symbols extracted
        references_found: Total references extracted
        references_resolved: References successfully resolved to targets
        files_reused: Files reused via content-hash optimization
        symbols_reused: Symbols reused via content-hash optimization
        references_reused: References reused via content-hash optimization
        errors: List of error messages (non-fatal)
        elapsed_seconds: Time taken to complete indexing
    """

    repository_id: int
    repository_name: str
    branch: str
    commits_indexed: int
    files_total: int
    files_processed: int
    files_skipped: int
    files_failed: int
    symbols_found: int
    references_found: int
    references_resolved: int
    files_reused: int
    symbols_reused: int
    references_reused: int
    errors: list[str]
    elapsed_seconds: float

    @property
    def files_succeeded(self) -> int:
        """Calculate successfully processed files (processed - failed)."""
        return max(0, self.files_processed - self.files_failed)

    @property
    def has_errors(self) -> bool:
        """Check if any errors occurred during indexing."""
        return len(self.errors) > 0 or self.files_failed > 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage (0-100)."""
        if self.files_total == 0:
            return 100.0
        return (self.files_succeeded / self.files_total) * 100.0
