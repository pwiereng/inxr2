"""Integration tests for /api/symbols endpoints."""

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

        # Link commit to default branch (required for scope=latest global search)
        await commit_adapter.link_commit_to_branch(
            saved_repo.id, saved_commit.id, "main"
        )

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

        # Link file to commit via commit_files junction
        await file_adapter.link_file_to_commit(saved_file.id, saved_commit.id)

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
            response = await client.get("/api/symbols?q=my&case_sensitive=false")

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

    async def test_search_symbols_top_level_only(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test searching symbols with top_level_only filter."""
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

        # Create a top-level class
        class_symbols = await symbol_adapter.save_many(
            [
                Symbol(
                    file_id=saved_file.id,
                    repository_id=saved_repo.id,
                    name="TopClass",
                    kind=SymbolKind.CLASS,
                    start_line=1,
                    start_column=0,
                    end_line=30,
                    end_column=0,
                ),
                Symbol(
                    file_id=saved_file.id,
                    repository_id=saved_repo.id,
                    name="top_func",
                    kind=SymbolKind.FUNCTION,
                    start_line=40,
                    start_column=0,
                    end_line=50,
                    end_column=0,
                ),
            ]
        )
        parent_id = class_symbols[0].id
        assert parent_id is not None

        # Create a nested method inside the class
        await symbol_adapter.save_many(
            [
                Symbol(
                    file_id=saved_file.id,
                    repository_id=saved_repo.id,
                    name="nested_method",
                    kind=SymbolKind.METHOD,
                    start_line=5,
                    start_column=4,
                    end_line=15,
                    end_column=0,
                    parent_symbol_id=parent_id,
                ),
            ]
        )

        # Act - search with top_level_only=true
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/symbols?q=&top_level_only=true&repository_id={saved_repo.id}"
            )

        # Assert - nested_method should be excluded
        assert response.status_code == 200
        data = response.json()
        names = {s["name"] for s in data["items"]}
        assert "TopClass" in names
        assert "top_func" in names
        assert "nested_method" not in names

        # Act - search without top_level_only (default=false)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/symbols?q=&repository_id={saved_repo.id}"
            )

        # Assert - all symbols should be returned
        assert response.status_code == 200
        data = response.json()
        names = {s["name"] for s in data["items"]}
        assert "TopClass" in names
        assert "top_func" in names
        assert "nested_method" in names

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
            path="src/other.py",
            content_hash="hash2",
            size_bytes=100,
            language="python",
        )
        saved_file2 = await file_adapter.save(file2)
        assert saved_file2.id is not None
        await file_adapter.link_file_to_commit(saved_file2.id, saved_commit.id)

        symbol_adapter = PostgresSymbolRepository(db_session)
        symbols = [
            Symbol(
                file_id=saved_file.id,
                repository_id=saved_repo.id,
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
