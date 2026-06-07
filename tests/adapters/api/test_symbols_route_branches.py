"""Branch-coverage tests for /api/symbols error and lookup paths.

Uses a minimal FastAPI app with dependency overrides (no database) so the
handler branches are exercised directly via fakes.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from inxr2.adapters.api.routes import symbols
from inxr2.application.use_cases.symbols.search_symbols import SearchSymbolsResponse
from inxr2.domain.entities import File, Symbol
from inxr2.domain.value_objects import SymbolKind
from inxr2.infrastructure.dependencies import (
    get_file_adapter,
    get_search_symbols_use_case,
    get_symbol_adapter,
)
from tests.fixtures.test_doubles import (
    InMemoryFileRepository,
    InMemorySymbolRepository,
)


class _StubSearchUseCase:
    """Minimal search-symbols use case stub for guard-clause tests."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error

    async def execute(self, request: object) -> SearchSymbolsResponse:
        if self._error is not None:
            raise self._error
        return SearchSymbolsResponse(symbols=[], total=0, limit=50, offset=0)


def _app_with_search(use_case: _StubSearchUseCase) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_search_symbols_use_case] = lambda: use_case
    app.include_router(symbols.router, prefix="/api")
    return app


def _app_with_symbol_lookup(
    symbol_repo: InMemorySymbolRepository, file_repo: InMemoryFileRepository
) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_symbol_adapter] = lambda: symbol_repo
    app.dependency_overrides[get_file_adapter] = lambda: file_repo
    app.include_router(symbols.router, prefix="/api")
    return app


@pytest.mark.asyncio
class TestSearchGuards:
    async def test_search_commit_without_repository_returns_400(self) -> None:
        app = _app_with_search(_StubSearchUseCase())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/symbols", params={"commit": "a" * 40})
        assert response.status_code == 400
        assert "repository_id is required" in response.json()["detail"]

    async def test_search_value_error_returns_422(self) -> None:
        app = _app_with_search(_StubSearchUseCase(error=ValueError("bad regex")))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/symbols", params={"q": "x", "mode": "regex"}
            )
        assert response.status_code == 422
        assert "bad regex" in response.json()["detail"]

    async def test_by_name_commit_without_repository_returns_400(self) -> None:
        app = _app_with_search(_StubSearchUseCase())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/symbols/by-name/foo", params={"commit": "a" * 40}
            )
        assert response.status_code == 400
        assert "repository_id is required" in response.json()["detail"]


@pytest.mark.asyncio
class TestGetSymbol:
    async def test_not_found_returns_404(self) -> None:
        app = _app_with_symbol_lookup(
            InMemorySymbolRepository(), InMemoryFileRepository()
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/symbols/4242")
        assert response.status_code == 404
        assert "Symbol not found" in response.json()["detail"]

    async def test_file_id_zero_skips_file_lookup(self) -> None:
        symbol_repo = InMemorySymbolRepository()
        # file_id=0 is falsy → handler skips the file lookup entirely.
        await symbol_repo.save(
            Symbol(
                id=7,
                file_id=0,
                repository_id=1,
                name="orphan",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=2,
                end_column=0,
            )
        )
        app = _app_with_symbol_lookup(symbol_repo, InMemoryFileRepository())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/symbols/7")
        assert response.status_code == 200
        assert response.json()["file_path"] is None

    async def test_missing_file_leaves_path_none(self) -> None:
        symbol_repo = InMemorySymbolRepository()
        # file_id points at a file the file repo does not have.
        await symbol_repo.save(
            Symbol(
                id=9,
                file_id=999,
                repository_id=1,
                name="dangling",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=2,
                end_column=0,
            )
        )
        app = _app_with_symbol_lookup(symbol_repo, InMemoryFileRepository())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/symbols/9")
        assert response.status_code == 200
        assert response.json()["file_path"] is None

    async def test_found_with_file_path(self) -> None:
        symbol_repo = InMemorySymbolRepository()
        file_repo = InMemoryFileRepository()
        saved_file = await file_repo.save(
            File(
                repository_id=1,
                path="src/found.py",
                content_hash="c" * 40,
                size_bytes=10,
                language="python",
            )
        )
        assert saved_file.id is not None
        await symbol_repo.save(
            Symbol(
                id=11,
                file_id=saved_file.id,
                repository_id=1,
                name="present",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=2,
                end_column=0,
            )
        )
        app = _app_with_symbol_lookup(symbol_repo, file_repo)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/symbols/11")
        assert response.status_code == 200
        assert response.json()["file_path"] == "src/found.py"
