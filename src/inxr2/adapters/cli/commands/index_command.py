"""
Index command implementation.

Handles full and incremental indexing with rich progress output.
"""

import asyncio
import csv
import logging
import os
import signal
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from inxr2.application.use_cases.indexing import (
    GetIndexStatusRequest,
    GetIndexStatusUseCase,
)
from inxr2.application.use_cases.indexing.orchestrator import DBQueryStats
from inxr2.infrastructure.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)

# Indexer version for tracking
INDEXER_VERSION = "0.1.0"

# Flag to track if we're in the middle of cleanup (prevent recursive cleanup)
_cleanup_in_progress = False


def _cleanup_and_exit(signum: int | None = None, frame: Any = None) -> None:
    """Handle Ctrl+C by cleaning up and forcefully exiting.

    This ensures the process actually terminates instead of continuing
    to run in the background.

    NOTE: We intentionally use os._exit() instead of sys.exit() because:
    1. sys.exit() raises SystemExit which can be caught, allowing zombie processes
    2. asyncio event loops may not cleanly shut down with sys.exit()
    3. We've seen cases where the process continues running after Ctrl+C
    os._exit() guarantees immediate termination after we've cleaned up DB connections.
    """
    global _cleanup_in_progress
    if _cleanup_in_progress:
        # Already cleaning up, force exit immediately
        os._exit(1)

    _cleanup_in_progress = True

    # Print message directly to stderr to ensure it shows
    import sys

    sys.stderr.write("\nInterrupted. Exiting...\n")
    sys.stderr.flush()

    # Force exit immediately - don't try to clean up database
    # The DB connection will be cleaned up when process terminates
    os._exit(1)


def _setup_signal_handlers() -> None:
    """Set up signal handlers for clean shutdown."""
    # Handle SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, _cleanup_and_exit)
    # Handle SIGTERM
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _cleanup_and_exit)
    # Handle SIGHUP (terminal disconnect)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, _cleanup_and_exit)


def reset_database(console: Console) -> None:
    """
    DESTRUCTIVE: Reset the entire database by truncating all tables.

    WARNING: This permanently deletes ALL indexed data from ALL repositories
    with no way to recover. This is equivalent to dropping and recreating the
    entire database schema.

    This is much faster than deleting data per-repository because TRUNCATE
    bypasses row-by-row deletion and reclaims storage immediately.

    The CLI requires the --yes flag to confirm this operation.

    NOTE: This function uses PostgreSQL-specific SQL (pg_terminate_backend,
    TRUNCATE CASCADE). It is only used by the CLI, not by tests.

    Args:
        console: Rich console for output
    """
    asyncio.run(_reset_database_async(console))


async def _reset_database_async(console: Console) -> None:
    """Async implementation of database reset using TRUNCATE CASCADE."""
    from sqlalchemy import text

    db = DatabaseConnection()

    try:
        async with db.session() as session:
            # First, kill all other connections to avoid lock contention
            console.print("  Terminating other database connections...")
            await session.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND pid <> pg_backend_pid();"
                )
            )
            await session.commit()

            # TRUNCATE CASCADE is much faster than DELETE for large tables
            # Order matters due to foreign key constraints, but CASCADE handles it
            console.print("  Truncating all tables...")
            await session.execute(
                text(
                    'TRUNCATE TABLE "references", symbols, files, branch_commits, '
                    "commits, index_status, repositories CASCADE;"
                )
            )
            await session.commit()

            # Verify the reset worked
            result = await session.execute(text("SELECT COUNT(*) FROM repositories"))
            repo_count = result.scalar()
            console.print(
                f"  [green]All tables truncated (repos: {repo_count})[/green]"
            )
    finally:
        await db.close()


def _utc_now() -> datetime:
    """Return current UTC time as a naive datetime.

    Uses datetime.now(UTC) instead of deprecated _utc_now().
    Returns naive datetime for PostgreSQL TIMESTAMP WITHOUT TIME ZONE columns.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def _to_naive_utc(dt: datetime | None) -> datetime | None:
    """Convert a datetime to timezone-naive UTC.

    PostgreSQL TIMESTAMP WITHOUT TIME ZONE columns expect naive datetimes.
    Git returns timezone-aware datetimes, so we convert them to UTC and strip
    the timezone info.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC)
        return dt.replace(tzinfo=None)
    return dt


@dataclass
class IndexingStats:
    """Statistics collected during indexing."""

    files_total: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    files_unchanged: int = 0  # Files not processed because they didn't change
    files_at_head: int = 0  # Number of files at HEAD commit (total in repo)
    lines_indexed: int = 0  # Approximate lines of code indexed
    symbols_found: int = 0
    references_found: int = 0
    references_resolved: int = 0
    # Content-hash reuse optimization counters
    files_reused: int = 0
    symbols_reused: int = 0
    references_reused: int = 0
    # Text search content counters
    comments_indexed: int = 0
    docstrings_indexed: int = 0
    commit_messages_indexed: int = 0
    errors: list[str] = field(default_factory=list)
    # Database query statistics
    db_stats: DBQueryStats = field(default_factory=DBQueryStats)

    @property
    def files_succeeded(self) -> int:
        return max(0, self.files_processed - self.files_failed)

    @property
    def text_contents_total(self) -> int:
        """Total text content items indexed (comments + docstrings + commit messages)."""
        return (
            self.comments_indexed
            + self.docstrings_indexed
            + self.commit_messages_indexed
        )


@dataclass
class IndexingResult:
    """Result of indexing a single repository/branch.

    Used for final summary display across multiple repos/branches.
    """

    repo_name: str
    branch: str
    success: bool
    files_total: int = 0
    commits_indexed: int = 0
    symbols_found: int = 0
    references_found: int = 0
    references_resolved: int = 0
    lines_indexed: int = 0
    elapsed_seconds: float = 0.0
    error_message: str | None = None
    # Commit range info
    oldest_commit_hash: str | None = None
    oldest_commit_date: str | None = None
    newest_commit_hash: str | None = None
    newest_commit_date: str | None = None

    @property
    def resolution_rate(self) -> float:
        """Calculate reference resolution rate as percentage."""
        if self.references_found == 0:
            return 0.0
        return (self.references_resolved / self.references_found) * 100


def create_progress() -> Progress:
    """Create a rich Progress instance with custom columns."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=Console(),
        transient=False,
    )


def run_full_index(
    repo_path: Path,
    branch: str | None,
    languages: list[str],
    console: Console,
    max_history: int | None = 100,
    force: bool = False,
    since_days: int | None = None,
    base_branch: str | None = None,
) -> IndexingResult | None:
    """
    Run full indexing of a repository with time travel support.

    This performs a complete index from scratch, indexing multiple commits
    to enable time travel functionality.

    Args:
        repo_path: Path to the git repository
        branch: Branch to index (uses current branch if None)
        languages: List of languages to index
        console: Rich console for output
        max_history: Maximum number of commits to index (None = all commits)
        force: If True, clear existing data for this repository before indexing
        since_days: Only index commits from the last N days (overrides max_history)
        base_branch: Base branch for feature branch optimization. When set,
                     only commits unique to this branch (after merge-base) are indexed.

    Returns:
        IndexingResult with stats for the final summary, or None if interrupted
    """
    # Set up signal handlers for clean shutdown on Ctrl+C
    _setup_signal_handlers()

    # Run the async indexing in an event loop with proper cleanup on Ctrl+C
    try:
        return asyncio.run(
            _run_full_index_async(
                repo_path=repo_path,
                branch=branch,
                languages=languages,
                console=console,
                max_history=max_history,
                force=force,
                since_days=since_days,
                base_branch=base_branch,
            )
        )
    except KeyboardInterrupt:
        # Signal handler should have already exited, but just in case
        _cleanup_and_exit()
        return None


async def _run_full_index_async(
    repo_path: Path,
    branch: str | None,
    languages: list[str],
    console: Console,
    max_history: int | None = 100,
    force: bool = False,
    since_days: int | None = None,
    base_branch: str | None = None,
) -> IndexingResult:
    """Async implementation of full indexing using the orchestrator."""
    from inxr2.adapters.external.git_service import GitService
    from inxr2.adapters.external.plaintext_parser import PlaintextParser
    from inxr2.adapters.external.treesitter import TreeSitterService
    from inxr2.adapters.persistence.repositories import (
        PostgresCommitRepository,
        PostgresFileRepository,
        PostgresIndexStatusRepository,
        PostgresReferenceRepository,
        PostgresRepositoryAdapter,
        PostgresSymbolRepository,
        PostgresTextContentRepository,
    )
    from inxr2.application.use_cases.indexing.default_orchestrator import (
        DefaultIndexingOrchestrator,
    )
    from inxr2.application.use_cases.indexing.orchestrator import (
        IndexRepositoryRequest,
    )

    # Initialize database connection
    db = DatabaseConnection()
    try:
        # Initialize services
        git_service = GitService()
        parser_service = TreeSitterService()

        # Initialize repositories
        async with db.session() as session:
            repository_repo = PostgresRepositoryAdapter(session)
            commit_repo = PostgresCommitRepository(session)
            file_repo = PostgresFileRepository(session)
            symbol_repo = PostgresSymbolRepository(session)
            reference_repo = PostgresReferenceRepository(session)
            index_status_repo = PostgresIndexStatusRepository(session)
            text_content_repo = PostgresTextContentRepository(session)

            # Create orchestrator
            orchestrator = DefaultIndexingOrchestrator(
                repository_repo=repository_repo,
                commit_repo=commit_repo,
                file_repo=file_repo,
                symbol_repo=symbol_repo,
                reference_repo=reference_repo,
                index_status_repo=index_status_repo,
                text_content_repo=text_content_repo,
                git_service=git_service,
                parser_service=parser_service,
                plaintext_parser=PlaintextParser(),
            )

            # Get repository info for display
            repo_info = git_service.get_repository_info(repo_path)
            current_branch = branch or repo_info.current_branch or "main"

            # Show what were about to index
            console.print(f"[cyan]Indexing {repo_path.name}[/cyan]")
            console.print(f"  Branch: [cyan]{current_branch}[/cyan]")
            if max_history:
                console.print(f"  Max history: {max_history} commits")
            if since_days:
                console.print(f"  Since: last {since_days} days")

            # Show commit range being indexed
            # Use list_branch_commits when base_branch optimization is active
            if base_branch and base_branch != current_branch:
                commits = git_service.list_branch_commits(
                    repo_path=repo_path,
                    branch=current_branch,
                    base_branch=base_branch,
                    max_count=max_history,
                    since_days=since_days,
                )
            else:
                commits = git_service.list_commits(
                    repo_path=repo_path,
                    branch=current_branch,
                    max_count=max_history,
                    since_days=since_days,
                )
            if not commits:
                # Fall back to HEAD if no commits in range
                head_hash = git_service.get_current_commit(repo_path, current_branch)
                head_info = git_service.get_commit_info(repo_path, head_hash)
                commits = [head_info]

            if commits:
                oldest = commits[0]
                newest = commits[-1]
                console.print(f"  Commits: {len(commits)}")
                oldest_date = oldest.author_date or oldest.commit_date
                newest_date = newest.author_date or newest.commit_date
                if oldest_date is not None and hasattr(oldest_date, "strftime"):
                    oldest_str = oldest_date.strftime("%Y-%m-%d %H:%M:%S UTC")
                else:
                    oldest_str = str(oldest_date) if oldest_date else "unknown"
                if newest_date is not None and hasattr(newest_date, "strftime"):
                    newest_str = newest_date.strftime("%Y-%m-%d %H:%M:%S UTC")
                else:
                    newest_str = str(newest_date) if newest_date else "unknown"
                console.print(f"  Oldest: {oldest.hash[:10]} ({oldest_str})")
                console.print(f"  Newest: {newest.hash[:10]} ({newest_str})")
            console.print()

            # Create indexing request
            request = IndexRepositoryRequest(
                repository_path=repo_path,
                branch=current_branch,
                languages=languages,
                max_history=max_history,
                since_days=since_days,
                base_branch=base_branch,
            )

            # Import progress types
            # Progress at specific percentages: 0, 1, 2, 5, 10, 15, 20, ...
            import sys

            from inxr2.application.use_cases.indexing.default_orchestrator import (
                IndexingProgress,
            )

            milestones = {
                0,
                1,
                2,
                5,
                10,
                15,
                20,
                25,
                30,
                35,
                40,
                45,
                50,
                55,
                60,
                65,
                70,
                75,
                80,
                85,
                90,
                95,
                100,
            }

            # Mutable progress state (using class for proper typing)
            class ProgressState:
                pcts: set[int] = set()
                phase: str = ""
                shown_start: bool = False

            state = ProgressState()

            def on_progress(p: IndexingProgress) -> None:
                # Show initial info at start
                if not state.shown_start and p.files_total > 0:
                    state.shown_start = True
                    console.print(
                        f"  [dim]Files to process: {p.files_total} | "
                        f"Cache size: {p.cache_size}[/dim]"
                    )

                if p.phase == "files" and p.files_total > 0:
                    pct = int((p.files_processed / p.files_total) * 100)
                    if pct in milestones and pct not in state.pcts:
                        state.pcts.add(pct)
                        sys.stdout.write(
                            f"\r  {pct}% ({p.files_processed}/{p.files_total}) | "
                            f"Symbols: {p.symbols_found} | Refs: {p.references_found} | "
                            f"Cache: {p.cache_size}    "
                        )
                        sys.stdout.flush()
                elif p.phase == "resolving":
                    if state.phase != "resolving":
                        # First resolving update - print header
                        state.phase = "resolving"
                        state.pcts = set()  # Reset milestones for resolution
                        sys.stdout.write("\n")
                        if p.refs_total > 0:
                            console.print(
                                f"  [cyan]Resolving references "
                                f"({p.refs_total} to process)...[/cyan]"
                            )
                        else:
                            console.print("  [cyan]Resolving references...[/cyan]")
                    # Show resolution progress at milestone percentages
                    if p.refs_total > 0:
                        pct = int((p.refs_resolved / p.refs_total) * 100)
                        if pct in milestones and pct not in state.pcts:
                            state.pcts.add(pct)
                            sys.stdout.write(
                                f"\r  Resolving: {pct}% "
                                f"({p.refs_resolved}/{p.refs_total})    "
                            )
                            sys.stdout.flush()

            # Run indexing with progress callback
            response = await orchestrator.index_repository(
                request, progress_callback=on_progress
            )

            # Show final resolution result if we were in resolving phase
            if state.phase == "resolving" and response.references_found > 0:
                pct = response.references_resolved * 100 // response.references_found
                sys.stdout.write(
                    f"\r  Resolved: {response.references_resolved}/"
                    f"{response.references_found} ({pct}%)    \n"
                )
                sys.stdout.flush()

            # Print summary
            stats = IndexingStats(
                files_total=response.files_total,
                files_processed=response.files_processed,
                files_skipped=response.files_skipped,
                files_failed=response.files_failed,
                files_unchanged=response.files_unchanged,
                files_at_head=response.files_at_head,
                lines_indexed=response.lines_indexed,
                symbols_found=response.symbols_found,
                references_found=response.references_found,
                references_resolved=response.references_resolved,
                files_reused=response.files_reused,
                symbols_reused=response.symbols_reused,
                references_reused=response.references_reused,
                comments_indexed=response.comments_indexed,
                docstrings_indexed=response.docstrings_indexed,
                commit_messages_indexed=response.commit_messages_indexed,
                errors=response.errors,
                db_stats=response.db_stats,
            )

            _print_summary(
                console,
                stats,
                commits_indexed=response.commits_indexed,
                elapsed_seconds=response.elapsed_seconds,
                indexing_seconds=response.indexing_seconds,
                resolving_seconds=response.resolving_seconds,
                repo_name=repo_path.name,
                branch=current_branch,
                max_history=max_history,
                since_days=since_days,
            )

            _write_csv_log(response)

            await session.commit()

            # Return result for final summary
            return IndexingResult(
                repo_name=repo_path.name,
                branch=current_branch,
                success=True,
                files_total=response.files_total,
                commits_indexed=response.commits_indexed,
                symbols_found=response.symbols_found,
                references_found=response.references_found,
                references_resolved=response.references_resolved,
                lines_indexed=response.lines_indexed,
                elapsed_seconds=response.elapsed_seconds,
                oldest_commit_hash=response.oldest_commit_hash,
                oldest_commit_date=response.oldest_commit_date,
                newest_commit_hash=response.newest_commit_hash,
                newest_commit_date=response.newest_commit_date,
            )

    finally:
        await db.close()


def show_index_status(repo_path: Path, console: Console) -> None:
    """Show indexing status for a repository."""
    asyncio.run(_show_index_status_async(repo_path, console))


async def _show_index_status_async(repo_path: Path, console: Console) -> None:
    """Async implementation of index status.

    Uses GetIndexStatusUseCase for business logic, handles presentation here.
    """
    from inxr2.adapters.external.git_service import GitService
    from inxr2.adapters.persistence.repositories import (
        PostgresIndexStatusRepository,
        PostgresRepositoryAdapter,
    )

    git_service = GitService()

    # Get repository info from git (external service)
    repo_info = git_service.get_repository_info(repo_path)
    current_branch = repo_info.current_branch or "unknown"
    current_commit = git_service.get_current_commit(repo_path, current_branch)
    repo_name = repo_info.name

    # Connect to database and execute use case
    db = DatabaseConnection()

    try:
        async with db.session() as session:
            # Create use case with dependencies
            use_case = GetIndexStatusUseCase(
                repository_repo=PostgresRepositoryAdapter(session),
                index_status_repo=PostgresIndexStatusRepository(session),
            )

            # Execute use case
            status = await use_case.execute(
                GetIndexStatusRequest(
                    repository_name=repo_name,
                    branch=current_branch,
                    current_commit_hash=current_commit,
                )
            )

            # Presentation: Create status table
            table = Table(show_header=False, box=None)
            table.add_column("Property", style="dim")
            table.add_column("Value")

            table.add_row("Repository", repo_name)
            table.add_row("Current Branch", current_branch)
            table.add_row(
                "Current Commit", current_commit[:8] if current_commit else "unknown"
            )
            table.add_row("", "")

            if status.is_indexed:
                table.add_row(
                    "Last Indexed Commit",
                    (
                        status.last_indexed_commit[:8]
                        if status.last_indexed_commit
                        else "unknown"
                    ),
                )
                table.add_row(
                    "Last Indexed At",
                    (
                        status.last_indexed_at.isoformat()
                        if status.last_indexed_at
                        else "unknown"
                    ),
                )
                table.add_row("Files Indexed", str(status.total_files_indexed))
                table.add_row("Symbols Indexed", str(status.total_symbols_indexed))
                table.add_row(
                    "References Indexed", str(status.total_references_indexed)
                )

                if status.is_up_to_date:
                    table.add_row("Status", "[green]Up to date[/green]")
                else:
                    table.add_row("Status", "[yellow]Updates available[/yellow]")
            else:
                table.add_row("Status", "[red]Not indexed[/red]")

            console.print(table)

    finally:
        await db.close()


# =============================================================================
# Helper Functions
# =============================================================================


def _filter_files_by_language(
    files: list[str], languages: list[str], include_all_text: bool = True
) -> list[str]:
    """Filter files to include text files.

    Args:
        files: List of file paths
        languages: Languages with symbol extraction support
        include_all_text: If True, include all text files (not just supported languages)
    """
    from inxr2.domain.services.language_detector import LanguageDetector

    if include_all_text:
        # Include all text files for browsing
        return [f for f in files if LanguageDetector.is_text_file(f)]

    # Legacy behavior: only include specified languages
    extensions: dict[str, set[str]] = {
        "python": {".py", ".pyi"},
        "typescript": {".ts", ".tsx"},
        "javascript": {".js", ".jsx", ".mjs", ".cjs"},
    }

    allowed_extensions: set[str] = set()
    for lang in languages:
        allowed_extensions.update(extensions.get(lang, set()))

    return [f for f in files if Path(f).suffix.lower() in allowed_extensions]


def _detect_language(file_path: str) -> str | None:
    """Detect language from file extension."""
    from inxr2.domain.services.language_detector import LanguageDetector

    return LanguageDetector.detect(file_path)


def _shorten_path(path: str, max_len: int = 50) -> str:
    """Shorten a path for display."""
    if len(path) <= max_len:
        return path
    parts = Path(path).parts
    if len(parts) <= 2:
        return path
    return f".../{'/'.join(parts[-2:])}"


def _format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs:.1f}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m {secs:.0f}s"


def _write_csv_log(response: Any) -> None:
    """Append a one-line CSV summary to index.log after each indexing run.

    Creates the file with headers if it doesn't exist. Failures are silently
    logged — CSV writing should never crash the CLI.
    """
    log_path = Path("index.log")
    headers = [
        "timestamp",
        "repository",
        "branch",
        "commits_indexed",
        "files_at_head",
        "files_processed",
        "files_failed",
        "files_reused",
        "symbols_found",
        "references_found",
        "references_resolved",
        "elapsed_seconds",
        "indexing_seconds",
        "resolving_seconds",
        "lines_indexed",
    ]
    try:
        write_header = not log_path.exists()
        with open(log_path, "a", newline="") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(headers)
            writer.writerow(
                [
                    datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
                    response.repository_name,
                    response.branch,
                    response.commits_indexed,
                    response.files_at_head,
                    response.files_processed,
                    response.files_failed,
                    response.files_reused,
                    response.symbols_found,
                    response.references_found,
                    response.references_resolved,
                    round(response.elapsed_seconds, 1),
                    round(response.indexing_seconds, 1),
                    round(response.resolving_seconds, 1),
                    response.lines_indexed,
                ]
            )
    except Exception:
        logger.debug("Failed to write CSV log to %s", log_path, exc_info=True)


def _print_summary(
    console: Console,
    stats: IndexingStats,
    is_incremental: bool = False,
    commits_indexed: int | None = None,
    elapsed_seconds: float | None = None,
    indexing_seconds: float | None = None,
    resolving_seconds: float | None = None,
    repo_name: str | None = None,
    branch: str | None = None,
    max_history: int | None = None,
    since_days: int | None = None,
) -> None:
    """Print indexing summary."""
    console.print()

    index_type = "Incremental" if is_incremental else "Full"

    # Create summary table
    table = Table(title=f"{index_type} Index Complete", show_header=False, box=None)
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    # Show repo/branch info
    if repo_name:
        table.add_row("Repository", f"[bold]{repo_name}[/bold]")
    if branch:
        table.add_row("Branch", f"[cyan]{branch}[/cyan]")
    # Show indexing range
    if since_days is not None:
        table.add_row("Range", f"[dim]last {since_days} days[/dim]")
    elif max_history is not None:
        table.add_row("Range", f"[dim]last {max_history} commits[/dim]")

    if repo_name or branch:
        table.add_row("", "")  # Separator after repo info

    if commits_indexed is not None:
        table.add_row("Commits Indexed", f"[magenta]{commits_indexed}[/magenta]")
    if stats.files_at_head > 0:
        table.add_row("Files at HEAD", f"[cyan]{stats.files_at_head:,}[/cyan]")
    if stats.lines_indexed > 0:
        table.add_row("Lines Indexed", f"[cyan]{stats.lines_indexed:,}[/cyan]")
    table.add_row("Files Processed", f"[green]{stats.files_succeeded}[/green]")
    if stats.files_unchanged > 0:
        table.add_row("Files Unchanged", f"[dim]{stats.files_unchanged}[/dim]")
    if stats.files_skipped > 0:
        table.add_row("Files Skipped", f"[dim]{stats.files_skipped}[/dim]")
    if stats.files_failed > 0:
        table.add_row("Files Failed", f"[red]{stats.files_failed}[/red]")
    table.add_row("Symbols Found", f"[cyan]{stats.symbols_found}[/cyan]")
    table.add_row("References Found", f"[cyan]{stats.references_found}[/cyan]")
    # Show resolution count with rate percentage
    if stats.references_found > 0:
        resolution_rate = stats.references_resolved * 100 / stats.references_found
        table.add_row(
            "References Resolved",
            f"[cyan]{stats.references_resolved}[/cyan] [dim]({resolution_rate:.1f}%)[/dim]",
        )
    else:
        table.add_row(
            "References Resolved", f"[cyan]{stats.references_resolved}[/cyan]"
        )

    # Show text search statistics if any content was indexed
    if stats.text_contents_total > 0:
        table.add_row("", "")  # Separator
        table.add_row(
            "Text Content Indexed",
            f"[cyan]{stats.text_contents_total:,}[/cyan] [dim](comments + docstrings + commit messages)[/dim]",
        )
        table.add_row("  Comments", f"[dim]{stats.comments_indexed:,}[/dim]")
        table.add_row("  Docstrings", f"[dim]{stats.docstrings_indexed:,}[/dim]")
        table.add_row(
            "  Commit Messages", f"[dim]{stats.commit_messages_indexed:,}[/dim]"
        )

    # Show reuse statistics if content-hash optimization was used
    if stats.files_reused > 0:
        table.add_row("", "")  # Separator
        table.add_row("Files Reused", f"[yellow]{stats.files_reused}[/yellow]")
        table.add_row("Symbols Reused", f"[yellow]{stats.symbols_reused}[/yellow]")
        table.add_row(
            "References Reused", f"[yellow]{stats.references_reused}[/yellow]"
        )

    # Show elapsed time
    if elapsed_seconds is not None:
        table.add_row("", "")  # Separator
        table.add_row("Total Time", f"[blue]{_format_duration(elapsed_seconds)}[/blue]")
        if indexing_seconds is not None and indexing_seconds > 0:
            table.add_row(
                "  Indexing",
                f"[dim]{_format_duration(indexing_seconds)}[/dim]",
            )
        if resolving_seconds is not None and resolving_seconds > 0:
            table.add_row(
                "  Resolving",
                f"[dim]{_format_duration(resolving_seconds)}[/dim]",
            )

    # Show DB query statistics
    db = stats.db_stats
    if db.total > 0:
        table.add_row("", "")  # Separator
        table.add_row("DB Queries", f"[dim]{db.total} total[/dim]")
        table.add_row("  Selects", f"[dim]{db.selects}[/dim]")
        table.add_row("  Inserts", f"[dim]{db.inserts}[/dim]")
        if db.updates > 0:
            table.add_row("  Updates", f"[dim]{db.updates}[/dim]")
        if db.deletes > 0:
            table.add_row("  Deletes", f"[dim]{db.deletes}[/dim]")

    console.print(Panel(table, border_style="green"))

    # Print errors if any
    if stats.errors:
        console.print(f"\n[yellow]Warnings ({len(stats.errors)}):[/yellow]")
        for error in stats.errors[:5]:  # Show first 5 errors
            console.print(f"  [dim]{error}[/dim]")
        if len(stats.errors) > 5:
            console.print(f"  [dim]... and {len(stats.errors) - 5} more[/dim]")


def _dict_to_symbol(
    d: dict[str, Any],
    file_id: int,
    repository_id: int,
    commit_id: int,
) -> Any:
    """Convert a symbol dict from parser to Symbol domain entity."""
    from inxr2.domain.entities import Symbol
    from inxr2.domain.value_objects import SymbolKind

    # Map kind string to SymbolKind enum
    kind_mapping = {
        "function": SymbolKind.FUNCTION,
        "method": SymbolKind.METHOD,
        "class": SymbolKind.CLASS,
        "interface": SymbolKind.INTERFACE,
        "constant": SymbolKind.CONSTANT,
        "variable": SymbolKind.VARIABLE,
        "field": SymbolKind.FIELD,
        "property": SymbolKind.PROPERTY,
        "type": SymbolKind.NAMESPACE,  # Map type aliases to namespace for now
        # C-specific kinds
        "struct": SymbolKind.STRUCT,
        "union": SymbolKind.UNION,
        "typedef": SymbolKind.TYPEDEF,
        "macro": SymbolKind.MACRO,
        "enum": SymbolKind.ENUM,
        "enum_value": SymbolKind.ENUM_VALUE,
        "struct_field": SymbolKind.STRUCT_FIELD,
        "union_field": SymbolKind.UNION_FIELD,
        # Java-specific kinds
        "annotation": SymbolKind.ANNOTATION,
        "record": SymbolKind.RECORD,
        "constructor": SymbolKind.CONSTRUCTOR,
    }

    kind_str = d.get("kind", "function").lower()
    kind = kind_mapping.get(kind_str, SymbolKind.FUNCTION)

    # Build metadata from language-specific flags (e.g., Java)
    metadata: dict[str, Any] | None = None
    flag_keys = ["is_static", "is_abstract", "is_final", "is_inner"]
    flags = {k: d[k] for k in flag_keys if k in d}
    if flags:
        metadata = flags

    return Symbol(
        file_id=file_id,
        repository_id=repository_id,
        commit_id=commit_id,
        name=d["name"],
        kind=kind,
        start_line=d.get("start_line", 1),
        start_column=d.get("start_column", 0),
        end_line=d.get("end_line", d.get("start_line", 1)),
        end_column=d.get("end_column", 0),
        qualified_name=d.get("qualified_name"),
        scope=d.get("scope"),
        signature=d.get("signature"),
        metadata=metadata,
    )


def _dict_to_reference(
    d: dict[str, Any],
    source_file_id: int,
    repository_id: int,
    commit_id: int,
) -> Any:
    """Convert a reference dict from parser to Reference domain entity."""
    from inxr2.domain.entities import Reference
    from inxr2.domain.value_objects import ReferenceType

    # Map type string to ReferenceType enum
    type_mapping = {
        "import": ReferenceType.IMPORT,
        "call": ReferenceType.CALL,
        "usage": ReferenceType.USAGE,
        "include": ReferenceType.INCLUDE,  # C/C++ #include
        "type_annotation": ReferenceType.TYPE_ANNOTATION,
        "inheritance": ReferenceType.INHERITANCE,  # Class inheritance (extends/implements)
        "instantiation": ReferenceType.INSTANTIATION,  # new ClassName()
    }

    type_str = d.get("type", "usage").lower()
    ref_type = type_mapping.get(type_str, ReferenceType.USAGE)

    source_column = d.get("source_column", 0)
    text = d.get("text", "")

    return Reference(
        repository_id=repository_id,
        commit_id=commit_id,
        source_file_id=source_file_id,
        source_line=d.get("source_line", 1),
        source_column=source_column,
        source_end_column=source_column + len(text),
        reference_text=text,
        reference_type=ref_type,
        metadata=(
            {"from_module": d.get("from_module")} if d.get("from_module") else None
        ),
    )
