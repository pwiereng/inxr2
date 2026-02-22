"""Tests for CLI rendering utilities and IndexingProgressRenderer."""

from io import StringIO

from rich.console import Console

from inxr2.adapters.cli.commands.index_command import IndexingStats
from inxr2.adapters.cli.rendering import (
    IndexingProgressRenderer,
    format_duration,
    shorten_path,
)
from inxr2.application.use_cases.indexing.default_orchestrator import IndexingProgress
from inxr2.application.use_cases.indexing.orchestrator import DBQueryStats


class TestFormatDuration:
    """Tests for format_duration utility function."""

    def test_seconds_only(self) -> None:
        assert format_duration(5.3) == "5.3s"

    def test_zero_seconds(self) -> None:
        assert format_duration(0.0) == "0.0s"

    def test_under_one_second(self) -> None:
        assert format_duration(0.7) == "0.7s"

    def test_just_under_one_minute(self) -> None:
        assert format_duration(59.9) == "59.9s"

    def test_minutes_and_seconds(self) -> None:
        assert format_duration(125.5) == "2m 5.5s"

    def test_exactly_one_minute(self) -> None:
        assert format_duration(60.0) == "1m 0.0s"

    def test_exactly_one_hour(self) -> None:
        assert format_duration(3600.0) == "1h 0m 0s"

    def test_hours_minutes_seconds(self) -> None:
        result = format_duration(3661.0)
        assert result == "1h 1m 1s"


class TestShortenPath:
    """Tests for shorten_path utility function."""

    def test_short_path_unchanged(self) -> None:
        path = "src/main.py"
        assert shorten_path(path, max_len=50) == path

    def test_path_at_max_length(self) -> None:
        path = "a" * 50
        assert shorten_path(path, max_len=50) == path

    def test_long_path_shortened(self) -> None:
        path = "very/long/path/to/some/deeply/nested/file.py"
        result = shorten_path(path, max_len=20)
        assert result.startswith("...")
        assert result.endswith("nested/file.py")

    def test_two_part_path_unchanged(self) -> None:
        path = "a" * 60 + "/" + "b" * 60
        assert shorten_path(path, max_len=50) == path

    def test_keeps_last_two_parts(self) -> None:
        path = "one/two/three/four/five.py"
        result = shorten_path(path, max_len=10)
        assert "four/five.py" in result


def _capture_console() -> tuple[Console, StringIO]:
    """Create a Console that writes to a StringIO buffer.

    Uses no_color=True so output is plain text without ANSI escape codes,
    and width=200 to prevent Rich from wrapping lines in assertions.
    """
    buf = StringIO()
    return Console(file=buf, no_color=True, width=200), buf


class TestPrintSummary:
    """Tests for IndexingProgressRenderer.print_summary."""

    def test_shows_repo_name(self) -> None:
        console, buf = _capture_console()
        renderer = IndexingProgressRenderer(console)
        renderer.print_summary(IndexingStats(), repo_name="my-repo")
        output = buf.getvalue()
        assert "my-repo" in output

    def test_shows_branch(self) -> None:
        console, buf = _capture_console()
        renderer = IndexingProgressRenderer(console)
        renderer.print_summary(IndexingStats(), branch="develop")
        output = buf.getvalue()
        assert "develop" in output

    def test_shows_elapsed_time(self) -> None:
        console, buf = _capture_console()
        renderer = IndexingProgressRenderer(console)
        renderer.print_summary(IndexingStats(), elapsed_seconds=45.2)
        output = buf.getvalue()
        assert "45.2s" in output

    def test_shows_resolution_rate(self) -> None:
        console, buf = _capture_console()
        renderer = IndexingProgressRenderer(console)
        stats = IndexingStats(references_found=200, references_resolved=150)
        renderer.print_summary(stats)
        output = buf.getvalue()
        assert "75.0%" in output

    def test_shows_file_version_stats(self) -> None:
        console, buf = _capture_console()
        renderer = IndexingProgressRenderer(console)
        stats = IndexingStats(file_versions_new=10, file_versions_cached=50)
        renderer.print_summary(stats)
        output = buf.getvalue()
        assert "File Versions (new)" in output
        assert "File Versions (cached)" in output

    def test_shows_errors(self) -> None:
        console, buf = _capture_console()
        renderer = IndexingProgressRenderer(console)
        stats = IndexingStats(errors=["error 1", "error 2"])
        renderer.print_summary(stats)
        output = buf.getvalue()
        assert "Warnings (2)" in output
        assert "error 1" in output

    def test_shows_db_stats(self) -> None:
        console, buf = _capture_console()
        renderer = IndexingProgressRenderer(console)
        stats = IndexingStats(
            db_stats=DBQueryStats(selects=10, inserts=5, updates=2, deletes=0)
        )
        renderer.print_summary(stats)
        output = buf.getvalue()
        assert "DB Queries" in output
        assert "Selects" in output

    def test_title_always_shows_index_complete(self) -> None:
        """Title should always show 'Index Complete'."""
        console, buf = _capture_console()
        renderer = IndexingProgressRenderer(console)
        renderer.print_summary(IndexingStats())
        output = buf.getvalue()
        assert "Index Complete" in output

    def test_shows_days_range(self) -> None:
        console, buf = _capture_console()
        renderer = IndexingProgressRenderer(console)
        renderer.print_summary(IndexingStats(), days=7)
        output = buf.getvalue()
        assert "last 7 days" in output

    def test_shows_text_content_stats(self) -> None:
        console, buf = _capture_console()
        renderer = IndexingProgressRenderer(console)
        stats = IndexingStats(
            comments_indexed=100, docstrings_indexed=50, commit_messages_indexed=25
        )
        renderer.print_summary(stats)
        output = buf.getvalue()
        assert "Text Content Indexed" in output
        assert "Comments" in output
        assert "Docstrings" in output
        assert "Commit Messages" in output

    def test_error_truncation_beyond_five(self) -> None:
        """More than 5 errors should show '... and N more'."""
        console, buf = _capture_console()
        renderer = IndexingProgressRenderer(console)
        stats = IndexingStats(errors=[f"error {i}" for i in range(8)])
        renderer.print_summary(stats)
        output = buf.getvalue()
        assert "Warnings (8)" in output
        assert "error 0" in output
        assert "error 4" in output
        assert "... and 3 more" in output

    def test_no_separator_without_repo_or_branch(self) -> None:
        """Without repo_name or branch, no separator row should appear."""
        console, buf = _capture_console()
        renderer = IndexingProgressRenderer(console)
        renderer.print_summary(IndexingStats(symbols_found=42))
        output = buf.getvalue()
        # The first content row should be a stats row, not a blank separator
        assert "Symbols Found" in output
        # repo_name/branch are absent
        assert "Repository" not in output
        assert "Branch" not in output


class TestProgressCallback:
    """Tests for IndexingProgressRenderer.create_progress_callback."""

    def test_initial_file_count(self) -> None:
        console, _ = _capture_console()
        renderer = IndexingProgressRenderer(console)
        output = StringIO()
        callback = renderer.create_progress_callback(output=output)

        progress = IndexingProgress(phase="files", files_processed=0, files_total=100)
        callback(progress)
        # The "Files to process" line goes to console, not output
        # But 0% milestone should write to output
        assert "0%" in output.getvalue()

    def test_file_milestone(self) -> None:
        console, _ = _capture_console()
        renderer = IndexingProgressRenderer(console)
        output = StringIO()
        callback = renderer.create_progress_callback(output=output)

        # Trigger initial display
        callback(IndexingProgress(phase="files", files_processed=0, files_total=100))
        # Hit 50% milestone
        callback(
            IndexingProgress(
                phase="files",
                files_processed=50,
                files_total=100,
                symbols_found=200,
                references_found=100,
            )
        )
        text = output.getvalue()
        assert "50%" in text
        assert "50/100" in text

    def test_phase_transition_to_resolving(self) -> None:
        console, console_buf = _capture_console()
        renderer = IndexingProgressRenderer(console)
        output = StringIO()
        callback = renderer.create_progress_callback(output=output)

        callback(
            IndexingProgress(
                phase="resolving",
                files_processed=100,
                files_total=100,
                refs_total=500,
                refs_resolved=0,
            )
        )
        console_text = console_buf.getvalue()
        assert "Resolving references" in console_text

    def test_resolution_milestone(self) -> None:
        console, _ = _capture_console()
        renderer = IndexingProgressRenderer(console)
        output = StringIO()
        callback = renderer.create_progress_callback(output=output)

        # Enter resolving phase
        callback(
            IndexingProgress(
                phase="resolving",
                files_processed=100,
                files_total=100,
                refs_total=200,
                refs_resolved=0,
            )
        )
        # Hit 50% resolution
        callback(
            IndexingProgress(
                phase="resolving",
                files_processed=100,
                files_total=100,
                refs_total=200,
                refs_resolved=100,
            )
        )
        text = output.getvalue()
        assert "Resolved:" in text
        assert "100/200" in text
        assert "50%" in text

    def test_spinner_rotates_on_each_call(self) -> None:
        """Each callback should show a different spinner character."""
        console, _ = _capture_console()
        renderer = IndexingProgressRenderer(console)
        output = StringIO()
        callback = renderer.create_progress_callback(output=output)

        progress = IndexingProgress(phase="files", files_processed=50, files_total=100)
        callback(progress)
        callback(progress)
        text = output.getvalue()
        # Both calls write output (spinner keeps line alive)
        assert text.count("50%") == 2
        # Different spinner chars on each line
        lines = [part.strip() for part in text.split("\r") if part.strip()]
        assert len(lines) == 2
        assert lines[0][0] != lines[1][0]  # spinner rotated

    def test_files_total_zero_no_crash(self) -> None:
        """files_total=0 should not cause division by zero."""
        console, _ = _capture_console()
        renderer = IndexingProgressRenderer(console)
        output = StringIO()
        callback = renderer.create_progress_callback(output=output)

        callback(IndexingProgress(phase="files", files_processed=0, files_total=0))
        # No output expected and no crash
        assert True

    def test_resolving_refs_total_zero(self) -> None:
        """Resolving phase with refs_total=0 should show header but no percentages."""
        console, console_buf = _capture_console()
        renderer = IndexingProgressRenderer(console)
        output = StringIO()
        callback = renderer.create_progress_callback(output=output)

        callback(
            IndexingProgress(
                phase="resolving",
                files_processed=100,
                files_total=100,
                refs_total=0,
                refs_resolved=0,
            )
        )
        console_text = console_buf.getvalue()
        assert "Resolving references" in console_text
        # No percentage output since refs_total=0
        assert "%" not in output.getvalue()


class TestCreateProgressBar:
    """Tests for IndexingProgressRenderer.create_progress_bar."""

    def test_returns_progress_instance(self) -> None:
        from rich.progress import Progress

        console, _ = _capture_console()
        renderer = IndexingProgressRenderer(console)
        result = renderer.create_progress_bar()
        assert isinstance(result, Progress)


class TestPrintFinalResolution:
    """Tests for IndexingProgressRenderer.print_final_resolution."""

    def test_prints_when_resolving(self) -> None:
        console, _ = _capture_console()
        renderer = IndexingProgressRenderer(console)
        output = StringIO()
        renderer.print_final_resolution(
            references_found=200,
            references_resolved=150,
            was_resolving=True,
            output=output,
        )
        text = output.getvalue()
        assert "150/200" in text
        assert "75%" in text

    def test_noop_when_not_resolving(self) -> None:
        console, _ = _capture_console()
        renderer = IndexingProgressRenderer(console)
        output = StringIO()
        renderer.print_final_resolution(
            references_found=200,
            references_resolved=150,
            was_resolving=False,
            output=output,
        )
        assert output.getvalue() == ""

    def test_noop_when_no_references(self) -> None:
        console, _ = _capture_console()
        renderer = IndexingProgressRenderer(console)
        output = StringIO()
        renderer.print_final_resolution(
            references_found=0,
            references_resolved=0,
            was_resolving=True,
            output=output,
        )
        assert output.getvalue() == ""
