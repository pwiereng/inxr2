"""Integration tests for API endpoints.

These tests verify that the FastAPI routes work correctly
with real use cases and database adapters.
"""

from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from inxr2.adapters.persistence.repositories.file_adapter import PostgresFileRepository
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from inxr2.domain.entities import Commit, File, Repository
from inxr2.domain.value_objects import CommitHash
from inxr2.infrastructure.fastapi.app import create_app


@pytest_asyncio.fixture
async def test_app(db_session: AsyncSession):
    """Create a FastAPI app with overridden database session."""
    from inxr2.infrastructure.database import get_db_session

    app = create_app()

    # Override the database session dependency
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db

    return app


@pytest.mark.asyncio
class TestRepositoriesAPI:
    """Tests for /api/repositories endpoints."""

    async def test_list_repositories_empty(
        self, test_app, db_session: AsyncSession
    ) -> None:
        """Test listing repositories when none exist."""
        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/repositories")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_list_repositories_with_data(
        self, test_app, db_session: AsyncSession
    ) -> None:
        """Test listing repositories with existing data."""
        # Arrange - create test repositories
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo1 = Repository(
            name="test-repo-api-1",
            url="https://github.com/test/repo1.git",
            description="Test repository 1",
        )
        repo2 = Repository(
            name="test-repo-api-2",
            url="https://github.com/test/repo2.git",
            description="Test repository 2",
        )
        await repo_adapter.save(repo1)
        await repo_adapter.save(repo2)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/repositories")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

        # Verify our repositories are in the response
        repo_names = {r["name"] for r in data}
        assert "test-repo-api-1" in repo_names
        assert "test-repo-api-2" in repo_names

    async def test_get_repository_files_not_found(self, test_app) -> None:
        """Test getting files for non-existent repository."""
        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/repositories/99999/files")

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_get_repository_files_with_data(
        self, test_app, db_session: AsyncSession
    ) -> None:
        """Test getting files for repository with files."""
        # Arrange - create repository with files
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="repo-with-files-api",
            url="https://github.com/test/files.git",
        )
        saved_repo = await repo_adapter.save(repository)

        # Create commit
        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("abc123" + "0" * 34),
            author_name="Test Author",
            author_email="test@example.com",
            committer_name="Test Author",
            committer_email="test@example.com",
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
            message="Test commit",
        )
        saved_commit = await commit_adapter.save(commit)

        # Create files
        file_adapter = PostgresFileRepository(db_session)
        files = [
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                path=f"src/api_file{i}.py",
                content_hash=f"hash{i}",
                size_bytes=100 * (i + 1),
                language="python",
                line_count=10 * (i + 1),
            )
            for i in range(3)
        ]
        await file_adapter.save_many(files)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/repositories/{saved_repo.id}/files")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

        # Verify file details
        paths = {f["path"] for f in data}
        assert "src/api_file0.py" in paths
        assert "src/api_file1.py" in paths
        assert "src/api_file2.py" in paths

        # Verify response structure
        first_file = data[0]
        assert "id" in first_file
        assert "path" in first_file
        assert "language" in first_file
        assert "size_bytes" in first_file
        assert "line_count" in first_file
