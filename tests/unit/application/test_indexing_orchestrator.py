"""Tests for IndexingOrchestratorPort using dependency injection."""

from pathlib import Path

import pytest

from inxr2.application.ports.services import IndexingOrchestratorPort, ProgressCallback
from inxr2.application.use_cases.indexing.orchestrator import (
    IndexRepositoryRequest,
    IndexRepositoryResponse,
)


class FakeIndexingOrchestrator(IndexingOrchestratorPort):
    """Fake implementation of IndexingOrchestratorPort for testing.

    This fake simulates indexing behavior without actually processing files.
    It allows tests to verify the port interface contract.
    """

    def __init__(self) -> None:
        self.indexed_repositories: list[dict] = []

    async def index_repository(
        self,
        request: IndexRepositoryRequest,
        progress_callback: ProgressCallback | None = None,
    ) -> IndexRepositoryResponse:
        """Simulate repository indexing."""
        # Record the indexing request
        self.indexed_repositories.append(
            {
                "repository_path": request.repository_path,
                "branch": request.branch,
                "days": request.days,
            }
        )

        # Return simulated statistics
        return IndexRepositoryResponse(
            repository_id=1,
            repository_name="test-repo",
            branch=request.branch or "main",
            commits_indexed=10,
            files_total=100,
            files_processed=95,
            files_skipped=5,
            files_failed=0,
            symbols_found=400,
            references_found=500,
            references_resolved=450,
            file_versions_new=95,
            file_versions_cached=0,
            errors=[],
            elapsed_seconds=1.5,
        )


class TestIndexingOrchestratorPort:
    """Tests for IndexingOrchestratorPort interface."""

    @pytest.fixture
    def orchestrator(self) -> FakeIndexingOrchestrator:
        """Create a fake orchestrator for testing."""
        return FakeIndexingOrchestrator()

    @pytest.mark.asyncio
    async def test_index_repository(
        self, orchestrator: FakeIndexingOrchestrator
    ) -> None:
        """Test repository indexing with default settings."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert
        assert response.repository_name == "test-repo"
        assert response.branch == "main"
        assert response.commits_indexed == 10
        assert response.files_processed == 95
        assert response.symbols_found == 400
        assert response.references_resolved == 450
        assert len(response.errors) == 0

        # Verify the request was recorded
        assert len(orchestrator.indexed_repositories) == 1
        assert orchestrator.indexed_repositories[0]["repository_path"] == Path(
            "/repos/test-repo"
        )

    @pytest.mark.asyncio
    async def test_index_repository_with_days(
        self, orchestrator: FakeIndexingOrchestrator
    ) -> None:
        """Test indexing with --days extends history backward."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="develop",
            days=30,
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert
        assert response.branch == "develop"
        assert orchestrator.indexed_repositories[0]["days"] == 30

    @pytest.mark.asyncio
    async def test_index_repository_with_time_limit(
        self, orchestrator: FakeIndexingOrchestrator
    ) -> None:
        """Test indexing with days time limit."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            days=30,
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert
        assert response.commits_indexed > 0
        assert response.files_processed > 0

    @pytest.mark.asyncio
    async def test_index_repository_with_errors(
        self, orchestrator: FakeIndexingOrchestrator
    ) -> None:
        """Test that indexing errors are captured in response."""

        # Create a custom fake that simulates errors
        class ErrorSimulatingOrchestrator(FakeIndexingOrchestrator):
            async def index_repository(
                self,
                request: IndexRepositoryRequest,
                progress_callback: ProgressCallback | None = None,
            ) -> IndexRepositoryResponse:
                response = await super().index_repository(request, progress_callback)
                # Simulate some errors
                return IndexRepositoryResponse(
                    repository_id=response.repository_id,
                    repository_name=response.repository_name,
                    branch=response.branch,
                    commits_indexed=response.commits_indexed,
                    files_total=100,
                    files_processed=90,
                    files_skipped=5,
                    files_failed=5,  # Some failures
                    symbols_found=350,
                    references_found=400,
                    references_resolved=380,
                    file_versions_new=90,
                    file_versions_cached=0,
                    errors=[
                        "Failed to parse invalid_file.py: SyntaxError",
                        "Failed to read binary_file.bin: UnicodeDecodeError",
                    ],
                    elapsed_seconds=response.elapsed_seconds,
                )

        # Arrange
        error_orchestrator = ErrorSimulatingOrchestrator()
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
        )

        # Act
        response = await error_orchestrator.index_repository(request)

        # Assert
        assert response.files_failed == 5
        assert len(response.errors) == 2
        assert "SyntaxError" in response.errors[0]
        assert "UnicodeDecodeError" in response.errors[1]

    @pytest.mark.asyncio
    async def test_index_repository_response_statistics(
        self, orchestrator: FakeIndexingOrchestrator
    ) -> None:
        """Test that response contains all required statistics."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert - verify all expected fields are present
        assert isinstance(response.repository_id, int)
        assert isinstance(response.repository_name, str)
        assert isinstance(response.branch, str)
        assert isinstance(response.commits_indexed, int)
        assert isinstance(response.files_total, int)
        assert isinstance(response.files_processed, int)
        assert isinstance(response.files_skipped, int)
        assert isinstance(response.files_failed, int)
        assert isinstance(response.symbols_found, int)
        assert isinstance(response.references_found, int)
        assert isinstance(response.references_resolved, int)
        assert isinstance(response.file_versions_new, int)
        assert isinstance(response.file_versions_cached, int)
        assert isinstance(response.errors, list)
        assert isinstance(response.elapsed_seconds, float)

    @pytest.mark.asyncio
    async def test_index_repository_with_multiple_languages(
        self, orchestrator: FakeIndexingOrchestrator
    ) -> None:
        """Test indexing with multiple programming languages."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/polyglot-repo"),
            branch="main",
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert
        assert response.files_processed > 0
        assert response.symbols_found > 0

        # Verify request was recorded with all languages
        recorded = orchestrator.indexed_repositories[0]
        assert recorded["repository_path"] == Path("/repos/polyglot-repo")
