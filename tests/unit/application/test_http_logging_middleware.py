"""Unit tests for HTTP logging middleware."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from inxr2.application.ports.repositories.query_log_port import (
    QueryLogPort,
)
from inxr2.infrastructure.fastapi.http_logging_middleware import (
    HttpLoggingMiddleware,
    _extract_repository,
)
from tests.fixtures.test_doubles import InMemoryQueryLogRepository


def _make_factory(port: QueryLogPort):  # type: ignore[no-untyped-def]
    @asynccontextmanager
    async def factory() -> AsyncGenerator[QueryLogPort, None]:
        yield port

    return factory


def _make_app(port: QueryLogPort | None = None, enabled: bool = True) -> FastAPI:
    app = FastAPI()

    @app.get("/api/test")
    async def test_route() -> dict[str, bool]:
        return {"ok": True}

    factory = _make_factory(port) if port is not None else None
    app.add_middleware(HttpLoggingMiddleware, port_factory=factory, enabled=enabled)
    return app


class TestExtractRepository:
    def test_extracts_from_path_segment(self) -> None:
        assert _extract_repository("/api/repositories/inxr2/files", {}) == "inxr2"

    def test_extracts_from_repository_query_param(self) -> None:
        assert _extract_repository("/api/symbols", {"repository": "myrepo"}) == "myrepo"

    def test_extracts_from_repo_query_param(self) -> None:
        assert _extract_repository("/api/symbols", {"repo": "myrepo"}) == "myrepo"

    def test_returns_none_when_no_repository(self) -> None:
        assert _extract_repository("/api/health", {}) is None

    def test_query_param_takes_priority_over_path(self) -> None:
        assert (
            _extract_repository(
                "/api/repositories/path-repo/files", {"repository": "param-repo"}
            )
            == "param-repo"
        )

    def test_skips_numeric_id_in_path(self) -> None:
        assert _extract_repository("/api/repositories/3/branches", {}) is None

    def test_handles_by_name_pattern(self) -> None:
        assert (
            _extract_repository("/api/repositories/by-name/inxr2/tree", {}) == "inxr2"
        )


@pytest.mark.asyncio
class TestHttpLoggingMiddleware:
    async def test_captures_result_count_from_list_response(self) -> None:
        port = InMemoryQueryLogRepository()
        app = FastAPI()

        @app.get("/api/items")
        async def items_route() -> dict[str, list[int]]:
            return {"results": [1, 2, 3]}

        factory = _make_factory(port)
        app.add_middleware(HttpLoggingMiddleware, port_factory=factory, enabled=True)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/api/items")

        entries = await port.list_recent()
        assert entries[0].result_count == 3

    async def test_result_count_none_for_non_list_response(self) -> None:
        port = InMemoryQueryLogRepository()
        app = _make_app(port=port)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/api/test")

        entries = await port.list_recent()
        assert entries[0].result_count is None

    async def test_logs_request_to_db(self) -> None:
        port = InMemoryQueryLogRepository()
        app = _make_app(port=port)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/test")

        assert response.status_code == 200
        entries = await port.list_recent()
        assert len(entries) == 1
        assert entries[0].source == "http"
        assert entries[0].tool_or_path == "/api/test"
        assert entries[0].status_code == 200
        assert entries[0].duration_ms is not None

    async def test_disabled_does_not_log(self) -> None:
        port = InMemoryQueryLogRepository()
        app = _make_app(port=port, enabled=False)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/api/test")

        entries = await port.list_recent()
        assert len(entries) == 0

    async def test_no_port_factory_still_returns_response(self) -> None:
        app = _make_app(port=None)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/test")

        assert response.status_code == 200

    async def test_extracts_repository_from_query_param(self) -> None:
        port = InMemoryQueryLogRepository()
        app = _make_app(port=port)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/api/test?repository=myrepo")

        entries = await port.list_recent()
        assert entries[0].repository == "myrepo"

    async def test_logs_query_params(self) -> None:
        port = InMemoryQueryLogRepository()
        app = _make_app(port=port)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/api/test?q=foo&limit=10")

        entries = await port.list_recent()
        assert entries[0].params == {"q": "foo", "limit": "10"}

    async def test_skips_activity_paths(self) -> None:
        port = InMemoryQueryLogRepository()
        app = FastAPI()

        @app.get("/api/activity")
        async def activity_route() -> dict[str, list]:
            return {"entries": []}

        @app.post("/api/activity/ingest")
        async def ingest_route() -> None:
            return None

        factory = _make_factory(port)
        app.add_middleware(HttpLoggingMiddleware, port_factory=factory, enabled=True)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/api/activity")
            await client.post("/api/activity/ingest", json={"source": "mcp"})

        entries = await port.list_recent()
        assert len(entries) == 0

    async def test_result_count_from_items_key(self) -> None:
        port = InMemoryQueryLogRepository()
        app = FastAPI()

        @app.get("/api/symbols")
        async def symbols_route() -> dict:
            return {"items": [1, 2], "total": 2}

        factory = _make_factory(port)
        app.add_middleware(HttpLoggingMiddleware, port_factory=factory, enabled=True)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/api/symbols")

        entries = await port.list_recent()
        assert entries[0].result_count == 2

    async def test_result_count_from_versions_key(self) -> None:
        port = InMemoryQueryLogRepository()
        app = FastAPI()

        @app.get("/api/file/history")
        async def history_route() -> dict:
            return {"versions": ["v1", "v2", "v3"], "total": 3}

        factory = _make_factory(port)
        app.add_middleware(HttpLoggingMiddleware, port_factory=factory, enabled=True)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/api/file/history")

        entries = await port.list_recent()
        assert entries[0].result_count == 3
