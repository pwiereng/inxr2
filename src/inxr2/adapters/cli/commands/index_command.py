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
                    'TRUNCATE TABLE "references", symbols, text_contents, '
                    "commit_files, files, branch_commits, commits, "
                    "index_status, repositories CASCADE;"
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
    files_at_head: int = 0  # Number of files at HEAD commit (total in repo)
    lines_indexed: int = 0  # Approximate lines of code indexed
    symbols_found: int = 0
    references_found: int = 0
    references_resolved: int = 0
    # Content-addressable file version counters
    file_versions_new: int = 0  # new file versions created
    file_versions_cached: int = 0  # existing file versions reused
    # Text search content counters
    comments_indexed: int = 0
    docstrings_indexed: int = 0
    commit_messages_indexed: int = 0
    errors: list[str] = field(default_factory=list)
    # Database query statistics
    db_stats: DBQueryStats = field(default_factory=DBQueryStats)
    # Database size tracking
    db_size_bytes: int = 0  # Total DB size after indexing
    db_size_added_bytes: int = 0  # Size added by this indexing run

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


def run_full_index(
    repo_path: Path,
    branch: str | None,
    console: Console,
    days: int | None = None,
    base_branch: str | None = None,
) -> IndexingResult | None:
    """
    Run full snapshot indexing of a repository.

    Every indexed commit stores the complete file tree. Indexing is idempotent:
    existing commits are skipped after a single DB lookup.

    Languages are auto-detected from file extensions — no configuration needed.

    Args:
        repo_path: Path to the git repository
        branch: Branch to index (uses current branch if None)
        console: Rich console for output
        days: Index commits from the last N days (None = forward fill only)
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
                console=console,
                days=days,
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
    console: Console,
    days: int | None = None,
    base_branch: str | None = None,
) -> IndexingResult:
    """Async implementation of full indexing using the orchestrator."""
    from sqlalchemy import text

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
            if days:
                console.print(f"  Days: last {days} days")
            console.print()

            # Create indexing request
            request = IndexRepositoryRequest(
                repository_path=repo_path,
                branch=current_branch,
                days=days,
                base_branch=base_branch,
            )

            # Set up progress renderer
            from inxr2.adapters.cli.rendering import IndexingProgressRenderer

            renderer = IndexingProgressRenderer(console)
            on_progress = renderer.create_progress_callback()

            # Measure DB size before indexing
            db_size_before = 0
            result_row = await session.execute(
                text("SELECT pg_database_size(current_database())")
            )
            db_size_before = result_row.scalar() or 0

            # Run indexing with progress callback
            response = await orchestrator.index_repository(
                request, progress_callback=on_progress
            )

            # Measure DB size after indexing
            await session.commit()
            db_size_after = 0
            result_row = await session.execute(
                text("SELECT pg_database_size(current_database())")
            )
            db_size_after = result_row.scalar() or 0

            # Show final resolution result
            renderer.print_final_resolution(
                references_found=response.references_found,
                references_resolved=response.references_resolved,
                was_resolving=response.references_found > 0,
            )

            # Print summary
            stats = IndexingStats(
                files_total=response.files_total,
                files_processed=response.files_processed,
                files_skipped=response.files_skipped,
                files_failed=response.files_failed,
                files_at_head=response.files_at_head,
                lines_indexed=response.lines_indexed,
                symbols_found=response.symbols_found,
                references_found=response.references_found,
                references_resolved=response.references_resolved,
                file_versions_new=response.file_versions_new,
                file_versions_cached=response.file_versions_cached,
                comments_indexed=response.comments_indexed,
                docstrings_indexed=response.docstrings_indexed,
                commit_messages_indexed=response.commit_messages_indexed,
                errors=response.errors,
                db_stats=response.db_stats,
                db_size_bytes=db_size_after,
                db_size_added_bytes=db_size_after - db_size_before,
            )

            renderer.print_summary(
                stats,
                commits_indexed=response.commits_indexed,
                elapsed_seconds=response.elapsed_seconds,
                indexing_seconds=response.indexing_seconds,
                resolving_seconds=response.resolving_seconds,
                repo_name=repo_path.name,
                branch=current_branch,
                days=days,
            )

            # Only log when actual indexing work was done
            if response.commits_indexed > 0:
                _write_csv_log(response, db_size_after, db_size_after - db_size_before)

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


def _detect_language(file_path: str) -> str | None:
    """Detect language from file extension."""
    from inxr2.domain.services.language_detector import LanguageDetector

    return LanguageDetector.detect(file_path)


def _write_csv_log(
    response: Any, db_size_bytes: int = 0, db_size_added_bytes: int = 0
) -> None:
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
        "file_versions_new",
        "file_versions_cached",
        "symbols_found",
        "references_found",
        "references_resolved",
        "elapsed_seconds",
        "indexing_seconds",
        "resolving_seconds",
        "lines_indexed",
        "db_size_mb",
        "db_size_added_mb",
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
                    response.file_versions_new,
                    response.file_versions_cached,
                    response.symbols_found,
                    response.references_found,
                    response.references_resolved,
                    round(response.elapsed_seconds, 1),
                    round(response.indexing_seconds, 1),
                    round(response.resolving_seconds, 1),
                    response.lines_indexed,
                    round(db_size_bytes / 1_048_576, 1),
                    round(db_size_added_bytes / 1_048_576, 1),
                ]
            )
            f.flush()
    except Exception:
        logger.debug("Failed to write CSV log to %s", log_path, exc_info=True)


def _dict_to_symbol(
    d: dict[str, Any],
    file_id: int,
    repository_id: int,
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
        "enum_member": SymbolKind.ENUM_MEMBER,
        "struct_field": SymbolKind.STRUCT_FIELD,
        "union_field": SymbolKind.UNION_FIELD,
        # Java-specific kinds
        "annotation": SymbolKind.ANNOTATION,
        "record": SymbolKind.RECORD,
        "constructor": SymbolKind.CONSTRUCTOR,
        # C#-specific kinds
        "delegate": SymbolKind.DELEGATE,
        "event": SymbolKind.EVENT,
        "indexer": SymbolKind.INDEXER,
        "namespace": SymbolKind.NAMESPACE,
    }

    kind_str = d.get("kind", "function").lower()
    kind = kind_mapping.get(kind_str, SymbolKind.FUNCTION)

    # Build metadata from language-specific flags
    metadata: dict[str, Any] | None = None
    flag_keys = [
        "is_static",
        "is_abstract",
        "is_final",
        "is_inner",
        "is_sealed",
        "is_virtual",
        "is_override",
        "is_async",
        "is_readonly",
        "is_partial",
    ]
    flags = {k: d[k] for k in flag_keys if k in d}
    if flags:
        metadata = flags

    return Symbol(
        file_id=file_id,
        repository_id=repository_id,
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
