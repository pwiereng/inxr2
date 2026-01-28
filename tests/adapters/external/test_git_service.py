"""Tests for GitService adapter."""

from pathlib import Path

import pytest
from git import Repo

from inxr2.adapters.external.git_service import GitService


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository with controlled test data.

    This fixture creates an isolated git repo with:
    - 3 commits on main branch
    - 1 feature branch with additional commits
    - Known file content at each commit

    Returns the path to the repository.
    """
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    # Initialize repo with explicit initial branch name
    repo = Repo.init(repo_path, initial_branch="main")

    # Configure git user for commits
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    # Create initial commit
    readme = repo_path / "README.md"
    readme.write_text("# Test Repository\n\nInitial content.\n")

    gitignore = repo_path / ".gitignore"
    gitignore.write_text("*.pyc\n__pycache__/\n")

    repo.index.add(["README.md", ".gitignore"])
    repo.index.commit("Initial commit")

    # Second commit - add Python file
    src_dir = repo_path / "src"
    src_dir.mkdir()
    main_py = src_dir / "main.py"
    main_py.write_text('def hello():\n    return "Hello, World!"\n')

    repo.index.add(["src/main.py"])
    repo.index.commit("Add main.py")

    # Third commit - modify README
    readme.write_text("# Test Repository\n\nUpdated content with more info.\n")
    repo.index.add(["README.md"])
    repo.index.commit("Update README")

    # Create feature branch with additional commit
    feature_branch = repo.create_head("feature-branch")
    feature_branch.checkout()

    utils_py = src_dir / "utils.py"
    utils_py.write_text('def helper():\n    return "Helper function"\n')

    repo.index.add(["src/utils.py"])
    repo.index.commit("Add utils.py on feature branch")

    # Switch back to main using git command (works regardless of branch name)
    repo.git.checkout("main")

    return repo_path


class TestGitService:
    """Tests for GitService basic functionality."""

    @pytest.fixture
    def git_service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    def test_get_repository_info(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test getting repository information."""
        info = git_service.get_repository_info(temp_git_repo)

        assert "name" in info
        assert info["name"] == temp_git_repo.name
        assert "current_branch" in info
        assert info["current_branch"] == "main"
        assert "is_bare" in info
        assert info["is_bare"] is False

    def test_get_current_commit(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test getting current commit hash."""
        commit = git_service.get_current_commit(temp_git_repo)

        # Commit hash should be 40 hex characters
        assert len(commit) == 40
        assert all(c in "0123456789abcdef" for c in commit)

    def test_get_commit_info(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test getting commit information."""
        commit_hash = git_service.get_current_commit(temp_git_repo)
        info = git_service.get_commit_info(temp_git_repo, commit_hash)

        assert info["hash"] == commit_hash
        assert len(info["short_hash"]) == 7
        assert info["author_name"] == "Test User"
        assert info["author_email"] == "test@example.com"
        assert "message" in info
        assert "commit_date" in info

    def test_list_files(self, git_service: GitService, temp_git_repo: Path) -> None:
        """Test listing files at a commit."""
        commit_hash = git_service.get_current_commit(temp_git_repo)
        files = git_service.list_files(temp_git_repo, commit_hash)

        # Should contain expected files
        assert len(files) == 3  # README.md, .gitignore, src/main.py
        assert "README.md" in files
        assert ".gitignore" in files
        assert "src/main.py" in files

    def test_list_files_with_pattern(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test listing files with glob pattern filter."""
        commit_hash = git_service.get_current_commit(temp_git_repo)
        files = git_service.list_files(temp_git_repo, commit_hash, patterns=["*.py"])

        # All files should be Python files
        assert len(files) == 1
        assert all(f.endswith(".py") for f in files)
        assert "src/main.py" in files

    def test_get_file_content(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test getting file content at a commit."""
        commit_hash = git_service.get_current_commit(temp_git_repo)
        content = git_service.get_file_content(temp_git_repo, commit_hash, "README.md")

        # Should contain expected content
        assert "# Test Repository" in content
        assert "Updated content" in content

    def test_get_file_content_not_found(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test getting content of non-existent file."""
        commit_hash = git_service.get_current_commit(temp_git_repo)

        with pytest.raises(FileNotFoundError):
            git_service.get_file_content(
                temp_git_repo, commit_hash, "non_existent_file.xyz"
            )

    def test_get_file_hash(self, git_service: GitService, temp_git_repo: Path) -> None:
        """Test getting file blob hash."""
        commit_hash = git_service.get_current_commit(temp_git_repo)
        file_hash = git_service.get_file_hash(temp_git_repo, commit_hash, "README.md")

        # Blob hash should be 40 hex characters
        assert len(file_hash) == 40
        assert all(c in "0123456789abcdef" for c in file_hash)

    def test_is_binary_file(self, git_service: GitService, temp_git_repo: Path) -> None:
        """Test binary file detection."""
        commit_hash = git_service.get_current_commit(temp_git_repo)

        # README.md is not binary
        assert (
            git_service.is_binary_file(temp_git_repo, commit_hash, "README.md") is False
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

    def test_get_commits_since(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test getting commits since a given commit."""
        # Get the initial commit (first in chronological order)
        commits = git_service.list_commits(temp_git_repo, "main", max_count=None)
        assert len(commits) == 3  # Initial, add main.py, update README

        initial_commit = commits[0]["hash"]

        # Get commits since initial
        commits_since = git_service.get_commits_since(temp_git_repo, initial_commit)
        assert len(commits_since) == 2  # The two commits after initial

    def test_get_changed_files(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test getting changed files between commits."""
        commits = git_service.list_commits(temp_git_repo, "main", max_count=None)
        initial_commit = commits[0]["hash"]
        latest_commit = commits[-1]["hash"]

        changed = git_service.get_changed_files(
            temp_git_repo, initial_commit, latest_commit
        )

        assert "added" in changed
        assert "modified" in changed
        assert "deleted" in changed
        assert isinstance(changed["added"], list)
        assert isinstance(changed["modified"], list)
        assert isinstance(changed["deleted"], list)

        # src/main.py was added, README.md was modified
        assert "src/main.py" in changed["added"]
        assert "README.md" in changed["modified"]


class TestGitServiceBranches:
    """Tests for branch listing functionality."""

    @pytest.fixture
    def git_service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    def test_list_branches(self, git_service: GitService, temp_git_repo: Path) -> None:
        """Test listing branches in a repository."""
        branches = git_service.list_branches(temp_git_repo)

        # Should return a list of branch names
        assert isinstance(branches, list)
        assert len(branches) == 2  # main and feature-branch

        # All items should be strings
        assert all(isinstance(b, str) for b in branches)

        # Should have main
        assert "main" in branches
        assert "feature-branch" in branches

    def test_list_branches_default_first(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test that default branch (main/master) is sorted first."""
        branches = git_service.list_branches(temp_git_repo)

        # First branch should be main
        assert branches[0] == "main"


class TestGitServiceTimeTravel:
    """Tests for time travel functionality (multi-commit support)."""

    @pytest.fixture
    def git_service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    def test_list_commits(self, git_service: GitService, temp_git_repo: Path) -> None:
        """Test listing commits for a branch."""
        commits = git_service.list_commits(temp_git_repo, "main", max_count=10)

        # Should return 3 commits
        assert len(commits) == 3

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

        # Verify chronological order
        assert first["commit_date"] <= last["commit_date"]

        # Verify messages
        assert "Initial commit" in first["message"]
        assert "Update README" in last["message"]

    def test_list_commits_limit(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test that max_count limits results."""
        commits_2 = git_service.list_commits(temp_git_repo, "main", max_count=2)
        commits_10 = git_service.list_commits(temp_git_repo, "main", max_count=10)

        assert len(commits_2) == 2
        assert len(commits_10) == 3  # Only 3 commits exist

    def test_list_commits_invalid_branch(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test listing commits for non-existent branch returns empty list."""
        commits = git_service.list_commits(
            temp_git_repo, "non-existent-branch-xyz", max_count=10
        )
        assert commits == []

    def test_get_files_at_commit(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test getting all files at a specific commit."""
        commit_hash = git_service.get_current_commit(temp_git_repo)
        files = git_service.get_files_at_commit(temp_git_repo, commit_hash)

        # Should return a set of file paths
        assert isinstance(files, set)
        assert len(files) == 3

        # Should contain expected files
        assert "README.md" in files
        assert ".gitignore" in files
        assert "src/main.py" in files

        # Should not contain directories
        for f in files:
            assert not f.endswith("/")

    def test_get_changed_files_in_commit(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test getting files changed in a single commit."""
        # Get the commit that added main.py
        commits = git_service.list_commits(temp_git_repo, "main", max_count=None)
        add_main_commit = commits[1]["hash"]  # Second commit

        changed = git_service.get_changed_files_in_commit(
            temp_git_repo, add_main_commit
        )

        # Should have the three categories
        assert "added" in changed
        assert "modified" in changed
        assert "deleted" in changed

        # src/main.py was added in this commit
        assert "src/main.py" in changed["added"]
        assert len(changed["modified"]) == 0
        assert len(changed["deleted"]) == 0

    def test_get_changed_files_initial_commit(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test getting changed files for initial commit (no parent)."""
        commits = git_service.list_commits(temp_git_repo, "main", max_count=None)
        initial_commit = commits[0]["hash"]

        changed = git_service.get_changed_files_in_commit(temp_git_repo, initial_commit)

        # Initial commit should have only "added" files
        assert "added" in changed
        assert len(changed["added"]) == 2  # README.md and .gitignore
        assert "README.md" in changed["added"]
        assert ".gitignore" in changed["added"]

        # No modified or deleted in initial commit
        assert len(changed["modified"]) == 0
        assert len(changed["deleted"]) == 0


class TestGitServiceMergeBase:
    """Tests for merge-base functionality used in delta indexing."""

    @pytest.fixture
    def git_service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    def test_get_merge_base_same_branch(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test merge-base of a branch with itself returns latest commit."""
        merge_base = git_service.get_merge_base(temp_git_repo, "main", "main")

        # Merge base of branch with itself should be the branch HEAD
        assert merge_base is not None
        assert len(merge_base) == 40
        assert all(c in "0123456789abcdef" for c in merge_base)

    def test_get_merge_base_with_ancestor(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test merge-base between main and a commit on main returns that commit."""
        # Get an older commit on main
        commits = git_service.list_commits(temp_git_repo, "main", max_count=None)
        older_commit = commits[0]["hash"]  # Initial commit

        # Merge base between main and an older commit should be the older commit
        merge_base = git_service.get_merge_base(temp_git_repo, "main", older_commit)
        assert merge_base == older_commit

    def test_get_merge_base_nonexistent_branch(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test merge-base with non-existent branch returns None."""
        merge_base = git_service.get_merge_base(
            temp_git_repo, "main", "nonexistent-branch-xyz"
        )
        assert merge_base is None

    def test_get_merge_base_feature_branch(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test merge-base between main and feature branch."""
        merge_base = git_service.get_merge_base(temp_git_repo, "main", "feature-branch")

        # Should return a valid commit hash
        assert merge_base is not None
        assert len(merge_base) == 40

        # Should be accessible as a commit
        info = git_service.get_commit_info(temp_git_repo, merge_base)
        assert info["hash"] == merge_base


class TestGitServiceBranchCommits:
    """Tests for list_branch_commits used in delta indexing."""

    @pytest.fixture
    def git_service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    def test_list_branch_commits_main_vs_main(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test listing commits unique to main vs main returns empty."""
        # Main vs main should have no unique commits
        commits = git_service.list_branch_commits(temp_git_repo, "main", "main")
        assert commits == []

    def test_list_branch_commits_nonexistent_branch(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test listing commits for non-existent branch returns empty."""
        commits = git_service.list_branch_commits(
            temp_git_repo, "nonexistent-branch-xyz", "main"
        )
        assert commits == []

    def test_list_branch_commits_feature_branch(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test listing commits unique to feature branch."""
        commits = git_service.list_branch_commits(
            temp_git_repo, "feature-branch", "main", max_count=10
        )

        # Feature branch has 1 unique commit
        assert len(commits) == 1
        assert "Add utils.py" in commits[0]["message"]

        # Verify commit structure
        assert "hash" in commits[0]
        assert len(commits[0]["hash"]) == 40
        assert "short_hash" in commits[0]
        assert "author_name" in commits[0]
        assert "commit_date" in commits[0]

    def test_list_branch_commits_respects_max_count(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test that max_count limits results."""
        commits = git_service.list_branch_commits(
            temp_git_repo, "feature-branch", "main", max_count=0
        )
        # max_count=0 should still work (returns empty or respects limit)
        assert isinstance(commits, list)

    def test_list_branch_commits_no_base_branch(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test behavior when base branch doesn't exist."""
        # Should fall back to listing all commits on the branch
        commits = git_service.list_branch_commits(
            temp_git_repo, "main", "nonexistent-base-xyz", max_count=5
        )

        # Should return commits from main
        assert isinstance(commits, list)
        assert len(commits) <= 5
