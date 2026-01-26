"""Tests for ListCommitsUseCase using dependency injection."""

from datetime import datetime
from pathlib import Path

import pytest

from inxr2.application.use_cases.commits import (
    ListCommitsRequest,
    ListCommitsUseCase,
)
from inxr2.domain.entities import Commit, Repository
from inxr2.domain.exceptions import RepositoryNotFound
from inxr2.domain.value_objects import CommitHash
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryRepositoryRepository,
)


class StubGitCommitInfoService:
    """Stub git service for testing commit info hydration."""

    def __init__(self) -> None:
        """Initialize with empty commit info map."""
        self._commit_info: dict[tuple[str, str], dict[str, str]] = {}
        self._fail_on: set[tuple[str, str]] = set()

    def set_commit_info(
        self, repo_path: str, commit_hash: str, info: dict[str, str]
    ) -> None:
        """Set commit info to return for a commit."""
        key = (repo_path, commit_hash)
        self._commit_info[key] = info

    def set_fail(self, repo_path: str, commit_hash: str) -> None:
        """Mark a commit to fail on lookup."""
        key = (repo_path, commit_hash)
        self._fail_on.add(key)

    def get_commit_info(self, repo_path: Path, commit_hash: str) -> dict[str, str]:
        """Return predefined commit info or raise error."""
        key = (str(repo_path), commit_hash)
        if key in self._fail_on:
            raise RuntimeError("Git lookup failed")
        return self._commit_info.get(key, {})


class TestListCommitsUseCase:
    """Tests for ListCommitsUseCase."""

    @pytest.fixture
    def repository_repo(self, tmp_path: Path) -> InMemoryRepositoryRepository:
        """Create repository with test data."""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()

        repo = InMemoryRepositoryRepository()
        repo.add(
            Repository(
                id=1,
                name="test-repo",
                url=str(repo_path),
                default_branch="main",
            )
        )
        return repo

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        """Create commit repository with test data."""
        repo = InMemoryCommitRepository()

        commit1 = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("abc123def456"),
            author_date=datetime(2025, 1, 1, 12, 0, 0),
            commit_date=datetime(2025, 1, 1, 12, 0, 0),
        )
        commit2 = Commit(
            id=2,
            repository_id=1,
            commit_hash=CommitHash("def456ghi789"),
            author_date=datetime(2025, 1, 2, 12, 0, 0),
            commit_date=datetime(2025, 1, 2, 12, 0, 0),
        )
        commit3 = Commit(
            id=3,
            repository_id=1,
            commit_hash=CommitHash("ghi789jkl012"),
            author_date=datetime(2025, 1, 3, 12, 0, 0),
            commit_date=datetime(2025, 1, 3, 12, 0, 0),
        )

        repo._commits[1] = commit1
        repo._commits[2] = commit2
        repo._commits[3] = commit3

        repo._branch_commits[(1, "main", 1)] = True
        repo._branch_commits[(1, "main", 2)] = True
        repo._branch_commits[(1, "main", 3)] = True
        repo._branch_commits[(1, "feature", 2)] = True
        repo._branch_commits[(1, "feature", 3)] = True

        return repo

    @pytest.fixture
    def git_service(self, tmp_path: Path) -> StubGitCommitInfoService:
        """Create stub git service with test commit info."""
        repo_path = tmp_path / "test-repo"
        service = StubGitCommitInfoService()
        service.set_commit_info(
            str(repo_path),
            "abc123def456",
            {
                "message": "Initial commit",
                "author_name": "Alice",
                "author_email": "alice@example.com",
            },
        )
        service.set_commit_info(
            str(repo_path),
            "def456ghi789",
            {
                "message": "Add feature X",
                "author_name": "Bob",
                "author_email": "bob@example.com",
            },
        )
        service.set_commit_info(
            str(repo_path),
            "ghi789jkl012",
            {
                "message": "Fix bug in feature X",
                "author_name": "Alice",
                "author_email": "alice@example.com",
            },
        )
        return service

    @pytest.fixture
    def use_case(
        self,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        git_service: StubGitCommitInfoService,
    ) -> ListCommitsUseCase:
        """Create use case with test dependencies."""
        return ListCommitsUseCase(
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

    # === Basic Listing Tests ===

    @pytest.mark.asyncio
    async def test_list_commits_returns_all(self, use_case: ListCommitsUseCase) -> None:
        """Should return all commits for repository."""
        request = ListCommitsRequest(repository_name="test-repo")

        result = await use_case.execute(request)

        assert result.total == 3

    @pytest.mark.asyncio
    async def test_list_commits_hydrates_metadata(
        self, use_case: ListCommitsUseCase
    ) -> None:
        """Should hydrate commits with git metadata."""
        request = ListCommitsRequest(repository_name="test-repo")

        result = await use_case.execute(request)

        # Check that metadata is hydrated
        messages = {c.message for c in result.commits}
        assert "Initial commit" in messages
        assert "Add feature X" in messages
        assert "Fix bug in feature X" in messages

        authors = {c.author_name for c in result.commits}
        assert "Alice" in authors
        assert "Bob" in authors

    # === Branch Filtering Tests ===

    @pytest.mark.asyncio
    async def test_filter_by_branch(self, use_case: ListCommitsUseCase) -> None:
        """Should filter commits by branch."""
        request = ListCommitsRequest(repository_name="test-repo", branch="feature")

        result = await use_case.execute(request)

        # Feature branch has commits 2 and 3
        assert result.total == 2

    # === Limit Tests ===

    @pytest.mark.asyncio
    async def test_respects_limit(self, use_case: ListCommitsUseCase) -> None:
        """Should respect limit parameter."""
        request = ListCommitsRequest(repository_name="test-repo", limit=2)

        result = await use_case.execute(request)

        assert result.total == 2

    # === Error Handling Tests ===

    @pytest.mark.asyncio
    async def test_raises_repository_not_found(
        self, use_case: ListCommitsUseCase
    ) -> None:
        """Should raise RepositoryNotFound for unknown repository."""
        request = ListCommitsRequest(repository_name="unknown-repo")

        with pytest.raises(RepositoryNotFound):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_handles_git_lookup_failure_gracefully(
        self,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        tmp_path: Path,
    ) -> None:
        """Should return empty metadata when git lookup fails."""
        repo_path = tmp_path / "test-repo"
        git_service = StubGitCommitInfoService()
        git_service.set_fail(str(repo_path), "abc123def456")

        use_case = ListCommitsUseCase(
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

        request = ListCommitsRequest(repository_name="test-repo")
        result = await use_case.execute(request)

        # Find the commit that should have failed
        failed_commit = next(
            c for c in result.commits if c.commit.commit_hash.value == "abc123def456"
        )
        assert failed_commit.message == ""
        assert failed_commit.author_name == ""
        assert failed_commit.author_email == ""

    # === Message Truncation Tests ===

    @pytest.mark.asyncio
    async def test_truncates_long_messages(
        self,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        tmp_path: Path,
    ) -> None:
        """Should truncate commit messages to 200 characters."""
        repo_path = tmp_path / "test-repo"
        git_service = StubGitCommitInfoService()
        long_message = "x" * 300
        git_service.set_commit_info(
            str(repo_path),
            "abc123def456",
            {
                "message": long_message,
                "author_name": "Alice",
                "author_email": "alice@example.com",
            },
        )

        use_case = ListCommitsUseCase(
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

        request = ListCommitsRequest(repository_name="test-repo")
        result = await use_case.execute(request)

        commit = next(
            c for c in result.commits if c.commit.commit_hash.value == "abc123def456"
        )
        assert len(commit.message) == 200
