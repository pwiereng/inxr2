"""
Status command implementation.

Shows overall INXR2 status and indexed repository information.
"""

import asyncio

from rich.console import Console
from rich.table import Table


def show_overall_status(console: Console) -> None:
    """Show overall INXR2 status."""
    asyncio.run(_show_overall_status_async(console))


async def _show_overall_status_async(console: Console) -> None:
    """Async implementation of overall status."""
    # TODO: Query database for repository list and stats

    # Create repositories table
    table = Table(title="Indexed Repositories")
    table.add_column("Repository", style="cyan")
    table.add_column("Branch", style="dim")
    table.add_column("Last Indexed", style="dim")
    table.add_column("Files", justify="right")
    table.add_column("Symbols", justify="right")
    table.add_column("Status")

    # TODO: Populate from database
    # For now, show placeholder
    console.print("[dim]No repositories indexed yet.[/dim]")
    console.print()
    console.print("To index a repository, run:")
    console.print("  [cyan]inxr2 index full --path /path/to/repo[/cyan]")
