"""Activity log API endpoint."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from ....application.ports.repositories.query_log_port import QueryLogEntry
from ....infrastructure.dependencies import QueryLogAdapterDep

router = APIRouter(prefix="/activity", tags=["activity"])


class QueryLogEntryResponse(BaseModel):
    """Response model for a single query log entry."""

    id: int | None
    source: str
    tool_or_path: str
    logged_at: datetime
    params: dict[str, Any] | None
    repository: str | None
    status_code: int | None
    duration_ms: int | None
    result_count: int | None
    session_id: str | None

    model_config = ConfigDict(from_attributes=True)


class ActivityLogResponse(BaseModel):
    """Response model for the activity log list."""

    entries: list[QueryLogEntryResponse]

    model_config = ConfigDict(from_attributes=True)


class IngestRequest(BaseModel):
    """Request body for MCP-side activity ingest."""

    source: str
    tool_or_path: str
    params: dict[str, Any] | None = None
    repository: str | None = None
    duration_ms: int | None = None
    result_count: int | None = None
    session_id: str | None = None


@router.get("", response_model=ActivityLogResponse)
async def list_activity(
    adapter: QueryLogAdapterDep,
    source: str | None = Query(None, description="Filter by source: 'http' or 'mcp'"),
    repository: str | None = Query(None, description="Filter by repository name"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> ActivityLogResponse:
    """
    Return recent activity log entries, newest first.

    Logs every HTTP API request and MCP tool call with timing and metadata.
    """
    entries = await adapter.list_recent(
        source=source,
        repository=repository,
        limit=limit,
        offset=offset,
    )
    return ActivityLogResponse(
        entries=[
            QueryLogEntryResponse(
                id=e.id,
                source=e.source,
                tool_or_path=e.tool_or_path,
                logged_at=e.logged_at,
                params=e.params,
                repository=e.repository,
                status_code=e.status_code,
                duration_ms=e.duration_ms,
                result_count=e.result_count,
                session_id=e.session_id,
            )
            for e in entries
        ]
    )


@router.post("/ingest", status_code=204)
async def ingest_activity(
    adapter: QueryLogAdapterDep,
    body: IngestRequest,
) -> None:
    """
    Ingest an activity entry from an external source (e.g. MCP server).

    Intentionally excluded from HTTP middleware logging to avoid self-referential noise.
    """
    await adapter.append(
        QueryLogEntry(
            source=body.source,
            tool_or_path=body.tool_or_path,
            logged_at=datetime.now(UTC),
            params=body.params,
            repository=body.repository,
            duration_ms=body.duration_ms,
            result_count=body.result_count,
            session_id=body.session_id,
        )
    )
