"""Integration tests for API endpoints.

These tests verify that the FastAPI routes work correctly
with real use cases and database adapters.
"""

import subprocess
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path

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


def _create_git_repo_with_commits(
    repo_path: Path,
    commits: list[tuple[str, str]],
    branch: str = "main",
) -> list[str]:
    """Create a real git repo with commits and return their hashes.

    Args:
        repo_path: Directory to initialize the git repo in.
        commits: List of (filename, message) tuples for each commit.
        branch: Branch name to create commits on.

    Returns:
        List of commit hashes (oldest first).
    """
    repo_path.mkdir(parents=True, exist_ok=True)
    env = {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@test.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@test.com",
    }

    def _run(*args: str) -> str:
        result = subprocess.run(
            args,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=True,
            env={**env, "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        return result.stdout.strip()

    _run("git", "init", "-b", branch)
    hashes = []
    for filename, message in commits:
        (repo_path / filename).write_text(f"content for {filename}\n")
        _run("git", "add", filename)
        _run("git", "commit", "-m", message)
        h = _run("git", "rev-parse", "HEAD")
        hashes.append(h)
    return hashes


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
                commit_id=saved_commit.id,
                path="src/main.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            ),
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                path="src/utils/helper.py",
                content_hash="hash2",
                size_bytes=200,
                language="python",
            ),
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
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
                commit_id=saved_commit.id,
                path="src/main.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            ),
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
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
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="stats-test-repo",
            url="https://github.com/test/stats.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        # Create commit
        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("stats12"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit = await commit_adapter.save(commit)
        assert saved_commit.id is not None

        # Create files with different languages
        file_adapter = PostgresFileRepository(db_session)
        files = [
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                path="main.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            ),
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                path="app.ts",
                content_hash="hash2",
                size_bytes=200,
                language="typescript",
            ),
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                path="helper.py",
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


@pytest.mark.asyncio
class TestSymbolsAPI:
    """Tests for /api/symbols endpoints."""

    async def _create_test_data(
        self, db_session: AsyncSession
    ) -> tuple[Repository, Commit, File]:
        """Create test repository, commit, and file for symbol tests."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="symbols-test-repo",
            url="https://github.com/test/symbols.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("symbols"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit = await commit_adapter.save(commit)
        assert saved_commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        file = File(
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            path="src/main.py",
            content_hash="hash1",
            size_bytes=100,
            language="python",
        )
        saved_file = await file_adapter.save(file)
        assert saved_file.id is not None

        return saved_repo, saved_commit, saved_file

    async def test_search_symbols_empty(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test searching symbols when none exist."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/symbols?q=test")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 0

    async def test_search_symbols_with_data(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test searching symbols with existing data."""
        from inxr2.adapters.persistence.repositories.symbol_adapter import (
            PostgresSymbolRepository,
        )
        from inxr2.domain.entities import Symbol
        from inxr2.domain.value_objects import SymbolKind

        # Arrange
        saved_repo, saved_commit, saved_file = await self._create_test_data(db_session)
        assert saved_repo.id is not None
        assert saved_commit.id is not None
        assert saved_file.id is not None

        symbol_adapter = PostgresSymbolRepository(db_session)
        symbols = [
            Symbol(
                file_id=saved_file.id,
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                name="MyClass",
                qualified_name="src.main.MyClass",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            ),
            Symbol(
                file_id=saved_file.id,
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                name="my_function",
                qualified_name="src.main.my_function",
                kind=SymbolKind.FUNCTION,
                start_line=12,
                start_column=0,
                end_line=20,
                end_column=0,
            ),
        ]
        await symbol_adapter.save_many(symbols)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/symbols?q=my")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        names = {s["name"] for s in data["items"]}
        assert "MyClass" in names
        assert "my_function" in names

    async def test_search_symbols_with_kind_filter(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test searching symbols with kind filter."""
        from inxr2.adapters.persistence.repositories.symbol_adapter import (
            PostgresSymbolRepository,
        )
        from inxr2.domain.entities import Symbol
        from inxr2.domain.value_objects import SymbolKind

        # Arrange
        saved_repo, saved_commit, saved_file = await self._create_test_data(db_session)
        assert saved_repo.id is not None
        assert saved_commit.id is not None
        assert saved_file.id is not None

        symbol_adapter = PostgresSymbolRepository(db_session)
        symbols = [
            Symbol(
                file_id=saved_file.id,
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                name="TestClass",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            ),
            Symbol(
                file_id=saved_file.id,
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                name="test_function",
                kind=SymbolKind.FUNCTION,
                start_line=12,
                start_column=0,
                end_line=20,
                end_column=0,
            ),
        ]
        await symbol_adapter.save_many(symbols)

        # Act - search for functions only
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/symbols?q=test&kind=function")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "test_function"
        assert data["items"][0]["kind"] == "function"

    async def test_get_symbol_by_id(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting a specific symbol by ID."""
        from inxr2.adapters.persistence.repositories.symbol_adapter import (
            PostgresSymbolRepository,
        )
        from inxr2.domain.entities import Symbol
        from inxr2.domain.value_objects import SymbolKind

        # Arrange
        saved_repo, saved_commit, saved_file = await self._create_test_data(db_session)
        assert saved_repo.id is not None
        assert saved_commit.id is not None
        assert saved_file.id is not None

        symbol_adapter = PostgresSymbolRepository(db_session)
        symbol = Symbol(
            file_id=saved_file.id,
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            name="UniqueSymbol",
            qualified_name="src.main.UniqueSymbol",
            kind=SymbolKind.CLASS,
            start_line=1,
            start_column=0,
            end_line=10,
            end_column=0,
            signature="class UniqueSymbol:",
            docstring="Test docstring",
        )
        saved_symbol = await symbol_adapter.save(symbol)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/symbols/{saved_symbol.id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == saved_symbol.id
        assert data["name"] == "UniqueSymbol"
        assert data["qualified_name"] == "src.main.UniqueSymbol"
        assert data["kind"] == "class"
        assert data["file_path"] == "src/main.py"
        assert data["signature"] == "class UniqueSymbol:"
        assert data["docstring"] == "Test docstring"

    async def test_get_symbol_not_found(self, test_app: FastAPI) -> None:
        """Test getting a non-existent symbol."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/symbols/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_get_symbol_references(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting references to a symbol."""
        from inxr2.adapters.persistence.repositories.reference_adapter import (
            PostgresReferenceRepository,
        )
        from inxr2.adapters.persistence.repositories.symbol_adapter import (
            PostgresSymbolRepository,
        )
        from inxr2.domain.entities import Reference, Symbol
        from inxr2.domain.value_objects import ReferenceType, SymbolKind

        # Arrange
        saved_repo, saved_commit, saved_file = await self._create_test_data(db_session)
        assert saved_repo.id is not None
        assert saved_commit.id is not None
        assert saved_file.id is not None

        symbol_adapter = PostgresSymbolRepository(db_session)
        symbol = Symbol(
            file_id=saved_file.id,
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            name="TargetSymbol",
            kind=SymbolKind.CLASS,
            start_line=1,
            start_column=0,
            end_line=10,
            end_column=0,
        )
        saved_symbol = await symbol_adapter.save(symbol)

        # Create references to this symbol
        reference_adapter = PostgresReferenceRepository(db_session)
        references = [
            Reference(
                source_file_id=saved_file.id,
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                source_line=15,
                source_column=4,
                source_end_column=16,
                reference_text="TargetSymbol",
                reference_type=ReferenceType.USAGE,
                target_symbol_id=saved_symbol.id,
            ),
            Reference(
                source_file_id=saved_file.id,
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                source_line=20,
                source_column=8,
                source_end_column=20,
                reference_text="TargetSymbol",
                reference_type=ReferenceType.CALL,
                target_symbol_id=saved_symbol.id,
            ),
        ]
        await reference_adapter.save_many(references)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/symbols/{saved_symbol.id}/references")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["symbol_name"] == "TargetSymbol"
        assert data["total"] == 2
        assert len(data["items"]) == 2

        # Verify reference details
        ref = data["items"][0]
        assert "source_line" in ref
        assert "source_column" in ref
        assert "reference_type" in ref
        assert ref["source_file_path"] == "src/main.py"

    async def test_get_symbol_references_not_found(self, test_app: FastAPI) -> None:
        """Test getting references for non-existent symbol."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/symbols/99999/references")

        assert response.status_code == 404

    async def test_get_symbols_by_name_multiple(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting all symbols with the same name (disambiguation)."""
        from inxr2.adapters.persistence.repositories.symbol_adapter import (
            PostgresSymbolRepository,
        )
        from inxr2.domain.entities import Symbol
        from inxr2.domain.value_objects import SymbolKind

        # Arrange - create multiple symbols with same name
        saved_repo, saved_commit, saved_file = await self._create_test_data(db_session)
        assert saved_repo.id is not None
        assert saved_commit.id is not None
        assert saved_file.id is not None

        # Create another file
        file_adapter = PostgresFileRepository(db_session)
        file2 = File(
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            path="src/other.py",
            content_hash="hash2",
            size_bytes=100,
            language="python",
        )
        saved_file2 = await file_adapter.save(file2)
        assert saved_file2.id is not None

        symbol_adapter = PostgresSymbolRepository(db_session)
        symbols = [
            Symbol(
                file_id=saved_file.id,
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                name="save",
                qualified_name="FileRepository.save",
                kind=SymbolKind.METHOD,
                start_line=10,
                start_column=4,
                end_line=20,
                end_column=0,
            ),
            Symbol(
                file_id=saved_file2.id,
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                name="save",
                qualified_name="CommitRepository.save",
                kind=SymbolKind.METHOD,
                start_line=15,
                start_column=4,
                end_line=25,
                end_column=0,
            ),
        ]
        await symbol_adapter.save_many(symbols)

        # Act - get all symbols named "save"
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/symbols/by-name/save?repository_id={saved_repo.id}"
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

        qualified_names = {s["qualified_name"] for s in data["items"]}
        assert "FileRepository.save" in qualified_names
        assert "CommitRepository.save" in qualified_names

    async def test_get_symbol_references_by_name(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting references by symbol name (for disambiguation)."""
        from inxr2.adapters.persistence.repositories.reference_adapter import (
            PostgresReferenceRepository,
        )
        from inxr2.adapters.persistence.repositories.symbol_adapter import (
            PostgresSymbolRepository,
        )
        from inxr2.domain.entities import Reference, Symbol
        from inxr2.domain.value_objects import ReferenceType, SymbolKind

        # Arrange
        saved_repo, saved_commit, saved_file = await self._create_test_data(db_session)
        assert saved_repo.id is not None
        assert saved_commit.id is not None
        assert saved_file.id is not None

        # Create symbol
        symbol_adapter = PostgresSymbolRepository(db_session)
        symbol = Symbol(
            file_id=saved_file.id,
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            name="save",
            qualified_name="Repository.save",
            kind=SymbolKind.METHOD,
            start_line=10,
            start_column=4,
            end_line=20,
            end_column=0,
        )
        saved_symbol = await symbol_adapter.save(symbol)
        assert saved_symbol.id is not None

        # Create multiple references with same text
        reference_adapter = PostgresReferenceRepository(db_session)
        references = [
            Reference(
                source_file_id=saved_file.id,
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                source_line=30,
                source_column=8,
                source_end_column=12,
                reference_text="save",
                reference_type=ReferenceType.CALL,
                target_symbol_id=saved_symbol.id,
            ),
            Reference(
                source_file_id=saved_file.id,
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                source_line=40,
                source_column=8,
                source_end_column=12,
                reference_text="save",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,  # Unresolved - different target
            ),
        ]
        await reference_adapter.save_many(references)

        # Act - get references by name (default behavior)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/symbols/{saved_symbol.id}/references")

        # Assert - should find both references (by name)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert all(r["reference_text"] == "save" for r in data["items"])


@pytest.mark.asyncio
class TestFilesAPI:
    """Tests for /api/files endpoints."""

    async def test_get_file_symbols(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting symbols for a specific file."""
        from inxr2.adapters.persistence.repositories.symbol_adapter import (
            PostgresSymbolRepository,
        )
        from inxr2.domain.entities import Symbol
        from inxr2.domain.value_objects import SymbolKind

        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="file-symbols-test",
            url="https://github.com/test/files.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("filesym"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit = await commit_adapter.save(commit)
        assert saved_commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        file = File(
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            path="src/module.py",
            content_hash="hash1",
            size_bytes=100,
            language="python",
        )
        saved_file = await file_adapter.save(file)
        assert saved_file.id is not None

        symbol_adapter = PostgresSymbolRepository(db_session)
        symbols = [
            Symbol(
                file_id=saved_file.id,
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                name="FileClass",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            ),
            Symbol(
                file_id=saved_file.id,
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                name="file_function",
                kind=SymbolKind.FUNCTION,
                start_line=12,
                start_column=0,
                end_line=20,
                end_column=0,
                signature="def file_function(x: int) -> str:",
            ),
        ]
        await symbol_adapter.save_many(symbols)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/files/{saved_file.id}/symbols")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["file_id"] == saved_file.id
        assert data["file_path"] == "src/module.py"
        assert data["total"] == 2
        assert len(data["symbols"]) == 2

        # Verify symbol details
        symbol_names = {s["name"] for s in data["symbols"]}
        assert "FileClass" in symbol_names
        assert "file_function" in symbol_names

    async def test_get_file_symbols_not_found(self, test_app: FastAPI) -> None:
        """Test getting symbols for non-existent file."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/files/99999/symbols")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_get_file_references(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting references from a specific file."""
        from inxr2.adapters.persistence.repositories.reference_adapter import (
            PostgresReferenceRepository,
        )
        from inxr2.adapters.persistence.repositories.symbol_adapter import (
            PostgresSymbolRepository,
        )
        from inxr2.domain.entities import Reference, Symbol
        from inxr2.domain.value_objects import ReferenceType, SymbolKind

        # Arrange - create repository, commit, file
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="file-refs-test",
            url="https://github.com/test/refs.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("fileref"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit = await commit_adapter.save(commit)
        assert saved_commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        file = File(
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            path="src/caller.py",
            content_hash="hash1",
            size_bytes=100,
            language="python",
        )
        saved_file = await file_adapter.save(file)
        assert saved_file.id is not None

        # Create a target symbol
        symbol_adapter = PostgresSymbolRepository(db_session)
        target_symbol = Symbol(
            file_id=saved_file.id,
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            name="target_function",
            kind=SymbolKind.FUNCTION,
            start_line=50,
            start_column=0,
            end_line=60,
            end_column=0,
        )
        saved_symbol = await symbol_adapter.save(target_symbol)

        # Create references from this file
        reference_adapter = PostgresReferenceRepository(db_session)
        references = [
            Reference(
                source_file_id=saved_file.id,
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                source_line=10,
                source_column=4,
                source_end_column=19,
                reference_text="target_function",
                reference_type=ReferenceType.CALL,
                target_symbol_id=saved_symbol.id,
            ),
            Reference(
                source_file_id=saved_file.id,
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                source_line=1,
                source_column=0,
                source_end_column=20,
                reference_text="from module import x",
                reference_type=ReferenceType.IMPORT,
                target_symbol_id=None,  # external import
            ),
            Reference(
                source_file_id=saved_file.id,
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                source_line=25,
                source_column=8,
                source_end_column=23,
                reference_text="target_function",
                reference_type=ReferenceType.USAGE,
                target_symbol_id=saved_symbol.id,
            ),
        ]
        await reference_adapter.save_many(references)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/files/{saved_file.id}/references")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["file_id"] == saved_file.id
        assert data["file_path"] == "src/caller.py"
        assert data["total"] == 3
        assert len(data["references"]) == 3

        # Verify reference details
        ref_types = {r["reference_type"] for r in data["references"]}
        assert "call" in ref_types
        assert "import" in ref_types
        assert "usage" in ref_types

        # Verify reference structure
        ref = data["references"][0]
        assert "id" in ref
        assert "reference_text" in ref
        assert "reference_type" in ref
        assert "source_line" in ref
        assert "source_column" in ref
        assert "target_symbol_id" in ref

    async def test_get_file_references_not_found(self, test_app: FastAPI) -> None:
        """Test getting references for non-existent file."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/files/99999/references")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_get_file_symbols_by_path(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting symbols for a file by repository name and path."""
        from inxr2.adapters.persistence.repositories.symbol_adapter import (
            PostgresSymbolRepository,
        )
        from inxr2.domain.entities import Symbol
        from inxr2.domain.value_objects import SymbolKind

        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="symbols-by-path-repo",
            url="https://github.com/test/symbolspath.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("sympath"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit = await commit_adapter.save(commit)
        assert saved_commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        file = File(
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            path="src/utils/helper.py",
            content_hash="hash1",
            size_bytes=100,
            language="python",
        )
        saved_file = await file_adapter.save(file)
        assert saved_file.id is not None

        symbol_adapter = PostgresSymbolRepository(db_session)
        symbol = Symbol(
            file_id=saved_file.id,
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            name="helper_function",
            kind=SymbolKind.FUNCTION,
            start_line=1,
            start_column=0,
            end_line=10,
            end_column=0,
        )
        await symbol_adapter.save(symbol)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path/symbols",
                params={"repo": "symbols-by-path-repo", "path": "src/utils/helper.py"},
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["file_path"] == "src/utils/helper.py"
        assert data["total"] == 1
        assert data["symbols"][0]["name"] == "helper_function"

    async def test_get_file_symbols_by_path_not_found(self, test_app: FastAPI) -> None:
        """Test getting symbols by path for non-existent repo/file."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path/symbols",
                params={"repo": "nonexistent", "path": "does/not/exist.py"},
            )

        assert response.status_code == 404

    async def test_get_file_references_by_path(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting references for a file by repository name and path."""
        from inxr2.adapters.persistence.repositories.reference_adapter import (
            PostgresReferenceRepository,
        )
        from inxr2.domain.entities import Reference
        from inxr2.domain.value_objects import ReferenceType

        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="refs-by-path-repo",
            url="https://github.com/test/refspath.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("refpath"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit = await commit_adapter.save(commit)
        assert saved_commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        file = File(
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            path="src/main.py",
            content_hash="hash1",
            size_bytes=100,
            language="python",
        )
        saved_file = await file_adapter.save(file)
        assert saved_file.id is not None

        reference_adapter = PostgresReferenceRepository(db_session)
        reference = Reference(
            source_file_id=saved_file.id,
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            source_line=5,
            source_column=0,
            source_end_column=10,
            reference_text="import os",
            reference_type=ReferenceType.IMPORT,
            target_symbol_id=None,
        )
        await reference_adapter.save(reference)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path/references",
                params={"repo": "refs-by-path-repo", "path": "src/main.py"},
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["file_path"] == "src/main.py"
        assert data["total"] == 1
        assert data["references"][0]["reference_type"] == "import"

    async def test_get_file_references_by_path_not_found(
        self, test_app: FastAPI
    ) -> None:
        """Test getting references by path for non-existent repo/file."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path/references",
                params={"repo": "nonexistent", "path": "does/not/exist.py"},
            )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestPathValidation:
    """Tests for path and repo name validation in by-path endpoints."""

    async def test_path_traversal_rejected(self, test_app: FastAPI) -> None:
        """Test that path traversal attempts are rejected."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path",
                params={"repo": "test-repo", "path": "../../../etc/passwd"},
            )

        assert response.status_code == 400
        assert "Path traversal" in response.json()["detail"]

    async def test_absolute_path_rejected(self, test_app: FastAPI) -> None:
        """Test that absolute paths are rejected."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path",
                params={"repo": "test-repo", "path": "/etc/passwd"},
            )

        assert response.status_code == 400
        assert "Absolute paths" in response.json()["detail"]

    async def test_empty_path_rejected(self, test_app: FastAPI) -> None:
        """Test that empty paths are rejected."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path",
                params={"repo": "test-repo", "path": "   "},
            )

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    async def test_invalid_repo_name_rejected(self, test_app: FastAPI) -> None:
        """Test that invalid repo names are rejected."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path",
                params={"repo": "test/../repo", "path": "src/main.py"},
            )

        assert response.status_code == 400
        assert "invalid characters" in response.json()["detail"].lower()

    async def test_valid_path_with_subdirs_accepted(self, test_app: FastAPI) -> None:
        """Test that valid paths with subdirectories work (return 404 for not found)."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path",
                params={"repo": "valid-repo", "path": "src/components/file.tsx"},
            )

        # Should get 404 (not found) not 400 (validation error)
        assert response.status_code == 404

    async def test_path_traversal_in_middle_rejected(self, test_app: FastAPI) -> None:
        """Test that path traversal in the middle of path is rejected."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path/symbols",
                params={"repo": "test-repo", "path": "src/../../../etc/passwd"},
            )

        assert response.status_code == 400
        assert "Path traversal" in response.json()["detail"]

    async def test_repo_name_dot_rejected(self, test_app: FastAPI) -> None:
        """Test that '.' as repo name is rejected."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path",
                params={"repo": ".", "path": "file.txt"},
            )

        assert response.status_code == 400
        assert "start/end with a dot" in response.json()["detail"]

    async def test_repo_name_dotdot_rejected(self, test_app: FastAPI) -> None:
        """Test that '..' as repo name is rejected."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path",
                params={"repo": "..", "path": "file.txt"},
            )

        assert response.status_code == 400
        assert "start/end with a dot" in response.json()["detail"]

    async def test_repo_name_starting_with_dot_rejected(
        self, test_app: FastAPI
    ) -> None:
        """Test that repo names starting with dot are rejected."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path",
                params={"repo": ".hidden", "path": "file.txt"},
            )

        assert response.status_code == 400
        assert "start/end with a dot" in response.json()["detail"]

    async def test_repo_name_ending_with_dot_rejected(self, test_app: FastAPI) -> None:
        """Test that repo names ending with dot are rejected."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path",
                params={"repo": "repo.", "path": "file.txt"},
            )

        assert response.status_code == 400
        assert "start/end with a dot" in response.json()["detail"]

    async def test_repo_name_with_middle_dot_accepted(self, test_app: FastAPI) -> None:
        """Test that repo names with dots in the middle are accepted."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path",
                params={"repo": "my.repo.name", "path": "file.txt"},
            )

        # Should get 404 (not found) not 400 (validation error)
        assert response.status_code == 404


@pytest.mark.asyncio
class TestCommitsAPI:
    """Tests for /api/commits endpoints (time travel)."""

    async def test_list_commits_empty(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test listing commits for a repository with no commits."""
        # Arrange - create repository without commits
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="commits-empty-repo",
            url="https://github.com/test/empty.git",
        )
        await repo_adapter.save(repository)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/commits",
                params={"repo": "commits-empty-repo"},
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["commits"] == []
        assert data["total"] == 0

    async def test_list_commits_with_data(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Test listing commits for a repository with commits."""
        # Arrange — create a real git repo so list_commits can read from git
        repo_path = tmp_path / "commits-data-repo"
        git_hashes = _create_git_repo_with_commits(
            repo_path,
            [("file1.txt", "First commit"), ("file2.txt", "Second commit")],
        )

        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="commits-data-repo",
            url=str(repo_path),
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        # Index one commit in DB so we can verify is_indexed
        commit_adapter = PostgresCommitRepository(db_session)
        indexed_commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash(git_hashes[0]),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        await commit_adapter.save(indexed_commit)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/commits",
                params={"repo": "commits-data-repo"},
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["commits"]) == 2

        # Verify commit structure (newest first)
        commit = data["commits"][0]
        assert "hash" in commit
        assert "short_hash" in commit
        assert "message" in commit
        assert "author_name" in commit
        assert "commit_date" in commit
        assert "is_indexed" in commit

        # Verify is_indexed: first git commit is indexed, second is not
        by_hash = {c["hash"]: c for c in data["commits"]}
        assert by_hash[git_hashes[0]]["is_indexed"] is True
        assert by_hash[git_hashes[1]]["is_indexed"] is False

    async def test_list_commits_with_branch_filter(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Test filtering commits by branch."""
        # Arrange — create a real git repo with commits on main branch
        repo_path = tmp_path / "commits-branch-repo"
        _create_git_repo_with_commits(
            repo_path,
            [("file1.txt", "Main commit 1"), ("file2.txt", "Main commit 2")],
            branch="main",
        )

        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="commits-branch-repo",
            url=str(repo_path),
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        # Act — filter by main branch
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/commits",
                params={"repo": "commits-branch-repo", "branch": "main"},
            )

        # Assert — should see both commits from main
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert "message" in data["commits"][0]
        assert "is_indexed" in data["commits"][0]

    async def test_list_commits_repo_not_found(self, test_app: FastAPI) -> None:
        """Test listing commits for non-existent repository."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/commits",
                params={"repo": "nonexistent-repo"},
            )

        assert response.status_code == 404

    async def test_get_commit_by_id(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting a specific commit by ID."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="commit-detail-repo",
            url="https://github.com/test/detail.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("detail1"),
            author_date=datetime(2025, 1, 1, 10, 30),
            commit_date=datetime(2025, 1, 1, 12, 0),
        )
        saved_commit = await commit_adapter.save(commit)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/commits/{saved_commit.id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == saved_commit.id
        assert data["hash"] == commit.commit_hash.value
        assert data["short_hash"] == "detail1"
        # Author/message/parent_hashes are hydrated from git - empty in test since repo doesn't exist
        assert "message" in data
        assert "author_name" in data
        assert "committer_name" in data
        assert "parent_hashes" in data

    async def test_get_commit_not_found(self, test_app: FastAPI) -> None:
        """Test getting a non-existent commit."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/commits/99999")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestFileHistoryAPI:
    """Tests for /api/files/history endpoint (time travel)."""

    async def test_get_file_history(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting file version history."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="file-history-repo",
            url="https://github.com/test/history.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit1 = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("hist1"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        commit2 = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("hist2"),
            author_date=datetime(2025, 1, 2),
            commit_date=datetime(2025, 1, 2),
        )
        saved_commit1 = await commit_adapter.save(commit1)
        assert saved_commit1.id is not None
        saved_commit2 = await commit_adapter.save(commit2)
        assert saved_commit2.id is not None

        file_adapter = PostgresFileRepository(db_session)
        files = [
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit1.id,
                path="src/main.py",
                content_hash="hash_v1",
                size_bytes=100,
                language="python",
            ),
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit2.id,
                path="src/main.py",
                content_hash="hash_v2",  # Different hash = file changed
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
                "/api/files/history",
                params={"repo": "file-history-repo", "path": "src/main.py"},
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "src/main.py"
        assert data["repository_name"] == "file-history-repo"
        assert data["total"] == 2
        assert len(data["versions"]) == 2

        # Verify version structure
        version = data["versions"][0]
        assert "commit_id" in version
        assert "commit_hash" in version
        assert "short_hash" in version
        assert "commit_date" in version
        assert "message" in version
        assert "content_hash" in version

        # Versions should have different content hashes
        content_hashes = {v["content_hash"] for v in data["versions"]}
        assert len(content_hashes) == 2

    async def test_get_file_history_not_found(self, test_app: FastAPI) -> None:
        """Test file history for non-existent file."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/history",
                params={"repo": "nonexistent", "path": "not/found.py"},
            )

        assert response.status_code == 404

    async def test_get_file_history_repo_not_found(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test file history when repository doesn't exist."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/history",
                params={"repo": "nonexistent-repo", "path": "src/main.py"},
            )

        assert response.status_code == 404


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

        file_adapter = PostgresFileRepository(db_session)
        files = [
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                path="src/utils.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            ),
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                path="src/main.py",
                content_hash="hash2",
                size_bytes=150,
                language="python",
            ),
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                path="tests/test_utils.py",
                content_hash="hash3",
                size_bytes=200,
                language="python",
            ),
        ]
        await file_adapter.save_many(files)

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
        await file_adapter.save(
            File(
                repository_id=saved_repo1.id,
                commit_id=saved_commit1.id,
                path="src/config.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            )
        )
        await file_adapter.save(
            File(
                repository_id=saved_repo2.id,
                commit_id=saved_commit2.id,
                path="src/config.py",
                content_hash="hash2",
                size_bytes=100,
                language="python",
            )
        )

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

        file_adapter = PostgresFileRepository(db_session)
        await file_adapter.save(
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                path="src/utils.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            )
        )
        await file_adapter.save(
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                path="src/utils.ts",
                content_hash="hash2",
                size_bytes=100,
                language="typescript",
            )
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

        file_adapter = PostgresFileRepository(db_session)
        await file_adapter.save(
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                path="src/module/helper.py",
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
                commit_id=saved_commit.id,
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
