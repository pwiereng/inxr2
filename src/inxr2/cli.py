"""
CLI entry point for INXR2.

Provides command-line interface for indexing repositories and running the server.
Uses Click for CLI framework and Rich for beautiful progress output.
"""

import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.logging import RichHandler

from inxr2.adapters.cli.commands import IndexingResult

# Initialize rich console for output
console = Console()


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


def setup_logging(verbose: bool, log_level: str) -> None:
    """Configure logging with rich handler."""
    level = (
        logging.DEBUG if verbose else getattr(logging, log_level.upper(), logging.INFO)
    )

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def validate_positive_days(
    ctx: click.Context, param: click.Parameter, value: int | None
) -> int | None:
    """Validate that --days is a positive integer when provided."""
    if value is not None and value <= 0:
        raise click.BadParameter("must be a positive integer (greater than 0)")
    return value


def _run_single_repo_index(
    path: Path,
    branch: str | None,
    languages: str,
    verbose: bool,
    index_func: Callable[..., Any],
    index_type: str,
    max_history: int | None = 100,
    force: bool = False,
    since_days: int | None = None,
    enable_text_search: bool = False,
) -> None:
    """Run indexing for a single repository path."""
    # Validate git repository
    git_dir = path / ".git"
    if not git_dir.exists():
        console.print(f"[red]Error:[/red] No .git directory found at {path}")
        console.print("Please specify a valid git repository path.")
        sys.exit(1)

    # Parse languages
    from inxr2.adapters.external.treesitter.service import TreeSitterService

    lang_list = [lang.strip().lower() for lang in languages.split(",")]
    supported_languages = set(TreeSitterService.SUPPORTED_LANGUAGES.keys())
    unsupported = set(lang_list) - supported_languages
    if unsupported:
        console.print(
            f"[yellow]Warning:[/yellow] Unsupported languages skipped: {unsupported}"
        )
        lang_list = [lang for lang in lang_list if lang in supported_languages]

    if not lang_list:
        console.print("[red]Error:[/red] No supported languages specified.")
        console.print(f"Supported languages: {', '.join(sorted(supported_languages))}")
        sys.exit(1)

    console.print(f"\n[bold blue]INXR2 {index_type} Index[/bold blue]")
    console.print(f"  Repository: {path.absolute()}")
    console.print(f"  Branch: {branch or '(current)'}")
    console.print(f"  Languages: {', '.join(lang_list)}")
    if since_days is not None:
        console.print(f"  Date filter: last {since_days} days")
    console.print()

    try:
        # Only pass since_days for full indexing (incremental doesn't support it)
        kwargs: dict[str, Any] = {
            "repo_path": path,
            "branch": branch,
            "languages": lang_list,
            "console": console,
            "max_history": max_history,
            "force": force,
            "enable_text_search": enable_text_search,
        }
        if index_type == "Full" and since_days is not None:
            kwargs["since_days"] = since_days
        index_func(**kwargs)
    except Exception as e:
        console.print(f"\n[red]Error during indexing:[/red] {e}")
        if verbose:
            console.print_exception()
        sys.exit(1)


def _run_config_based_index(
    config_path: Path,
    repo_filter: str | None,
    branch_override: str | None,
    languages_override: str | None,
    verbose: bool,
    index_func: Callable[..., Any],
    index_type: str,
    max_history_override: int | None = None,
    force: bool = False,
    since_days: int | None = None,
    enable_text_search: bool = False,
) -> None:
    """Run indexing for repositories defined in config file."""
    from inxr2.adapters.config.yaml_config import YamlConfigService

    # Load configuration
    try:
        config_service = YamlConfigService()
        config = config_service.load(config_path)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Configuration Error:[/red]\n{e}")
        sys.exit(1)

    # Filter repositories if specified
    if repo_filter:
        repo_config = config.get_repository(repo_filter)
        if not repo_config:
            console.print(
                f"[red]Error:[/red] Repository '{repo_filter}' not found in config."
            )
            console.print(
                f"Available repositories: {', '.join(config.get_repository_names())}"
            )
            sys.exit(1)
        repos_to_index = [repo_config]
    else:
        repos_to_index = list(config.repositories)

    # Filter to only repos with local paths (remote URLs not yet supported)
    repos_with_paths = [r for r in repos_to_index if r.path]
    if len(repos_with_paths) < len(repos_to_index):
        skipped = len(repos_to_index) - len(repos_with_paths)
        console.print(
            f"[yellow]Warning:[/yellow] Skipping {skipped} repository(ies) with "
            "remote URLs (not yet supported)"
        )

    if not repos_with_paths:
        console.print("[red]Error:[/red] No repositories with local paths to index.")
        sys.exit(1)

    total_repos = len(repos_with_paths)
    console.print(f"\n[bold blue]INXR2 {index_type} Index[/bold blue]")
    console.print(f"  Config: {config_path}")
    console.print(f"  Repositories: {total_repos}")
    if since_days is not None:
        console.print(f"  Date filter: last {since_days} days")
    console.print()

    # Track overall stats
    results: list[IndexingResult] = []
    start_time = time.time()

    for idx, repo in enumerate(repos_with_paths, 1):
        # Resolve path (guaranteed to be non-None since repos_with_paths filters by r.path)
        resolved_path = repo.get_resolved_path()
        if resolved_path is None:
            continue  # Should never happen, but satisfies type checker

        # Determine branches to index (override > all config branches > None for current)
        branches_to_index: list[str | None]
        if branch_override:
            branches_to_index = [branch_override]
        elif repo.branches:
            branches_to_index = list(repo.branches)
        else:
            branches_to_index = [None]  # Will use current branch

        # Determine languages (override > config)
        if languages_override:
            lang_list = [lang.strip().lower() for lang in languages_override.split(",")]
        else:
            lang_list = [lang.lower() for lang in repo.languages]

        # Filter to supported languages (from TreeSitterService)
        from inxr2.adapters.external.treesitter.service import TreeSitterService

        supported_languages = set(TreeSitterService.SUPPORTED_LANGUAGES.keys())
        lang_list = [lang for lang in lang_list if lang in supported_languages]

        if not lang_list:
            console.print(
                f"[yellow]Skipping[/yellow] [{idx}/{total_repos}] {repo.name}: "
                "no supported languages"
            )
            continue

        # Create git service for branch activity checks
        from inxr2.adapters.external.git_service import GitService

        git_service = GitService()

        # Index each branch
        # First branch in config is the primary branch (main/master/trunk)
        # Primary branch is always indexed; other branches filtered by --days
        total_branches = len(branches_to_index)

        for branch_idx, branch in enumerate(branches_to_index, 1):
            is_primary_branch = branch_idx == 1

            # Resolve branch name for activity checks
            # Note: get_repository_info returns current_branch=None in detached HEAD state,
            # so we use `or` to handle both missing key and None value
            repo_info = git_service.get_repository_info(resolved_path)
            branch_name = branch or repo_info.get("current_branch") or "main"

            # Determine indexing parameters based on branch type and --days
            max_history = max_history_override or config.indexing.max_commit_history
            use_since_days: int | None = None
            primary_fallback_to_head = False

            if since_days is not None:
                # Check if branch has commits within the --days window
                commits = git_service.list_commits(
                    repo_path=resolved_path,
                    branch=branch_name,
                    max_count=1,
                    since_days=since_days,
                )
                has_recent_commits = len(commits) > 0

                if is_primary_branch:
                    # Primary branch: use --days if has recent commits, else fall back to HEAD
                    if has_recent_commits:
                        use_since_days = since_days
                    else:
                        # Fall back to HEAD only
                        max_history = 1
                        primary_fallback_to_head = True
                else:
                    # Non-primary branch: skip if no recent commits
                    if not has_recent_commits:
                        console.print(
                            f"[bold cyan][{idx}/{total_repos}][/bold cyan] "
                            f"[dim][{branch_idx}/{total_branches}][/dim] {repo.name}"
                        )
                        console.print(f"  Branch: {branch_name}")
                        console.print(
                            f"  [yellow]Skipped:[/yellow] No commits within "
                            f"last {since_days} days"
                        )
                        console.print()
                        continue
                    use_since_days = since_days

            # Show progress: [repo/total_repos] [branch/total_branches] repo_name
            if total_branches > 1:
                progress_str = (
                    f"[bold cyan][{idx}/{total_repos}][/bold cyan] "
                    f"[dim][{branch_idx}/{total_branches}][/dim] {repo.name}"
                )
            else:
                progress_str = (
                    f"[bold cyan][{idx}/{total_repos}][/bold cyan] {repo.name}"
                )
            console.print(f"{progress_str} ({resolved_path})")

            # Build branch line with role indicator
            branch_display = branch or "(current)"
            if is_primary_branch:
                branch_line = (
                    f"  Branch: {branch_display} [bold magenta](primary)[/bold magenta]"
                )
            else:
                branch_line = f"  Branch: {branch_display}"
            console.print(branch_line)

            # Show indexing strategy based on branch type and --days
            if since_days is not None:
                if is_primary_branch:
                    if primary_fallback_to_head:
                        console.print(
                            f"  [dim]Strategy: HEAD only "
                            f"(no commits in last {since_days} days)[/dim]"
                        )
                    else:
                        console.print(
                            f"  [dim]Strategy: last {since_days} days "
                            f"(has recent commits)[/dim]"
                        )
                else:
                    # Non-primary with recent commits (if we got here, it wasn't skipped)
                    console.print(f"  [dim]Strategy: last {since_days} days[/dim]")
            console.print()

            try:
                kwargs: dict[str, Any] = {
                    "repo_path": resolved_path,
                    "branch": branch,
                    "languages": lang_list,
                    "console": console,
                    "max_history": max_history,
                    "force": force,
                    "enable_text_search": enable_text_search,
                }
                if index_type == "Full" and use_since_days is not None:
                    kwargs["since_days"] = use_since_days

                # Feature branch optimization: if indexing a non-default branch,
                # use the first branch in config as base_branch to only index
                # commits unique to this branch (after merge-base)
                if index_type == "Full" and len(repo.branches) > 1:
                    default_branch = repo.branches[0]  # First branch is the default
                    if branch and branch != default_branch:
                        kwargs["base_branch"] = default_branch

                result = index_func(**kwargs)
                if result:
                    results.append(result)
            except Exception as e:
                console.print(f"  [red]Error:[/red] {e}")
                if verbose:
                    console.print_exception()
                results.append(
                    IndexingResult(
                        repo_name=repo.name,
                        branch=branch or "(current)",
                        success=False,
                        error_message=str(e),
                    )
                )
                # Continue with next branch/repository

            console.print()

    # Calculate totals
    total_time = time.time() - start_time
    successful = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)
    total_files = sum(r.files_total for r in results)
    total_lines = sum(r.lines_indexed for r in results)
    total_refs = sum(r.references_found for r in results)
    total_resolved = sum(r.references_resolved for r in results)
    overall_resolution = (total_resolved / total_refs * 100) if total_refs > 0 else 0

    # Print summary
    console.print()
    console.print("[bold]Indexing Summary:[/bold]")
    console.print()

    for r in results:
        status = "[green]OK[/green]" if r.success else "[red]FAIL[/red]"
        resolution = f"{r.resolution_rate:.1f}%" if r.references_found > 0 else "-"

        # Repository/branch header
        console.print(f"[cyan]{r.repo_name}[/cyan] / {r.branch}  {status}")

        if r.success:
            # Commit range (short hashes)
            if r.oldest_commit_hash and r.newest_commit_hash:
                oldest_short = r.oldest_commit_hash[:7]
                newest_short = r.newest_commit_hash[:7]
                if oldest_short == newest_short:
                    console.print(f"  Commit: {oldest_short} ({r.oldest_commit_date})")
                else:
                    console.print(
                        f"  Commits: {oldest_short}..{newest_short} "
                        f"({r.oldest_commit_date} to {r.newest_commit_date})"
                    )

            # Stats line
            files_str = f"{r.files_total:,} files" if r.files_total > 0 else ""
            lines_str = f"{r.lines_indexed:,} lines" if r.lines_indexed > 0 else ""
            time_str = (
                _format_duration(r.elapsed_seconds) if r.elapsed_seconds > 0 else ""
            )
            stats_parts = [
                p
                for p in [files_str, lines_str, f"resolution {resolution}", time_str]
                if p
            ]
            if stats_parts:
                console.print(f"  {', '.join(stats_parts)}")
        else:
            # Error message
            if r.error_message:
                console.print(f"  [red]Error:[/red] {r.error_message}")

        console.print()

    # Print totals
    console.print()
    console.print(f"  [bold]Total:[/bold] {len(results)} repo/branch combinations")
    console.print(f"  [green]Successful:[/green] {successful}")
    if failed > 0:
        console.print(f"  [red]Failed:[/red] {failed}")
    console.print(f"  [cyan]Files:[/cyan] {total_files:,}")
    console.print(f"  [cyan]Lines:[/cyan] {total_lines:,}")
    console.print(
        f"  [cyan]Resolution:[/cyan] {total_resolved:,}/{total_refs:,} ({overall_resolution:.1f}%)"
    )
    console.print(f"  [blue]Total Time:[/blue] {_format_duration(total_time)}")


@click.group()
@click.version_option()
def main() -> None:
    """INXR2 - Cross-reference code browser for git repositories."""
    pass


# =============================================================================
# Index Command Group
# =============================================================================


@main.group()
def index() -> None:
    """Index repositories for code navigation."""
    pass


@index.command("full")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Path to git repository to index (required if --config not provided)",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to YAML configuration file",
)
@click.option(
    "--repo",
    "-r",
    default=None,
    help="Repository name from config to index (indexes all if not specified)",
)
@click.option(
    "--branch",
    "-b",
    default=None,
    help="Branch to index (default: from config or current branch)",
)
@click.option(
    "--languages",
    "-l",
    default=None,
    help="Comma-separated list of languages to index (default: from config or python,typescript)",
)
@click.option(
    "--history",
    "-H",
    type=int,
    default=None,
    help="Maximum number of commits to index for time travel (default: from config or 100)",
)
@click.option(
    "--days",
    "-d",
    type=int,
    default=None,
    callback=validate_positive_days,
    help="Only index commits from the last N days (overrides --history when specified)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Set log level",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force re-index by clearing existing data for the repository first",
)
@click.option(
    "--reset-db",
    is_flag=True,
    help="Reset entire database before indexing (TRUNCATE all tables - much faster than --force for full re-index). Requires --yes flag.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Confirm destructive operations like --reset-db without prompting",
)
@click.option(
    "--enable-text-search",
    "--text-search",
    is_flag=True,
    help="Enable indexing of code comments for text search",
)
def index_full(
    path: Path | None,
    config: Path | None,
    repo: str | None,
    branch: str | None,
    languages: str | None,
    history: int | None,
    days: int | None,
    verbose: bool,
    log_level: str,
    force: bool,
    reset_db: bool,
    yes: bool,
    enable_text_search: bool,
) -> None:
    """
    Perform full indexing of repository/repositories.

    Indexes all files from scratch, extracting symbols and references.
    This will clear any existing index data for the repository.

    Examples:
        inxr2 index full --path /path/to/repo --branch main
        inxr2 index full --config config.yaml
        inxr2 index full --config config.yaml --repo myrepo
    """
    setup_logging(verbose, log_level)

    # Validate that either path or config is provided
    if not path and not config:
        console.print("[red]Error:[/red] Either --path or --config must be specified.")
        sys.exit(1)

    if path and config:
        console.print(
            "[red]Error:[/red] Cannot specify both --path and --config. Use one or the other."
        )
        sys.exit(1)

    # Reset database if requested (much faster than per-repo --force)
    if reset_db:
        if not yes:
            console.print(
                "[red]Error:[/red] --reset-db requires --yes flag to confirm. "
                "This will permanently delete ALL indexed data."
            )
            sys.exit(1)
        console.print("[yellow]Resetting database...[/yellow]")
        from inxr2.adapters.cli.commands.index_command import reset_database

        try:
            reset_database(console=console)
            console.print("[green]Database reset complete[/green]\n")
        except Exception as e:
            console.print(f"[red]Error resetting database:[/red] {e}")
            sys.exit(1)

    # Import indexing function (lazy import to speed up CLI startup)
    from inxr2.adapters.cli.commands.index_command import run_full_index

    if config:
        # Config-based indexing
        _run_config_based_index(
            config_path=config,
            repo_filter=repo,
            branch_override=branch,
            languages_override=languages,
            verbose=verbose,
            index_func=run_full_index,
            index_type="Full",
            max_history_override=history,
            force=force,
            since_days=days,
            enable_text_search=enable_text_search,
        )
    else:
        # Single repository path-based indexing
        assert path is not None
        _run_single_repo_index(
            path=path,
            branch=branch,
            languages=languages or "python,typescript",
            verbose=verbose,
            index_func=run_full_index,
            index_type="Full",
            # --days overrides --history: disable commit cap when filtering by date
            max_history=None if days else (history or 100),
            force=force,
            since_days=days,
            enable_text_search=enable_text_search,
        )


@index.command("incremental")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Path to git repository to index (required if --config not provided)",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to YAML configuration file",
)
@click.option(
    "--repo",
    "-r",
    default=None,
    help="Repository name from config to index (indexes all if not specified)",
)
@click.option(
    "--branch",
    "-b",
    default=None,
    help="Branch to index (default: from config or current branch)",
)
@click.option(
    "--languages",
    "-l",
    default=None,
    help="Comma-separated list of languages to index (default: from config or python,typescript)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Set log level",
)
@click.option(
    "--enable-text-search",
    "--text-search",
    is_flag=True,
    help="Enable indexing of code comments for text search",
)
def index_incremental(
    path: Path | None,
    config: Path | None,
    repo: str | None,
    branch: str | None,
    languages: str | None,
    verbose: bool,
    log_level: str,
    enable_text_search: bool,
) -> None:
    """
    Perform incremental indexing of repository/repositories.

    Only indexes files that have changed since the last index.
    Much faster than full indexing for repositories with few changes.

    Examples:
        inxr2 index incremental --path /path/to/repo
        inxr2 index incremental --config config.yaml
        inxr2 index incremental --config config.yaml --repo myrepo
    """
    setup_logging(verbose, log_level)

    # Validate that either path or config is provided
    if not path and not config:
        console.print("[red]Error:[/red] Either --path or --config must be specified.")
        sys.exit(1)

    if path and config:
        console.print(
            "[red]Error:[/red] Cannot specify both --path and --config. Use one or the other."
        )
        sys.exit(1)

    # Import indexing function (lazy import to speed up CLI startup)
    from inxr2.adapters.cli.commands.index_command import run_incremental_index

    if config:
        # Config-based indexing
        _run_config_based_index(
            config_path=config,
            repo_filter=repo,
            branch_override=branch,
            languages_override=languages,
            verbose=verbose,
            index_func=run_incremental_index,
            index_type="Incremental",
            enable_text_search=enable_text_search,
        )
    else:
        # Single repository path-based indexing
        assert path is not None
        _run_single_repo_index(
            path=path,
            branch=branch,
            languages=languages or "python,typescript",
            verbose=verbose,
            index_func=run_incremental_index,
            index_type="Incremental",
            enable_text_search=enable_text_search,
        )


@index.command("status")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Path to git repository",
)
def index_status(path: Path) -> None:
    """
    Show indexing status for a repository.

    Displays information about when the repository was last indexed,
    how many files/symbols/references are indexed, and whether updates are available.

    Example:
        inxr2 index status --path /path/to/repo
    """
    # Validate git repository
    git_dir = path / ".git"
    if not git_dir.exists():
        console.print(f"[red]Error:[/red] No .git directory found at {path}")
        sys.exit(1)

    console.print("\n[bold blue]INXR2 Index Status[/bold blue]")
    console.print(f"  Repository: {path.absolute()}")
    console.print()

    # Import and run status check (lazy import to speed up CLI startup)
    from inxr2.adapters.cli.commands.index_command import show_index_status

    try:
        show_index_status(repo_path=path, console=console)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        sys.exit(1)


# =============================================================================
# Config Command Group
# =============================================================================


@main.group()
def config() -> None:
    """Manage INXR2 configuration files."""
    pass


@config.command("validate")
@click.argument(
    "config_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
)
def config_validate(config_path: Path) -> None:
    """
    Validate a configuration file.

    Checks YAML syntax, schema validation, and path existence.

    Example:
        inxr2 config validate config.yaml
    """
    from inxr2.adapters.config.yaml_config import YamlConfigService

    console.print(f"\n[bold blue]Validating configuration:[/bold blue] {config_path}")
    console.print()

    config_service = YamlConfigService()
    errors = config_service.validate(config_path)

    if errors:
        console.print("[red]Validation failed:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        sys.exit(1)
    else:
        console.print("[green]Configuration is valid![/green]")


@config.command("show")
@click.argument(
    "config_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
)
def config_show(config_path: Path) -> None:
    """
    Show parsed configuration.

    Displays the configuration with environment variables expanded.

    Example:
        inxr2 config show config.yaml
    """
    from rich.table import Table

    from inxr2.adapters.config.yaml_config import YamlConfigService

    console.print(f"\n[bold blue]Configuration:[/bold blue] {config_path}")
    console.print()

    try:
        config_service = YamlConfigService()
        app_config = config_service.load(config_path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    # Show repositories table
    repo_table = Table(title="Repositories")
    repo_table.add_column("Name", style="cyan")
    repo_table.add_column("Path/URL")
    repo_table.add_column("Branches")
    repo_table.add_column("Languages")

    for repo in app_config.repositories:
        location = repo.path or repo.url or "(none)"
        branches = ", ".join(repo.branches)
        languages = ", ".join(repo.languages)
        repo_table.add_row(repo.name, location, branches, languages)

    console.print(repo_table)
    console.print()

    # Show indexing config
    console.print("[bold]Indexing Settings:[/bold]")
    console.print(f"  Incremental: {app_config.indexing.incremental}")
    console.print(f"  Max commit history: {app_config.indexing.max_commit_history}")
    console.print(f"  Batch size: {app_config.indexing.batch_size}")
    console.print()

    # Show server config
    console.print("[bold]Server Settings:[/bold]")
    console.print(f"  Host: {app_config.server.host}")
    console.print(f"  Port: {app_config.server.port}")


# =============================================================================
# Database Command Group
# =============================================================================


@main.group()
def db() -> None:
    """Database management commands."""
    pass


@db.command("reset")
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Confirm reset without prompting",
)
def db_reset(yes: bool) -> None:
    """
    Reset the database by truncating all tables.

    This permanently deletes ALL indexed data including repositories,
    commits, files, symbols, and references.

    Example:
        inxr2 db reset --yes
    """
    if not yes:
        console.print(
            "[red]Error:[/red] --yes flag required to confirm. "
            "This will permanently delete ALL indexed data."
        )
        sys.exit(1)

    console.print("[yellow]Resetting database...[/yellow]")

    from inxr2.adapters.cli.commands.index_command import reset_database

    try:
        reset_database(console=console)
        console.print("[green]Database reset complete[/green]")
    except Exception as e:
        console.print(f"[red]Error resetting database:[/red] {e}")
        sys.exit(1)


# =============================================================================
# Serve Command
# =============================================================================


@main.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def serve(host: str, port: int, reload: bool) -> None:
    """Start the FastAPI web server."""
    import uvicorn

    console.print("[bold blue]Starting INXR2 API server[/bold blue]")
    console.print(f"  Host: {host}")
    console.print(f"  Port: {port}")
    if reload:
        console.print("  [yellow]Auto-reload enabled[/yellow]")
    console.print()

    uvicorn.run(
        "inxr2.main:app",
        host=host,
        port=port,
        reload=reload,
    )


# =============================================================================
# Status Command (top-level)
# =============================================================================


@main.command("status")
def status() -> None:
    """
    Show overall INXR2 status.

    Displays information about all indexed repositories and system health.
    """
    console.print("\n[bold blue]INXR2 Status[/bold blue]")
    console.print()

    # Import and show status (lazy import)
    from inxr2.adapters.cli.commands.status_command import show_overall_status

    try:
        show_overall_status(console=console)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
