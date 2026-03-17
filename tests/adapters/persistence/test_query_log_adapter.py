"""Integration tests for PostgresQueryLogRepository."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.query_log_adapter import (
    PostgresQueryLogRepository,
)
from inxr2.application.ports.repositories.query_log_port import QueryLogEntry


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
class TestPostgresQueryLogRepository:
    async def test_append_and_list(self, db_session: AsyncSession) -> None:
        repo = PostgresQueryLogRepository(db_session)
        await repo.append(
            _entry(
                "/api/symbols",
                logged_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
                status_code=200,
                duration_ms=15,
                repository="inxr2",
            )
        )
        await db_session.flush()

        results = await repo.list_recent()
        assert len(results) == 1
        assert results[0].source == "http"
        assert results[0].tool_or_path == "/api/symbols"
        assert results[0].status_code == 200
        assert results[0].duration_ms == 15
        assert results[0].repository == "inxr2"

    async def test_list_returns_newest_first(self, db_session: AsyncSession) -> None:
        repo = PostgresQueryLogRepository(db_session)
        for i in range(3):
            await repo.append(
                _entry(f"/p{i}", logged_at=datetime(2026, 1, 1, i, tzinfo=UTC))
            )
        await db_session.flush()

        results = await repo.list_recent()
        assert results[0].tool_or_path == "/p2"
        assert results[-1].tool_or_path == "/p0"

    async def test_list_filters_by_source(self, db_session: AsyncSession) -> None:
        repo = PostgresQueryLogRepository(db_session)
        await repo.append(_entry("/p", source="http"))
        await repo.append(_entry("search_symbols", source="mcp"))
        await db_session.flush()

        results = await repo.list_recent(source="mcp")
        assert len(results) == 1
        assert results[0].source == "mcp"

    async def test_list_filters_by_repository(self, db_session: AsyncSession) -> None:
        repo = PostgresQueryLogRepository(db_session)
        await repo.append(_entry("/p1", repository="inxr2"))
        await repo.append(_entry("/p2", repository="other"))
        await db_session.flush()

        results = await repo.list_recent(repository="inxr2")
        assert len(results) == 1
        assert results[0].repository == "inxr2"

    async def test_list_respects_limit_and_offset(
        self, db_session: AsyncSession
    ) -> None:
        repo = PostgresQueryLogRepository(db_session)
        for i in range(5):
            await repo.append(
                _entry(f"/p{i}", logged_at=datetime(2026, 1, 1, i, tzinfo=UTC))
            )
        await db_session.flush()

        results = await repo.list_recent(limit=2, offset=1)
        assert len(results) == 2
        # Newest first: p4, p3, p2, p1, p0 → offset 1 → p3, p2
        assert results[0].tool_or_path == "/p3"

    async def test_ring_buffer_deletes_oldest(self, db_session: AsyncSession) -> None:
        repo = PostgresQueryLogRepository(db_session, max_entries=2)
        for i in range(3):
            await repo.append(
                _entry(f"/p{i}", logged_at=datetime(2026, 1, 1, i, tzinfo=UTC))
            )
        await db_session.flush()

        results = await repo.list_recent(limit=10)
        assert len(results) == 2
        paths = {r.tool_or_path for r in results}
        assert "/p2" in paths
        assert "/p1" in paths
        assert "/p0" not in paths

    async def test_empty_returns_empty_list(self, db_session: AsyncSession) -> None:
        repo = PostgresQueryLogRepository(db_session)
        results = await repo.list_recent()
        assert results == []
