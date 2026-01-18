"""
Index command implementation.

Handles full and incremental indexing with rich progress output.
"""

import asyncio
import hashlib
import logging
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

logger = logging.getLogger(__name__)

# Indexer version for tracking
INDEXER_VERSION = "0.1.0"


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
    max_history: int = 100,
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
        max_history: Maximum number of commits to index (default: 100)
    """
    # Run the async indexing in an event loop
    asyncio.run(
        _run_full_index_async(
            repo_path=repo_path,
            branch=branch,
            languages=languages,
            console=console,
            max_history=max_history,
        )
    )


async def _run_full_index_async(
    repo_path: Path,
    branch: str | None,
    languages: list[str],
    console: Console,
    max_history: int = 100,
) -> None:
    """Async implementation of full indexing with multi-commit support."""
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
    from inxr2.infrastructure.database.connection import DatabaseConnection

    stats = IndexingStats()

    # Initialize services
    git_service = GitService()
    parser_service = TreeSitterService()

    # Get repository info
    console.print("[dim]Analyzing repository...[/dim]")
    repo_info = git_service.get_repository_info(repo_path)
    current_branch = branch or repo_info.get("current_branch", "main")

    # Get list of commits for time travel (oldest first)
    console.print(f"[dim]Loading commit history (max {max_history} commits)...[/dim]")
    commits_to_index = git_service.list_commits(repo_path, current_branch, max_history)

    if not commits_to_index:
        console.print("[yellow]No commits found for this branch.[/yellow]")
        return

    oldest_commit = commits_to_index[0]
    newest_commit = commits_to_index[-1]

    console.print(f"  Branch: [cyan]{current_branch}[/cyan]")
    console.print(f"  Commits to index: [green]{len(commits_to_index)}[/green]")
    console.print(f"  Oldest commit: [dim]{oldest_commit['short_hash']}[/dim]")
    console.print(f"  Newest commit: [cyan]{newest_commit['short_hash']}[/cyan]")
    console.print()

    # Set up database connection
    console.print("[dim]Connecting to database...[/dim]")
    db = DatabaseConnection()

    try:
        async with db.session() as session:
            # Initialize repositories
            repo_repository = PostgresRepositoryAdapter(session)
            commit_repository = PostgresCommitRepository(session)
            file_repository = PostgresFileRepository(session)
            symbol_repository = PostgresSymbolRepository(session)
            reference_repository = PostgresReferenceRepository(session)
            index_status_repository = PostgresIndexStatusRepository(session)

            # Get or create repository record
            repo_name = repo_info.get("name", repo_path.name)
            db_repo = await repo_repository.find_by_name(repo_name)
            if db_repo is None:
                from inxr2.domain.entities import Repository

                db_repo = await repo_repository.save(
                    Repository(
                        name=repo_name,
                        # Store local path for file content retrieval
                        url=str(repo_path.absolute()),
                        description=f"Indexed from {repo_path}",
                        default_branch=current_branch,
                    )
                )
                console.print(f"  Created repository: [green]{repo_name}[/green]")
            else:
                console.print(f"  Using repository: [cyan]{repo_name}[/cyan]")

            # Ensure repository has an ID after save (for downstream operations)
            if db_repo.id is None:
                raise RuntimeError("Repository record missing database ID after save")
            repo_id = db_repo.id

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

            # Index each commit from oldest to newest
            with create_progress() as progress:
                commit_task = progress.add_task(
                    "[green]Indexing commits...",
                    total=len(commits_to_index),
                )
                file_task = progress.add_task(
                    "[dim]Preparing...",
                    total=100,
                    visible=True,
                )

                for commit_info in commits_to_index:
                    commit_hash = commit_info["hash"]
                    short_hash = commit_info["short_hash"]

                    progress.update(
                        file_task,
                        description=f"[cyan]Commit {short_hash}[/cyan]",
                        completed=0,
                    )

                    # Get or create commit record
                    db_commit = await commit_repository.find_by_hash(
                        repo_id, commit_hash
                    )
                    if db_commit is None:
                        db_commit = await commit_repository.save(
                            Commit(
                                repository_id=repo_id,
                                commit_hash=CommitHash(value=commit_hash),
                                short_hash=short_hash,
                                parent_hashes=commit_info.get("parent_hashes", []),
                                branch=current_branch,
                                author_name=commit_info.get("author_name", "unknown"),
                                author_email=commit_info.get("author_email", ""),
                                committer_name=commit_info.get(
                                    "committer_name", "unknown"
                                ),
                                committer_email=commit_info.get("committer_email", ""),
                                author_date=_to_naive_utc(
                                    commit_info.get("author_date")
                                )
                                or _utc_now(),
                                commit_date=_to_naive_utc(
                                    commit_info.get("commit_date")
                                )
                                or _utc_now(),
                                message=commit_info.get("message", ""),
                            )
                        )
                    if db_commit.id is None:
                        raise RuntimeError(
                            "Commit record missing database ID after save"
                        )
                    commit_id = db_commit.id

                    progress.update(file_task, completed=10)

                    # Get files at this commit
                    all_files = git_service.list_files(repo_path, commit_hash)
                    files_to_index = _filter_files_by_language(all_files, languages)

                    progress.update(file_task, completed=20)

                    # Index each file at this commit
                    for file_path in files_to_index:
                        try:
                            # Check if file already exists for this commit
                            existing_file = await file_repository.find_by_path(
                                repo_id, commit_id, file_path
                            )

                            if existing_file:
                                # Skip - already indexed
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

                            # Parse file and extract symbols
                            if language and parser_service.supports_language(language):
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

                            stats.files_processed += 1

                        except Exception as e:
                            stats.files_failed += 1
                            stats.errors.append(f"{file_path}@{short_hash}: {str(e)}")
                            logger.warning(
                                f"Failed to index {file_path}@{short_hash}: {e}"
                            )

                    progress.update(file_task, completed=100)
                    progress.update(commit_task, advance=1)

                progress.update(
                    file_task, description="[green]Complete[/green]", completed=100
                )

            # Resolve references to symbols (commit-aware)
            stats.references_resolved = await resolve_references_commit_aware(
                repo_id, session, console
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

    # Print summary with commit info
    _print_summary(console, stats, commits_indexed=len(commits_to_index))


def run_incremental_index(
    repo_path: Path,
    branch: str | None,
    languages: list[str],
    console: Console,
) -> None:
    """
    Run incremental indexing of a repository.

    Only indexes files that have changed since the last index.
    """
    asyncio.run(
        _run_incremental_index_async(
            repo_path=repo_path,
            branch=branch,
            languages=languages,
            console=console,
        )
    )


async def _run_incremental_index_async(
    repo_path: Path,
    branch: str | None,
    languages: list[str],
    console: Console,
) -> None:
    """Async implementation of incremental indexing."""
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
    from inxr2.infrastructure.database.connection import DatabaseConnection

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
                db_commit = await commit_repository.save(
                    Commit(
                        repository_id=repo_id,
                        commit_hash=CommitHash(value=current_commit),
                        short_hash=current_commit[:7],
                        parent_hashes=commit_info.get("parent_hashes", []),
                        branch=current_branch,
                        author_name=commit_info.get("author_name", "unknown"),
                        author_email=commit_info.get("author_email", ""),
                        committer_name=commit_info.get("committer_name", "unknown"),
                        committer_email=commit_info.get("committer_email", ""),
                        author_date=_to_naive_utc(commit_info.get("author_date"))
                        or _utc_now(),
                        commit_date=_to_naive_utc(commit_info.get("commit_date"))
                        or _utc_now(),
                        message=commit_info.get("message", ""),
                    )
                )

            if db_commit.id is None:
                raise RuntimeError("Commit record missing database ID after save")
            commit_id = db_commit.id

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

                            if language and parser_service.supports_language(language):
                                # Parse and extract
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

                            stats.files_processed += 1

                        except Exception as e:
                            stats.files_failed += 1
                            stats.errors.append(f"{file_path}: {str(e)}")
                            logger.warning(f"Failed to index {file_path}: {e}")

                        progress.update(main_task, advance=1)

                    progress.update(
                        file_task, description="[green]Complete[/green]", completed=100
                    )

            # Resolve references to symbols
            stats.references_resolved = await resolve_references(
                repo_id, session, console
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

    _print_summary(console, stats, is_incremental=True)


def show_index_status(repo_path: Path, console: Console) -> None:
    """Show indexing status for a repository."""
    asyncio.run(_show_index_status_async(repo_path, console))


async def _show_index_status_async(repo_path: Path, console: Console) -> None:
    """Async implementation of index status."""
    from inxr2.adapters.external.git_service import GitService
    from inxr2.adapters.persistence.repositories import (
        PostgresIndexStatusRepository,
        PostgresRepositoryAdapter,
    )
    from inxr2.infrastructure.database.connection import DatabaseConnection

    git_service = GitService()

    # Get repository info
    repo_info = git_service.get_repository_info(repo_path)
    current_branch = repo_info.get("current_branch", "unknown")
    current_commit = git_service.get_current_commit(repo_path, current_branch)

    # Connect to database
    db = DatabaseConnection()

    try:
        async with db.session() as session:
            repo_repository = PostgresRepositoryAdapter(session)
            index_status_repository = PostgresIndexStatusRepository(session)

            # Find repository
            repo_name = repo_info.get("name", repo_path.name)
            db_repo = await repo_repository.find_by_name(repo_name)

            # Create status table
            table = Table(show_header=False, box=None)
            table.add_column("Property", style="dim")
            table.add_column("Value")

            table.add_row("Repository", repo_info.get("name", str(repo_path)))
            table.add_row("Current Branch", current_branch)
            table.add_row(
                "Current Commit", current_commit[:8] if current_commit else "unknown"
            )
            table.add_row("", "")

            if db_repo:
                if db_repo.id is None:
                    index_status = None
                else:
                    repo_id = db_repo.id
                    index_status = (
                        await index_status_repository.find_by_repository_and_branch(
                            repo_id, current_branch
                        )
                    )

                if index_status and index_status.last_indexed_commit:
                    table.add_row(
                        "Last Indexed Commit", index_status.last_indexed_commit[:8]
                    )
                    table.add_row(
                        "Last Indexed At",
                        (
                            index_status.last_indexed_at.isoformat()
                            if index_status.last_indexed_at
                            else "unknown"
                        ),
                    )
                    table.add_row(
                        "Files Indexed", str(index_status.total_files_indexed)
                    )
                    table.add_row(
                        "Symbols Indexed", str(index_status.total_symbols_indexed)
                    )
                    table.add_row(
                        "References Indexed",
                        str(index_status.total_references_indexed),
                    )

                    if index_status.last_indexed_commit == current_commit:
                        table.add_row("Status", "[green]Up to date[/green]")
                    else:
                        table.add_row("Status", "[yellow]Updates available[/yellow]")
                else:
                    table.add_row("Status", "[red]Not indexed[/red]")
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


def _print_summary(
    console: Console,
    stats: IndexingStats,
    is_incremental: bool = False,
    commits_indexed: int | None = None,
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
        "type": SymbolKind.NAMESPACE,  # Map type aliases to namespace for now
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


async def resolve_references(
    repository_id: int,
    session: Any,
    console: Console,
) -> int:
    """
    Resolve references to their target symbols.

    After indexing, this function matches reference_text to symbol names
    and updates the target_symbol_id for each reference.

    Args:
        repository_id: The repository ID to resolve references for
        session: Database session
        console: Rich console for output

    Returns:
        Number of references resolved
    """
    from sqlalchemy import text

    console.print("[cyan]Resolving references...[/cyan]")

    # Update references where reference_text matches a symbol name
    # in the same repository (function calls, class instantiations, etc.)
    result = await session.execute(
        text(
            """
            UPDATE "references" r
            SET target_symbol_id = s.id
            FROM symbols s
            WHERE r.repository_id = :repo_id
              AND s.repository_id = :repo_id
              AND r.reference_text = s.name
              AND r.target_symbol_id IS NULL
        """
        ),
        {"repo_id": repository_id},
    )
    await session.commit()

    resolved_count = result.rowcount or 0
    console.print(f"[green]Resolved {resolved_count} references to symbols[/green]")

    return resolved_count


async def resolve_references_commit_aware(
    repository_id: int,
    session: Any,
    console: Console,
) -> int:
    """
    Resolve references to their target symbols with commit awareness.

    For time travel support, references are matched to symbols from the same
    commit, ensuring that navigation stays within the same version of the code.

    Args:
        repository_id: The repository ID to resolve references for
        session: Database session
        console: Rich console for output

    Returns:
        Number of references resolved
    """
    from sqlalchemy import text

    console.print("[cyan]Resolving references (commit-aware)...[/cyan]")

    # Update references where reference_text matches a symbol name
    # in the same repository AND same commit (for time travel consistency)
    result = await session.execute(
        text(
            """
            UPDATE "references" r
            SET target_symbol_id = s.id
            FROM symbols s
            WHERE r.repository_id = :repo_id
              AND s.repository_id = :repo_id
              AND r.commit_id = s.commit_id
              AND r.reference_text = s.name
              AND r.target_symbol_id IS NULL
        """
        ),
        {"repo_id": repository_id},
    )
    await session.commit()

    resolved_count = result.rowcount or 0
    console.print(f"[green]Resolved {resolved_count} references to symbols[/green]")

    return resolved_count
