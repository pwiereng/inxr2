"""Integration tests for GET /api/activity endpoint."""

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from inxr2.adapters.api.routes import activity
from inxr2.application.ports.repositories.query_log_port import QueryLogEntry
from inxr2.infrastructure.dependencies import get_query_log_adapter
from tests.fixtures.test_doubles import InMemoryQueryLogRepository


def _make_app(port: InMemoryQueryLogRepository) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_query_log_adapter] = lambda: port
    app.include_router(activity.router, prefix="/api")
    return app


@pytest.mark.asyncio
class TestActivityRoute:
    async def test_returns_entries(self) -> None:
        port = InMemoryQueryLogRepository()
        await port.append(
            QueryLogEntry(
                source="http",
                tool_or_path="/api/symbols",
                logged_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
                status_code=200,
                duration_ms=15,
                repository="inxr2",
            )
        )
        app = _make_app(port)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/activity")

        assert response.status_code == 200
        data = response.json()
        assert len(data["entries"]) == 1
        e = data["entries"][0]
        assert e["source"] == "http"
        assert e["tool_or_path"] == "/api/symbols"
        assert e["status_code"] == 200
        assert e["duration_ms"] == 15
        assert e["repository"] == "inxr2"

    async def test_filter_by_source(self) -> None:
        port = InMemoryQueryLogRepository()
        await port.append(
            QueryLogEntry(
                source="http", tool_or_path="/api/p", logged_at=datetime.now(UTC)
            )
        )
        await port.append(
            QueryLogEntry(
                source="mcp", tool_or_path="search_symbols", logged_at=datetime.now(UTC)
            )
        )
        app = _make_app(port)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/activity?source=mcp")

        data = response.json()
        assert len(data["entries"]) == 1
        assert data["entries"][0]["source"] == "mcp"

    async def test_filter_by_repository(self) -> None:
        port = InMemoryQueryLogRepository()
        await port.append(
            QueryLogEntry(
                source="http",
                tool_or_path="/p1",
                logged_at=datetime.now(UTC),
                repository="a",
            )
        )
        await port.append(
            QueryLogEntry(
                source="http",
                tool_or_path="/p2",
                logged_at=datetime.now(UTC),
                repository="b",
            )
        )
        app = _make_app(port)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/activity?repository=a")

        data = response.json()
        assert len(data["entries"]) == 1
        assert data["entries"][0]["repository"] == "a"

    async def test_empty_returns_empty_list(self) -> None:
        port = InMemoryQueryLogRepository()
        app = _make_app(port)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/activity")

        assert response.status_code == 200
        assert response.json()["entries"] == []

    async def test_limit_and_offset(self) -> None:
        port = InMemoryQueryLogRepository()
        for i in range(5):
            await port.append(
                QueryLogEntry(
                    source="http",
                    tool_or_path=f"/p{i}",
                    logged_at=datetime(2026, 1, 1, i, tzinfo=UTC),
                )
            )
        app = _make_app(port)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/activity?limit=2&offset=0")

        data = response.json()
        assert len(data["entries"]) == 2
        # Newest first
        assert data["entries"][0]["tool_or_path"] == "/p4"
