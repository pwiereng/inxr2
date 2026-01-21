"""Tests for GetIndexStatusUseCase using dependency injection."""

from datetime import datetime

import pytest

from inxr2.application.use_cases.indexing import (
    GetIndexStatusRequest,
    GetIndexStatusUseCase,
)
from inxr2.domain.entities import IndexStatus, Repository
from tests.fixtures.test_doubles import (
    InMemoryIndexStatusRepository,
    InMemoryRepositoryRepository,
)


class TestGetIndexStatusUseCase:
    """Tests for GetIndexStatusUseCase."""

    @pytest.fixture
    def repository_repo(self) -> InMemoryRepositoryRepository:
        """Create a repository repo with test data."""
        repo = InMemoryRepositoryRepository()
        # Add a test repository
        repo.add(
            Repository(
                id=1,
                name="test-repo",
                url="/path/to/test-repo",
                description="Test repository",
            )
        )
        return repo

    @pytest.fixture
    def index_status_repo(self) -> InMemoryIndexStatusRepository:
        """Create an index status repo with test data."""
        repo = InMemoryIndexStatusRepository()
        # Add a test index status
        repo.add(
            IndexStatus(
                id=1,
                repository_id=1,
                branch="main",
                indexing_status="completed",
                last_indexed_commit="abc123def456",
                last_indexed_at=datetime(2024, 1, 15, 10, 30, 0),
                total_files_indexed=100,
                total_symbols_indexed=500,
                total_references_indexed=1000,
            )
        )
        return repo

    @pytest.fixture
    def use_case(
        self,
        repository_repo: InMemoryRepositoryRepository,
        index_status_repo: InMemoryIndexStatusRepository,
    ) -> GetIndexStatusUseCase:
        """Create the use case with fake repositories."""
        return GetIndexStatusUseCase(
            repository_repo=repository_repo,
            index_status_repo=index_status_repo,
        )

    @pytest.mark.asyncio
    async def test_get_status_for_indexed_repository(
        self, use_case: GetIndexStatusUseCase
    ) -> None:
        """Test getting status for an indexed repository."""
        # Arrange
        request = GetIndexStatusRequest(
            repository_name="test-repo",
            branch="main",
            current_commit_hash="abc123def456",
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.repository_name == "test-repo"
        assert response.branch == "main"
        assert response.is_indexed is True
        assert response.last_indexed_commit == "abc123def456"
        assert response.total_files_indexed == 100
        assert response.total_symbols_indexed == 500
        assert response.total_references_indexed == 1000
        assert response.is_up_to_date is True  # Current commit matches

    @pytest.mark.asyncio
    async def test_get_status_for_outdated_index(
        self, use_case: GetIndexStatusUseCase
    ) -> None:
        """Test getting status when index is outdated."""
        # Arrange
        request = GetIndexStatusRequest(
            repository_name="test-repo",
            branch="main",
            current_commit_hash="different_commit_hash",  # Different from indexed
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.is_indexed is True
        assert response.is_up_to_date is False  # Different commit

    @pytest.mark.asyncio
    async def test_get_status_for_unknown_repository(
        self, use_case: GetIndexStatusUseCase
    ) -> None:
        """Test getting status for a repository not in database."""
        # Arrange
        request = GetIndexStatusRequest(
            repository_name="unknown-repo",
            branch="main",
            current_commit_hash="abc123",
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.repository_name == "unknown-repo"
        assert response.is_indexed is False
        assert response.last_indexed_commit is None
        assert response.total_files_indexed == 0

    @pytest.mark.asyncio
    async def test_get_status_for_unindexed_branch(
        self,
        repository_repo: InMemoryRepositoryRepository,
        index_status_repo: InMemoryIndexStatusRepository,
    ) -> None:
        """Test getting status for a branch that hasn't been indexed."""
        # Arrange
        use_case = GetIndexStatusUseCase(
            repository_repo=repository_repo,
            index_status_repo=index_status_repo,
        )
        request = GetIndexStatusRequest(
            repository_name="test-repo",
            branch="feature-branch",  # Not indexed
            current_commit_hash="xyz789",
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.is_indexed is False
        assert response.branch == "feature-branch"

    @pytest.mark.asyncio
    async def test_get_status_without_current_commit(
        self, use_case: GetIndexStatusUseCase
    ) -> None:
        """Test getting status when current commit is not provided."""
        # Arrange
        request = GetIndexStatusRequest(
            repository_name="test-repo",
            branch="main",
            current_commit_hash=None,  # Not provided
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.is_indexed is True
        assert response.is_up_to_date is False  # Can't be up to date without commit
        assert response.current_commit_hash is None
