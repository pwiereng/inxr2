"""Staleness check for repository indexed data."""

from __future__ import annotations

from typing import Any

from src.client import Inxr2Client
from src.errors import ApiNotFoundError, McpToolError


class StalenessResult:
    """Result of a staleness check, including the fetched repo data."""

    __slots__ = ("warning", "repo_data")

    def __init__(self, warning: str | None, repo_data: dict[str, Any]) -> None:
        self.warning = warning
        self.repo_data = repo_data


async def check_staleness(client: Inxr2Client, repository_name: str) -> StalenessResult:
    """Check staleness and return both the warning (if any) and the repo data."""
    try:
        repo = await client.get(f"/api/repositories/by-name/{repository_name}")
    except ApiNotFoundError as exc:
        # The API's detail doesn't name the repository, so name it here
        raise McpToolError(
            f"Repository `{repository_name}` not found. "
            "Call `list_repositories` to see the indexed repositories."
        ) from exc
    stats = await client.get(f"/api/repositories/{repo['id']}/stats")
    warning = None
    if stats.get("is_stale"):
        indexed_commit = (stats.get("last_indexed_commit") or "unknown")[:7]
        indexed_at = stats.get("last_indexed_at") or "unknown"
        warning = (
            f"Warning: Indexed data may be stale — repository '{repository_name}' "
            f"has commits newer than the last index "
            f"(indexed up to {indexed_commit}, at {indexed_at})."
        )
    return StalenessResult(warning=warning, repo_data=repo)


def prepend_warning(output: str, warning: str | None) -> str:
    """Prepend a staleness warning to output if present."""
    if warning:
        return warning + "\n\n" + output
    return output
