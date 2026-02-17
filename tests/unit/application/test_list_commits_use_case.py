"""Tests for ListCommitsUseCase using dependency injection."""

from datetime import datetime
from pathlib import Path

import pytest

from inxr2.application.ports.services import CommitInfo
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


def _make_commit_info(
    hash: str,
    short_hash: str,
    author_name: str = "Alice",
    author_email: str = "alice@example.com",
    commit_date: datetime | None = None,
    message: str = "",
) -> CommitInfo:
    """Helper to create CommitInfo with defaults."""
    dt = commit_date or datetime(2025, 1, 1)
    return CommitInfo(
        hash=hash,
        short_hash=short_hash,
        author_name=author_name,
        author_email=author_email,
        author_date=dt,
        committer_name=author_name,
        committer_email=author_email,
        commit_date=dt,
        message=message,
        parent_hashes=[],
    )


class StubGitListCommitsService:
    """Stub git service that returns predefined commits for list_commits."""

    def __init__(self) -> None:
        # Map (repo_path, branch) -> list of CommitInfo (oldest first)
        self._commits: dict[tuple[str, str], list[CommitInfo]] = {}
        self._tags: dict[str, list[str]] = {}
        # Map (repo_path, branch, base_branch) -> list of branch-specific CommitInfo
        self._branch_commits: dict[tuple[str, str, str], list[CommitInfo]] = {}
        self._branch_commits_error: bool = False
        # Map (repo_path, branch, base_branch) -> merge-base hash
        self._merge_bases: dict[tuple[str, str, str], str | None] = {}

    def set_commits(
        self, repo_path: str, branch: str, commits: list[CommitInfo]
    ) -> None:
        self._commits[(repo_path, branch)] = commits

    def set_tags(self, tags: dict[str, list[str]]) -> None:
        self._tags = tags

    def set_branch_commits(
        self,
        repo_path: str,
        branch: str,
        base_branch: str,
        commits: list[CommitInfo],
    ) -> None:
        self._branch_commits[(repo_path, branch, base_branch)] = commits

    def set_merge_base(
        self,
        repo_path: str,
        branch: str,
        base_branch: str,
        merge_base_hash: str | None,
    ) -> None:
        self._merge_bases[(repo_path, branch, base_branch)] = merge_base_hash

    def set_branch_commits_error(self, error: bool = True) -> None:
        self._branch_commits_error = error

    def list_commits(
        self,
        repo_path: Path,
        branch: str,
        max_count: int | None = 1000,
        since_days: int | None = None,
    ) -> list[CommitInfo]:
        key = (str(repo_path), branch)
        all_commits = self._commits.get(key, [])
        if max_count is not None:
            # Mirror real git: iter_commits(max_count=N) returns the N newest
            return all_commits[-max_count:]
        return list(all_commits)

    def get_tags(self, repo_path: Path) -> dict[str, list[str]]:
        return self._tags

    def get_merge_base(
        self,
        repo_path: Path,
        branch1: str,
        branch2: str,
    ) -> str | None:
        key = (str(repo_path), branch1, branch2)
        return self._merge_bases.get(key)

    def list_branch_commits(
        self,
        repo_path: Path,
        branch: str,
        base_branch: str,
        max_count: int | None = 1000,
        since_days: int | None = None,
    ) -> list[CommitInfo]:
        if self._branch_commits_error:
            raise RuntimeError("list_branch_commits failed")
        key = (str(repo_path), branch, base_branch)
        return list(self._branch_commits.get(key, []))


class TestListCommitsUseCase:
    """Tests for ListCommitsUseCase."""

    @pytest.fixture
    def repository_repo(self, tmp_path: Path) -> InMemoryRepositoryRepository:
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
        """Create commit repository with indexed commits."""
        repo = InMemoryCommitRepository()
        # Only commits 1 and 2 are indexed
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
        repo._commits[1] = commit1
        repo._commits[2] = commit2
        repo._branch_commits[(1, "main", 1)] = True
        repo._branch_commits[(1, "main", 2)] = True
        return repo

    @pytest.fixture
    def git_service(self, tmp_path: Path) -> StubGitListCommitsService:
        """Create stub git service with 3 commits (oldest first)."""
        repo_path = tmp_path / "test-repo"
        service = StubGitListCommitsService()
        service.set_commits(
            str(repo_path),
            "main",
            [
                _make_commit_info(
                    "abc123def456",
                    "abc123d",
                    "Alice",
                    "alice@example.com",
                    datetime(2025, 1, 1),
                    "Initial commit",
                ),
                _make_commit_info(
                    "def456ghi789",
                    "def456g",
                    "Bob",
                    "bob@example.com",
                    datetime(2025, 1, 2),
                    "Add feature X",
                ),
                _make_commit_info(
                    "ghi789jkl012",
                    "ghi789j",
                    "Alice",
                    "alice@example.com",
                    datetime(2025, 1, 3),
                    "Fix bug in feature X",
                ),
            ],
        )
        return service

    @pytest.fixture
    def use_case(
        self,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        git_service: StubGitListCommitsService,
    ) -> ListCommitsUseCase:
        return ListCommitsUseCase(
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

    # === Basic Listing Tests ===

    @pytest.mark.asyncio
    async def test_list_commits_returns_all(self, use_case: ListCommitsUseCase) -> None:
        """Should return all git commits for the branch."""
        request = ListCommitsRequest(repository_name="test-repo")
        result = await use_case.execute(request)
        assert result.total == 3

    @pytest.mark.asyncio
    async def test_list_commits_newest_first(
        self, use_case: ListCommitsUseCase
    ) -> None:
        """Should return commits newest first."""
        request = ListCommitsRequest(repository_name="test-repo")
        result = await use_case.execute(request)
        assert result.commits[0].short_hash == "ghi789j"
        assert result.commits[2].short_hash == "abc123d"

    @pytest.mark.asyncio
    async def test_list_commits_has_metadata(
        self, use_case: ListCommitsUseCase
    ) -> None:
        """Should include commit metadata from git."""
        request = ListCommitsRequest(repository_name="test-repo")
        result = await use_case.execute(request)

        messages = {c.message for c in result.commits}
        assert "Initial commit" in messages
        assert "Add feature X" in messages

        authors = {c.author_name for c in result.commits}
        assert "Alice" in authors
        assert "Bob" in authors

    # === Indexed Status Tests ===

    @pytest.mark.asyncio
    async def test_marks_indexed_commits(self, use_case: ListCommitsUseCase) -> None:
        """Should mark commits that exist in DB as indexed."""
        request = ListCommitsRequest(repository_name="test-repo")
        result = await use_case.execute(request)

        by_hash = {c.hash: c for c in result.commits}
        # Commits 1 and 2 are in the DB
        assert by_hash["abc123def456"].is_indexed is True
        assert by_hash["def456ghi789"].is_indexed is True
        # Commit 3 is not indexed
        assert by_hash["ghi789jkl012"].is_indexed is False

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

    # === Full Message Tests ===

    @pytest.mark.asyncio
    async def test_preserves_full_messages(
        self,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        tmp_path: Path,
    ) -> None:
        """Should preserve full commit messages without truncation."""
        repo_path = tmp_path / "test-repo"
        git_service = StubGitListCommitsService()
        long_message = "x" * 300
        git_service.set_commits(
            str(repo_path),
            "main",
            [
                _make_commit_info(
                    "abc123def456",
                    "abc123d",
                    message=long_message,
                ),
            ],
        )

        use_case = ListCommitsUseCase(
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

        request = ListCommitsRequest(repository_name="test-repo")
        result = await use_case.execute(request)
        assert len(result.commits[0].message) == 300

    # === Tag Tests ===

    @pytest.mark.asyncio
    async def test_populates_tags_from_git(
        self,
        git_service: StubGitListCommitsService,
        use_case: ListCommitsUseCase,
    ) -> None:
        """Should attach matching git tags to each commit."""
        git_service.set_tags(
            {
                "abc123def456": ["v1.0"],
                "def456ghi789": ["v1.1", "release-2025"],
            }
        )

        request = ListCommitsRequest(repository_name="test-repo")
        result = await use_case.execute(request)

        by_hash = {c.hash: c for c in result.commits}
        assert by_hash["abc123def456"].tags == ["v1.0"]
        assert sorted(by_hash["def456ghi789"].tags) == ["release-2025", "v1.1"]
        assert by_hash["ghi789jkl012"].tags == []

    @pytest.mark.asyncio
    async def test_empty_tags_when_no_tags(
        self,
        use_case: ListCommitsUseCase,
    ) -> None:
        """Should return empty tags when repo has no tags."""
        request = ListCommitsRequest(repository_name="test-repo")
        result = await use_case.execute(request)

        for c in result.commits:
            assert c.tags == []

    # === Branch-Specific Commit Highlighting Tests ===

    @pytest.mark.asyncio
    async def test_branch_specific_flags_on_feature_branch(
        self,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        tmp_path: Path,
    ) -> None:
        """Non-default branch should flag branch-specific commits and mark fork point."""
        repo_path = tmp_path / "test-repo"
        git_service = StubGitListCommitsService()
        # Full history (oldest first): shared1, shared2, branch1, branch2
        git_service.set_commits(
            str(repo_path),
            "feature",
            [
                _make_commit_info("shared1", "shared1", message="Shared commit"),
                _make_commit_info("shared2", "shared2", message="Shared commit 2"),
                _make_commit_info("branch1", "branch1", message="Branch commit 1"),
                _make_commit_info("branch2", "branch2", message="Branch commit 2"),
            ],
        )
        # Branch-specific commits (oldest first): branch1, branch2
        git_service.set_branch_commits(
            str(repo_path),
            "feature",
            "main",
            [
                _make_commit_info("branch1", "branch1", message="Branch commit 1"),
                _make_commit_info("branch2", "branch2", message="Branch commit 2"),
            ],
        )
        # Merge-base is the last common ancestor (shared2)
        git_service.set_merge_base(str(repo_path), "feature", "main", "shared2")

        use_case = ListCommitsUseCase(
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

        request = ListCommitsRequest(repository_name="test-repo", branch="feature")
        result = await use_case.execute(request)

        by_hash = {c.hash: c for c in result.commits}
        assert by_hash["branch2"].is_branch_specific is True
        assert by_hash["branch1"].is_branch_specific is True
        # Branch commits are not the merge-base
        assert by_hash["branch1"].is_merge_base is False
        assert by_hash["branch2"].is_merge_base is False
        # Merge-base is the last shared commit before branching
        assert by_hash["shared1"].is_branch_specific is False
        assert by_hash["shared1"].is_merge_base is False
        assert by_hash["shared2"].is_branch_specific is False
        assert by_hash["shared2"].is_merge_base is True

    @pytest.mark.asyncio
    async def test_default_branch_has_no_highlighting(
        self,
        use_case: ListCommitsUseCase,
    ) -> None:
        """Default branch should have no branch-specific or merge-base flags."""
        request = ListCommitsRequest(repository_name="test-repo", branch="main")
        result = await use_case.execute(request)

        for c in result.commits:
            assert c.is_branch_specific is False
            assert c.is_merge_base is False

    @pytest.mark.asyncio
    async def test_no_branch_commits_graceful_degradation(
        self,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        tmp_path: Path,
    ) -> None:
        """When no branch-specific commits found, all flags should be False."""
        repo_path = tmp_path / "test-repo"
        git_service = StubGitListCommitsService()
        git_service.set_commits(
            str(repo_path),
            "feature",
            [
                _make_commit_info("aaa", "aaa1234", message="Commit A"),
                _make_commit_info("bbb", "bbb1234", message="Commit B"),
            ],
        )
        # No branch_commits set (returns empty list by default)

        use_case = ListCommitsUseCase(
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

        request = ListCommitsRequest(repository_name="test-repo", branch="feature")
        result = await use_case.execute(request)

        for c in result.commits:
            assert c.is_branch_specific is False
            assert c.is_merge_base is False

    @pytest.mark.asyncio
    async def test_branch_commits_error_graceful_degradation(
        self,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        tmp_path: Path,
    ) -> None:
        """When list_branch_commits raises, all flags should be False."""
        repo_path = tmp_path / "test-repo"
        git_service = StubGitListCommitsService()
        git_service.set_commits(
            str(repo_path),
            "feature",
            [
                _make_commit_info("aaa", "aaa1234", message="Commit A"),
            ],
        )
        git_service.set_branch_commits_error(True)

        use_case = ListCommitsUseCase(
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

        request = ListCommitsRequest(repository_name="test-repo", branch="feature")
        result = await use_case.execute(request)

        for c in result.commits:
            assert c.is_branch_specific is False
            assert c.is_merge_base is False
