"""HTTP client for communicating with the INXR2 API."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx


class Inxr2Client(ABC):
    """Abstract interface for INXR2 API communication."""

    @abstractmethod
    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Make a GET request to the INXR2 API and return parsed JSON."""
        ...

    @abstractmethod
    async def post(self, path: str, json: dict[str, Any]) -> Any:
        """Make a POST request to the INXR2 API and return parsed JSON (or None for 204)."""
        ...


class HttpInxr2Client(Inxr2Client):
    """Real HTTP client that calls the INXR2 API."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        # Filter out None values from params
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def post(self, path: str, json: dict[str, Any]) -> Any:
        response = await self._client.post(path, json=json)
        response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()

    async def close(self) -> None:
        await self._client.aclose()
