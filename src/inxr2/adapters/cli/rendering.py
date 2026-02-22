"""
Rendering utilities for CLI progress output.

Encapsulates Rich progress bars, milestone-based progress callbacks,
and summary formatting for the indexing command.
"""

from __future__ import annotations

import bisect
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


# Milestone percentages used for progress reporting (sorted for bisect lookup)
_MILESTONES = (
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
)


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

        Both phases use a manual ASCII spinner updated on each callback.
        The percentage display uses milestone thresholds (every 5%) to
        avoid noisy jumps, while the spinner and counts update every tick.

        Args:
            output: Stream to write progress lines to. Defaults to sys.stdout.
        """
        out = output or sys.stdout
        console = self._console

        _SPINNER = "|/-\\"

        class _State:
            phase: str = ""
            shown_start: bool = False
            files_started: bool = False
            tick: int = 0
            last_pct: int = 0

        state = _State()

        def on_progress(p: IndexingProgress) -> None:
            if not state.shown_start and p.files_total > 0:
                state.shown_start = True
                console.print(f"  [dim]Files to process: {p.files_total}[/dim]")

            if p.phase == "files" and p.files_total > 0:
                state.files_started = True
                pct = int((p.files_processed / p.files_total) * 100)
                state.tick += 1
                spinner = _SPINNER[state.tick % len(_SPINNER)]
                milestone = _MILESTONES[bisect.bisect_right(_MILESTONES, pct) - 1]
                if milestone > state.last_pct:
                    state.last_pct = milestone
                # Always update the line with current spinner
                out.write(
                    f"\r  {spinner} Files: {p.files_processed}/{p.files_total} | "
                    f"Symbols: {p.symbols_found} | Refs: {p.references_found} "
                    f"({state.last_pct}%)    "
                )
                out.flush()
            elif p.phase == "resolving":
                if state.phase != "resolving":
                    # Finalize file phase with actual percentage
                    if state.files_started and p.files_total > 0:
                        final_pct = int((p.files_processed / p.files_total) * 100)
                        out.write(
                            f"\r  Files: {p.files_processed}/{p.files_total} | "
                            f"Symbols: {p.symbols_found} | Refs: {p.references_found} "
                            f"({final_pct}%)    "
                        )
                        out.flush()
                    state.phase = "resolving"
                    state.tick = 0
                    state.last_pct = 0
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
                    milestone = _MILESTONES[bisect.bisect_right(_MILESTONES, pct) - 1]
                    if milestone > state.last_pct:
                        state.last_pct = milestone
                    state.tick += 1
                    spinner = _SPINNER[state.tick % len(_SPINNER)]
                    out.write(
                        f"\r  {spinner} Resolved: {p.refs_resolved}/{p.refs_total} "
                        f"({state.last_pct}%)    "
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
        commits_indexed: int | None = None,
        elapsed_seconds: float | None = None,
        indexing_seconds: float | None = None,
        resolving_seconds: float | None = None,
        repo_name: str | None = None,
        branch: str | None = None,
        days: int | None = None,
    ) -> None:
        """Print indexing summary as a Rich panel with a table."""
        console = self._console
        console.print()

        table = Table(title="Index Complete", show_header=False, box=None)
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        if repo_name:
            table.add_row("Repository", f"[bold]{repo_name}[/bold]")
        if branch:
            table.add_row("Branch", f"[cyan]{branch}[/cyan]")
        if days is not None:
            table.add_row("Range", f"[dim]last {days} days[/dim]")

        if repo_name or branch:
            table.add_row("", "")

        if commits_indexed is not None:
            table.add_row("Commits Indexed", f"[magenta]{commits_indexed}[/magenta]")
        if stats.files_at_head > 0:
            table.add_row("Files at HEAD", f"[cyan]{stats.files_at_head:,}[/cyan]")
        if stats.lines_indexed > 0:
            table.add_row("Lines Indexed", f"[cyan]{stats.lines_indexed:,}[/cyan]")
        table.add_row("Files Processed", f"[green]{stats.files_succeeded}[/green]")
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

        if stats.file_versions_new > 0 or stats.file_versions_cached > 0:
            table.add_row("", "")
            table.add_row(
                "File Versions (new)",
                f"[green]{stats.file_versions_new}[/green]",
            )
            table.add_row(
                "File Versions (cached)",
                f"[yellow]{stats.file_versions_cached}[/yellow]",
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

        if stats.db_size_bytes > 0:
            table.add_row("", "")
            size_mb = stats.db_size_bytes / 1_048_576
            table.add_row("DB Size", f"[blue]{size_mb:.1f} MB[/blue]")
            if stats.db_size_added_bytes > 0:
                added_mb = stats.db_size_added_bytes / 1_048_576
                table.add_row("  Added", f"[dim]+{added_mb:.1f} MB[/dim]")
            elif stats.db_size_added_bytes < 0:
                freed_mb = abs(stats.db_size_added_bytes) / 1_048_576
                table.add_row("  Freed", f"[dim]-{freed_mb:.1f} MB[/dim]")

        console.print(Panel(table, border_style="green"))

        if stats.errors:
            console.print(f"\n[yellow]Warnings ({len(stats.errors)}):[/yellow]")
            for error in stats.errors[:5]:
                console.print(f"  [dim]{error}[/dim]")
            if len(stats.errors) > 5:
                console.print(f"  [dim]... and {len(stats.errors) - 5} more[/dim]")
