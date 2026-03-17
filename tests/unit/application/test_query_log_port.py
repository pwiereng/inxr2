"""Unit tests for QueryLogPort — verified against InMemoryQueryLogRepository fake."""

from datetime import UTC, datetime

import pytest

from inxr2.application.ports.repositories.query_log_port import QueryLogEntry
from tests.fixtures.test_doubles import InMemoryQueryLogRepository


def _entry(
    path: str = "/api/test", source: str = "http", **kwargs: object
) -> QueryLogEntry:
    return QueryLogEntry(
        source=source,
        tool_or_path=path,
        logged_at=kwargs.pop("logged_at", datetime.now(UTC)),  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
class TestInMemoryQueryLogRepository:
    async def test_append_adds_entry(self) -> None:
        repo = InMemoryQueryLogRepository()
        await repo.append(_entry("/api/symbols"))
        results = await repo.list_recent()
        assert len(results) == 1
        assert results[0].tool_or_path == "/api/symbols"

    async def test_list_recent_returns_newest_first(self) -> None:
        repo = InMemoryQueryLogRepository()
        for i in range(3):
            await repo.append(
                _entry(f"/api/p{i}", logged_at=datetime(2026, 1, 1, i, tzinfo=UTC))
            )
        results = await repo.list_recent()
        assert results[0].tool_or_path == "/api/p2"
        assert results[-1].tool_or_path == "/api/p0"

    async def test_list_recent_filters_by_source(self) -> None:
        repo = InMemoryQueryLogRepository()
        await repo.append(_entry("/api/symbols", source="http"))
        await repo.append(_entry("search_symbols", source="mcp"))
        results = await repo.list_recent(source="mcp")
        assert len(results) == 1
        assert results[0].source == "mcp"

    async def test_list_recent_filters_by_repository(self) -> None:
        repo = InMemoryQueryLogRepository()
        await repo.append(_entry("/api/symbols", repository="inxr2"))
        await repo.append(_entry("/api/files", repository="other"))
        results = await repo.list_recent(repository="inxr2")
        assert len(results) == 1
        assert results[0].repository == "inxr2"

    async def test_list_recent_limit(self) -> None:
        repo = InMemoryQueryLogRepository()
        for i in range(5):
            await repo.append(_entry(f"/api/p{i}"))
        results = await repo.list_recent(limit=3)
        assert len(results) == 3

    async def test_list_recent_offset(self) -> None:
        repo = InMemoryQueryLogRepository()
        for i in range(5):
            await repo.append(
                _entry(f"/api/p{i}", logged_at=datetime(2026, 1, 1, i, tzinfo=UTC))
            )
        results = await repo.list_recent(limit=2, offset=1)
        assert len(results) == 2
        # Newest first: p4, p3, p2, p1, p0 → offset 1 → p3, p2
        assert results[0].tool_or_path == "/api/p3"

    async def test_ring_buffer_cap_drops_oldest(self) -> None:
        repo = InMemoryQueryLogRepository(max_entries=3)
        for i in range(5):
            await repo.append(
                _entry(f"/api/p{i}", logged_at=datetime(2026, 1, 1, i, tzinfo=UTC))
            )
        results = await repo.list_recent(limit=10)
        assert len(results) == 3
        paths = {r.tool_or_path for r in results}
        assert "/api/p4" in paths
        assert "/api/p3" in paths
        assert "/api/p2" in paths
        assert "/api/p0" not in paths
        assert "/api/p1" not in paths

    async def test_empty_repo_returns_empty_list(self) -> None:
        repo = InMemoryQueryLogRepository()
        results = await repo.list_recent()
        assert results == []
