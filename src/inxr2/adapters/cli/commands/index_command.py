"""
Index command implementation.

Handles full and incremental indexing with rich progress output.
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
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


def _to_naive_utc(dt: datetime | None) -> datetime | None:
    """Convert a datetime to timezone-naive UTC.

    PostgreSQL TIMESTAMP WITHOUT TIME ZONE columns expect naive datetimes.
    Git returns timezone-aware datetimes, so we convert them to UTC and strip
    the timezone info.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
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
) -> None:
    """
    Run full indexing of a repository.

    This performs a complete index from scratch, clearing any existing data.
    """
    # Run the async indexing in an event loop
    asyncio.run(
        _run_full_index_async(
            repo_path=repo_path,
            branch=branch,
            languages=languages,
            console=console,
        )
    )


async def _run_full_index_async(
    repo_path: Path,
    branch: str | None,
    languages: list[str],
    console: Console,
) -> None:
    """Async implementation of full indexing."""
    from inxr2.adapters.external.git_service import GitService
    from inxr2.adapters.external.treesitter_service import TreeSitterService
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
    commit_hash = git_service.get_current_commit(repo_path, current_branch)
    commit_info = git_service.get_commit_info(repo_path, commit_hash)

    console.print(f"  Commit: [cyan]{commit_hash[:8]}[/cyan]")
    console.print(f"  Branch: [cyan]{current_branch}[/cyan]")
    console.print()

    # Get list of files to index
    console.print("[dim]Collecting files...[/dim]")
    all_files = git_service.list_files(repo_path, commit_hash)

    # Filter by supported languages
    files_to_index = _filter_files_by_language(all_files, languages)
    stats.files_total = len(files_to_index)
    stats.files_skipped = len(all_files) - len(files_to_index)

    console.print(f"  Total files: {len(all_files)}")
    console.print(f"  Files to index: [green]{stats.files_total}[/green]")
    console.print(f"  Files skipped: [dim]{stats.files_skipped}[/dim]")
    console.print()

    if stats.files_total == 0:
        console.print("[yellow]No files to index for the specified languages.[/yellow]")
        return

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
                        url=repo_info.get("url"),
                        description=f"Indexed from {repo_path}",
                        default_branch=current_branch,
                    )
                )
                console.print(f"  Created repository: [green]{repo_name}[/green]")
            else:
                console.print(f"  Using repository: [cyan]{repo_name}[/cyan]")

            # Get or create commit record
            db_commit = await commit_repository.find_by_hash(db_repo.id, commit_hash)
            if db_commit is None:
                db_commit = await commit_repository.save(
                    Commit(
                        repository_id=db_repo.id,
                        commit_hash=CommitHash(value=commit_hash),
                        short_hash=commit_hash[:7],
                        parent_hashes=commit_info.get("parent_hashes", []),
                        branch=current_branch,
                        author_name=commit_info.get("author_name", "unknown"),
                        author_email=commit_info.get("author_email", ""),
                        committer_name=commit_info.get("committer_name", "unknown"),
                        committer_email=commit_info.get("committer_email", ""),
                        author_date=_to_naive_utc(commit_info.get("author_date")),
                        commit_date=_to_naive_utc(commit_info.get("commit_date")),
                        message=commit_info.get("message", ""),
                    )
                )
                console.print(f"  Created commit: [cyan]{commit_hash[:8]}[/cyan]")

            # Update index status to in_progress
            index_status = await index_status_repository.find_by_repository_and_branch(
                db_repo.id, current_branch
            )
            if index_status is None:
                index_status = IndexStatus(
                    repository_id=db_repo.id,
                    branch=current_branch,
                    indexing_status="in_progress",
                    indexing_started_at=datetime.utcnow(),
                    indexer_version=INDEXER_VERSION,
                )
            else:
                # Create updated status (frozen dataclass)
                index_status = IndexStatus(
                    id=index_status.id,
                    repository_id=db_repo.id,
                    branch=current_branch,
                    indexing_status="in_progress",
                    indexing_started_at=datetime.utcnow(),
                    last_indexed_commit=index_status.last_indexed_commit,
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

            # Index files with progress
            with create_progress() as progress:
                main_task = progress.add_task(
                    "[green]Indexing files...",
                    total=stats.files_total,
                )
                file_task = progress.add_task(
                    "[dim]Preparing...",
                    total=100,
                    visible=True,
                )

                for file_path in files_to_index:
                    short_path = _shorten_path(file_path, max_len=50)
                    progress.update(
                        file_task, description=f"[cyan]{short_path}[/cyan]", completed=0
                    )

                    try:
                        # Get file content
                        content = git_service.get_file_content(
                            repo_path, commit_hash, file_path
                        )
                        progress.update(file_task, completed=20)

                        # Calculate content hash
                        content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()
                        progress.update(file_task, completed=25)

                        # Detect language
                        language = _detect_language(file_path)
                        progress.update(file_task, completed=30)

                        # Create file record
                        db_file = await file_repository.save(
                            File(
                                repository_id=db_repo.id,
                                commit_id=db_commit.id,
                                path=file_path,
                                content_hash=content_hash,
                                size_bytes=len(content.encode("utf-8")),
                                language=language,
                                line_count=content.count("\n") + 1,
                            )
                        )
                        progress.update(file_task, completed=40)

                        # Parse file and extract symbols
                        if language and parser_service.supports_language(language):
                            symbol_dicts, ref_dicts = await parser_service.parse_file(
                                content=content,
                                language=language,
                                file_path=file_path,
                            )
                            progress.update(file_task, completed=60)

                            # Convert and save symbols
                            if symbol_dicts:
                                symbols = [
                                    _dict_to_symbol(
                                        s,
                                        file_id=db_file.id,
                                        repository_id=db_repo.id,
                                        commit_id=db_commit.id,
                                    )
                                    for s in symbol_dicts
                                ]
                                await symbol_repository.save_many(symbols)
                                stats.symbols_found += len(symbols)
                            progress.update(file_task, completed=80)

                            # Convert and save references
                            if ref_dicts:
                                references = [
                                    _dict_to_reference(
                                        r,
                                        source_file_id=db_file.id,
                                        repository_id=db_repo.id,
                                        commit_id=db_commit.id,
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

            # Update index status to completed
            index_status = IndexStatus(
                id=index_status.id,
                repository_id=db_repo.id,
                branch=current_branch,
                indexing_status="completed",
                last_indexed_commit=commit_hash,
                last_indexed_at=datetime.utcnow(),
                indexing_started_at=index_status.indexing_started_at,
                total_commits_indexed=1,
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

    # Print summary
    _print_summary(console, stats)


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
    from inxr2.adapters.external.treesitter_service import TreeSitterService
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
                console.print(
                    "\n[yellow]No previous index found. Running full index instead.[/yellow]"
                )
                await db.close()
                await _run_full_index_async(repo_path, branch, languages, console)
                return

            # Check index status
            index_status = await index_status_repository.find_by_repository_and_branch(
                db_repo.id, current_branch
            )

            if index_status is None or index_status.last_indexed_commit is None:
                console.print(
                    "\n[yellow]No previous index found. Running full index instead.[/yellow]"
                )
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
            db_commit = await commit_repository.find_by_hash(db_repo.id, current_commit)
            if db_commit is None:
                db_commit = await commit_repository.save(
                    Commit(
                        repository_id=db_repo.id,
                        commit_hash=CommitHash(value=current_commit),
                        short_hash=current_commit[:7],
                        parent_hashes=commit_info.get("parent_hashes", []),
                        branch=current_branch,
                        author_name=commit_info.get("author_name", "unknown"),
                        author_email=commit_info.get("author_email", ""),
                        committer_name=commit_info.get("committer_name", "unknown"),
                        committer_email=commit_info.get("committer_email", ""),
                        author_date=_to_naive_utc(commit_info.get("author_date")),
                        commit_date=_to_naive_utc(commit_info.get("commit_date")),
                        message=commit_info.get("message", ""),
                    )
                )

            # Update index status to in_progress
            index_status = IndexStatus(
                id=index_status.id,
                repository_id=db_repo.id,
                branch=current_branch,
                indexing_status="in_progress",
                indexing_started_at=datetime.utcnow(),
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
                        db_repo.id, db_commit.id, file_path
                    )
                    if db_file:
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
                                    repository_id=db_repo.id,
                                    commit_id=db_commit.id,
                                    path=file_path,
                                    content_hash=content_hash,
                                    size_bytes=len(content.encode("utf-8")),
                                    language=language,
                                    line_count=content.count("\n") + 1,
                                )
                            )
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
                                            file_id=db_file.id,
                                            repository_id=db_repo.id,
                                            commit_id=db_commit.id,
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
                                            source_file_id=db_file.id,
                                            repository_id=db_repo.id,
                                            commit_id=db_commit.id,
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

            # Update index status to completed
            index_status = IndexStatus(
                id=index_status.id,
                repository_id=db_repo.id,
                branch=current_branch,
                indexing_status="completed",
                last_indexed_commit=current_commit,
                last_indexed_at=datetime.utcnow(),
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
                index_status = (
                    await index_status_repository.find_by_repository_and_branch(
                        db_repo.id, current_branch
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


def _filter_files_by_language(files: list[str], languages: list[str]) -> list[str]:
    """Filter files to only include those matching specified languages."""
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
    ext = Path(file_path).suffix.lower()
    mapping = {
        ".py": "python",
        ".pyi": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
    }
    return mapping.get(ext)


def _shorten_path(path: str, max_len: int = 50) -> str:
    """Shorten a path for display."""
    if len(path) <= max_len:
        return path
    parts = Path(path).parts
    if len(parts) <= 2:
        return path
    return f".../{'/'.join(parts[-2:])}"


def _print_summary(
    console: Console, stats: IndexingStats, is_incremental: bool = False
) -> None:
    """Print indexing summary."""
    console.print()

    index_type = "Incremental" if is_incremental else "Full"

    # Create summary table
    table = Table(title=f"{index_type} Index Complete", show_header=False, box=None)
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("Files Processed", f"[green]{stats.files_succeeded}[/green]")
    if stats.files_skipped > 0:
        table.add_row("Files Skipped", f"[dim]{stats.files_skipped}[/dim]")
    if stats.files_failed > 0:
        table.add_row("Files Failed", f"[red]{stats.files_failed}[/red]")
    table.add_row("Symbols Found", f"[cyan]{stats.symbols_found}[/cyan]")
    table.add_row("References Found", f"[cyan]{stats.references_found}[/cyan]")

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
