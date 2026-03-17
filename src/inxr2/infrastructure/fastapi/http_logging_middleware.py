"""HTTP request/response logging middleware for FastAPI."""

import json
import logging
import time
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ...application.ports.repositories.query_log_port import QueryLogEntry, QueryLogPort

logger = logging.getLogger(__name__)

PortFactory = Callable[[], AbstractAsyncContextManager[QueryLogPort]]

# Top-level JSON keys that contain result lists across our API endpoints
_RESULT_LIST_KEYS = (
    "results",
    "items",
    "files",
    "entries",
    "symbols",
    "commits",
    "branches",
    "repositories",
    "statuses",
    "renames",
    "references",
    "dependencies",
    "versions",
)

# Paths to skip logging (avoid self-referential noise in the activity log)
_SKIP_PREFIXES = ("/api/activity",)


def _extract_repository(path: str, params: dict[str, Any]) -> str | None:
    """Extract repository name from query params or path segment.

    Query params take priority. In the path, numeric IDs are skipped and the
    ``by-name`` sentinel is unwrapped to return the following segment.
    """
    repo = params.get("repository") or params.get("repo")
    if repo:
        return str(repo)
    parts = path.split("/")
    try:
        idx = parts.index("repositories")
        segment = parts[idx + 1] if idx + 1 < len(parts) else ""
        if not segment:
            return None
        if segment.isdigit():
            return None
        if segment == "by-name":
            name = parts[idx + 2] if idx + 2 < len(parts) else ""
            return name or None
        return segment
    except (ValueError, IndexError):
        pass
    return None


def _extract_result_count(body: bytes, status_code: int) -> int | None:
    """Parse JSON response body and return item count if a result list is found."""
    if status_code < 200 or status_code >= 300:
        return None
    try:
        data = json.loads(body)
        if isinstance(data, list):
            return len(data)
        for key in _RESULT_LIST_KEYS:
            if key in data and isinstance(data[key], list):
                return len(data[key])
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


class HttpLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every HTTP request/response as structured JSON and optionally writes to DB."""

    def __init__(
        self,
        app: Any,
        port_factory: PortFactory | None = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(app)
        self._port_factory = port_factory
        self._enabled = enabled

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self._enabled or any(
            request.url.path.startswith(p) for p in _SKIP_PREFIXES
        ):
            result: Response = await call_next(request)
            return result

        start = time.monotonic()
        response: Response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        # Consume response body to inspect result count, then rebuild response.
        # body_iterator is set by Starlette's call_next at runtime but absent from stubs.
        # Accumulate into a list to avoid O(n²) reallocation on concatenation.
        chunks: list[bytes] = []
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode())
        body = b"".join(chunks)

        result_count = _extract_result_count(body, response.status_code)

        # Rebuild response with the same body so it still reaches the client.
        # Note: dict(response.headers) coalesces duplicate header names (e.g. multiple
        # Set-Cookie); this is acceptable for a JSON API. Preserve background tasks.
        new_response = Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
        new_response.background = response.background

        params: dict[str, Any] = dict(request.query_params)
        repository = _extract_repository(request.url.path, params)

        entry = QueryLogEntry(
            source="http",
            tool_or_path=request.url.path,
            logged_at=datetime.now(UTC),
            params=params if params else None,
            repository=repository,
            status_code=response.status_code,
            duration_ms=duration_ms,
            result_count=result_count,
        )

        log_data = {
            "timestamp": entry.logged_at.isoformat(),
            "source": "http",
            "method": request.method,
            "path": entry.tool_or_path,
            "params": entry.params,
            "status": entry.status_code,
            "duration_ms": entry.duration_ms,
            "result_count": entry.result_count,
            "repository": entry.repository,
        }
        logger.info(json.dumps(log_data))

        if self._port_factory is not None:
            try:
                async with self._port_factory() as port:
                    await port.append(entry)
            except Exception:
                logger.exception("Failed to write HTTP query log entry to DB")

        return new_response
