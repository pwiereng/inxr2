"""Tests for CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from inxr2.cli import main


class TestCLIBasics:
    """Basic CLI tests."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI test runner."""
        return CliRunner()

    def test_main_help(self, runner: CliRunner) -> None:
        """Test main help command."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "INXR2" in result.output
        assert "index" in result.output
        assert "serve" in result.output
        assert "status" in result.output

    def test_version(self, runner: CliRunner) -> None:
        """Test version command."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        # Should show version number
        assert "version" in result.output.lower() or "0." in result.output


class TestIndexCommands:
    """Tests for index subcommands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI test runner."""
        return CliRunner()

    def test_index_help(self, runner: CliRunner) -> None:
        """Test index help command."""
        result = runner.invoke(main, ["index", "--help"])
        assert result.exit_code == 0
        assert "full" in result.output
        assert "incremental" in result.output
        assert "status" in result.output

    def test_index_full_help(self, runner: CliRunner) -> None:
        """Test index full help command."""
        result = runner.invoke(main, ["index", "full", "--help"])
        assert result.exit_code == 0
        assert "--path" in result.output
        assert "--branch" in result.output
        assert "--languages" in result.output
        assert "--verbose" in result.output

    def test_index_incremental_help(self, runner: CliRunner) -> None:
        """Test index incremental help command."""
        result = runner.invoke(main, ["index", "incremental", "--help"])
        assert result.exit_code == 0
        assert "--path" in result.output
        assert "--branch" in result.output

    def test_index_status_help(self, runner: CliRunner) -> None:
        """Test index status help command."""
        result = runner.invoke(main, ["index", "status", "--help"])
        assert result.exit_code == 0
        assert "--path" in result.output

    def test_index_full_missing_path_or_config(self, runner: CliRunner) -> None:
        """Test index full without path or config."""
        result = runner.invoke(main, ["index", "full"])
        assert result.exit_code != 0
        assert (
            "--path or --config" in result.output
            or "must be specified" in result.output
        )

    def test_index_full_invalid_path(self, runner: CliRunner) -> None:
        """Test index full with invalid path."""
        result = runner.invoke(main, ["index", "full", "--path", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_index_full_not_git_repo(self, runner: CliRunner) -> None:
        """Test index full on non-git directory."""
        with runner.isolated_filesystem():
            # Create a directory that's not a git repo
            Path("not-a-repo").mkdir()

            result = runner.invoke(main, ["index", "full", "--path", "not-a-repo"])
            assert result.exit_code != 0
            assert "No .git directory" in result.output


class TestIndexOnRealRepo:
    """Tests that run indexing on the actual INXR2 repository."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def repo_path(self) -> Path:
        """Get the INXR2 repository path."""
        return Path(__file__).parent.parent.parent.parent

    def test_index_status_on_repo(self, runner: CliRunner, repo_path: Path) -> None:
        """Test index status on INXR2 repo."""
        result = runner.invoke(main, ["index", "status", "--path", str(repo_path)])
        # Should not error (may show "not indexed" which is fine)
        assert result.exit_code == 0
        assert "Repository" in result.output


class TestServeCommand:
    """Tests for serve command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI test runner."""
        return CliRunner()

    def test_serve_help(self, runner: CliRunner) -> None:
        """Test serve help command."""
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--host" in result.output
        assert "--port" in result.output
        assert "--reload" in result.output


class TestStatusCommand:
    """Tests for top-level status command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI test runner."""
        return CliRunner()

    def test_status_help(self, runner: CliRunner) -> None:
        """Test status help command."""
        result = runner.invoke(main, ["status", "--help"])
        assert result.exit_code == 0
