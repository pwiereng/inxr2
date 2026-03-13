"""Tests for centralized API exception handlers."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from inxr2.adapters.api.exception_handlers import register_exception_handlers
from inxr2.application.use_cases.files import (
    BinaryFileError,
    RepositoryPathNotFoundError,
)
from inxr2.domain.exceptions import (
    CommitNotFound,
    FileNotFound,
    RepositoryNotFound,
    SymbolNotFound,
)


def _create_app_with_handlers() -> FastAPI:
    """Create a minimal FastAPI app with exception handlers registered."""
    app = FastAPI()
    register_exception_handlers(app)
    return app


class TestRepositoryNotFoundHandler:
    @pytest.mark.asyncio
    async def test_returns_404(self) -> None:
        app = _create_app_with_handlers()

        @app.get("/test")
        async def route() -> dict[str, str]:
            raise RepositoryNotFound("my-repo")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/test")

        assert resp.status_code == 404
        assert resp.json() == {"detail": "Repository not found"}


class TestFileNotFoundHandler:
    @pytest.mark.asyncio
    async def test_returns_404_with_message(self) -> None:
        app = _create_app_with_handlers()

        @app.get("/test")
        async def route() -> dict[str, str]:
            raise FileNotFound("src/main.py", repository_name="repo")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/test")

        assert resp.status_code == 404
        assert "src/main.py" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_includes_commit_context(self) -> None:
        app = _create_app_with_handlers()

        @app.get("/test")
        async def route() -> dict[str, str]:
            raise FileNotFound("src/main.py", commit_hash="abc123")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/test")

        assert resp.status_code == 404
        assert "abc123" in resp.json()["detail"]


class TestCommitNotFoundHandler:
    @pytest.mark.asyncio
    async def test_returns_404(self) -> None:
        app = _create_app_with_handlers()

        @app.get("/test")
        async def route() -> dict[str, str]:
            raise CommitNotFound(commit_hash="abc123")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/test")

        assert resp.status_code == 404
        assert resp.json() == {"detail": "Commit not found"}


class TestSymbolNotFoundHandler:
    @pytest.mark.asyncio
    async def test_returns_404(self) -> None:
        app = _create_app_with_handlers()

        @app.get("/test")
        async def route() -> dict[str, str]:
            raise SymbolNotFound("42")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/test")

        assert resp.status_code == 404
        assert resp.json() == {"detail": "Symbol not found"}


class TestBinaryFileHandler:
    @pytest.mark.asyncio
    async def test_returns_400(self) -> None:
        app = _create_app_with_handlers()

        @app.get("/test")
        async def route() -> dict[str, str]:
            raise BinaryFileError("image.png")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/test")

        assert resp.status_code == 400
        assert resp.json() == {
            "detail": "File is binary and cannot be displayed as text"
        }


class TestRepositoryPathNotFoundHandler:
    @pytest.mark.asyncio
    async def test_returns_500(self) -> None:
        app = _create_app_with_handlers()

        @app.get("/test")
        async def route() -> dict[str, str]:
            raise RepositoryPathNotFoundError("/repos/missing")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/test")

        assert resp.status_code == 500
        assert "/repos/missing" in resp.json()["detail"]


class TestUnhandledExceptionsPassThrough:
    @pytest.mark.asyncio
    async def test_value_error_is_not_caught(self) -> None:
        app = _create_app_with_handlers()

        @app.get("/test")
        async def route() -> dict[str, str]:
            raise ValueError("bad input")

        # ValueError is not handled by our exception handlers, so it propagates
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            resp = await client.get("/test")

        assert resp.status_code == 500
