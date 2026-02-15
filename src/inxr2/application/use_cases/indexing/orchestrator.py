"""
Indexing orchestrator DTOs and enums.

This module defines the request/response objects for the indexing
orchestration port, separating indexing concerns from CLI adapter.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DBQueryStats:
    """
    Statistics about database queries during indexing.

    Tracks the number of database operations by type to help
    identify optimization opportunities.
    """

    selects: int = 0
    inserts: int = 0
    updates: int = 0
    deletes: int = 0

    def __add__(self, other: "DBQueryStats") -> "DBQueryStats":
        """Allow adding stats together."""
        return DBQueryStats(
            selects=self.selects + other.selects,
            inserts=self.inserts + other.inserts,
            updates=self.updates + other.updates,
            deletes=self.deletes + other.deletes,
        )

    @property
    def total(self) -> int:
        """Total number of queries."""
        return self.selects + self.inserts + self.updates + self.deletes


@dataclass
class IndexRepositoryRequest:
    """
    Request to index a repository.

    Uses full snapshot indexing — every indexed commit stores the complete file tree.
    Indexing is idempotent: existing commits are skipped after a single DB lookup.

    For a full re-index, use `inxr2 db reset` first to clear the database.

    Attributes:
        repository_path: Path to the git repository
        branch: Branch to index (None = current branch)
        languages: List of programming languages to parse
        days: Index commits from last N days (None = forward fill only)
        base_branch: Base branch to compare against for feature branch indexing.
                     When set, only commits unique to this branch (after merge-base)
                     will be indexed. If None, all reachable commits are indexed.
    """

    repository_path: Path
    branch: str | None = None
    languages: list[str] | None = None
    days: int | None = None
    base_branch: str | None = None


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
        files_total: Total changed files found across indexed commits
        files_processed: Files successfully processed
        files_skipped: Files skipped (wrong language, too large, etc.)
        files_failed: Files that failed to process
        files_at_head: Number of files at HEAD commit (total in repo)
        lines_indexed: Approximate lines of code indexed
        symbols_found: Total symbols extracted
        references_found: Total references extracted
        references_resolved: References successfully resolved to targets
        files_reused: Files reused via content-hash optimization
        symbols_reused: Symbols reused via content-hash optimization
        references_reused: References reused via content-hash optimization
        comments_indexed: Number of comments indexed for text search
        docstrings_indexed: Number of docstrings indexed for text search
        commit_messages_indexed: Number of commit messages indexed for text search
        non_code_files_indexed: Number of non-code files indexed for text search
        errors: List of error messages (non-fatal)
        elapsed_seconds: Time taken to complete indexing
        db_stats: Database query statistics (selects, inserts, updates)
    """

    repository_id: int
    repository_name: str
    branch: str
    commits_indexed: int
    files_total: int
    files_processed: int
    files_skipped: int
    files_failed: int
    files_at_head: int = 0
    lines_indexed: int = 0
    symbols_found: int = 0
    references_found: int = 0
    references_resolved: int = 0
    files_reused: int = 0
    symbols_reused: int = 0
    references_reused: int = 0
    comments_indexed: int = 0
    docstrings_indexed: int = 0
    commit_messages_indexed: int = 0
    non_code_files_indexed: int = 0
    errors: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    indexing_seconds: float = 0.0
    resolving_seconds: float = 0.0
    db_stats: DBQueryStats = field(default_factory=DBQueryStats)
    # Commit range info for summary
    oldest_commit_hash: str | None = None
    oldest_commit_date: str | None = None
    newest_commit_hash: str | None = None
    newest_commit_date: str | None = None

    @property
    def files_succeeded(self) -> int:
        """Number of successfully processed files.

        With the current counting logic:
        - files_processed: incremented only for successfully parsed/reused files
        - files_failed: incremented for files that threw exceptions
        - files_skipped: incremented for unsupported languages

        So files_succeeded = files_processed (they're equivalent now).
        """
        return self.files_processed

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
