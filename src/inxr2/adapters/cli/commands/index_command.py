"""
Index command implementation.

Handles full and incremental indexing with rich progress output.
"""

import asyncio
import hashlib
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
    ResolveReferencesRequest,
    ResolveReferencesUseCase,
)
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

    console = Console()
    console.print("\n[yellow]Interrupted. Cleaning up and exiting...[/yellow]")

    # Try to clean up database connections
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            db = DatabaseConnection()
            loop.run_until_complete(db.close())
        finally:
            loop.close()
    except Exception:
        pass  # Ignore cleanup errors

    # Force exit - don't let anything continue
    console.print("[dim]Exiting.[/dim]")
    os._exit(1)


def _setup_signal_handlers() -> None:
    """Set up signal handlers for clean shutdown."""
    # Handle SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, _cleanup_and_exit)
    signal.signal(signal.SIGTERM, _cleanup_and_exit)


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
    symbols_found: int = 0
    references_found: int = 0
    references_resolved: int = 0
    # Content-hash reuse optimization counters
    files_reused: int = 0
    symbols_reused: int = 0
    references_reused: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def files_succeeded(self) -> int:
        return max(0, self.files_processed - self.files_failed)


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
) -> None:
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
    """
    # Set up signal handlers for clean shutdown on Ctrl+C
    _setup_signal_handlers()

    # Run the async indexing in an event loop with proper cleanup on Ctrl+C
    try:
        asyncio.run(
            _run_full_index_async(
                repo_path=repo_path,
                branch=branch,
                languages=languages,
                console=console,
                max_history=max_history,
                force=force,
                since_days=since_days,
            )
        )
    except KeyboardInterrupt:
        # Signal handler should have already exited, but just in case
        _cleanup_and_exit()


async def _run_full_index_async(
    repo_path: Path,
    branch: str | None,
    languages: list[str],
    console: Console,
    max_history: int | None = 100,
    force: bool = False,
    since_days: int | None = None,
) -> None:
    """Async implementation of full indexing with multi-commit support."""
    import time

    from inxr2.adapters.external.git_service import GitService
    from inxr2.adapters.external.treesitter import TreeSitterService
    from inxr2.adapters.persistence.repositories import (
        PostgresCommitRepository,
        PostgresFileRepository,
        PostgresIndexStatusRepository,
        PostgresReferenceRepository,
        PostgresRepositoryAdapter,
        PostgresSymbolRepository,
    )
    from inxr2.domain.entities import Commit, File, IndexStatus
    from inxr2.domain.value_objects import CommitHash

    start_time = time.monotonic()
    stats = IndexingStats()

    # Initialize services
    git_service = GitService()
    parser_service = TreeSitterService()

    # Get repository info
    console.print("[dim]Analyzing repository...[/dim]")
    repo_info = git_service.get_repository_info(repo_path)
    current_branch = branch or repo_info.get("current_branch", "main")
    default_branch = repo_info.get("default_branch", "main")

    # Get list of commits for time travel (oldest first)
    # For non-default branches, only index commits unique to that branch (delta)
    if since_days is not None:
        history_msg = f"last {since_days} days"
    elif max_history:
        history_msg = f"max {max_history}"
    else:
        history_msg = "all"
    console.print(f"[dim]Loading commit history ({history_msg})...[/dim]")

    is_default_branch = current_branch in (default_branch, "main", "master")
    if is_default_branch:
        # Default branch: index all commits
        commits_to_index = git_service.list_commits(
            repo_path, current_branch, max_history, since_days=since_days
        )
    else:
        # Feature branch: only index commits unique to this branch (delta from default)
        console.print(f"  [dim]Getting branch delta from {default_branch}...[/dim]")
        commits_to_index = git_service.list_branch_commits(
            repo_path,
            current_branch,
            default_branch,
            max_history,
            since_days=since_days,
        )

    if not commits_to_index:
        if since_days is not None:
            # No commits in date range, but always index HEAD
            console.print(
                f"[yellow]No commits in last {since_days} days. "
                f"Indexing HEAD only.[/yellow]"
            )
            head_commit = git_service.get_current_commit(repo_path, current_branch)
            head_info = git_service.get_commit_info(repo_path, head_commit)
            commits_to_index = [head_info]
        else:
            console.print("[yellow]No commits found for this branch.[/yellow]")
            if not is_default_branch:
                console.print(
                    f"[dim]This may mean the branch has no unique commits vs {default_branch}.[/dim]"
                )
            return

    oldest_commit = commits_to_index[0]
    newest_commit = commits_to_index[-1]

    console.print(f"  Branch: [cyan]{current_branch}[/cyan]")
    if not is_default_branch:
        console.print(f"  [dim]Branch delta from: {default_branch}[/dim]")
    console.print(f"  Commits to index: [green]{len(commits_to_index)}[/green]")
    oldest_date = oldest_commit["commit_date"].strftime("%Y-%m-%d")
    newest_date = newest_commit["commit_date"].strftime("%Y-%m-%d")
    console.print(
        f"  Oldest commit: [dim]{oldest_commit['short_hash']} ({oldest_date})[/dim]"
    )
    console.print(
        f"  Newest commit: [cyan]{newest_commit['short_hash']} ({newest_date})[/cyan]"
    )
    console.print()

    # Set up database connection
    console.print("[dim]Connecting to database...[/dim]")
    db = DatabaseConnection()

    try:
        async with db.session() as session:
            console.print("  [dim]Initializing...[/dim]")
            # Initialize repositories
            repo_repository = PostgresRepositoryAdapter(session)
            commit_repository = PostgresCommitRepository(session)
            file_repository = PostgresFileRepository(session)
            symbol_repository = PostgresSymbolRepository(session)
            reference_repository = PostgresReferenceRepository(session)
            index_status_repository = PostgresIndexStatusRepository(session)

            # Get or create repository record (atomic upsert to avoid race conditions)
            repo_name = repo_info.get("name", repo_path.name)
            db_repo, created = await repo_repository.get_or_create(
                name=repo_name,
                url=str(repo_path.absolute()),
                description=f"Indexed from {repo_path}",
                default_branch=current_branch,
            )
            if created:
                console.print(f"  Created repository: [green]{repo_name}[/green]")
            else:
                console.print(f"  Using repository: [cyan]{repo_name}[/cyan]")

            # Ensure repository has an ID after save (for downstream operations)
            if db_repo.id is None:
                raise RuntimeError("Repository record missing database ID after save")
            repo_id = db_repo.id

            # If force flag is set, clear all existing data for this repository
            if force:
                console.print(
                    "  [yellow]Force mode:[/yellow] Clearing existing data..."
                )
                # Use raw SQL for faster bulk deletion
                from sqlalchemy import text

                await session.execute(
                    text('DELETE FROM "references" WHERE repository_id = :repo_id'),
                    {"repo_id": repo_id},
                )
                console.print("    Cleared references")
                await session.execute(
                    text("DELETE FROM symbols WHERE repository_id = :repo_id"),
                    {"repo_id": repo_id},
                )
                console.print("    Cleared symbols")
                await session.execute(
                    text("DELETE FROM files WHERE repository_id = :repo_id"),
                    {"repo_id": repo_id},
                )
                console.print("    Cleared files")
                await session.execute(
                    text("DELETE FROM commits WHERE repository_id = :repo_id"),
                    {"repo_id": repo_id},
                )
                console.print("    Cleared commits")
                await session.execute(
                    text("DELETE FROM index_status WHERE repository_id = :repo_id"),
                    {"repo_id": repo_id},
                )
                console.print("    Cleared index status")
                await session.flush()
                console.print("  [green]Existing data cleared[/green]")

            # Update index status to in_progress
            index_status = await index_status_repository.find_by_repository_and_branch(
                repo_id, current_branch
            )
            if index_status is None:
                index_status = IndexStatus(
                    repository_id=repo_id,
                    branch=current_branch,
                    indexing_status="in_progress",
                    indexing_started_at=_utc_now(),
                    indexer_version=INDEXER_VERSION,
                )
            else:
                # Create updated status (frozen dataclass)
                index_status = IndexStatus(
                    id=index_status.id,
                    repository_id=repo_id,
                    branch=current_branch,
                    indexing_status="in_progress",
                    indexing_started_at=_utc_now(),
                    last_indexed_commit=index_status.last_indexed_commit,
                    oldest_indexed_commit=index_status.oldest_indexed_commit,
                    last_indexed_at=index_status.last_indexed_at,
                    total_commits_indexed=index_status.total_commits_indexed,
                    total_files_indexed=0,  # Reset for full index
                    total_symbols_indexed=0,
                    total_references_indexed=0,
                    error_count=0,
                    indexer_version=INDEXER_VERSION,
                )
            index_status = await index_status_repository.save(index_status)

            console.print()

            # Pre-calculate total files for progress tracking
            console.print("[dim]Calculating files to index...[/dim]")
            total_files_estimate = 0
            num_commits = len(commits_to_index)
            for i, commit_info in enumerate(commits_to_index):
                all_files = git_service.list_files(repo_path, commit_info["hash"])
                total_files_estimate += len(
                    _filter_files_by_language(all_files, languages)
                )
                # Show progress every 10 commits or at the end
                if (i + 1) % 10 == 0 or i == num_commits - 1:
                    console.print(
                        f"  [dim]Scanned {i + 1}/{num_commits} commits "
                        f"({total_files_estimate} files so far)[/dim]"
                    )
            console.print(
                f"  Total: [cyan]{num_commits}[/cyan] commits, "
                f"[cyan]{total_files_estimate}[/cyan] files"
            )
            console.print()

            # Load content hash -> file_id map for fast donor lookup
            with console.status("[dim]Loading content hash cache...[/dim]"):
                content_hash_cache: dict[str, int] = (
                    await file_repository.get_content_hash_to_file_id_map(repo_id)
                )
            console.print(f"  Cached hashes: [cyan]{len(content_hash_cache)}[/cyan]")
            console.print()

            # Initialize Tree-sitter parsers before starting (shows INFO message)
            _ = parser_service

            # Index each commit from oldest to newest
            console.print("[dim]Indexing files...[/dim]")
            files_indexed_so_far = 0
            last_progress_pct = -1  # Start at -1 so 0% is printed
            with create_progress() as progress:
                commit_task = progress.add_task(
                    "[green]Indexing commits...",
                    total=len(commits_to_index),
                )
                file_task = progress.add_task(
                    "[cyan]Files...",
                    total=total_files_estimate,
                    visible=True,
                )

                for commit_info in commits_to_index:
                    commit_hash = commit_info["hash"]
                    short_hash = commit_info["short_hash"]

                    # Get or create commit record
                    # Commits are unique by (repository_id, commit_hash) - same
                    # commit on multiple branches shares the same record
                    db_commit = await commit_repository.find_by_hash(
                        repo_id, commit_hash
                    )
                    if db_commit is None:
                        # Note: Author info, message, parent_hashes are NOT stored.
                        # They are queried from git on-demand. See ARCHITECTURAL_REVIEW.md.
                        db_commit = await commit_repository.save(
                            Commit(
                                repository_id=repo_id,
                                commit_hash=CommitHash(value=commit_hash),
                                author_date=_to_naive_utc(
                                    commit_info.get("author_date")
                                )
                                or _utc_now(),
                                commit_date=_to_naive_utc(
                                    commit_info.get("commit_date")
                                )
                                or _utc_now(),
                            )
                        )
                    if db_commit.id is None:
                        raise RuntimeError(
                            "Commit record missing database ID after save"
                        )
                    commit_id = db_commit.id

                    # Link commit to the current branch (idempotent)
                    await commit_repository.link_commit_to_branch(
                        repo_id, commit_id, current_branch
                    )

                    # Get files at this commit
                    all_files = git_service.list_files(repo_path, commit_hash)
                    files_to_index = _filter_files_by_language(all_files, languages)

                    # Index each file at this commit
                    for file_path in files_to_index:
                        try:
                            # Check if file already exists for this commit
                            existing_file = await file_repository.find_by_path(
                                repo_id, commit_id, file_path
                            )

                            if existing_file:
                                # Skip - already indexed, but still count for progress
                                files_indexed_so_far += 1
                                progress.update(
                                    file_task, completed=files_indexed_so_far
                                )
                                continue

                            # Get file content
                            content = git_service.get_file_content(
                                repo_path, commit_hash, file_path
                            )

                            # Calculate content hash
                            content_hash = hashlib.sha1(
                                content.encode("utf-8")
                            ).hexdigest()

                            # Detect language
                            language = _detect_language(file_path)

                            # Check cache for donor file with same content (in-memory lookup)
                            donor_file_id = content_hash_cache.get(content_hash)

                            # Create new file record
                            db_file = await file_repository.save(
                                File(
                                    repository_id=repo_id,
                                    commit_id=commit_id,
                                    path=file_path,
                                    content_hash=content_hash,
                                    size_bytes=len(content.encode("utf-8")),
                                    language=language,
                                    line_count=content.count("\n") + 1,
                                )
                            )
                            if db_file.id is None:
                                raise RuntimeError(
                                    "File record missing database ID after save"
                                )
                            file_id = db_file.id

                            # Content-hash reuse: copy symbols/refs from donor
                            if donor_file_id is not None:
                                # REUSE: Copy symbols/references from donor file
                                symbols_copied = (
                                    await symbol_repository.copy_symbols_to_file(
                                        source_file_id=donor_file_id,
                                        target_file_id=file_id,
                                        target_commit_id=commit_id,
                                        target_repository_id=repo_id,
                                    )
                                )
                                refs_copied = (
                                    await reference_repository.copy_references_to_file(
                                        source_file_id=donor_file_id,
                                        target_file_id=file_id,
                                        target_commit_id=commit_id,
                                        target_repository_id=repo_id,
                                    )
                                )
                                stats.files_reused += 1
                                stats.symbols_reused += symbols_copied
                                stats.references_reused += refs_copied
                                # Also count for overall stats (for index_status)
                                stats.symbols_found += symbols_copied
                                stats.references_found += refs_copied
                            else:
                                # PARSE: No donor, use Tree-sitter as usual
                                if language and parser_service.supports_language(
                                    language
                                ):
                                    symbol_dicts, ref_dicts = (
                                        await parser_service.parse_file(
                                            content=content,
                                            language=language,
                                            file_path=file_path,
                                        )
                                    )

                                    # Convert and save symbols
                                    if symbol_dicts:
                                        symbols = [
                                            _dict_to_symbol(
                                                s,
                                                file_id=file_id,
                                                repository_id=db_repo.id,
                                                commit_id=commit_id,
                                            )
                                            for s in symbol_dicts
                                        ]
                                        await symbol_repository.save_many(symbols)
                                        stats.symbols_found += len(symbols)

                                    # Convert and save references
                                    if ref_dicts:
                                        references = [
                                            _dict_to_reference(
                                                r,
                                                source_file_id=file_id,
                                                repository_id=repo_id,
                                                commit_id=commit_id,
                                            )
                                            for r in ref_dicts
                                        ]
                                        await reference_repository.save_many(references)
                                        stats.references_found += len(references)

                                # Add to cache so later files can reuse
                                content_hash_cache[content_hash] = file_id

                            stats.files_processed += 1

                        except Exception as e:
                            stats.files_failed += 1
                            stats.errors.append(f"{file_path}@{short_hash}: {str(e)}")
                            logger.warning(
                                f"Failed to index {file_path}@{short_hash}: {e}"
                            )

                        # Update file progress after each file
                        files_indexed_so_far += 1
                        progress.update(file_task, completed=files_indexed_so_far)

                        # Print progress: 0%, 1%, 2%, 5%, then every 10%
                        if total_files_estimate > 0:
                            current_pct = (
                                files_indexed_so_far * 100
                            ) // total_files_estimate
                            # Milestones: 0, 1, 2, 5, 10, 20, 30, ...
                            milestones = {
                                0,
                                1,
                                2,
                                5,
                                10,
                                20,
                                30,
                                40,
                                50,
                                60,
                                70,
                                80,
                                90,
                                100,
                            }
                            if (
                                current_pct in milestones
                                and current_pct > last_progress_pct
                            ):
                                last_progress_pct = current_pct
                                progress.console.print(
                                    f"  [dim]{current_pct}% complete "
                                    f"({files_indexed_so_far}/{total_files_estimate} files, "
                                    f"{stats.symbols_found} symbols, "
                                    f"cache: {len(content_hash_cache)})[/dim]"
                                )
                    progress.update(commit_task, advance=1)

                progress.update(
                    file_task,
                    description="[green]Complete[/green]",
                    completed=total_files_estimate,
                )

            # Resolve references to symbols (commit-aware for time travel consistency)
            console.print("[cyan]Resolving references (commit-aware)...[/cyan]")
            resolve_use_case = ResolveReferencesUseCase(
                reference_repository=reference_repository
            )
            resolve_result = await resolve_use_case.execute(
                ResolveReferencesRequest(repository_id=repo_id, commit_aware=True)
            )
            stats.references_resolved = resolve_result.resolved_count
            console.print(
                f"[green]Resolved {stats.references_resolved} references to symbols[/green]"
            )

            # Update index status to completed
            index_status = IndexStatus(
                id=index_status.id,
                repository_id=repo_id,
                branch=current_branch,
                indexing_status="completed",
                last_indexed_commit=newest_commit["hash"],
                oldest_indexed_commit=oldest_commit["hash"],
                last_indexed_at=_utc_now(),
                indexing_started_at=index_status.indexing_started_at,
                total_commits_indexed=len(commits_to_index),
                total_files_indexed=stats.files_succeeded,
                total_symbols_indexed=stats.symbols_found,
                total_references_indexed=stats.references_found,
                error_count=stats.files_failed,
                error_message=(stats.errors[0] if stats.errors else None),
                indexer_version=INDEXER_VERSION,
            )
            await index_status_repository.save(index_status)

    finally:
        await db.close()

    # Print summary with commit info and elapsed time
    elapsed_seconds = time.monotonic() - start_time
    _print_summary(
        console,
        stats,
        commits_indexed=len(commits_to_index),
        elapsed_seconds=elapsed_seconds,
    )


def run_incremental_index(
    repo_path: Path,
    branch: str | None,
    languages: list[str],
    console: Console,
    max_history: int = 1,  # Ignored for incremental - only indexes since last commit
    force: bool = False,  # Ignored for incremental - accepted for API compatibility
) -> None:
    """
    Run incremental indexing of a repository.

    Only indexes files that have changed since the last index.
    The max_history and force parameters are accepted for API compatibility
    but ignored (incremental always indexes from the last indexed commit to HEAD).
    """
    # Set up signal handlers for clean shutdown on Ctrl+C
    _setup_signal_handlers()

    try:
        asyncio.run(
            _run_incremental_index_async(
                repo_path=repo_path,
                branch=branch,
                languages=languages,
                console=console,
            )
        )
    except KeyboardInterrupt:
        # Signal handler should have already exited, but just in case
        _cleanup_and_exit()


async def _run_incremental_index_async(
    repo_path: Path,
    branch: str | None,
    languages: list[str],
    console: Console,
) -> None:
    """Async implementation of incremental indexing."""
    import time

    from inxr2.adapters.external.git_service import GitService
    from inxr2.adapters.external.treesitter import TreeSitterService
    from inxr2.adapters.persistence.repositories import (
        PostgresCommitRepository,
        PostgresFileRepository,
        PostgresIndexStatusRepository,
        PostgresReferenceRepository,
        PostgresRepositoryAdapter,
        PostgresSymbolRepository,
    )
    from inxr2.domain.entities import Commit, File, IndexStatus
    from inxr2.domain.value_objects import CommitHash

    start_time = time.monotonic()
    stats = IndexingStats()

    # Initialize services
    git_service = GitService()
    parser_service = TreeSitterService()

    # Get repository info
    console.print("[dim]Analyzing repository...[/dim]")
    repo_info = git_service.get_repository_info(repo_path)
    current_branch = branch or repo_info.get("current_branch", "main")
    current_commit = git_service.get_current_commit(repo_path, current_branch)

    console.print(f"  Current commit: [cyan]{current_commit[:8]}[/cyan]")
    console.print(f"  Branch: [cyan]{current_branch}[/cyan]")

    # Connect to database and check last indexed commit
    console.print("[dim]Checking index status...[/dim]")
    db = DatabaseConnection()

    try:
        async with db.session() as session:
            repo_repository = PostgresRepositoryAdapter(session)
            index_status_repository = PostgresIndexStatusRepository(session)

            # Find repository
            repo_name = repo_info.get("name", repo_path.name)
            db_repo = await repo_repository.find_by_name(repo_name)

            if db_repo is None:
                msg = "[yellow]No previous index. Running full index.[/yellow]"
                console.print(f"\n{msg}")
                await db.close()
                await _run_full_index_async(repo_path, branch, languages, console)
                return

            # Ensure repository ID is available
            if db_repo.id is None:
                msg = "[red]Repository record missing database ID; aborting incremental index.[/red]"
                console.print(f"\n{msg}")
                await db.close()
                raise RuntimeError("Repository record missing database ID")

            repo_id = db_repo.id

            # Check index status
            index_status = await index_status_repository.find_by_repository_and_branch(
                repo_id, current_branch
            )

            if index_status is None or index_status.last_indexed_commit is None:
                msg = "[yellow]No previous index. Running full index.[/yellow]"
                console.print(f"\n{msg}")
                await db.close()
                await _run_full_index_async(repo_path, branch, languages, console)
                return

            last_indexed_commit = index_status.last_indexed_commit

            if last_indexed_commit == current_commit:
                console.print(
                    "\n[green]Already up to date![/green] No changes since last index."
                )
                return

            console.print(f"  Last indexed: [dim]{last_indexed_commit[:8]}[/dim]")
            console.print()

            # Get changed files
            console.print("[dim]Detecting changes...[/dim]")
            changed_files = git_service.get_changed_files(
                repo_path, last_indexed_commit, current_commit
            )

            # Filter by languages
            added_modified = _filter_files_by_language(
                changed_files.get("added", []) + changed_files.get("modified", []),
                languages,
            )
            deleted = changed_files.get("deleted", [])

            console.print(f"  Added/Modified: [green]{len(added_modified)}[/green]")
            console.print(f"  Deleted: [red]{len(deleted)}[/red]")
            console.print()

            stats.files_total = len(added_modified)

            if stats.files_total == 0 and len(deleted) == 0:
                console.print("[green]No relevant changes found.[/green]")
                return

            # Initialize remaining repositories
            commit_repository = PostgresCommitRepository(session)
            file_repository = PostgresFileRepository(session)
            symbol_repository = PostgresSymbolRepository(session)
            reference_repository = PostgresReferenceRepository(session)

            # Get commit info and create commit record
            commit_info = git_service.get_commit_info(repo_path, current_commit)

            db_commit = await commit_repository.find_by_hash(repo_id, current_commit)
            if db_commit is None:
                # Note: Author info, message, parent_hashes are NOT stored.
                # They are queried from git on-demand. See ARCHITECTURAL_REVIEW.md.
                db_commit = await commit_repository.save(
                    Commit(
                        repository_id=repo_id,
                        commit_hash=CommitHash(value=current_commit),
                        author_date=_to_naive_utc(commit_info.get("author_date"))
                        or _utc_now(),
                        commit_date=_to_naive_utc(commit_info.get("commit_date"))
                        or _utc_now(),
                    )
                )

            if db_commit.id is None:
                raise RuntimeError("Commit record missing database ID after save")
            commit_id = db_commit.id

            # Link commit to the current branch (idempotent)
            await commit_repository.link_commit_to_branch(
                repo_id, commit_id, current_branch
            )

            # Update index status to in_progress
            index_status = IndexStatus(
                id=index_status.id,
                repository_id=repo_id,
                branch=current_branch,
                indexing_status="in_progress",
                indexing_started_at=_utc_now(),
                last_indexed_commit=last_indexed_commit,
                last_indexed_at=index_status.last_indexed_at,
                total_commits_indexed=index_status.total_commits_indexed,
                total_files_indexed=index_status.total_files_indexed,
                total_symbols_indexed=index_status.total_symbols_indexed,
                total_references_indexed=index_status.total_references_indexed,
                indexer_version=INDEXER_VERSION,
            )
            await index_status_repository.save(index_status)

            # Process deletions first (find and delete by path)
            if deleted:
                console.print("[dim]Processing deletions...[/dim]")
                for file_path in deleted:
                    # Find file by path and delete its symbols/references
                    db_file = await file_repository.find_by_path(
                        repo_id, db_commit.id, file_path
                    )
                    if db_file:
                        if db_file.id is None:
                            raise RuntimeError(
                                "Existing file record missing database ID"
                            )
                        await symbol_repository.delete_by_file(db_file.id)
                        await reference_repository.delete_by_file(db_file.id)

            # Index changed files with progress
            if added_modified:
                import hashlib

                # Load content hash -> file_id map for fast donor lookup
                with console.status("[dim]Loading content hash cache...[/dim]"):
                    content_hash_cache: dict[str, int] = (
                        await file_repository.get_content_hash_to_file_id_map(repo_id)
                    )
                console.print(
                    f"  Cached hashes: [cyan]{len(content_hash_cache)}[/cyan]"
                )

                with create_progress() as progress:
                    main_task = progress.add_task(
                        "[green]Indexing changed files...",
                        total=stats.files_total,
                    )
                    file_task = progress.add_task("[dim]Preparing...", total=100)

                    for file_path in added_modified:
                        short_path = _shorten_path(file_path, max_len=50)
                        progress.update(
                            file_task,
                            description=f"[cyan]{short_path}[/cyan]",
                            completed=0,
                        )

                        try:
                            content = git_service.get_file_content(
                                repo_path, current_commit, file_path
                            )
                            progress.update(file_task, completed=20)

                            content_hash = hashlib.sha1(
                                content.encode("utf-8")
                            ).hexdigest()
                            language = _detect_language(file_path)
                            progress.update(file_task, completed=30)

                            # Check cache for donor file (in-memory lookup)
                            donor_file_id = content_hash_cache.get(content_hash)

                            # Create new file record
                            db_file = await file_repository.save(
                                File(
                                    repository_id=repo_id,
                                    commit_id=commit_id,
                                    path=file_path,
                                    content_hash=content_hash,
                                    size_bytes=len(content.encode("utf-8")),
                                    language=language,
                                    line_count=content.count("\n") + 1,
                                )
                            )
                            if db_file.id is None:
                                raise RuntimeError(
                                    "File record missing database ID after save"
                                )
                            file_id = db_file.id
                            progress.update(file_task, completed=50)

                            # Content-hash reuse: copy symbols/refs from donor
                            if donor_file_id is not None:
                                # REUSE: Copy symbols/references from donor file
                                symbols_copied = (
                                    await symbol_repository.copy_symbols_to_file(
                                        source_file_id=donor_file_id,
                                        target_file_id=file_id,
                                        target_commit_id=commit_id,
                                        target_repository_id=repo_id,
                                    )
                                )
                                progress.update(file_task, completed=70)
                                refs_copied = (
                                    await reference_repository.copy_references_to_file(
                                        source_file_id=donor_file_id,
                                        target_file_id=file_id,
                                        target_commit_id=commit_id,
                                        target_repository_id=repo_id,
                                    )
                                )
                                progress.update(file_task, completed=100)
                                stats.files_reused += 1
                                stats.symbols_reused += symbols_copied
                                stats.references_reused += refs_copied
                                # Also count for overall stats (for index_status)
                                stats.symbols_found += symbols_copied
                                stats.references_found += refs_copied
                            elif language and parser_service.supports_language(
                                language
                            ):
                                # PARSE: No donor, use Tree-sitter as usual
                                symbol_dicts, ref_dicts = (
                                    await parser_service.parse_file(
                                        content=content,
                                        language=language,
                                        file_path=file_path,
                                    )
                                )
                                progress.update(file_task, completed=70)

                                # Save symbols
                                if symbol_dicts:
                                    symbols = [
                                        _dict_to_symbol(
                                            s,
                                            file_id=file_id,
                                            repository_id=repo_id,
                                            commit_id=commit_id,
                                        )
                                        for s in symbol_dicts
                                    ]
                                    await symbol_repository.save_many(symbols)
                                    stats.symbols_found += len(symbols)
                                progress.update(file_task, completed=85)

                                # Save references
                                if ref_dicts:
                                    references = [
                                        _dict_to_reference(
                                            r,
                                            source_file_id=file_id,
                                            repository_id=repo_id,
                                            commit_id=commit_id,
                                        )
                                        for r in ref_dicts
                                    ]
                                    await reference_repository.save_many(references)
                                    stats.references_found += len(references)
                                progress.update(file_task, completed=100)

                                # Add to cache so later files can reuse
                                content_hash_cache[content_hash] = file_id

                            stats.files_processed += 1

                        except Exception as e:
                            stats.files_failed += 1
                            stats.errors.append(f"{file_path}: {str(e)}")
                            logger.warning(f"Failed to index {file_path}: {e}")

                        progress.update(main_task, advance=1)

                    progress.update(
                        file_task, description="[green]Complete[/green]", completed=100
                    )

            # Resolve references to symbols (cross-commit for incremental indexing)
            console.print("[cyan]Resolving references...[/cyan]")
            resolve_use_case = ResolveReferencesUseCase(
                reference_repository=reference_repository
            )
            resolve_result = await resolve_use_case.execute(
                ResolveReferencesRequest(repository_id=repo_id, commit_aware=False)
            )
            stats.references_resolved = resolve_result.resolved_count
            console.print(
                f"[green]Resolved {stats.references_resolved} references to symbols[/green]"
            )

            # Update index status to completed
            index_status = IndexStatus(
                id=index_status.id,
                repository_id=repo_id,
                branch=current_branch,
                indexing_status="completed",
                last_indexed_commit=current_commit,
                last_indexed_at=_utc_now(),
                indexing_started_at=index_status.indexing_started_at,
                total_commits_indexed=index_status.total_commits_indexed + 1,
                total_files_indexed=index_status.total_files_indexed
                + stats.files_succeeded,
                total_symbols_indexed=index_status.total_symbols_indexed
                + stats.symbols_found,
                total_references_indexed=index_status.total_references_indexed
                + stats.references_found,
                error_count=stats.files_failed,
                error_message=stats.errors[0] if stats.errors else None,
                indexer_version=INDEXER_VERSION,
            )
            await index_status_repository.save(index_status)

    finally:
        await db.close()

    elapsed_seconds = time.monotonic() - start_time
    _print_summary(console, stats, is_incremental=True, elapsed_seconds=elapsed_seconds)


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
    current_branch = repo_info.get("current_branch", "unknown")
    current_commit = git_service.get_current_commit(repo_path, current_branch)
    repo_name = repo_info.get("name", repo_path.name)

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


def _print_summary(
    console: Console,
    stats: IndexingStats,
    is_incremental: bool = False,
    commits_indexed: int | None = None,
    elapsed_seconds: float | None = None,
) -> None:
    """Print indexing summary."""
    console.print()

    index_type = "Incremental" if is_incremental else "Full"

    # Create summary table
    table = Table(title=f"{index_type} Index Complete", show_header=False, box=None)
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    if commits_indexed is not None:
        table.add_row("Commits Indexed", f"[magenta]{commits_indexed}[/magenta]")
    table.add_row("Files Processed", f"[green]{stats.files_succeeded}[/green]")
    if stats.files_skipped > 0:
        table.add_row("Files Skipped", f"[dim]{stats.files_skipped}[/dim]")
    if stats.files_failed > 0:
        table.add_row("Files Failed", f"[red]{stats.files_failed}[/red]")
    table.add_row("Symbols Found", f"[cyan]{stats.symbols_found}[/cyan]")
    table.add_row("References Found", f"[cyan]{stats.references_found}[/cyan]")
    table.add_row("References Resolved", f"[cyan]{stats.references_resolved}[/cyan]")

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
