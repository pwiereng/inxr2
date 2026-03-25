"""Integration tests for /api/repositories endpoints."""

from collections.abc import AsyncGenerator
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
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


def make_test_commit_hash(prefix: str) -> CommitHash:
    """Create a valid 40-character test commit hash with a readable prefix.

    Args:
        prefix: A short readable prefix (will be padded to 40 chars with zeros)

    Returns:
        A CommitHash with exactly 40 characters
    """
    # Ensure exactly 40 characters (standard git commit hash length)
    padded = (prefix + "0" * 40)[:40]
    return CommitHash(padded)


@pytest_asyncio.fixture
async def test_app(db_session: AsyncSession) -> FastAPI:
    """Create a FastAPI app with overridden database session."""
    from inxr2.infrastructure.database import get_db_session

    app = create_app()

    # Override the database session dependency
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db

    return app


@pytest.mark.asyncio
class TestRepositoriesAPI:
    """Tests for /api/repositories endpoints."""

    async def test_list_repositories_empty(
        self, test_app: FastAPI, db_session: AsyncSession
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
        self, test_app: FastAPI, db_session: AsyncSession
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

    async def test_get_repository_files_not_found(self, test_app: FastAPI) -> None:
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
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting files for repository with files."""
        # Arrange - create repository with files
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="repo-with-files-api",
            url="https://github.com/test/files.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        # Create commit
        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("abc123"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit = await commit_adapter.save(commit)
        assert saved_commit.id is not None

        # Create files
        file_adapter = PostgresFileRepository(db_session)
        files = [
            File(
                repository_id=saved_repo.id,
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

    async def test_get_repository_by_id(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting a specific repository by ID."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="specific-repo-test",
            url="https://github.com/test/specific.git",
            description="Specific test repo",
        )
        saved = await repo_adapter.save(repository)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/repositories/{saved.id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == saved.id
        assert data["name"] == "specific-repo-test"
        assert data["description"] == "Specific test repo"

    async def test_get_repository_not_found(self, test_app: FastAPI) -> None:
        """Test getting a non-existent repository."""
        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/repositories/99999")

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_get_repository_tree(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting the file tree for a repository."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="tree-test-repo",
            url="https://github.com/test/tree.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        # Create commit
        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("tree123"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit = await commit_adapter.save(commit)
        assert saved_commit.id is not None

        # Create files with nested paths
        file_adapter = PostgresFileRepository(db_session)
        files = [
            File(
                repository_id=saved_repo.id,
                path="src/main.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            ),
            File(
                repository_id=saved_repo.id,
                path="src/utils/helper.py",
                content_hash="hash2",
                size_bytes=200,
                language="python",
            ),
            File(
                repository_id=saved_repo.id,
                path="tests/test_main.py",
                content_hash="hash3",
                size_bytes=150,
                language="python",
            ),
        ]
        await file_adapter.save_many(files)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/repositories/{saved_repo.id}/tree")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["repository_id"] == saved_repo.id
        assert data["repository_name"] == "tree-test-repo"
        assert data["total_files"] == 3
        assert data["total_directories"] >= 2  # src, src/utils, tests
        assert "root" in data
        assert len(data["root"]) == 2  # src and tests directories

    async def test_get_repository_tree_not_found(self, test_app: FastAPI) -> None:
        """Test getting tree for non-existent repository."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/repositories/99999/tree")

        assert response.status_code == 404

    async def test_get_repository_tree_by_id_passes_changed_only(
        self, test_app: FastAPI
    ) -> None:
        """Test that the by-ID tree endpoint passes changed_only to the use case."""
        from inxr2.application.use_cases.repositories.get_repository_tree import (
            GetRepositoryTreeRequest,
            GetRepositoryTreeResponse,
        )
        from inxr2.infrastructure.dependencies import get_repository_tree_use_case

        # Spy that captures the request
        captured_requests: list[GetRepositoryTreeRequest] = []

        class SpyUseCase:
            async def execute(
                self, request: GetRepositoryTreeRequest
            ) -> GetRepositoryTreeResponse:
                captured_requests.append(request)
                return GetRepositoryTreeResponse(
                    repository_id=request.repository_id or 0,
                    repository_name="spy-repo",
                    root=[],
                    total_files=0,
                    total_directories=0,
                )

        spy = SpyUseCase()
        test_app.dependency_overrides[get_repository_tree_use_case] = lambda: spy

        # Act — pass changed_only=true to the by-ID endpoint
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/repositories/1/tree",
                params={"commit": "a" * 40, "changed_only": "true"},
            )

        # Assert — endpoint passes changed_only=True to the use case
        assert response.status_code == 200
        assert len(captured_requests) == 1
        assert captured_requests[0].changed_only is True
        assert captured_requests[0].repository_id == 1
        assert captured_requests[0].commit_hash == "a" * 40

    async def test_get_repository_by_name(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting a repository by name."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="by-name-test-repo",
            url="https://github.com/test/byname.git",
            description="Test repo for by-name lookup",
        )
        await repo_adapter.save(repository)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/repositories/by-name/by-name-test-repo")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "by-name-test-repo"
        assert data["description"] == "Test repo for by-name lookup"

    async def test_get_repository_by_name_not_found(self, test_app: FastAPI) -> None:
        """Test getting a non-existent repository by name."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/repositories/by-name/nonexistent-repo")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_get_repository_tree_by_name(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting the file tree for a repository by name."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="tree-by-name-repo",
            url="https://github.com/test/treebyname.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        # Create commit
        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("treename"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit = await commit_adapter.save(commit)
        assert saved_commit.id is not None

        # Create files
        file_adapter = PostgresFileRepository(db_session)
        files = [
            File(
                repository_id=saved_repo.id,
                path="src/main.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            ),
            File(
                repository_id=saved_repo.id,
                path="tests/test_main.py",
                content_hash="hash2",
                size_bytes=150,
                language="python",
            ),
        ]
        await file_adapter.save_many(files)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/repositories/by-name/tree-by-name-repo/tree"
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["repository_name"] == "tree-by-name-repo"
        assert data["total_files"] == 2

    async def test_get_repository_tree_by_name_not_found(
        self, test_app: FastAPI
    ) -> None:
        """Test getting tree for non-existent repository by name."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/repositories/by-name/nonexistent-repo/tree"
            )

        assert response.status_code == 404

    async def test_get_repository_stats(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting statistics for a repository."""
        from inxr2.adapters.persistence.repositories.reference_adapter import (
            PostgresReferenceRepository,
        )
        from inxr2.domain.entities import Reference
        from inxr2.domain.value_objects import ReferenceType

        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="stats-test-repo",
            url="https://github.com/test/stats.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        # Create commits with different dates
        commit_adapter = PostgresCommitRepository(db_session)
        commit1 = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("stats12"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit1 = await commit_adapter.save(commit1)
        assert saved_commit1.id is not None
        await commit_adapter.link_commit_to_branch(
            saved_repo.id, saved_commit1.id, "main"
        )

        commit2 = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("stats13"),
            author_date=datetime(2025, 6, 15),
            commit_date=datetime(2025, 6, 15),
        )
        saved_commit2 = await commit_adapter.save(commit2)
        assert saved_commit2.id is not None
        await commit_adapter.link_commit_to_branch(
            saved_repo.id, saved_commit2.id, "main"
        )

        # Create files with different languages and line counts
        file_adapter = PostgresFileRepository(db_session)
        files = [
            File(
                repository_id=saved_repo.id,
                path="main.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
                line_count=50,
            ),
            File(
                repository_id=saved_repo.id,
                path="app.ts",
                content_hash="hash2",
                size_bytes=200,
                language="typescript",
                line_count=80,
            ),
            File(
                repository_id=saved_repo.id,
                path="helper.py",
                content_hash="hash3",
                size_bytes=150,
                language="python",
                line_count=30,
            ),
        ]
        saved_files = await file_adapter.save_many(files)
        file_ids = [f.id for f in saved_files if f.id is not None]
        await file_adapter.link_files_to_commit(file_ids, saved_commit2.id)

        # Create references (some resolved, some not)
        ref_adapter = PostgresReferenceRepository(db_session)
        from inxr2.adapters.persistence.repositories.symbol_adapter import (
            PostgresSymbolRepository,
        )
        from inxr2.domain.entities import Symbol
        from inxr2.domain.value_objects import SymbolKind

        symbol_adapter = PostgresSymbolRepository(db_session)
        first_file_id = saved_files[0].id
        assert first_file_id is not None
        sym = await symbol_adapter.save(
            Symbol(
                file_id=first_file_id,
                repository_id=saved_repo.id,
                name="helper",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )
        await ref_adapter.save_many(
            [
                Reference(
                    source_file_id=first_file_id,
                    repository_id=saved_repo.id,
                    source_line=10,
                    source_column=0,
                    source_end_column=6,
                    reference_text="helper",
                    reference_type=ReferenceType.CALL,
                    target_symbol_id=sym.id,  # resolved
                ),
                Reference(
                    source_file_id=first_file_id,
                    repository_id=saved_repo.id,
                    source_line=12,
                    source_column=0,
                    source_end_column=8,
                    reference_text="external",
                    reference_type=ReferenceType.CALL,
                    target_symbol_id=None,  # unresolved
                ),
            ]
        )

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/repositories/{saved_repo.id}/stats")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["repository_id"] == saved_repo.id
        assert data["name"] == "stats-test-repo"
        assert data["total_files"] == 3
        assert "languages" in data
        assert data["languages"]["python"] == 2
        assert data["languages"]["typescript"] == 1
        # New fields
        assert data["total_lines"] == 160  # 50 + 80 + 30
        assert data["total_references_resolved"] == 1
        assert data["total_references_unresolved"] == 1
        assert data["commit_date_earliest"] is not None
        assert data["commit_date_latest"] is not None

    async def test_get_all_repository_stats_batch(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test batch stats endpoint returns stats for all repositories."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo1 = Repository(
            name="batch-stats-repo-1",
            url="https://github.com/test/batch1.git",
        )
        repo2 = Repository(
            name="batch-stats-repo-2",
            url="https://github.com/test/batch2.git",
        )
        saved1 = await repo_adapter.save(repo1)
        saved2 = await repo_adapter.save(repo2)
        assert saved1.id is not None
        assert saved2.id is not None

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/repositories/stats")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        names = {s["name"] for s in data}
        assert "batch-stats-repo-1" in names
        assert "batch-stats-repo-2" in names

        # Each entry has the new fields
        for entry in data:
            assert "total_lines" in entry
            assert "total_references_resolved" in entry
            assert "total_references_unresolved" in entry
            assert "commit_date_earliest" in entry
            assert "commit_date_latest" in entry
