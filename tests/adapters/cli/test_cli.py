"""Tests for CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner
from git import Repo

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
        # Index command now runs directly (no "full" subcommand needed)
        assert "--config" in result.output
        assert "--path" in result.output
        assert "status" in result.output

    def test_index_full_help(self, runner: CliRunner) -> None:
        """Test index full help command."""
        result = runner.invoke(main, ["index", "--help"])
        assert result.exit_code == 0
        assert "--path" in result.output
        assert "--branch" in result.output
        assert "--languages" in result.output
        assert "--verbose" in result.output

    def test_index_status_help(self, runner: CliRunner) -> None:
        """Test index status help command."""
        result = runner.invoke(main, ["index", "status", "--help"])
        assert result.exit_code == 0
        assert "--path" in result.output

    def test_index_full_missing_path_or_config(self, runner: CliRunner) -> None:
        """Test index full without path or config."""
        result = runner.invoke(main, ["index"])
        assert result.exit_code != 0
        assert (
            "--path or --config" in result.output
            or "must be specified" in result.output
        )

    def test_index_full_invalid_path(self, runner: CliRunner) -> None:
        """Test index full with invalid path."""
        result = runner.invoke(main, ["index", "--path", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_index_full_not_git_repo(self, runner: CliRunner) -> None:
        """Test index full on non-git directory."""
        with runner.isolated_filesystem():
            # Create a directory that's not a git repo
            Path("not-a-repo").mkdir()

            result = runner.invoke(main, ["index", "--path", "not-a-repo"])
            assert result.exit_code != 0
            assert "No .git directory" in result.output

    def test_index_full_days_must_be_positive(self, runner: CliRunner) -> None:
        """Test that --days rejects zero or negative values."""
        # Test zero
        result = runner.invoke(main, ["index", "--path", ".", "--days", "0"])
        assert result.exit_code != 0
        assert "positive integer" in result.output.lower()

        # Test negative
        result = runner.invoke(main, ["index", "--path", ".", "--days", "-5"])
        assert result.exit_code != 0
        assert "positive integer" in result.output.lower()


class TestIndexOnTempRepo:
    """Tests that run indexing on a temporary git repository.

    These tests use an isolated SQLite database to avoid touching the
    live PostgreSQL database. The temp paths are automatically cleaned
    up by pytest's tmp_path fixture.
    """

    @pytest.fixture
    def runner(self, isolated_cli_runner: CliRunner) -> CliRunner:
        """Use the isolated CLI runner with test database."""
        return isolated_cli_runner

    @pytest.fixture
    def temp_git_repo(self, tmp_path: Path) -> Path:
        """Create a temporary git repository for testing.

        Uses a unique path based on tmp_path to avoid clashing with
        any existing repos in the database.
        """
        # Use unique name based on tmp_path to avoid database collisions
        repo_path = tmp_path / "cli-test-repo"
        repo_path.mkdir()

        # Initialize git repo
        repo = Repo.init(repo_path, initial_branch="main")
        repo.config_writer().set_value("user", "name", "Test User").release()
        repo.config_writer().set_value("user", "email", "test@example.com").release()

        # Create a test file and commit
        test_file = repo_path / "test.py"
        test_file.write_text("def hello():\n    pass\n")
        repo.index.add(["test.py"])
        repo.index.commit("Initial commit")

        return repo_path

    def test_index_status_on_repo(self, runner: CliRunner, temp_git_repo: Path) -> None:
        """Test index status on a git repo.

        The temp repo uses a unique path so it won't exist in the database,
        and the command should show "not indexed" status.
        """
        result = runner.invoke(main, ["index", "status", "--path", str(temp_git_repo)])
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


class TestBranchActivityFiltering:
    """Tests for branch activity filtering with --days option.

    These tests use an isolated SQLite database to avoid touching the
    live PostgreSQL database. The isolated_cli_runner fixture from
    conftest.py provides database isolation via DATABASE_URL env var.
    """

    @pytest.fixture
    def runner(self, isolated_cli_runner: CliRunner) -> CliRunner:
        """Use the isolated CLI runner with test database."""
        return isolated_cli_runner

    @pytest.fixture
    def temp_git_repo_with_branches(self, tmp_path: Path) -> Path:
        """Create a temp git repo with multiple branches and different commit ages."""
        from datetime import datetime, timedelta

        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()

        # Initialize git repo
        repo = Repo.init(repo_path, initial_branch="main")
        repo.config_writer().set_value("user", "name", "Test User").release()
        repo.config_writer().set_value("user", "email", "test@example.com").release()

        # Create initial commit on main (recent)
        test_file = repo_path / "main.py"
        test_file.write_text("# main branch\ndef main():\n    pass\n")
        repo.index.add(["main.py"])
        repo.index.commit("Initial commit on main")

        # Create old-branch with an old commit
        repo.create_head("old-branch")
        repo.heads["old-branch"].checkout()
        old_file = repo_path / "old.py"
        old_file.write_text("# old branch\ndef old():\n    pass\n")
        repo.index.add(["old.py"])
        # Create commit with old date (30 days ago)
        old_date = datetime.now() - timedelta(days=30)
        commit_date = old_date.strftime("%Y-%m-%d %H:%M:%S")
        repo.index.commit(
            "Old commit",
            author_date=commit_date,
            commit_date=commit_date,
        )

        # Go back to main
        repo.heads["main"].checkout()

        return repo_path

    @pytest.fixture
    def config_file(self, tmp_path: Path, temp_git_repo_with_branches: Path) -> Path:
        """Create a config file for the test repo."""
        config_path = tmp_path / "config.yaml"
        config_content = f"""
repositories:
  - name: test-repo
    path: {temp_git_repo_with_branches}
    branches:
      - main
      - old-branch
    languages:
      - python

indexing:
  max_commit_history: 100
"""
        config_path.write_text(config_content)
        return config_path

    def test_old_branch_skipped_with_days_filter(
        self, runner: CliRunner, config_file: Path
    ) -> None:
        """Test that branches without recent commits are skipped when --days is used."""
        result = runner.invoke(
            main,
            ["index", "--config", str(config_file), "--days", "7"],
            catch_exceptions=False,
        )

        # Command should succeed with isolated test database
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Old branch should be skipped
        assert "old-branch" in result.output
        assert "Skipped" in result.output
        assert "No commits within last 7 days" in result.output

    def test_all_branches_indexed_without_days_filter(
        self, runner: CliRunner, config_file: Path
    ) -> None:
        """Test that all branches are indexed when --days is not used."""
        result = runner.invoke(
            main,
            ["index", "--config", str(config_file)],
            catch_exceptions=False,
        )

        # Command should succeed with isolated test database
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Both branches should be attempted (not skipped for activity reasons)
        assert "No commits within" not in result.output

    def test_primary_branch_always_indexed_with_days_filter(
        self, runner: CliRunner, config_file: Path
    ) -> None:
        """Test that the primary branch (first in config) is always indexed even with --days."""
        result = runner.invoke(
            main,
            ["index", "--config", str(config_file), "--days", "7"],
            catch_exceptions=False,
        )

        # Command should succeed with isolated test database
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Main branch (primary) should be indexed, not skipped
        lines = result.output.split("\n")
        main_branch_skipped = False
        for i, line in enumerate(lines):
            if "Branch: main" in line:
                # Check if the next few lines contain "Skipped"
                context = "\n".join(lines[i : i + 3])
                if "Skipped" in context:
                    main_branch_skipped = True
                break

        assert not main_branch_skipped, "Primary branch (main) should never be skipped"

    def test_primary_branch_with_recent_commits_uses_days_filter(
        self, runner: CliRunner, config_file: Path
    ) -> None:
        """Test that primary branch uses --days filter when it has recent commits."""
        result = runner.invoke(
            main,
            ["index", "--config", str(config_file), "--days", "7"],
            catch_exceptions=False,
        )

        # Command should succeed with isolated test database
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Main branch has recent commits, so should use --days filter (not just HEAD)
        assert "(primary)" in result.output
        lines = result.output.split("\n")
        main_using_days = False
        for i, line in enumerate(lines):
            if "Branch: main" in line and "(primary)" in line:
                # Check subsequent lines for the strategy
                context = "\n".join(lines[i : i + 3])
                # Should show "last 7 days (has recent commits)" strategy
                if "last 7 days" in context and "has recent commits" in context:
                    main_using_days = True
                break

        assert (
            main_using_days
        ), "Primary branch with recent commits should use --days filter"

    @pytest.fixture
    def temp_git_repo_primary_old(self, tmp_path: Path) -> Path:
        """Create a temp git repo where the primary branch has only old commits."""
        from datetime import datetime, timedelta

        repo_path = tmp_path / "primary-old-repo"
        repo_path.mkdir()

        # Initialize git repo
        repo = Repo.init(repo_path, initial_branch="main")
        repo.config_writer().set_value("user", "name", "Test User").release()
        repo.config_writer().set_value("user", "email", "test@example.com").release()

        # Create old commit on main (30 days ago)
        test_file = repo_path / "main.py"
        test_file.write_text("# main branch\ndef main():\n    pass\n")
        repo.index.add(["main.py"])
        old_date = datetime.now() - timedelta(days=30)
        commit_date = old_date.strftime("%Y-%m-%d %H:%M:%S")
        repo.index.commit(
            "Old commit on main",
            author_date=commit_date,
            commit_date=commit_date,
        )

        return repo_path

    @pytest.fixture
    def config_file_primary_old(
        self, tmp_path: Path, temp_git_repo_primary_old: Path
    ) -> Path:
        """Create a config file for the repo with old primary branch."""
        config_path = tmp_path / "config-primary-old.yaml"
        config_content = f"""
repositories:
  - name: primary-old-test
    path: {temp_git_repo_primary_old}
    branches:
      - main
    languages:
      - python

indexing:
  max_commit_history: 100
"""
        config_path.write_text(config_content)
        return config_path

    def test_primary_branch_no_recent_commits_falls_back_to_head(
        self, runner: CliRunner, config_file_primary_old: Path
    ) -> None:
        """Test that primary branch falls back to HEAD only when no recent commits."""
        result = runner.invoke(
            main,
            ["index", "--config", str(config_file_primary_old), "--days", "7"],
            catch_exceptions=False,
        )

        # Command should succeed with isolated test database
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Primary branch has no recent commits, should fall back to HEAD only
        assert "(primary)" in result.output
        lines = result.output.split("\n")
        main_head_only = False
        for i, line in enumerate(lines):
            if "Branch: main" in line and "(primary)" in line:
                # Check subsequent lines for HEAD-only strategy
                context = "\n".join(lines[i : i + 3])
                # Should show "HEAD only (no commits in last 7 days)" strategy
                if "HEAD only" in context and "no commits in last 7 days" in context:
                    main_head_only = True
                break

        assert (
            main_head_only
        ), "Primary branch with no recent commits should fall back to HEAD only"
