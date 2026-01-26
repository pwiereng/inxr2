"""Tests for GetRepositoryBranchesUseCase using dependency injection."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from inxr2.application.use_cases.repositories import (
    GetRepositoryBranchesRequest,
    GetRepositoryBranchesUseCase,
)
from inxr2.domain.entities import IndexStatus, Repository
from inxr2.domain.exceptions import RepositoryNotFound
from tests.fixtures.test_doubles import (
    InMemoryIndexStatusRepository,
    InMemoryRepositoryRepository,
)


class StubGitBranchService:
    """Stub git service for testing branch operations."""

    def __init__(self, branches: list[str] | None = None) -> None:
        """Initialize with predefined branches."""
        self._branches = branches or []
        self._error: Exception | None = None

    def set_branches(self, branches: list[str]) -> None:
        """Set branches to return."""
        self._branches = branches

    def set_error(self, error: Exception) -> None:
        """Set error to raise on list_branches."""
        self._error = error

    def list_branches(self, repo_path: Path) -> list[str]:
        """Return predefined branches."""
        if self._error:
            raise self._error
        return self._branches


class TestGetRepositoryBranchesUseCase:
    """Tests for GetRepositoryBranchesUseCase."""

    @pytest.fixture
    def repository_repo(self, tmp_path: Path) -> InMemoryRepositoryRepository:
        """Create repository with test data."""
        # Create a temp directory that exists for the repository path
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
    def index_status_repo(self) -> InMemoryIndexStatusRepository:
        """Create index status repository with test data."""
        repo = InMemoryIndexStatusRepository()
        # Completed indexing for main branch
        repo.add(
            IndexStatus(
                id=1,
                repository_id=1,
                branch="main",
                indexing_status="completed",
                last_indexed_commit="abc123",
                oldest_indexed_commit="def456",
                total_commits_indexed=50,
                last_indexed_at=datetime(2025, 1, 15, 10, 0, 0),
            )
        )
        # Completed indexing for feature branch
        repo.add(
            IndexStatus(
                id=2,
                repository_id=1,
                branch="feature",
                indexing_status="completed",
                last_indexed_commit="ghi789",
                oldest_indexed_commit="ghi789",
                total_commits_indexed=5,
                last_indexed_at=datetime(2025, 1, 14, 10, 0, 0),
            )
        )
        # In-progress indexing for develop branch (should not be included)
        repo.add(
            IndexStatus(
                id=3,
                repository_id=1,
                branch="develop",
                indexing_status="in_progress",
                last_indexed_commit=None,
                oldest_indexed_commit=None,
                total_commits_indexed=0,
            )
        )
        return repo

    @pytest.fixture
    def git_service(self) -> StubGitBranchService:
        """Create stub git service with test branches."""
        service = StubGitBranchService()
        service.set_branches(["main", "feature", "develop", "hotfix"])
        return service

    @pytest.fixture
    def use_case(
        self,
        repository_repo: InMemoryRepositoryRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        git_service: StubGitBranchService,
    ) -> GetRepositoryBranchesUseCase:
        """Create use case with test dependencies."""
        return GetRepositoryBranchesUseCase(
            repository_repo=repository_repo,
            index_status_repo=index_status_repo,
            git_service=git_service,
        )

    # === Repository Resolution Tests ===

    @pytest.mark.asyncio
    async def test_get_branches_by_repository_id(
        self, use_case: GetRepositoryBranchesUseCase
    ) -> None:
        """Should get branches when repository ID is provided."""
        request = GetRepositoryBranchesRequest(repository_id=1)

        response = await use_case.execute(request)

        assert len(response.branches) == 4
        assert response.default_branch == "main"

    @pytest.mark.asyncio
    async def test_get_branches_by_repository_name(
        self, use_case: GetRepositoryBranchesUseCase
    ) -> None:
        """Should get branches when repository name is provided."""
        request = GetRepositoryBranchesRequest(repository_name="test-repo")

        response = await use_case.execute(request)

        assert len(response.branches) == 4
        assert response.default_branch == "main"

    @pytest.mark.asyncio
    async def test_raises_repository_not_found_for_unknown_id(
        self, use_case: GetRepositoryBranchesUseCase
    ) -> None:
        """Should raise RepositoryNotFound for unknown repository ID."""
        request = GetRepositoryBranchesRequest(repository_id=999)

        with pytest.raises(RepositoryNotFound) as exc_info:
            await use_case.execute(request)

        assert "999" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_repository_not_found_for_unknown_name(
        self, use_case: GetRepositoryBranchesUseCase
    ) -> None:
        """Should raise RepositoryNotFound for unknown repository name."""
        request = GetRepositoryBranchesRequest(repository_name="unknown-repo")

        with pytest.raises(RepositoryNotFound) as exc_info:
            await use_case.execute(request)

        assert "unknown-repo" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_value_error_when_no_identifier_provided(
        self, use_case: GetRepositoryBranchesUseCase
    ) -> None:
        """Should raise ValueError when neither ID nor name is provided."""
        request = GetRepositoryBranchesRequest()

        with pytest.raises(ValueError) as exc_info:
            await use_case.execute(request)

        assert "repository_id or repository_name" in str(exc_info.value)

    # === Branch Listing Tests ===

    @pytest.mark.asyncio
    async def test_returns_all_git_branches(
        self, use_case: GetRepositoryBranchesUseCase
    ) -> None:
        """Should return all branches from git."""
        request = GetRepositoryBranchesRequest(repository_id=1)

        response = await use_case.execute(request)

        branch_names = [b.name for b in response.branches]
        assert branch_names == ["main", "feature", "develop", "hotfix"]

    @pytest.mark.asyncio
    async def test_includes_indexing_status_for_completed_branches(
        self, use_case: GetRepositoryBranchesUseCase
    ) -> None:
        """Should include indexing status for branches with completed indexing."""
        request = GetRepositoryBranchesRequest(repository_id=1)

        response = await use_case.execute(request)

        main_branch = next(b for b in response.branches if b.name == "main")
        assert main_branch.last_indexed_commit == "abc123"
        assert main_branch.oldest_indexed_commit == "def456"
        assert main_branch.commit_count == 50
        assert main_branch.last_indexed_at is not None

    @pytest.mark.asyncio
    async def test_returns_none_for_unindexed_branches(
        self, use_case: GetRepositoryBranchesUseCase
    ) -> None:
        """Should return None indexing info for unindexed branches."""
        request = GetRepositoryBranchesRequest(repository_id=1)

        response = await use_case.execute(request)

        hotfix_branch = next(b for b in response.branches if b.name == "hotfix")
        assert hotfix_branch.last_indexed_commit is None
        assert hotfix_branch.oldest_indexed_commit is None
        assert hotfix_branch.commit_count == 0
        assert hotfix_branch.last_indexed_at is None

    @pytest.mark.asyncio
    async def test_ignores_in_progress_indexing_status(
        self, use_case: GetRepositoryBranchesUseCase
    ) -> None:
        """Should ignore in-progress indexing status (not completed)."""
        request = GetRepositoryBranchesRequest(repository_id=1)

        response = await use_case.execute(request)

        develop_branch = next(b for b in response.branches if b.name == "develop")
        # develop has in_progress status, should be treated as unindexed
        assert develop_branch.last_indexed_commit is None
        assert develop_branch.commit_count == 0

    # === Path Validation Tests ===

    @pytest.mark.asyncio
    async def test_raises_value_error_for_nonexistent_path(
        self,
        repository_repo: InMemoryRepositoryRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        git_service: StubGitBranchService,
    ) -> None:
        """Should raise ValueError if repository path doesn't exist."""
        # Add a repository with a non-existent path
        repository_repo.add(
            Repository(
                id=2,
                name="missing-path",
                url="/nonexistent/path",
                default_branch="main",
            )
        )

        use_case = GetRepositoryBranchesUseCase(
            repository_repo=repository_repo,
            index_status_repo=index_status_repo,
            git_service=git_service,
        )

        request = GetRepositoryBranchesRequest(repository_id=2)

        with pytest.raises(ValueError) as exc_info:
            await use_case.execute(request)

        assert "path not found" in str(exc_info.value).lower()


class TestGetRepositoryBranchesUseCaseEdgeCases:
    """Edge case tests for GetRepositoryBranchesUseCase."""

    @pytest.mark.asyncio
    async def test_empty_branch_list(self, tmp_path: Path) -> None:
        """Should handle repository with no branches."""
        repo_path = tmp_path / "empty-repo"
        repo_path.mkdir()

        repository_repo = InMemoryRepositoryRepository()
        repository_repo.add(
            Repository(
                id=1, name="empty", url=str(repo_path), default_branch="main"
            )
        )

        git_service = StubGitBranchService(branches=[])
        index_status_repo = InMemoryIndexStatusRepository()

        use_case = GetRepositoryBranchesUseCase(
            repository_repo=repository_repo,
            index_status_repo=index_status_repo,
            git_service=git_service,
        )

        request = GetRepositoryBranchesRequest(repository_id=1)
        response = await use_case.execute(request)

        assert response.branches == []
        assert response.default_branch == "main"

    @pytest.mark.asyncio
    async def test_git_error_propagates(self, tmp_path: Path) -> None:
        """Should propagate git errors."""
        repo_path = tmp_path / "error-repo"
        repo_path.mkdir()

        repository_repo = InMemoryRepositoryRepository()
        repository_repo.add(
            Repository(
                id=1, name="error", url=str(repo_path), default_branch="main"
            )
        )

        git_service = StubGitBranchService()
        git_service.set_error(ValueError("Not a git repository"))
        index_status_repo = InMemoryIndexStatusRepository()

        use_case = GetRepositoryBranchesUseCase(
            repository_repo=repository_repo,
            index_status_repo=index_status_repo,
            git_service=git_service,
        )

        request = GetRepositoryBranchesRequest(repository_id=1)

        with pytest.raises(ValueError) as exc_info:
            await use_case.execute(request)

        assert "git repository" in str(exc_info.value).lower()
