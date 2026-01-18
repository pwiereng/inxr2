"""
CLI entry point for INXR2.

Provides command-line interface for indexing repositories and running the server.
Uses Click for CLI framework and Rich for beautiful progress output.
"""

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.logging import RichHandler

# Initialize rich console for output
console = Console()


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


def _run_single_repo_index(
    path: Path,
    branch: str | None,
    languages: str,
    verbose: bool,
    index_func: Callable[..., Any],
    index_type: str,
    max_history: int = 100,
) -> None:
    """Run indexing for a single repository path."""
    # Validate git repository
    git_dir = path / ".git"
    if not git_dir.exists():
        console.print(f"[red]Error:[/red] No .git directory found at {path}")
        console.print("Please specify a valid git repository path.")
        sys.exit(1)

    # Parse languages
    lang_list = [lang.strip().lower() for lang in languages.split(",")]
    supported_languages = {"python", "typescript", "javascript"}
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
    console.print()

    try:
        index_func(
            repo_path=path,
            branch=branch,
            languages=lang_list,
            console=console,
            max_history=max_history,
        )
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
        repos_to_index = config.repositories

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
    console.print()

    # Track overall stats
    successful = 0
    failed = 0

    for idx, repo in enumerate(repos_with_paths, 1):
        # Resolve path
        resolved_path = repo.get_resolved_path()

        # Determine branch (override > config > None for current)
        branch = branch_override or (repo.branches[0] if repo.branches else None)

        # Determine languages (override > config)
        if languages_override:
            lang_list = [lang.strip().lower() for lang in languages_override.split(",")]
        else:
            lang_list = [lang.lower() for lang in repo.languages]

        # Filter to supported languages
        supported_languages = {"python", "typescript", "javascript"}
        lang_list = [lang for lang in lang_list if lang in supported_languages]

        if not lang_list:
            console.print(
                f"[yellow]Skipping[/yellow] [{idx}/{total_repos}] {repo.name}: "
                "no supported languages"
            )
            continue

        console.print(
            f"[bold cyan][{idx}/{total_repos}][/bold cyan] {repo.name} ({resolved_path})"
        )
        console.print(f"  Branch: {branch or '(current)'}")
        console.print()

        # Determine max_history (override > config)
        max_history = max_history_override or config.indexing.max_commit_history

        try:
            index_func(
                repo_path=resolved_path,
                branch=branch,
                languages=lang_list,
                console=console,
                max_history=max_history,
            )
            successful += 1
        except Exception as e:
            console.print(f"  [red]Error:[/red] {e}")
            if verbose:
                console.print_exception()
            failed += 1
            # Continue with next repository

        console.print()

    # Summary
    console.print("[bold]Indexing Summary:[/bold]")
    console.print(f"  Successful: [green]{successful}[/green]")
    if failed > 0:
        console.print(f"  Failed: [red]{failed}[/red]")


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
def index_full(
    path: Path | None,
    config: Path | None,
    repo: str | None,
    branch: str | None,
    languages: str | None,
    history: int | None,
    verbose: bool,
    log_level: str,
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
            max_history=history or 100,
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
def index_incremental(
    path: Path | None,
    config: Path | None,
    repo: str | None,
    branch: str | None,
    languages: str | None,
    verbose: bool,
    log_level: str,
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
