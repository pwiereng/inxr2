"""Branch-coverage tests for /api/repositories error and result-type paths."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from inxr2.adapters.api.routes import repositories
from inxr2.application.use_cases.symbols.get_symbol_tree import (
    GetSymbolTreeFilesResponse,
    GetSymbolTreeSymbolsResponse,
)
from inxr2.infrastructure.dependencies import (
    get_repository_branches_use_case,
    get_symbol_tree_use_case,
)


class _RaisingUseCase:
    def __init__(self, error: Exception) -> None:
        self._error = error

    async def execute(self, request: object) -> object:
        raise self._error


class _ReturningUseCase:
    def __init__(self, value: object) -> None:
        self._value = value

    async def execute(self, request: object) -> object:
        return self._value


def _app_branches(use_case: object) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_repository_branches_use_case] = lambda: use_case
    app.include_router(repositories.router, prefix="/api")
    return app


def _app_tree(use_case: object) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_symbol_tree_use_case] = lambda: use_case
    app.include_router(repositories.router, prefix="/api")
    return app


@pytest.mark.asyncio
class TestRepositoryBranchesErrors:
    async def test_path_not_found_returns_500(self) -> None:
        app = _app_branches(_RaisingUseCase(ValueError("Repository path not found")))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/repositories/by-name/demo/branches")
        assert response.status_code == 500
        assert "path not found" in response.json()["detail"].lower()

    async def test_other_value_error_returns_400(self) -> None:
        app = _app_branches(_RaisingUseCase(ValueError("not a git repository")))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/repositories/by-name/demo/branches")
        assert response.status_code == 400
        assert "not a git repository" in response.json()["detail"]


@pytest.mark.asyncio
class TestSymbolTree:
    async def test_files_tier_response(self) -> None:
        app = _app_tree(
            _ReturningUseCase(GetSymbolTreeFilesResponse(files=[], repository_id=3))
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/repositories/by-name/demo/symbol-tree")
        assert response.status_code == 200
        data = response.json()
        assert data["repository_id"] == 3
        assert data["files"] == []

    async def test_symbols_tier_response(self) -> None:
        app = _app_tree(
            _ReturningUseCase(GetSymbolTreeSymbolsResponse(symbols=[], repository_id=4))
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/repositories/by-name/demo/symbol-tree",
                params={"file_id": 1},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["repository_id"] == 4
        assert data["symbols"] == []

    async def test_value_error_returns_404(self) -> None:
        app = _app_tree(_RaisingUseCase(ValueError("Repository 'demo' not found")))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/repositories/by-name/demo/symbol-tree")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
