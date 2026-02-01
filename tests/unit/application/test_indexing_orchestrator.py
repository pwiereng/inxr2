"""Tests for IndexingOrchestratorPort using dependency injection."""

from pathlib import Path

import pytest

from inxr2.application.ports.services import IndexingOrchestratorPort
from inxr2.application.use_cases.indexing.orchestrator import (
    IncrementalIndexRequest,
    IndexingStrategy,
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
        self.incremental_updates: list[dict] = []

    async def index_repository(
        self, request: IndexRepositoryRequest
    ) -> IndexRepositoryResponse:
        """Simulate full repository indexing."""
        # Record the indexing request
        self.indexed_repositories.append(
            {
                "repository_path": request.repository_path,
                "branch": request.branch,
                "strategy": request.strategy,
                "force": request.force,
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
            files_reused=0,
            symbols_reused=0,
            references_reused=0,
            errors=[],
            elapsed_seconds=1.5,
        )

    async def index_incremental(
        self, request: IncrementalIndexRequest
    ) -> IndexRepositoryResponse:
        """Simulate incremental indexing."""
        # Record the incremental request
        self.incremental_updates.append(
            {
                "repository_id": request.repository_id,
                "branch": request.branch,
            }
        )

        # Return simulated statistics (fewer files than full index)
        return IndexRepositoryResponse(
            repository_id=request.repository_id,
            repository_name="test-repo",
            branch=request.branch or "main",
            commits_indexed=2,
            files_total=10,
            files_processed=8,
            files_skipped=2,
            files_failed=0,
            symbols_found=40,
            references_found=50,
            references_resolved=45,
            files_reused=5,
            symbols_reused=20,
            references_reused=25,
            errors=[],
            elapsed_seconds=0.3,
        )


class TestIndexingOrchestratorPort:
    """Tests for IndexingOrchestratorPort interface."""

    @pytest.fixture
    def orchestrator(self) -> FakeIndexingOrchestrator:
        """Create a fake orchestrator for testing."""
        return FakeIndexingOrchestrator()

    @pytest.mark.asyncio
    async def test_index_repository_full_strategy(
        self, orchestrator: FakeIndexingOrchestrator
    ) -> None:
        """Test full repository indexing with default settings."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python", "typescript"],
            strategy=IndexingStrategy.FULL,
            max_history=100,
            force=False,
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
        assert orchestrator.indexed_repositories[0]["strategy"] == IndexingStrategy.FULL

    @pytest.mark.asyncio
    async def test_index_repository_with_force(
        self, orchestrator: FakeIndexingOrchestrator
    ) -> None:
        """Test indexing with force flag clears existing data."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="develop",
            languages=["java"],
            strategy=IndexingStrategy.FULL,
            max_history=50,
            force=True,  # Force re-index
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert
        assert response.branch == "develop"
        assert orchestrator.indexed_repositories[0]["force"] is True

    @pytest.mark.asyncio
    async def test_index_repository_with_time_limit(
        self, orchestrator: FakeIndexingOrchestrator
    ) -> None:
        """Test indexing with since_days time limit."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            strategy=IndexingStrategy.FULL,
            max_history=None,  # No commit limit
            since_days=30,  # Only last 30 days
            force=False,
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert
        assert response.commits_indexed > 0
        assert response.files_processed > 0

    @pytest.mark.asyncio
    async def test_index_incremental(
        self, orchestrator: FakeIndexingOrchestrator
    ) -> None:
        """Test incremental indexing updates only changed commits."""
        # Arrange
        request = IncrementalIndexRequest(
            repository_id=1,
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_incremental(request)

        # Assert
        assert response.repository_id == 1
        assert response.commits_indexed == 2  # Only new commits
        assert response.files_total < 100  # Fewer files than full index
        assert response.files_reused > 0  # Content-hash optimization
        assert response.symbols_reused > 0
        assert response.references_reused > 0

        # Verify the request was recorded
        assert len(orchestrator.incremental_updates) == 1
        assert orchestrator.incremental_updates[0]["repository_id"] == 1

    @pytest.mark.asyncio
    async def test_index_repository_with_errors(
        self, orchestrator: FakeIndexingOrchestrator
    ) -> None:
        """Test that indexing errors are captured in response."""

        # Create a custom fake that simulates errors
        class ErrorSimulatingOrchestrator(FakeIndexingOrchestrator):
            async def index_repository(
                self, request: IndexRepositoryRequest
            ) -> IndexRepositoryResponse:
                response = await super().index_repository(request)
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
                    files_reused=0,
                    symbols_reused=0,
                    references_reused=0,
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
            languages=["python"],
            strategy=IndexingStrategy.FULL,
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
            languages=["python"],
            strategy=IndexingStrategy.FULL,
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
        assert isinstance(response.files_reused, int)
        assert isinstance(response.symbols_reused, int)
        assert isinstance(response.references_reused, int)
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
            languages=["python", "typescript", "java", "c"],
            strategy=IndexingStrategy.FULL,
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert
        assert response.files_processed > 0
        assert response.symbols_found > 0

        # Verify request was recorded with all languages
        recorded = orchestrator.indexed_repositories[0]
        assert recorded["repository_path"] == Path("/repos/polyglot-repo")

    @pytest.mark.asyncio
    async def test_incremental_index_on_different_branch(
        self, orchestrator: FakeIndexingOrchestrator
    ) -> None:
        """Test incremental indexing on a feature branch."""
        # Arrange
        request = IncrementalIndexRequest(
            repository_id=1,
            repository_path=Path("/repos/test-repo"),
            branch="feature-branch",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_incremental(request)

        # Assert
        assert response.branch == "feature-branch"
        assert orchestrator.incremental_updates[0]["branch"] == "feature-branch"
