"""
Rendering utilities for CLI progress output.

Encapsulates Rich progress bars, milestone-based progress callbacks,
and summary formatting for the indexing command.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

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

if TYPE_CHECKING:
    from inxr2.adapters.cli.commands.index_command import IndexingStats
    from inxr2.application.use_cases.indexing.default_orchestrator import (
        IndexingProgress,
    )


def format_duration(seconds: float) -> str:
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


def shorten_path(path: str, max_len: int = 50) -> str:
    """Shorten a path for display."""
    if len(path) <= max_len:
        return path
    parts = Path(path).parts
    if len(parts) <= 2:
        return path
    return f".../{'/'.join(parts[-2:])}"


# Milestone percentages used for progress reporting
_MILESTONES = {
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


class IndexingProgressRenderer:
    """Renders indexing progress to the console.

    Encapsulates Rich progress bar creation, milestone-based progress
    callbacks, final resolution display, and summary table formatting.
    """

    def __init__(self, console: Console) -> None:
        self._console = console

    def create_progress_bar(self) -> Progress:
        """Create a Rich Progress instance with custom columns."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self._console,
            transient=False,
        )

    def create_progress_callback(
        self, output: TextIO | None = None
    ) -> Callable[[IndexingProgress], None]:
        """Return a closure that prints progress at milestone percentages.

        Args:
            output: Stream to write progress lines to. Defaults to sys.stdout.
        """
        out = output or sys.stdout
        console = self._console

        class _State:
            pcts: set[int] = set()
            phase: str = ""
            shown_start: bool = False

        state = _State()

        def on_progress(p: IndexingProgress) -> None:
            if not state.shown_start and p.files_total > 0:
                state.shown_start = True
                console.print(
                    f"  [dim]Files to process: {p.files_total} | "
                    f"Cache size: {p.cache_size}[/dim]"
                )

            if p.phase == "files" and p.files_total > 0:
                pct = int((p.files_processed / p.files_total) * 100)
                if pct in _MILESTONES and pct not in state.pcts:
                    state.pcts.add(pct)
                    out.write(
                        f"\r  {pct}% ({p.files_processed}/{p.files_total}) | "
                        f"Symbols: {p.symbols_found} | Refs: {p.references_found} | "
                        f"Cache: {p.cache_size}    "
                    )
                    out.flush()
            elif p.phase == "resolving":
                if state.phase != "resolving":
                    state.phase = "resolving"
                    state.pcts = set()
                    out.write("\n")
                    if p.refs_total > 0:
                        console.print(
                            f"  [cyan]Resolving references "
                            f"({p.refs_total} to process)...[/cyan]"
                        )
                    else:
                        console.print("  [cyan]Resolving references...[/cyan]")
                if p.refs_total > 0:
                    pct = int((p.refs_resolved / p.refs_total) * 100)
                    if pct in _MILESTONES and pct not in state.pcts:
                        state.pcts.add(pct)
                        out.write(
                            f"\r  Resolving: {pct}% "
                            f"({p.refs_resolved}/{p.refs_total})    "
                        )
                        out.flush()

        return on_progress

    def print_final_resolution(
        self,
        references_found: int,
        references_resolved: int,
        was_resolving: bool,
        output: TextIO | None = None,
    ) -> None:
        """Print final resolution result after the resolving phase."""
        if was_resolving and references_found > 0:
            out = output or sys.stdout
            pct = references_resolved * 100 // references_found
            out.write(
                f"\r  Resolved: {references_resolved}/"
                f"{references_found} ({pct}%)    \n"
            )
            out.flush()

    def print_summary(
        self,
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
        """Print indexing summary as a Rich panel with a table."""
        console = self._console
        console.print()

        index_type = "Incremental" if is_incremental else "Full"

        table = Table(title=f"{index_type} Index Complete", show_header=False, box=None)
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        if repo_name:
            table.add_row("Repository", f"[bold]{repo_name}[/bold]")
        if branch:
            table.add_row("Branch", f"[cyan]{branch}[/cyan]")
        if since_days is not None:
            table.add_row("Range", f"[dim]last {since_days} days[/dim]")
        elif max_history is not None:
            table.add_row("Range", f"[dim]last {max_history} commits[/dim]")

        if repo_name or branch:
            table.add_row("", "")

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
        if stats.references_found > 0:
            resolution_rate = stats.references_resolved * 100 / stats.references_found
            table.add_row(
                "References Resolved",
                f"[cyan]{stats.references_resolved}[/cyan] "
                f"[dim]({resolution_rate:.1f}%)[/dim]",
            )
        else:
            table.add_row(
                "References Resolved",
                f"[cyan]{stats.references_resolved}[/cyan]",
            )

        if stats.text_contents_total > 0:
            table.add_row("", "")
            table.add_row(
                "Text Content Indexed",
                f"[cyan]{stats.text_contents_total:,}[/cyan] "
                f"[dim](comments + docstrings + commit messages)[/dim]",
            )
            table.add_row("  Comments", f"[dim]{stats.comments_indexed:,}[/dim]")
            table.add_row("  Docstrings", f"[dim]{stats.docstrings_indexed:,}[/dim]")
            table.add_row(
                "  Commit Messages",
                f"[dim]{stats.commit_messages_indexed:,}[/dim]",
            )

        if stats.files_reused > 0:
            table.add_row("", "")
            table.add_row("Files Reused", f"[yellow]{stats.files_reused}[/yellow]")
            table.add_row("Symbols Reused", f"[yellow]{stats.symbols_reused}[/yellow]")
            table.add_row(
                "References Reused",
                f"[yellow]{stats.references_reused}[/yellow]",
            )

        if elapsed_seconds is not None:
            table.add_row("", "")
            table.add_row(
                "Total Time",
                f"[blue]{format_duration(elapsed_seconds)}[/blue]",
            )
            if indexing_seconds is not None and indexing_seconds > 0:
                table.add_row(
                    "  Indexing",
                    f"[dim]{format_duration(indexing_seconds)}[/dim]",
                )
            if resolving_seconds is not None and resolving_seconds > 0:
                table.add_row(
                    "  Resolving",
                    f"[dim]{format_duration(resolving_seconds)}[/dim]",
                )

        db = stats.db_stats
        if db.total > 0:
            table.add_row("", "")
            table.add_row("DB Queries", f"[dim]{db.total} total[/dim]")
            table.add_row("  Selects", f"[dim]{db.selects}[/dim]")
            table.add_row("  Inserts", f"[dim]{db.inserts}[/dim]")
            if db.updates > 0:
                table.add_row("  Updates", f"[dim]{db.updates}[/dim]")
            if db.deletes > 0:
                table.add_row("  Deletes", f"[dim]{db.deletes}[/dim]")

        console.print(Panel(table, border_style="green"))

        if stats.errors:
            console.print(f"\n[yellow]Warnings ({len(stats.errors)}):[/yellow]")
            for error in stats.errors[:5]:
                console.print(f"  [dim]{error}[/dim]")
            if len(stats.errors) > 5:
                console.print(f"  [dim]... and {len(stats.errors) - 5} more[/dim]")
