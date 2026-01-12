"""
CLI entry point for INXR2.

Provides command-line interface for indexing repositories and running the server.
Uses Click for CLI framework and Rich for beautiful progress output.
"""

import logging
import sys
from pathlib import Path

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
    required=True,
    help="Path to git repository to index",
)
@click.option(
    "--branch",
    "-b",
    default=None,
    help="Branch to index (default: current branch)",
)
@click.option(
    "--languages",
    "-l",
    default="python,typescript",
    help="Comma-separated list of languages to index (default: python,typescript)",
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
    path: Path,
    branch: str | None,
    languages: str,
    verbose: bool,
    log_level: str,
) -> None:
    """
    Perform full indexing of a repository.

    Indexes all files from scratch, extracting symbols and references.
    This will clear any existing index data for the repository.

    Example:
        inxr2 index full --path /path/to/repo --branch main
    """
    setup_logging(verbose, log_level)

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
            f"[yellow]Warning:[/yellow] Unsupported languages skipped: "
            f"{unsupported}"
        )
        lang_list = [lang for lang in lang_list if lang in supported_languages]

    if not lang_list:
        console.print("[red]Error:[/red] No supported languages specified.")
        console.print(f"Supported languages: {', '.join(sorted(supported_languages))}")
        sys.exit(1)

    console.print("\n[bold blue]INXR2 Full Index[/bold blue]")
    console.print(f"  Repository: {path.absolute()}")
    console.print(f"  Branch: {branch or '(current)'}")
    console.print(f"  Languages: {', '.join(lang_list)}")
    console.print()

    # Import and run indexing (lazy import to speed up CLI startup)
    from inxr2.adapters.cli.commands.index_command import run_full_index

    try:
        run_full_index(
            repo_path=path,
            branch=branch,
            languages=lang_list,
            console=console,
        )
    except Exception as e:
        console.print(f"\n[red]Error during indexing:[/red] {e}")
        if verbose:
            console.print_exception()
        sys.exit(1)


@index.command("incremental")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Path to git repository to index",
)
@click.option(
    "--branch",
    "-b",
    default=None,
    help="Branch to index (default: current branch)",
)
@click.option(
    "--languages",
    "-l",
    default="python,typescript",
    help="Comma-separated list of languages to index (default: python,typescript)",
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
    path: Path,
    branch: str | None,
    languages: str,
    verbose: bool,
    log_level: str,
) -> None:
    """
    Perform incremental indexing of a repository.

    Only indexes files that have changed since the last index.
    Much faster than full indexing for repositories with few changes.

    Example:
        inxr2 index incremental --path /path/to/repo
    """
    setup_logging(verbose, log_level)

    # Validate git repository
    git_dir = path / ".git"
    if not git_dir.exists():
        console.print(f"[red]Error:[/red] No .git directory found at {path}")
        console.print("Please specify a valid git repository path.")
        sys.exit(1)

    # Parse languages
    lang_list = [lang.strip().lower() for lang in languages.split(",")]
    supported_languages = {"python", "typescript", "javascript"}
    lang_list = [lang for lang in lang_list if lang in supported_languages]

    console.print("\n[bold blue]INXR2 Incremental Index[/bold blue]")
    console.print(f"  Repository: {path.absolute()}")
    console.print(f"  Branch: {branch or '(current)'}")
    console.print(f"  Languages: {', '.join(lang_list)}")
    console.print()

    # Import and run indexing (lazy import to speed up CLI startup)
    from inxr2.adapters.cli.commands.index_command import run_incremental_index

    try:
        run_incremental_index(
            repo_path=path,
            branch=branch,
            languages=lang_list,
            console=console,
        )
    except Exception as e:
        console.print(f"\n[red]Error during indexing:[/red] {e}")
        if verbose:
            console.print_exception()
        sys.exit(1)


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
