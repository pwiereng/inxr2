"""
Status command implementation.

Shows overall INXR2 status and indexed repository information.
"""

import asyncio

from rich.console import Console
from rich.table import Table

from inxr2.application.ports.repositories import (
    IndexStatusRepositoryPort,
    RepositoryPort,
)


def show_overall_status(console: Console) -> None:
    """Show overall INXR2 status."""
    asyncio.run(_show_overall_status_async(console))


async def _show_overall_status_async(
    console: Console,
    repository_repo: RepositoryPort | None = None,
    index_status_repo: IndexStatusRepositoryPort | None = None,
) -> None:
    """Async implementation of overall status.

    Args:
        console: Rich console for output.
        repository_repo: Optional injected repository port (for testing).
        index_status_repo: Optional injected index status port (for testing).
    """
    if (repository_repo is None) != (index_status_repo is None):
        raise ValueError(
            "Both repository_repo and index_status_repo must be provided, or neither"
        )

    if repository_repo is not None and index_status_repo is not None:
        await _render_status(console, repository_repo, index_status_repo)
    else:
        from inxr2.adapters.cli.dependencies import cli_repositories

        async with cli_repositories() as repos:
            await _render_status(
                console, repos.repository_repo, repos.index_status_repo
            )


async def _render_status(
    console: Console,
    repository_repo: RepositoryPort,
    index_status_repo: IndexStatusRepositoryPort,
) -> None:
    """Render status table using provided repositories."""
    repos = await repository_repo.list_all()
    if not repos:
        console.print("[dim]No repositories indexed yet.[/dim]")
        console.print()
        console.print("To index a repository, run:")
        console.print("  [cyan]inxr2 index --config config.yaml[/cyan]")
        return

    table = Table(title="Indexed Repositories")
    table.add_column("Repository", style="cyan")
    table.add_column("Branch", style="dim")
    table.add_column("Last Indexed", style="dim")
    table.add_column("Files", justify="right")
    table.add_column("Symbols", justify="right")
    table.add_column("References", justify="right")
    table.add_column("Status")

    for repo in repos:
        assert repo.id is not None
        statuses = await index_status_repo.list_by_repository(repo.id)
        if not statuses:
            table.add_row(repo.name, "-", "-", "-", "-", "-", "[red]Not indexed[/red]")
            continue
        for idx_status in statuses:
            status_text = {
                "completed": "[green]Completed[/green]",
                "in_progress": "[yellow]In progress[/yellow]",
                "failed": "[red]Failed[/red]",
            }.get(
                idx_status.indexing_status,
                f"[dim]{idx_status.indexing_status}[/dim]",
            )
            last_indexed = (
                idx_status.last_indexed_at.strftime("%Y-%m-%d %H:%M")
                if idx_status.last_indexed_at
                else "-"
            )
            table.add_row(
                repo.name,
                idx_status.branch,
                last_indexed,
                str(idx_status.total_files_indexed),
                str(idx_status.total_symbols_indexed),
                str(idx_status.total_references_indexed),
                status_text,
            )

    console.print(table)
