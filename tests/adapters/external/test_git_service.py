"""Tests for GitService adapter."""

from pathlib import Path

import pytest
from git import Repo

from inxr2.adapters.external.git_service import GitService
from inxr2.domain.exceptions import (
    CommitNotFound,
    GitOperationError,
    InvalidRepositoryPath,
)


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

        assert info.name == temp_git_repo.name
        assert info.current_branch == "main"
        assert info.is_bare is False

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

        assert info.hash == commit_hash
        assert len(info.short_hash) == 7
        assert info.author_name == "Test User"
        assert info.author_email == "test@example.com"
        assert info.message
        assert info.commit_date is not None

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
        """Test handling of invalid repository path raises InvalidRepositoryPath."""
        # Create a directory that's not a git repo
        not_git = tmp_path / "not-a-git-repo"
        not_git.mkdir()

        with pytest.raises(InvalidRepositoryPath, match="Not a valid git repository"):
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

        initial_commit = commits[0].hash

        # Get commits since initial
        commits_since = git_service.get_commits_since(temp_git_repo, initial_commit)
        assert len(commits_since) == 2  # The two commits after initial

    def test_get_changed_files(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test getting changed files between commits."""
        commits = git_service.list_commits(temp_git_repo, "main", max_count=None)
        initial_commit = commits[0].hash
        latest_commit = commits[-1].hash

        changed = git_service.get_changed_files(
            temp_git_repo, initial_commit, latest_commit
        )

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
            assert len(commit.hash) == 40
            assert len(commit.short_hash) == 7
            assert commit.author_name
            assert commit.author_email
            assert commit.commit_date is not None
            assert commit.message is not None
            assert isinstance(commit.parent_hashes, list)

        # Verify chronological order
        assert first.commit_date <= last.commit_date

        # Verify messages
        assert "Initial commit" in first.message
        assert "Update README" in last.message

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
        add_main_commit = commits[1].hash  # Second commit

        changed = git_service.get_changed_files_in_commit(
            temp_git_repo, add_main_commit
        )

        # src/main.py was added in this commit
        assert "src/main.py" in changed.added
        assert len(changed.modified) == 0
        assert len(changed.deleted) == 0

    def test_get_changed_files_initial_commit(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Test getting changed files for initial commit (no parent)."""
        commits = git_service.list_commits(temp_git_repo, "main", max_count=None)
        initial_commit = commits[0].hash

        changed = git_service.get_changed_files_in_commit(temp_git_repo, initial_commit)

        # Initial commit should have only "added" files
        assert len(changed.added) == 2  # README.md and .gitignore
        assert "README.md" in changed.added
        assert ".gitignore" in changed.added

        # No modified or deleted in initial commit
        assert len(changed.modified) == 0
        assert len(changed.deleted) == 0


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
        older_commit = commits[0].hash  # Initial commit

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
        assert info.hash == merge_base


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
        assert "Add utils.py" in commits[0].message

        # Verify commit structure
        assert len(commits[0].hash) == 40
        assert commits[0].short_hash
        assert commits[0].author_name
        assert commits[0].commit_date is not None

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


class TestGitServiceRemoteBranchCommits:
    """Tests for list_branch_commits when branches only exist as remote refs.

    Regression tests for issue #188: indexer fails to walk branch history
    when only remote refs exist (e.g., read-only mounts without local branches).
    """

    @pytest.fixture
    def git_service(self) -> GitService:
        return GitService()

    @pytest.fixture
    def remote_only_repo(self, tmp_path: Path) -> Path:
        """Create a repo where branches only exist as remote refs (origin/*).

        Creates an upstream repo with main (2 commits) and feature-branch
        (1 unique commit), then clones it and deletes all local branches.
        """
        # Create upstream repo with commits
        upstream_path = tmp_path / "upstream"
        upstream_path.mkdir()
        upstream = Repo.init(upstream_path, initial_branch="main")
        upstream.config_writer().set_value("user", "name", "Test User").release()
        upstream.config_writer().set_value(
            "user", "email", "test@example.com"
        ).release()

        # Two commits on main
        readme = upstream_path / "README.md"
        readme.write_text("# Test\n")
        upstream.index.add(["README.md"])
        upstream.index.commit("Initial commit")

        main_py = upstream_path / "main.py"
        main_py.write_text("def main(): pass\n")
        upstream.index.add(["main.py"])
        upstream.index.commit("Add main.py")

        # Feature branch with one unique commit
        upstream.create_head("feature-branch").checkout()
        utils_py = upstream_path / "utils.py"
        utils_py.write_text("def helper(): pass\n")
        upstream.index.add(["utils.py"])
        upstream.index.commit("Add utils.py on feature branch")

        upstream.git.checkout("main")

        # Clone and remove all local branches so only origin/* refs remain
        clone_path = tmp_path / "clone"
        clone = Repo.clone_from(str(upstream_path), str(clone_path))
        clone.remotes.origin.fetch()
        clone.git.checkout("--detach", "HEAD")
        for branch in list(clone.branches):
            clone.git.branch("-D", str(branch))

        return clone_path

    def test_list_branch_commits_both_remote_only(
        self, git_service: GitService, remote_only_repo: Path
    ) -> None:
        """list_branch_commits returns correct commits when both branches
        only exist as remote refs (origin/*)."""
        commits = git_service.list_branch_commits(
            remote_only_repo, "feature-branch", "main"
        )
        assert len(commits) == 1
        assert "Add utils.py" in commits[0].message

    def test_list_commits_remote_only(
        self, git_service: GitService, remote_only_repo: Path
    ) -> None:
        """list_commits works when branch only exists as origin/*."""
        commits = git_service.list_commits(remote_only_repo, "main", max_count=10)
        assert len(commits) == 2
        assert "Initial commit" in commits[0].message
        assert "Add main.py" in commits[1].message

    def test_list_branch_commits_main_vs_main_remote_only(
        self, git_service: GitService, remote_only_repo: Path
    ) -> None:
        """list_branch_commits with same branch returns empty when remote-only."""
        commits = git_service.list_branch_commits(remote_only_repo, "main", "main")
        assert commits == []


class TestGitServiceNarrowedExceptions:
    """Regression tests: verify exception translation from GitPython to domain types.

    These tests exercise the actual error paths and confirm that GitPython
    exceptions are properly translated to domain exceptions (CommitNotFound,
    GitOperationError, InvalidRepositoryPath) or handled internally.
    """

    @pytest.fixture
    def git_service(self) -> GitService:
        return GitService()

    def test_get_current_commit_bad_branch_falls_back_to_head(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """get_current_commit with non-existent branch falls back to HEAD."""
        head_hash = git_service.get_current_commit(temp_git_repo)
        # Non-existent branch triggers BadName → fallback to head.commit
        result = git_service.get_current_commit(temp_git_repo, "no-such-branch-xyz")
        assert result == head_hash

    def test_get_changed_files_invalid_from_commit_raises_commit_not_found(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """get_changed_files with garbage from_commit raises CommitNotFound."""
        good_hash = git_service.get_current_commit(temp_git_repo)
        bad_hash = "deadbeef" * 5
        with pytest.raises(CommitNotFound) as exc_info:
            git_service.get_changed_files(temp_git_repo, bad_hash, good_hash)
        assert exc_info.value.commit_hash == bad_hash

    def test_get_changed_files_invalid_to_commit_raises_commit_not_found(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """get_changed_files with garbage to_commit raises CommitNotFound with correct hash."""
        good_hash = git_service.get_current_commit(temp_git_repo)
        bad_hash = "deadbeef" * 5
        with pytest.raises(CommitNotFound) as exc_info:
            git_service.get_changed_files(temp_git_repo, good_hash, bad_hash)
        assert exc_info.value.commit_hash == bad_hash

    def test_get_blame_invalid_commit_raises_commit_not_found(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """get_blame with garbage commit hash raises CommitNotFound."""
        with pytest.raises(CommitNotFound):
            git_service.get_blame(temp_git_repo, "deadbeef" * 5, "README.md")

    def test_get_blame_missing_file_raises_filenotfounderror(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """get_blame with non-existent file raises FileNotFoundError."""
        commit_hash = git_service.get_current_commit(temp_git_repo)
        with pytest.raises(FileNotFoundError):
            git_service.get_blame(temp_git_repo, commit_hash, "no-such-file.txt")

    def test_get_merge_base_bad_branches_returns_none(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """get_merge_base with two non-existent branches returns None."""
        result = git_service.get_merge_base(
            temp_git_repo, "no-branch-aaa", "no-branch-bbb"
        )
        assert result is None

    def test_list_branches_with_no_errors(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """list_branches succeeds and the ValueError/GitCommandError catches don't interfere."""
        branches = git_service.list_branches(temp_git_repo)
        assert "main" in branches
        assert "feature-branch" in branches


class TestGitServiceExceptionTranslation:
    """Tests that GitService translates git.exc exceptions to domain exceptions."""

    @pytest.fixture
    def git_service(self) -> GitService:
        return GitService()

    def test_get_commit_info_bad_hash_raises_commit_not_found(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """get_commit_info with non-existent hash raises CommitNotFound."""
        with pytest.raises(CommitNotFound) as exc_info:
            git_service.get_commit_info(temp_git_repo, "deadbeef" * 5)
        assert exc_info.value.commit_hash == "deadbeef" * 5

    def test_get_commit_info_short_bad_hash_raises_commit_not_found(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """get_commit_info with short non-existent hash raises CommitNotFound."""
        with pytest.raises(CommitNotFound):
            git_service.get_commit_info(temp_git_repo, "0000000")

    def test_get_changed_files_in_commit_bad_hash_raises_commit_not_found(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """get_changed_files_in_commit with bad hash raises CommitNotFound."""
        with pytest.raises(CommitNotFound) as exc_info:
            git_service.get_changed_files_in_commit(temp_git_repo, "deadbeef" * 5)
        assert exc_info.value.commit_hash == "deadbeef" * 5

    def test_invalid_repo_path_raises_invalid_repository_path(
        self, git_service: GitService, tmp_path: Path
    ) -> None:
        """Accessing a non-git directory raises InvalidRepositoryPath."""
        not_git = tmp_path / "not-a-repo"
        not_git.mkdir()

        with pytest.raises(InvalidRepositoryPath) as exc_info:
            git_service.get_commit_info(not_git, "abc123")
        assert str(not_git) in exc_info.value.path

    def test_nonexistent_path_raises_invalid_repository_path(
        self, git_service: GitService, tmp_path: Path
    ) -> None:
        """Accessing a path that doesn't exist raises InvalidRepositoryPath."""
        missing = tmp_path / "no-such-directory"

        with pytest.raises(InvalidRepositoryPath) as exc_info:
            git_service.get_commit_info(missing, "abc123")
        assert str(missing) in exc_info.value.path

    def test_get_commit_info_valid_hash_succeeds(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """get_commit_info with a valid hash returns CommitInfo."""
        commit_hash = git_service.get_current_commit(temp_git_repo)
        info = git_service.get_commit_info(temp_git_repo, commit_hash)
        assert info.hash == commit_hash

    def test_domain_exceptions_are_domain_exception_subclasses(self) -> None:
        """Domain exceptions inherit from DomainException for broad catching."""
        from inxr2.domain.exceptions import DomainException

        assert issubclass(CommitNotFound, DomainException)
        assert issubclass(GitOperationError, DomainException)
        assert issubclass(InvalidRepositoryPath, DomainException)


@pytest.fixture
def repo_with_rename(tmp_path: Path) -> tuple[Path, str, str, str]:
    """Create a git repo with a single file rename commit.

    Returns (repo_path, old_name, new_name, rename_commit_hash).
    """
    repo_path = tmp_path / "rename-repo"
    repo_path.mkdir()
    repo = Repo.init(repo_path, initial_branch="main")
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    # Commit 1: add the original file
    old_name = "old_name.py"
    (repo_path / old_name).write_text("def foo(): pass\n")
    repo.index.add([old_name])
    repo.index.commit("Add old_name.py")

    # Commit 2: rename the file
    new_name = "new_name.py"
    repo.index.move([old_name, new_name])
    rename_commit = repo.index.commit("Rename old_name.py to new_name.py")

    return repo_path, old_name, new_name, str(rename_commit.hexsha)


class TestGetFileRenamesInCommit:
    """Tests for get_file_renames_in_commit."""

    @pytest.fixture
    def git_service(self) -> GitService:
        return GitService()

    def test_rename_direction_old_to_new(
        self,
        git_service: GitService,
        repo_with_rename: tuple[Path, str, str, str],
    ) -> None:
        """Regression test for issue #351: old_path/new_path must not be swapped.

        old_path = name before the commit (in parent), new_path = name after.
        Previously R=True was passed to parent.diff() which reversed a_path/b_path,
        causing every rename to be stored with old and new swapped in the DB.
        """
        repo_path, old_name, new_name, rename_commit = repo_with_rename
        renames = git_service.get_file_renames_in_commit(repo_path, rename_commit)

        assert len(renames) == 1
        assert (
            renames[0].old_path == old_name
        ), f"old_path should be '{old_name}' (name before rename), got '{renames[0].old_path}'"
        assert (
            renames[0].new_path == new_name
        ), f"new_path should be '{new_name}' (name after rename), got '{renames[0].new_path}'"

    def test_no_renames_in_regular_commit(
        self,
        git_service: GitService,
        temp_git_repo: Path,
    ) -> None:
        """A commit with no renames returns an empty list."""
        commit_hash = git_service.get_current_commit(temp_git_repo)
        renames = git_service.get_file_renames_in_commit(temp_git_repo, commit_hash)
        assert renames == []

    def test_initial_commit_with_no_parent_returns_empty(
        self,
        git_service: GitService,
        tmp_path: Path,
    ) -> None:
        """Initial commit (no parent) returns empty list — nothing to diff against."""
        repo_path = tmp_path / "fresh"
        repo_path.mkdir()
        repo = Repo.init(repo_path, initial_branch="main")
        repo.config_writer().set_value("user", "name", "T").release()
        repo.config_writer().set_value("user", "email", "t@t.com").release()
        (repo_path / "f.py").write_text("x = 1\n")
        repo.index.add(["f.py"])
        initial = repo.index.commit("init")

        renames = git_service.get_file_renames_in_commit(repo_path, str(initial.hexsha))
        assert renames == []


@pytest.fixture
def merge_repo_old_branch_commits(tmp_path: Path) -> tuple[Path, int]:
    """Create a git repo where feature branches were committed before the window
    but merged recently (within it).

    This reproduces the real-world scenario for issue #338:
      - All first-parent commits (I1, I2, M1, M2) are within a 30-day window
      - Feature branch commits are older than 30 days
      - Merge commits (M1, M2) are today and bring in the old branch commits

    History (dates in parentheses):
      main: I1(25d) ← I2(20d) ← M1(today) ← M2(today) ← HEAD
                        ↑                ↑
                   F1a(35d) ← F1b(33d)  F2a(32d) ← F2b(31d) ← F2c(30.5d)

    With git --since=30d:
      - All first-parent commits are within window (returned)
      - Feature branch commits are older than 30d → git stops traversal
      - Result: only ~4 commits (I1, I2, M1, M2) — WRONG

    Correct result: all 9 commits — feature branch commits are reachable
    from the recent merge commits and must be included.
    """
    from datetime import UTC, datetime, timedelta

    repo_path = tmp_path / "merge-old-repo"
    repo_path.mkdir()
    repo = Repo.init(repo_path, initial_branch="main")
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    def date_str(days_ago: float) -> str:
        """Return an ISO date string N days in the past (UTC, with timezone offset)."""
        d = datetime.now(UTC) - timedelta(days=days_ago)
        return d.strftime("%Y-%m-%dT%H:%M:%S+0000")

    def commit_with_date(
        msg: str, filename: str, content: str, days_ago: float
    ) -> None:
        (repo_path / filename).write_text(content)
        repo.index.add([filename])
        date = date_str(days_ago)
        repo.index.commit(msg, author_date=date, commit_date=date)

    # I1 and I2: first-parent commits within the 30-day window
    commit_with_date("main: initial", "README.md", "# Test\n", days_ago=25)
    commit_with_date("main: second", "main.py", "def main(): pass\n", days_ago=20)

    # Feature branch 1: commits OLDER than 30 days
    repo.create_head("feature-1").checkout()
    commit_with_date(
        "feature-1: add alpha", "alpha.py", "def alpha(): pass\n", days_ago=35
    )
    commit_with_date(
        "feature-1: add beta", "beta.py", "def beta(): pass\n", days_ago=33
    )

    # Merge feature-1 into main TODAY (recent merge, within 30-day window)
    repo.git.checkout("main")
    today = date_str(0)
    repo.git.merge(
        "feature-1",
        "--no-ff",
        "-m",
        "Merge feature-1 into main",
        env={"GIT_AUTHOR_DATE": today, "GIT_COMMITTER_DATE": today},
    )

    # Feature branch 2: commits OLDER than 30 days
    repo.create_head("feature-2").checkout()
    commit_with_date(
        "feature-2: add gamma", "gamma.py", "def gamma(): pass\n", days_ago=32
    )
    commit_with_date(
        "feature-2: add delta", "delta.py", "def delta(): pass\n", days_ago=31
    )
    commit_with_date(
        "feature-2: add epsilon", "epsilon.py", "def epsilon(): pass\n", days_ago=30.5
    )

    # Merge feature-2 into main TODAY (recent merge, within 30-day window)
    repo.git.checkout("main")
    repo.git.merge(
        "feature-2",
        "--no-ff",
        "-m",
        "Merge feature-2 into main",
        env={"GIT_AUTHOR_DATE": today, "GIT_COMMITTER_DATE": today},
    )

    # Total commits reachable from HEAD: 9
    # I1(25d) + I2(20d) + F1a(35d) + F1b(33d) + M1(0d) + F2a(32d) + F2b(31d) + F2c(30.5d) + M2(0d)
    total = 9
    return repo_path, total


@pytest.fixture
def merge_repo(tmp_path: Path) -> tuple[Path, int]:
    """Create a git repo with two merged feature branches.

    History (newest → oldest, topological order):
      main: I1 ← I2 ← M1 ← M2 ← (HEAD)
                   ↑         ↑
              F1a ← F1b    F2a ← F2b ← F2c

    Total commits: 2 (main) + 2 (feature-1) + 3 (feature-2) + 2 (merges) = 9

    Returns (repo_path, total_commit_count).
    """
    repo_path = tmp_path / "merge-repo"
    repo_path.mkdir()
    repo = Repo.init(repo_path, initial_branch="main")
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    def commit(msg: str, filename: str, content: str) -> None:
        (repo_path / filename).write_text(content)
        repo.index.add([filename])
        repo.index.commit(msg)

    # I1, I2: two commits on main
    commit("main: initial", "README.md", "# Test\n")
    commit("main: second", "main.py", "def main(): pass\n")

    # Feature branch 1: F1a, F1b
    repo.create_head("feature-1").checkout()
    commit("feature-1: add alpha", "alpha.py", "def alpha(): pass\n")
    commit("feature-1: add beta", "beta.py", "def beta(): pass\n")

    # Merge feature-1 into main → M1
    repo.git.checkout("main")
    repo.git.merge("feature-1", "--no-ff", "-m", "Merge feature-1 into main")

    # Feature branch 2: F2a, F2b, F2c
    repo.create_head("feature-2").checkout()
    commit("feature-2: add gamma", "gamma.py", "def gamma(): pass\n")
    commit("feature-2: add delta", "delta.py", "def delta(): pass\n")
    commit("feature-2: add epsilon", "epsilon.py", "def epsilon(): pass\n")

    # Merge feature-2 into main → M2
    repo.git.checkout("main")
    repo.git.merge("feature-2", "--no-ff", "-m", "Merge feature-2 into main")

    # Total: I1 + I2 + F1a + F1b + M1 + F2a + F2b + F2c + M2 = 9 commits
    total = 9
    return repo_path, total


class TestListCommitsMergeHistory:
    """Regression tests for issue #338: list_commits must return all commits
    reachable from a branch, including commits from merged feature branches
    (non-first-parent commits).
    """

    @pytest.fixture
    def git_service(self) -> GitService:
        return GitService()

    def test_list_commits_returns_all_commits_without_since(
        self,
        git_service: GitService,
        merge_repo: tuple[Path, int],
    ) -> None:
        """list_commits without since_days must include non-first-parent commits.

        Without --since, git log follows all parents.  This test verifies that
        list_commits returns every reachable commit, not only the 5 commits on
        the first-parent chain (I1, I2, M1, M2, HEAD).
        """
        repo_path, total_commits = merge_repo
        commits = git_service.list_commits(repo_path, "main", max_count=None)

        commit_hashes = {c.hash for c in commits}
        assert len(commits) == total_commits, (
            f"Expected {total_commits} commits (all reachable), "
            f"got {len(commits)}.  Missing commits suggests first-parent-only traversal."
        )
        # Verify feature branch commits are present by checking messages
        messages = {c.message for c in commits}
        assert any(
            "feature-1" in m for m in messages
        ), "feature-1 branch commits missing from list_commits result"
        assert any(
            "feature-2" in m for m in messages
        ), "feature-2 branch commits missing from list_commits result"
        assert len(commit_hashes) == total_commits, "Duplicate commits returned"

    def test_list_commits_with_since_returns_all_commits_in_window(
        self,
        git_service: GitService,
        merge_repo: tuple[Path, int],
    ) -> None:
        """list_commits with since_days must include non-first-parent commits.

        This is the critical regression test for issue #338.  When --since is
        passed to git log, GitPython's iter_commits may prune branches that
        appear to start before the cutoff, silently dropping all commits from
        merged feature branches.

        All commits in merge_repo were made moments ago, so since_days=1 must
        return the full set.
        """
        repo_path, total_commits = merge_repo
        commits = git_service.list_commits(
            repo_path, "main", max_count=None, since_days=1
        )

        assert len(commits) == total_commits, (
            f"Expected {total_commits} commits with since_days=1 "
            f"(all commits are recent), got {len(commits)}.  "
            f"This indicates list_commits is walking first-parent only when "
            f"--since is used, skipping merged feature branch commits."
        )
        messages = {c.message for c in commits}
        assert any(
            "feature-1" in m for m in messages
        ), "feature-1 branch commits missing when using since_days"
        assert any(
            "feature-2" in m for m in messages
        ), "feature-2 branch commits missing when using since_days"

    def test_list_commits_with_since_includes_old_branch_commits_merged_recently(
        self,
        git_service: GitService,
        merge_repo_old_branch_commits: tuple[Path, int],
    ) -> None:
        """list_commits must return feature branch commits that are older than
        the since_days window but were merged into main within that window.

        This is the exact regression test for issue #338.  In the real codebase,
        a 30-day backfill misses ~566 commits because the feature branch commits
        were authored before the 30-day cutoff — even though the merges are recent.

        git log --since=<date> stops traversal when a commit is older than the
        cutoff.  For merged feature branches this means all branch commits are
        silently dropped once the oldest one falls outside the window.
        """
        repo_path, total_commits = merge_repo_old_branch_commits
        # Use since_days=30: merge commits are today (inside window),
        # but feature branch commits are 30.5–35 days old (outside window).
        commits = git_service.list_commits(
            repo_path, "main", max_count=None, since_days=30
        )

        commit_hashes = {c.hash for c in commits}
        # The 2 merge commits (M1, M2) are within the 30-day window.
        # The feature branch commits (F1a, F1b, F2a, F2b, F2c) are outside it.
        # But they ARE reachable from recent merge commits, so a correct
        # full-DAG indexer must include them.
        assert len(commits) == total_commits, (
            f"Expected {total_commits} commits (all reachable from recent merges), "
            f"got {len(commits)}.  "
            f"Feature branch commits older than --since cutoff are being silently "
            f"dropped even though their merge commits are within the window."
        )
        messages = {c.message for c in commits}
        assert any("feature-1" in m for m in messages), (
            "feature-1 branch commits (older than since window) missing — "
            "list_commits stops traversal when branch commits predate --since cutoff"
        )
        assert any("feature-2" in m for m in messages), (
            "feature-2 branch commits (older than since window) missing — "
            "list_commits stops traversal when branch commits predate --since cutoff"
        )
        assert len(commit_hashes) == len(commits), "Duplicate commits returned"

    def test_list_commits_with_since_excludes_pre_window_first_parent_commits(
        self,
        git_service: GitService,
        tmp_path: Path,
    ) -> None:
        """list_commits boundary logic: commits before the first-parent window
        boundary are excluded; old merged-branch commits introduced within the
        window are still included.

        This exercises the boundary_hash code path (boundary_hash is not None),
        which is the core of the fix for issue #338.

        History (dates in parentheses):
          main: OLD1(60d) ← OLD2(55d) ← M1(today) ← HEAD
                                              ↑
                                    F1a(45d) ← F1b(40d)

        With since_days=30:
          - First-parent walk: HEAD(today) → M1(today) → OLD2(55d) → STOP
          - boundary_hash = OLD2
          - Full traversal of OLD2..HEAD: M1, F1a, F1b = 3 commits
          - OLD1 and OLD2 are excluded (before the first-parent boundary)
        """
        from datetime import UTC, datetime, timedelta

        repo_path = tmp_path / "boundary-repo"
        repo_path.mkdir()
        repo = Repo.init(repo_path, initial_branch="main")
        repo.config_writer().set_value("user", "name", "Test User").release()
        repo.config_writer().set_value("user", "email", "test@example.com").release()

        def date_str(days_ago: float) -> str:
            d = datetime.now(UTC) - timedelta(days=days_ago)
            return d.strftime("%Y-%m-%dT%H:%M:%S+0000")

        def commit_with_date(
            msg: str, filename: str, content: str, days_ago: float
        ) -> None:
            (repo_path / filename).write_text(content)
            repo.index.add([filename])
            date = date_str(days_ago)
            repo.index.commit(msg, author_date=date, commit_date=date)

        # OLD1, OLD2: first-parent commits outside the 30-day window
        commit_with_date("old: initial", "README.md", "# Old\n", days_ago=60)
        commit_with_date("old: second", "old.py", "x = 1\n", days_ago=55)

        # Feature branch with commits also outside the window, branched from OLD2
        repo.create_head("feature-1").checkout()
        commit_with_date(
            "feature-1: add foo", "foo.py", "def foo(): pass\n", days_ago=45
        )
        commit_with_date(
            "feature-1: add bar", "bar.py", "def bar(): pass\n", days_ago=40
        )

        # Merge feature-1 into main TODAY (within 30-day window)
        repo.git.checkout("main")
        today = date_str(0)
        repo.git.merge(
            "feature-1",
            "--no-ff",
            "-m",
            "Merge feature-1 into main",
            env={"GIT_AUTHOR_DATE": today, "GIT_COMMITTER_DATE": today},
        )

        commits = git_service.list_commits(
            repo_path, "main", max_count=None, since_days=30
        )
        messages = {c.message for c in commits}

        # Only M1, F1a, F1b should be returned (3 commits)
        assert len(commits) == 3, (
            f"Expected 3 commits (M1 + F1a + F1b), got {len(commits)}: "
            f"{[c.message for c in commits]}"
        )
        # Merge commit and feature branch commits are present
        assert any(
            "Merge feature-1" in m for m in messages
        ), "Merge commit missing from results"
        assert any(
            "feature-1" in m for m in messages
        ), "Feature branch commits missing from results"
        # Old first-parent commits are excluded
        assert not any(
            "old:" in m for m in messages
        ), f"Pre-boundary first-parent commits should be excluded, got: {messages}"
