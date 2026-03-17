"""Query log port interface and data class."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class QueryLogEntry:
    """A single query log entry (HTTP request or MCP tool call)."""

    source: str  # 'http' | 'mcp'
    tool_or_path: str
    logged_at: datetime
    params: dict[str, Any] | None = None
    repository: str | None = None
    status_code: int | None = None  # None for MCP
    duration_ms: int | None = None
    result_count: int | None = None
    session_id: str | None = None
    id: int | None = field(default=None, compare=False)


class QueryLogPort(ABC):
    """Port for writing and querying the activity log."""

    @abstractmethod
    async def append(self, entry: QueryLogEntry) -> None:
        """Append a log entry (ring buffer — oldest rows auto-deleted at cap)."""

    @abstractmethod
    async def list_recent(
        self,
        source: str | None = None,
        repository: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[QueryLogEntry]:
        """Return log entries, newest first."""
