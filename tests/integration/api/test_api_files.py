"""Integration tests for /api/files and /api/renames endpoints."""

from datetime import datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from inxr2.adapters.persistence.repositories.file_adapter import PostgresFileRepository
from inxr2.adapters.persistence.repositories.file_rename_adapter import (
    PostgresFileRenameRepository,
)
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from inxr2.domain.entities import Commit, File, FileRename, Repository
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
            path="src/utils/helper.py",
            content_hash="hash1",
            size_bytes=100,
            language="python",
        )
        saved_file = await file_adapter.save(file)
        assert saved_file.id is not None

        # Link file to commit and commit to branch for resolve_file
        await file_adapter.link_file_to_commit(saved_file.id, saved_commit.id)
        await commit_adapter.link_commit_to_branch(
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            branch="main",
        )

        symbol_adapter = PostgresSymbolRepository(db_session)
        symbol = Symbol(
            file_id=saved_file.id,
            repository_id=saved_repo.id,
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
            path="src/main.py",
            content_hash="hash1",
            size_bytes=100,
            language="python",
        )
        saved_file = await file_adapter.save(file)
        assert saved_file.id is not None

        # Link file to commit and commit to branch for resolve_file
        await file_adapter.link_file_to_commit(saved_file.id, saved_commit.id)
        await commit_adapter.link_commit_to_branch(
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            branch="main",
        )

        reference_adapter = PostgresReferenceRepository(db_session)
        reference = Reference(
            source_file_id=saved_file.id,
            repository_id=saved_repo.id,
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
        assert "must contain only" in response.json()["detail"].lower()

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
        assert "cannot start or end with a dot" in response.json()["detail"]

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
        assert "cannot start or end with a dot" in response.json()["detail"]

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
        assert "cannot start or end with a dot" in response.json()["detail"]

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
        assert "cannot start or end with a dot" in response.json()["detail"]

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
                path="src/main.py",
                content_hash="hash_v1",
                size_bytes=100,
                language="python",
            ),
            File(
                repository_id=saved_repo.id,
                path="src/main.py",
                content_hash="hash_v2",  # Different hash = file changed
                size_bytes=150,
                language="python",
            ),
        ]
        saved_files = await file_adapter.save_many(files)
        assert saved_files[0].id is not None
        assert saved_files[1].id is not None
        await file_adapter.link_file_to_commit(saved_files[0].id, saved_commit1.id)
        await file_adapter.link_file_to_commit(saved_files[1].id, saved_commit2.id)

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
class TestRenamesResolvePathAPI:
    """Tests for GET /api/renames/resolve-path endpoint."""

    async def _setup_repo_and_commits(
        self,
        db_session: AsyncSession,
        repo_name: str,
    ) -> tuple[Repository, Commit, Commit, Commit]:
        """Create repo and three commits with increasing dates."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            Repository(name=repo_name, url=f"https://github.com/test/{repo_name}.git")
        )
        assert repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit_a = await commit_adapter.save(
            Commit(
                repository_id=repo.id,
                commit_hash=make_test_commit_hash(f"{repo_name}-a"),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        commit_b = await commit_adapter.save(
            Commit(
                repository_id=repo.id,
                commit_hash=make_test_commit_hash(f"{repo_name}-b"),
                author_date=datetime(2025, 1, 2),
                commit_date=datetime(2025, 1, 2),
            )
        )
        commit_c = await commit_adapter.save(
            Commit(
                repository_id=repo.id,
                commit_hash=make_test_commit_hash(f"{repo_name}-c"),
                author_date=datetime(2025, 1, 3),
                commit_date=datetime(2025, 1, 3),
            )
        )
        return repo, commit_a, commit_b, commit_c

    async def test_file_found_at_commit_returns_found_true(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """File exists at path+commit → found: True."""
        repo, commit_a, _, _ = await self._setup_repo_and_commits(
            db_session, "resolve-found"
        )
        assert repo.id is not None
        assert commit_a.id is not None

        file_adapter = PostgresFileRepository(db_session)
        file = await file_adapter.save(
            File(
                repository_id=repo.id,
                path="src/foo.py",
                content_hash="a" * 40,
                size_bytes=100,
                language="python",
                line_count=10,
            )
        )
        assert file.id is not None
        await file_adapter.link_files_to_commit([file.id], commit_a.id)

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/renames/resolve-path",
                params={
                    "repo": repo.name,
                    "path": "src/foo.py",
                    "commit": commit_a.commit_hash.value,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is True
        assert data["resolved_path"] is None

    async def test_renamed_from_backward_in_time(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """File at commit A browsed under its future name (new.py) → renamed_from old.py."""
        repo, commit_a, commit_b, _ = await self._setup_repo_and_commits(
            db_session, "resolve-backward"
        )
        assert repo.id is not None
        assert commit_a.id is not None
        assert commit_b.id is not None

        # old.py exists at commit A (before the rename at commit B)
        file_adapter = PostgresFileRepository(db_session)
        old_file = await file_adapter.save(
            File(
                repository_id=repo.id,
                path="src/old.py",
                content_hash="b" * 40,
                size_bytes=200,
                language="python",
                line_count=20,
            )
        )
        assert old_file.id is not None
        await file_adapter.link_files_to_commit([old_file.id], commit_a.id)

        # Rename record: old.py → new.py at commit B (date: 2025-01-02)
        rename_adapter = PostgresFileRenameRepository(db_session)
        await rename_adapter.save_renames(
            [
                FileRename(
                    repository_id=repo.id,
                    commit_id=commit_b.id,
                    old_path="src/old.py",
                    new_path="src/new.py",
                    similarity=100,
                )
            ]
        )

        # Browse new.py at commit A (before rename)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/renames/resolve-path",
                params={
                    "repo": repo.name,
                    "path": "src/new.py",
                    "commit": commit_a.commit_hash.value,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is False
        assert data["resolved_path"] == "src/old.py"
        assert data["renamed_from"] == "src/old.py"
        assert data["renamed_to"] is None
        assert data["rename_commit_hash"] is not None

    async def test_renamed_to_forward_in_time(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """File at commit C browsed under its old name (old.py) → renamed_to new.py."""
        repo, _, commit_b, commit_c = await self._setup_repo_and_commits(
            db_session, "resolve-forward"
        )
        assert repo.id is not None
        assert commit_b.id is not None
        assert commit_c.id is not None

        # new.py exists at commit C (after the rename at commit B)
        file_adapter = PostgresFileRepository(db_session)
        new_file = await file_adapter.save(
            File(
                repository_id=repo.id,
                path="src/new.py",
                content_hash="c" * 40,
                size_bytes=300,
                language="python",
                line_count=30,
            )
        )
        assert new_file.id is not None
        await file_adapter.link_files_to_commit([new_file.id], commit_c.id)

        # Rename record: old.py → new.py at commit B (date: 2025-01-02)
        rename_adapter = PostgresFileRenameRepository(db_session)
        await rename_adapter.save_renames(
            [
                FileRename(
                    repository_id=repo.id,
                    commit_id=commit_b.id,
                    old_path="src/old.py",
                    new_path="src/new.py",
                    similarity=100,
                )
            ]
        )

        # Browse old.py at commit C (after rename)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/renames/resolve-path",
                params={
                    "repo": repo.name,
                    "path": "src/old.py",
                    "commit": commit_c.commit_hash.value,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is False
        assert data["resolved_path"] == "src/new.py"
        assert data["renamed_to"] == "src/new.py"
        assert data["renamed_from"] is None
        assert data["rename_commit_hash"] is not None

    async def test_no_rename_returns_not_found(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """File doesn't exist and no rename record → found: False, resolved_path: None."""
        repo, commit_a, _, _ = await self._setup_repo_and_commits(
            db_session, "resolve-no-rename"
        )
        assert repo.id is not None

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/renames/resolve-path",
                params={
                    "repo": repo.name,
                    "path": "src/ghost.py",
                    "commit": commit_a.commit_hash.value,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is False
        assert data["resolved_path"] is None

    async def test_multi_hop_rename_chain(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """A→B→C renames: browsing A at commit after both renames resolves to C."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            Repository(
                name="resolve-multihop",
                url="https://github.com/test/resolve-multihop.git",
            )
        )
        assert repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit_initial = await commit_adapter.save(
            Commit(
                repository_id=repo.id,
                commit_hash=make_test_commit_hash("multihop-init"),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        commit_rename1 = await commit_adapter.save(
            Commit(
                repository_id=repo.id,
                commit_hash=make_test_commit_hash("multihop-r1"),
                author_date=datetime(2025, 1, 2),
                commit_date=datetime(2025, 1, 2),
            )
        )
        commit_rename2 = await commit_adapter.save(
            Commit(
                repository_id=repo.id,
                commit_hash=make_test_commit_hash("multihop-r2"),
                author_date=datetime(2025, 1, 3),
                commit_date=datetime(2025, 1, 3),
            )
        )
        commit_final = await commit_adapter.save(
            Commit(
                repository_id=repo.id,
                commit_hash=make_test_commit_hash("multihop-fin"),
                author_date=datetime(2025, 1, 4),
                commit_date=datetime(2025, 1, 4),
            )
        )
        assert commit_initial.id is not None
        assert commit_rename1.id is not None
        assert commit_rename2.id is not None
        assert commit_final.id is not None

        # c.py exists at commit_final (after both renames)
        file_adapter = PostgresFileRepository(db_session)
        c_file = await file_adapter.save(
            File(
                repository_id=repo.id,
                path="src/c.py",
                content_hash="d" * 40,
                size_bytes=100,
                language="python",
                line_count=10,
            )
        )
        assert c_file.id is not None
        await file_adapter.link_files_to_commit([c_file.id], commit_final.id)

        # a.py existed at commit_initial
        a_file = await file_adapter.save(
            File(
                repository_id=repo.id,
                path="src/a.py",
                content_hash="e" * 40,
                size_bytes=100,
                language="python",
                line_count=10,
            )
        )
        assert a_file.id is not None
        await file_adapter.link_files_to_commit([a_file.id], commit_initial.id)

        # Renames: a.py → b.py at commit_rename1, b.py → c.py at commit_rename2
        rename_adapter = PostgresFileRenameRepository(db_session)
        await rename_adapter.save_renames(
            [
                FileRename(
                    repository_id=repo.id,
                    commit_id=commit_rename1.id,
                    old_path="src/a.py",
                    new_path="src/b.py",
                    similarity=95,
                ),
                FileRename(
                    repository_id=repo.id,
                    commit_id=commit_rename2.id,
                    old_path="src/b.py",
                    new_path="src/c.py",
                    similarity=95,
                ),
            ]
        )

        # Browse src/a.py at commit_final → should follow a→b→c, resolve to c.py
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/renames/resolve-path",
                params={
                    "repo": repo.name,
                    "path": "src/a.py",
                    "commit": commit_final.commit_hash.value,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is False
        assert data["resolved_path"] == "src/c.py"
        assert data["renamed_to"] == "src/b.py"  # first hop direction
        assert data["renamed_from"] is None

    async def test_repo_not_found_returns_404(self, test_app: FastAPI) -> None:
        """Non-existent repo → 404."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/renames/resolve-path",
                params={
                    "repo": "nonexistent-repo",
                    "path": "src/foo.py",
                    "commit": "a" * 40,
                },
            )
        assert response.status_code == 404

    async def test_rename_resolved_regardless_of_commit_timestamp_order(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Regression: rename resolved correctly even when timestamps are misleading.

        Simulates a non-linear history (diverging branches) where the rename
        commit has an earlier clock time than the target commit, yet the target
        commit is genealogically before the rename.  The old date-based logic
        compared timestamps and failed to find the rename in this case.
        The existence-check approach is immune to this: it simply checks whether
        the candidate path exists at the target commit, regardless of dates.
        """
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            Repository(
                name="resolve-nonlinear",
                url="https://github.com/test/resolve-nonlinear.git",
            )
        )
        assert repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        # target commit has a LATER timestamp than the rename commit —
        # simulating a diverging branch where clocks don't reflect ancestry.
        commit_target = await commit_adapter.save(
            Commit(
                repository_id=repo.id,
                commit_hash=make_test_commit_hash("nonlinear-target"),
                author_date=datetime(2025, 6, 15),  # later clock time
                commit_date=datetime(2025, 6, 15),
            )
        )
        commit_rename = await commit_adapter.save(
            Commit(
                repository_id=repo.id,
                commit_hash=make_test_commit_hash("nonlinear-rename"),
                author_date=datetime(
                    2025, 1, 1
                ),  # earlier clock time, but genealogically after
                commit_date=datetime(2025, 1, 1),
            )
        )
        assert commit_target.id is not None
        assert commit_rename.id is not None

        # old.py exists at commit_target (genealogically before the rename)
        file_adapter = PostgresFileRepository(db_session)
        old_file = await file_adapter.save(
            File(
                repository_id=repo.id,
                path="src/old.py",
                content_hash="f" * 40,
                size_bytes=100,
                language="python",
                line_count=10,
            )
        )
        assert old_file.id is not None
        await file_adapter.link_files_to_commit([old_file.id], commit_target.id)

        # Rename: old.py → new.py at commit_rename
        rename_adapter = PostgresFileRenameRepository(db_session)
        await rename_adapter.save_renames(
            [
                FileRename(
                    repository_id=repo.id,
                    commit_id=commit_rename.id,
                    old_path="src/old.py",
                    new_path="src/new.py",
                    similarity=100,
                )
            ]
        )

        # Browse new.py at commit_target — rename commit is older by clock but
        # genealogically in the future, so old.py is the correct resolution.
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/renames/resolve-path",
                params={
                    "repo": repo.name,
                    "path": "src/new.py",
                    "commit": commit_target.commit_hash.value,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is False
        assert data["resolved_path"] == "src/old.py"
        assert data["renamed_from"] == "src/old.py"

    async def test_commit_not_found_returns_404(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Existing repo but unknown commit hash → 404."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            Repository(
                name="resolve-commit-404",
                url="https://github.com/test/resolve-commit-404.git",
            )
        )

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/renames/resolve-path",
                params={
                    "repo": repo.name,
                    "path": "src/foo.py",
                    "commit": "f" * 40,
                },
            )
        assert response.status_code == 404
