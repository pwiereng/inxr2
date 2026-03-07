"""Staleness check for repository indexed data."""

from __future__ import annotations

from src.client import Inxr2Client


async def check_staleness(client: Inxr2Client, repository_name: str) -> str | None:
    """Return a warning string if repo's indexed data is stale, None otherwise."""
    repo = await client.get(f"/api/repositories/by-name/{repository_name}")
    stats = await client.get(f"/api/repositories/{repo['id']}/stats")
    if stats.get("is_stale"):
        indexed_commit = (stats.get("last_indexed_commit") or "unknown")[:7]
        indexed_at = stats.get("last_indexed_at") or "unknown"
        return (
            f"Warning: Indexed data may be stale — repository '{repository_name}' "
            f"has commits newer than the last index "
            f"(indexed up to {indexed_commit}, at {indexed_at})."
        )
    return None
