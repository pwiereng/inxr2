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
