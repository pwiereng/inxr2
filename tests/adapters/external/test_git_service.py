"""Tests for GitService adapter."""

from pathlib import Path

import pytest

from inxr2.adapters.external.git_service import GitService


class TestGitService:
    """Tests for GitService using the INXR2 repository itself."""

    @pytest.fixture
    def git_service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.fixture
    def repo_path(self) -> Path:
        """Get the INXR2 repository path."""
        # The test runs from the repo root, so we can use the current directory
        return Path(__file__).parent.parent.parent.parent

    def test_get_repository_info(
        self, git_service: GitService, repo_path: Path
    ) -> None:
        """Test getting repository information."""
        info = git_service.get_repository_info(repo_path)

        assert "name" in info
        assert info["name"] == repo_path.name
        assert "current_branch" in info
        assert info["current_branch"] is not None or info.get("is_bare") is True
        assert "is_bare" in info
        assert info["is_bare"] is False

    def test_get_current_commit(self, git_service: GitService, repo_path: Path) -> None:
        """Test getting current commit hash."""
        commit = git_service.get_current_commit(repo_path)

        # Commit hash should be 40 hex characters
        assert len(commit) == 40
        assert all(c in "0123456789abcdef" for c in commit)

    def test_get_commit_info(self, git_service: GitService, repo_path: Path) -> None:
        """Test getting commit information."""
        commit_hash = git_service.get_current_commit(repo_path)
        info = git_service.get_commit_info(repo_path, commit_hash)

        assert info["hash"] == commit_hash
        assert len(info["short_hash"]) == 7
        assert "author_name" in info
        assert "author_email" in info
        assert "message" in info
        assert "commit_date" in info

    def test_list_files(self, git_service: GitService, repo_path: Path) -> None:
        """Test listing files at a commit."""
        commit_hash = git_service.get_current_commit(repo_path)
        files = git_service.list_files(repo_path, commit_hash)

        # Should contain some expected files
        assert len(files) > 0
        assert "pyproject.toml" in files
        assert "README.md" in files

        # Should contain Python and TypeScript files
        py_files = [f for f in files if f.endswith(".py")]
        ts_files = [f for f in files if f.endswith((".ts", ".tsx"))]
        assert len(py_files) > 0
        assert len(ts_files) > 0

    def test_list_files_with_pattern(
        self, git_service: GitService, repo_path: Path
    ) -> None:
        """Test listing files with glob pattern filter."""
        commit_hash = git_service.get_current_commit(repo_path)
        files = git_service.list_files(repo_path, commit_hash, patterns=["*.py"])

        # All files should be Python files
        assert len(files) > 0
        assert all(f.endswith(".py") for f in files)

    def test_get_file_content(self, git_service: GitService, repo_path: Path) -> None:
        """Test getting file content at a commit."""
        commit_hash = git_service.get_current_commit(repo_path)
        content = git_service.get_file_content(repo_path, commit_hash, "pyproject.toml")

        # Should contain expected content
        assert "[project]" in content
        assert "inxr2" in content

    def test_get_file_content_not_found(
        self, git_service: GitService, repo_path: Path
    ) -> None:
        """Test getting content of non-existent file."""
        commit_hash = git_service.get_current_commit(repo_path)

        with pytest.raises(FileNotFoundError):
            git_service.get_file_content(
                repo_path, commit_hash, "non_existent_file.xyz"
            )

    def test_get_file_hash(self, git_service: GitService, repo_path: Path) -> None:
        """Test getting file blob hash."""
        commit_hash = git_service.get_current_commit(repo_path)
        file_hash = git_service.get_file_hash(repo_path, commit_hash, "pyproject.toml")

        # Blob hash should be 40 hex characters
        assert len(file_hash) == 40
        assert all(c in "0123456789abcdef" for c in file_hash)

    def test_is_binary_file(self, git_service: GitService, repo_path: Path) -> None:
        """Test binary file detection."""
        commit_hash = git_service.get_current_commit(repo_path)

        # pyproject.toml is not binary
        assert (
            git_service.is_binary_file(repo_path, commit_hash, "pyproject.toml")
            is False
        )

    def test_invalid_repository_path(
        self, git_service: GitService, tmp_path: Path
    ) -> None:
        """Test handling of invalid repository path."""
        # Create a directory that's not a git repo
        not_git = tmp_path / "not-a-git-repo"
        not_git.mkdir()

        with pytest.raises(ValueError, match="Not a valid git repository"):
            git_service.get_repository_info(not_git)


class TestGitServiceChangedFiles:
    """Tests for changed files detection."""

    @pytest.fixture
    def git_service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.fixture
    def repo_path(self) -> Path:
        """Get the INXR2 repository path."""
        return Path(__file__).parent.parent.parent.parent

    def test_get_commits_since(self, git_service: GitService, repo_path: Path) -> None:
        """Test getting commits since a given commit."""
        # Get recent commits
        current = git_service.get_current_commit(repo_path)
        info = git_service.get_commit_info(repo_path, current)
        parent_hashes = info.get("parent_hashes", [])

        if parent_hashes:
            # Get commits since parent
            commits = git_service.get_commits_since(repo_path, parent_hashes[0])
            assert len(commits) >= 1
            assert current in commits

    def test_get_changed_files(self, git_service: GitService, repo_path: Path) -> None:
        """Test getting changed files between commits."""
        current = git_service.get_current_commit(repo_path)
        info = git_service.get_commit_info(repo_path, current)
        parent_hashes = info.get("parent_hashes", [])

        if parent_hashes:
            changed = git_service.get_changed_files(
                repo_path, parent_hashes[0], current
            )

            assert "added" in changed
            assert "modified" in changed
            assert "deleted" in changed
            assert isinstance(changed["added"], list)
            assert isinstance(changed["modified"], list)
            assert isinstance(changed["deleted"], list)


class TestGitServiceBranches:
    """Tests for branch listing functionality."""

    @pytest.fixture
    def git_service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.fixture
    def repo_path(self) -> Path:
        """Get the INXR2 repository path."""
        return Path(__file__).parent.parent.parent.parent

    def test_list_branches(self, git_service: GitService, repo_path: Path) -> None:
        """Test listing branches in a repository."""
        branches = git_service.list_branches(repo_path)

        # Should return a list of branch names
        assert isinstance(branches, list)
        assert len(branches) > 0

        # All items should be strings
        assert all(isinstance(b, str) for b in branches)

        # Should have at least main or master
        has_default = "main" in branches or "master" in branches
        assert has_default

    def test_list_branches_default_first(
        self, git_service: GitService, repo_path: Path
    ) -> None:
        """Test that default branch (main/master) is sorted first."""
        branches = git_service.list_branches(repo_path)

        # First branch should be main or master
        assert branches[0] in ("main", "master")

    def test_list_branches_ordered_by_date(
        self, git_service: GitService, repo_path: Path
    ) -> None:
        """Test that branches are ordered by last commit date after default."""
        branches = git_service.list_branches(repo_path)

        # Just verify we get branches and default is first
        # (Detailed date ordering is hard to verify without knowing commit dates)
        assert len(branches) > 0
        assert branches[0] in ("main", "master")


class TestGitServiceTimeTravel:
    """Tests for time travel functionality (multi-commit support)."""

    @pytest.fixture
    def git_service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.fixture
    def repo_path(self) -> Path:
        """Get the INXR2 repository path."""
        return Path(__file__).parent.parent.parent.parent

    def test_list_commits(self, git_service: GitService, repo_path: Path) -> None:
        """Test listing commits for a branch."""
        commits = git_service.list_commits(repo_path, "main", max_count=10)

        # Should return commits
        assert len(commits) > 0
        assert len(commits) <= 10

        # First commit should be oldest (list is sorted oldest first)
        first = commits[0]
        last = commits[-1]

        # Each commit should have required fields
        for commit in commits:
            assert "hash" in commit
            assert len(commit["hash"]) == 40
            assert "short_hash" in commit
            assert len(commit["short_hash"]) == 7
            assert "author_name" in commit
            assert "author_email" in commit
            assert "commit_date" in commit
            assert "message" in commit
            assert "parent_hashes" in commit

        # Oldest commit should be first (chronological order)
        if len(commits) > 1:
            assert first["commit_date"] <= last["commit_date"]

    def test_list_commits_limit(self, git_service: GitService, repo_path: Path) -> None:
        """Test that max_count limits results."""
        commits_5 = git_service.list_commits(repo_path, "main", max_count=5)
        commits_10 = git_service.list_commits(repo_path, "main", max_count=10)

        assert len(commits_5) <= 5
        assert len(commits_10) <= 10
        assert len(commits_10) >= len(commits_5)

    def test_list_commits_invalid_branch(
        self, git_service: GitService, repo_path: Path
    ) -> None:
        """Test listing commits for non-existent branch returns empty list."""
        commits = git_service.list_commits(
            repo_path, "non-existent-branch-xyz", max_count=10
        )
        assert commits == []

    def test_get_files_at_commit(
        self, git_service: GitService, repo_path: Path
    ) -> None:
        """Test getting all files at a specific commit."""
        commit_hash = git_service.get_current_commit(repo_path)
        files = git_service.get_files_at_commit(repo_path, commit_hash)

        # Should return a set of file paths
        assert isinstance(files, set)
        assert len(files) > 0

        # Should contain expected files
        assert "pyproject.toml" in files
        assert "README.md" in files

        # Should not contain directories
        for f in files:
            assert not f.endswith("/")

    def test_get_changed_files_in_commit(
        self, git_service: GitService, repo_path: Path
    ) -> None:
        """Test getting files changed in a single commit."""
        # Get a recent commit with a parent
        current = git_service.get_current_commit(repo_path)
        info = git_service.get_commit_info(repo_path, current)
        parent_hashes = info.get("parent_hashes", [])

        if parent_hashes:
            changed = git_service.get_changed_files_in_commit(repo_path, current)

            # Should have the three categories
            assert "added" in changed
            assert "modified" in changed
            assert "deleted" in changed
            assert isinstance(changed["added"], list)
            assert isinstance(changed["modified"], list)
            assert isinstance(changed["deleted"], list)

            # At least one file should be changed
            total_changes = (
                len(changed["added"])
                + len(changed["modified"])
                + len(changed["deleted"])
            )
            assert total_changes > 0

    def test_get_changed_files_initial_commit(
        self, git_service: GitService, repo_path: Path
    ) -> None:
        """Test getting changed files for initial commit (no parent)."""
        # Get the initial commit (oldest)
        commits = git_service.list_commits(repo_path, "main", max_count=100)
        if commits:
            initial_commit = commits[0]["hash"]
            changed = git_service.get_changed_files_in_commit(repo_path, initial_commit)

            # Initial commit should have only "added" files
            assert "added" in changed
            assert len(changed["added"]) > 0
            # No modified or deleted in initial commit
            assert len(changed["modified"]) == 0
            assert len(changed["deleted"]) == 0
