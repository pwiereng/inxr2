"""Tests for HttpInxr2Client error handling, over an in-process transport."""

import httpx
import pytest

from src.client import HttpInxr2Client
from src.errors import ApiNotFoundError


def _client(
    status: int, json: object | None = None, text: str | None = None
) -> HttpInxr2Client:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json, text=text)

    return HttpInxr2Client("http://test", transport=httpx.MockTransport(respond))


class TestHttpInxr2ClientGet:
    async def test_returns_json(self) -> None:
        client = _client(200, json={"ok": True})

        assert await client.get("/api/x") == {"ok": True}

    async def test_404_raises_api_not_found_with_detail(self) -> None:
        client = _client(404, json={"detail": "File not found: src/gone.py"})

        with pytest.raises(ApiNotFoundError) as exc_info:
            await client.get("/api/symbols/file-structure")

        assert exc_info.value.detail == "File not found: src/gone.py"
        assert "404 Not Found" not in str(exc_info.value)

    async def test_404_without_json_detail_names_the_path(self) -> None:
        client = _client(404, text="<html>nope</html>")

        with pytest.raises(ApiNotFoundError, match="/api/nowhere"):
            await client.get("/api/nowhere")

    async def test_other_errors_still_raise_http_status_error(self) -> None:
        client = _client(500, json={"detail": "boom"})

        with pytest.raises(httpx.HTTPStatusError, match="500"):
            await client.get("/api/x")
