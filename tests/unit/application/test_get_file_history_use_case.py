"""Tests for GetFileHistoryUseCase using dependency injection."""

from datetime import datetime
from pathlib import Path

import pytest

from inxr2.application.use_cases.files import (
    GetFileHistoryRequest,
    GetFileHistoryUseCase,
)
from inxr2.domain.entities import Commit, File, Repository
from inxr2.domain.exceptions import FileNotFound, RepositoryNotFound
from inxr2.domain.value_objects import CommitHash
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryRepositoryRepository,
)


class StubGitCommitInfoService:
    """Stub git service for testing commit info retrieval."""

    def __init__(self) -> None:
        """Initialize with empty commit info map."""
        self._commit_info: dict[tuple[str, str], dict[str, str]] = {}

    def set_commit_info(
        self, repo_path: str, commit_hash: str, info: dict[str, str]
    ) -> None:
        """Set commit info to return for a commit."""
        key = (repo_path, commit_hash)
        self._commit_info[key] = info

    def get_commit_info(self, repo_path: Path, commit_hash: str) -> dict[str, str]:
        """Return predefined commit info or empty dict."""
        key = (str(repo_path), commit_hash)
        return self._commit_info.get(key, {})


class TestGetFileHistoryUseCase:
    """Tests for GetFileHistoryUseCase."""

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

        # Add multiple commits for version history
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

        # Link commits to branches
        repo._branch_commits[(1, "main", 1)] = True
        repo._branch_commits[(1, "main", 2)] = True
        repo._branch_commits[(1, "main", 3)] = True
        repo._branch_commits[(1, "feature", 2)] = True  # Shared with main
        repo._branch_commits[(1, "feature", 3)] = True  # Shared with main

        return repo

    @pytest.fixture
    def file_repo(
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        """Create file repository with test data."""
        repo = InMemoryFileRepository(commit_repo=commit_repo)

        # Add file versions at different commits
        repo.add(
            File(
                id=1,
                repository_id=1,
                commit_id=1,
                path="src/main.py",
                content_hash="hash1",
                size_bytes=100,
                language="Python",
            )
        )
        repo.add(
            File(
                id=2,
                repository_id=1,
                commit_id=2,
                path="src/main.py",
                content_hash="hash2",
                size_bytes=150,
                language="Python",
            )
        )
        repo.add(
            File(
                id=3,
                repository_id=1,
                commit_id=3,
                path="src/main.py",
                content_hash="hash3",
                size_bytes=200,
                language="Python",
            )
        )

        return repo

    @pytest.fixture
    def git_service(self, tmp_path: Path) -> StubGitCommitInfoService:
        """Create stub git service with test commit info."""
        repo_path = tmp_path / "test-repo"
        service = StubGitCommitInfoService()
        service.set_commit_info(
            str(repo_path),
            "abc123def456",
            {"message": "Initial commit"},
        )
        service.set_commit_info(
            str(repo_path),
            "def456ghi789",
            {"message": "Add feature X"},
        )
        service.set_commit_info(
            str(repo_path),
            "ghi789jkl012",
            {"message": "Fix bug in feature X"},
        )
        return service

    @pytest.fixture
    def use_case(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
        git_service: StubGitCommitInfoService,
    ) -> GetFileHistoryUseCase:
        """Create use case with test dependencies."""
        return GetFileHistoryUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

    # === Basic History Retrieval Tests ===

    @pytest.mark.asyncio
    async def test_get_file_history_returns_all_versions(
        self, use_case: GetFileHistoryUseCase
    ) -> None:
        """Should return all indexed versions of a file."""
        request = GetFileHistoryRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        result = await use_case.execute(request)

        assert result.total == 3
        assert len(result.versions) == 3
        assert result.path == "src/main.py"
        assert result.repository_name == "test-repo"

    @pytest.mark.asyncio
    async def test_get_file_history_includes_commit_metadata(
        self, use_case: GetFileHistoryUseCase
    ) -> None:
        """Should include commit hash, date, and message for each version."""
        request = GetFileHistoryRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        result = await use_case.execute(request)

        # Check that we have the expected commit hashes
        commit_hashes = {v.commit_hash for v in result.versions}
        assert "abc123def456" in commit_hashes
        assert "def456ghi789" in commit_hashes
        assert "ghi789jkl012" in commit_hashes

    @pytest.mark.asyncio
    async def test_get_file_history_hydrates_messages(
        self, use_case: GetFileHistoryUseCase
    ) -> None:
        """Should hydrate commit messages from git."""
        request = GetFileHistoryRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        result = await use_case.execute(request)

        messages = {v.message for v in result.versions}
        assert "Initial commit" in messages
        assert "Add feature X" in messages
        assert "Fix bug in feature X" in messages

    @pytest.mark.asyncio
    async def test_get_file_history_includes_content_hash(
        self, use_case: GetFileHistoryUseCase
    ) -> None:
        """Should include content hash to identify changes between versions."""
        request = GetFileHistoryRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        result = await use_case.execute(request)

        content_hashes = {v.content_hash for v in result.versions}
        assert "hash1" in content_hashes
        assert "hash2" in content_hashes
        assert "hash3" in content_hashes

    # === Branch Filtering Tests ===

    @pytest.mark.asyncio
    async def test_get_file_history_filters_by_branch(
        self, use_case: GetFileHistoryUseCase
    ) -> None:
        """Should filter versions by branch when specified."""
        request = GetFileHistoryRequest(
            repository_name="test-repo",
            file_path="src/main.py",
            branch="feature",
        )

        result = await use_case.execute(request)

        # feature branch only has commits 2 and 3
        assert result.total == 2
        commit_hashes = {v.commit_hash for v in result.versions}
        assert "abc123def456" not in commit_hashes  # commit 1 is main-only
        assert "def456ghi789" in commit_hashes
        assert "ghi789jkl012" in commit_hashes

    @pytest.mark.asyncio
    async def test_get_file_history_fallback_to_default_branch(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
        git_service: StubGitCommitInfoService,
    ) -> None:
        """Should fall back to default branch when specified branch has no commits."""
        use_case = GetFileHistoryUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

        request = GetFileHistoryRequest(
            repository_name="test-repo",
            file_path="src/main.py",
            branch="empty-branch",  # No commits on this branch
        )

        result = await use_case.execute(request)

        # Should fall back to main branch (3 versions)
        assert result.total == 3

    # === Error Handling Tests ===

    @pytest.mark.asyncio
    async def test_raises_repository_not_found(
        self, use_case: GetFileHistoryUseCase
    ) -> None:
        """Should raise RepositoryNotFound for unknown repository."""
        request = GetFileHistoryRequest(
            repository_name="unknown-repo",
            file_path="src/main.py",
        )

        with pytest.raises(RepositoryNotFound):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_raises_file_not_found(self, use_case: GetFileHistoryUseCase) -> None:
        """Should raise FileNotFound for unknown file path."""
        request = GetFileHistoryRequest(
            repository_name="test-repo",
            file_path="nonexistent/file.py",
        )

        with pytest.raises(FileNotFound):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_handles_missing_commit_message_gracefully(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
        tmp_path: Path,
    ) -> None:
        """Should return empty message when git info unavailable."""
        # Create git service that returns empty info
        git_service = StubGitCommitInfoService()

        use_case = GetFileHistoryUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

        request = GetFileHistoryRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        result = await use_case.execute(request)

        # All messages should be empty since git service returns nothing
        for version in result.versions:
            assert version.message == ""

    # === Short Hash Tests ===

    @pytest.mark.asyncio
    async def test_includes_short_hash(self, use_case: GetFileHistoryUseCase) -> None:
        """Should include short hash for display."""
        request = GetFileHistoryRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        result = await use_case.execute(request)

        # Short hash is first 7 chars of full hash
        short_hashes = {v.short_hash for v in result.versions}
        assert "abc123d" in short_hashes
        assert "def456g" in short_hashes
        assert "ghi789j" in short_hashes

    # === Message Truncation Tests ===

    @pytest.mark.asyncio
    async def test_truncates_long_messages(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
        tmp_path: Path,
    ) -> None:
        """Should truncate commit messages to 100 characters."""
        repo_path = tmp_path / "test-repo"
        git_service = StubGitCommitInfoService()
        long_message = "x" * 200
        git_service.set_commit_info(
            str(repo_path),
            "abc123def456",
            {"message": long_message},
        )

        use_case = GetFileHistoryUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

        request = GetFileHistoryRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        result = await use_case.execute(request)

        # Find the version with the long message (commit 1)
        version = next(v for v in result.versions if v.commit_hash == "abc123def456")
        assert len(version.message) == 100
