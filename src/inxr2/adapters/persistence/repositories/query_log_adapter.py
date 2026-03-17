"""PostgreSQL query log repository adapter."""

import os
from datetime import UTC

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.ports.repositories.query_log_port import (
    QueryLogEntry,
    QueryLogPort,
)
from ..models.query_log import QueryLogModel

_DEFAULT_MAX_ENTRIES = int(os.getenv("MAX_QUERY_LOG_ENTRIES", "10000"))


class PostgresQueryLogRepository(QueryLogPort):
    """PostgreSQL implementation of QueryLogPort (ring-buffer activity log)."""

    def __init__(
        self, session: AsyncSession, max_entries: int = _DEFAULT_MAX_ENTRIES
    ) -> None:
        self._session = session
        self._max_entries = max_entries

    async def append(self, entry: QueryLogEntry) -> None:
        """Insert a log entry and trim the oldest rows if over cap."""
        # Strip timezone for storage (all times are UTC, stored as naive)
        logged_at = (
            entry.logged_at.replace(tzinfo=None)
            if entry.logged_at.tzinfo
            else entry.logged_at
        )

        model = QueryLogModel(
            logged_at=logged_at,
            source=entry.source,
            tool_or_path=entry.tool_or_path,
            params=entry.params,
            repository=entry.repository,
            status_code=entry.status_code,
            duration_ms=entry.duration_ms,
            result_count=entry.result_count,
            session_id=entry.session_id,
        )
        self._session.add(model)
        await self._session.flush()

        # Ring-buffer: find the (max_entries+1)-th newest id and delete everything at or
        # below it. One DELETE per insert — a no-op (0 rows) when under cap, eliminates
        # the separate COUNT(*) query from the original approach.
        cutoff_subq = (
            select(QueryLogModel.id)
            .order_by(QueryLogModel.id.desc())
            .offset(self._max_entries)
            .limit(1)
            .scalar_subquery()
        )
        await self._session.execute(
            delete(QueryLogModel).where(QueryLogModel.id <= cutoff_subq)
        )

    async def list_recent(
        self,
        source: str | None = None,
        repository: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[QueryLogEntry]:
        """Return log entries, newest first."""
        stmt = select(QueryLogModel).order_by(QueryLogModel.id.desc())
        if source is not None:
            stmt = stmt.where(QueryLogModel.source == source)
        if repository is not None:
            stmt = stmt.where(QueryLogModel.repository == repository)
        stmt = stmt.limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entry(m) for m in models]

    @staticmethod
    def _to_entry(model: QueryLogModel) -> QueryLogEntry:
        logged_at = model.logged_at
        if logged_at.tzinfo is None:
            logged_at = logged_at.replace(tzinfo=UTC)
        return QueryLogEntry(
            id=model.id,
            source=model.source,
            tool_or_path=model.tool_or_path,
            logged_at=logged_at,
            params=model.params,
            repository=model.repository,
            status_code=model.status_code,
            duration_ms=model.duration_ms,
            result_count=model.result_count,
            session_id=model.session_id,
        )
