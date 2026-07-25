"""Integration tests for /api/search endpoints."""

from datetime import datetime

import pytest
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


@pytest.mark.asyncio
class TestFileSearchAPI:
    """Tests for /api/search/files endpoint."""

    async def test_search_files_returns_matching_files(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test searching files by name."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="file-search-repo",
            url="https://github.com/test/filesearch.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("fsearch"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit = await commit_adapter.save(commit)
        assert saved_commit.id is not None

        # Link commit to default branch (required for scope=latest global search)
        await commit_adapter.link_commit_to_branch(
            saved_repo.id, saved_commit.id, "main"
        )

        file_adapter = PostgresFileRepository(db_session)
        files = [
            File(
                repository_id=saved_repo.id,
                path="src/utils.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            ),
            File(
                repository_id=saved_repo.id,
                path="src/main.py",
                content_hash="hash2",
                size_bytes=150,
                language="python",
            ),
            File(
                repository_id=saved_repo.id,
                path="tests/test_utils.py",
                content_hash="hash3",
                size_bytes=200,
                language="python",
            ),
        ]
        saved_files = await file_adapter.save_many(files)

        # Link files to commit (required for scope=latest global search)
        file_ids = [f.id for f in saved_files if f.id is not None]
        await file_adapter.link_files_to_commit(file_ids, saved_commit.id)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/search/files",
                params={"q": "utils"},
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert len(data["files"]) == 2
        paths = {f["path"] for f in data["files"]}
        assert "src/utils.py" in paths
        assert "tests/test_utils.py" in paths

    async def test_search_files_with_repository_filter(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test searching files filtered by repository name."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo1 = Repository(
            name="search-repo-1",
            url="https://github.com/test/repo1.git",
        )
        repo2 = Repository(
            name="search-repo-2",
            url="https://github.com/test/repo2.git",
        )
        saved_repo1 = await repo_adapter.save(repo1)
        saved_repo2 = await repo_adapter.save(repo2)
        assert saved_repo1.id is not None
        assert saved_repo2.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit1 = Commit(
            repository_id=saved_repo1.id,
            commit_hash=make_test_commit_hash("repofil1"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        commit2 = Commit(
            repository_id=saved_repo2.id,
            commit_hash=make_test_commit_hash("repofil2"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit1 = await commit_adapter.save(commit1)
        saved_commit2 = await commit_adapter.save(commit2)
        assert saved_commit1.id is not None
        assert saved_commit2.id is not None

        file_adapter = PostgresFileRepository(db_session)
        file1 = await file_adapter.save(
            File(
                repository_id=saved_repo1.id,
                path="src/config.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            )
        )
        file2 = await file_adapter.save(
            File(
                repository_id=saved_repo2.id,
                path="src/config.py",
                content_hash="hash2",
                size_bytes=100,
                language="python",
            )
        )
        assert file1.id is not None
        assert file2.id is not None
        await file_adapter.link_file_to_commit(file1.id, saved_commit1.id)
        await file_adapter.link_file_to_commit(file2.id, saved_commit2.id)

        # Act - search within repo1 only
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/search/files",
                params={"q": "config", "repository": "search-repo-1"},
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["files"][0]["repository_name"] == "search-repo-1"

    async def test_search_files_with_language_filter(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test searching files filtered by language."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="lang-filter-repo",
            url="https://github.com/test/langfilter.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("langfil"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit = await commit_adapter.save(commit)
        assert saved_commit.id is not None

        # Link commit to default branch (required for scope=latest global search)
        await commit_adapter.link_commit_to_branch(
            saved_repo.id, saved_commit.id, "main"
        )

        file_adapter = PostgresFileRepository(db_session)
        saved_f1 = await file_adapter.save(
            File(
                repository_id=saved_repo.id,
                path="src/utils.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            )
        )
        saved_f2 = await file_adapter.save(
            File(
                repository_id=saved_repo.id,
                path="src/utils.ts",
                content_hash="hash2",
                size_bytes=100,
                language="typescript",
            )
        )

        # Link files to commit (required for scope=latest global search)
        assert saved_f1.id is not None and saved_f2.id is not None
        await file_adapter.link_files_to_commit(
            [saved_f1.id, saved_f2.id], saved_commit.id
        )

        # Act - search for python files only
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/search/files",
                params={"q": "utils", "language": "python"},
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["files"][0]["path"] == "src/utils.py"
        assert data["files"][0]["language"] == "python"

    async def test_search_files_returns_file_metadata(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test that file search returns all expected metadata."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="file-metadata-repo",
            url="https://github.com/test/metadata.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("metadata"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit = await commit_adapter.save(commit)
        assert saved_commit.id is not None

        # Link commit to default branch (required for scope=latest global search)
        await commit_adapter.link_commit_to_branch(
            saved_repo.id, saved_commit.id, "main"
        )

        file_adapter = PostgresFileRepository(db_session)
        saved_file = await file_adapter.save(
            File(
                repository_id=saved_repo.id,
                path="src/module/helper.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            )
        )

        # Link file to commit (required for scope=latest global search)
        assert saved_file.id is not None
        await file_adapter.link_file_to_commit(saved_file.id, saved_commit.id)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/search/files",
                params={"q": "helper"},
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1

        file = data["files"][0]
        assert file["path"] == "src/module/helper.py"
        assert file["name"] == "helper.py"
        assert file["language"] == "python"
        assert file["repository_name"] == "file-metadata-repo"
        assert "commit_hash" in file
        assert "commit_id" in file

    async def test_search_files_empty_query_rejected(self, test_app: FastAPI) -> None:
        """Test that empty queries are rejected."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/search/files",
                params={"q": ""},
            )

        assert response.status_code == 422  # Validation error

    async def test_search_files_no_results(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test searching files with no matching results."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="no-results-repo",
            url="https://github.com/test/noresults.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("noreslt"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit = await commit_adapter.save(commit)
        assert saved_commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        await file_adapter.save(
            File(
                repository_id=saved_repo.id,
                path="src/main.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            )
        )

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/search/files",
                params={"q": "nonexistent"},
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        assert data["files"] == []

    async def test_search_files_repository_not_found(self, test_app: FastAPI) -> None:
        """Test searching files with non-existent repository."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/search/files",
                params={"q": "test", "repository": "nonexistent-repo"},
            )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
