"""list_repositories tool: List available repos and their indexed branches."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from src.client import Inxr2Client

TOOL_NAME = "list_repositories"

TOOL_DESCRIPTION = (
    "List all indexed repositories and their available branches. "
    "Use this to discover what repositories and branches are available "
    "before querying with other tools. Only shows branches that have "
    "been indexed — branches that exist in git but have never been indexed "
    "will not appear. Each branch shows commit count, last-indexed commit SHA, "
    "and commits_behind (0 = current; '? (stale)' = newer commits exist; "
    "'unknown' = staleness could not be determined). "
    "Use this to verify whether the index is current before relying on results."
)

TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "repository": {
            "type": "string",
            "description": "Show details for a specific repository only (optional)",
        },
    },
}


async def _fetch_stats_safe(client: Inxr2Client, repo_id: int) -> dict[str, Any]:
    """Fetch repo stats, returning an empty dict on any error (staleness is informational)."""
    try:
        return await client.get(f"/api/repositories/{repo_id}/stats")  # type: ignore[no-any-return]
    except Exception:
        return {}


def _commits_behind_str(is_stale: bool | None) -> str:
    if is_stale is None:
        return "unknown"
    return "? (stale) ⚠️" if is_stale else "0"


async def handle(
    client: Inxr2Client,
    arguments: dict[str, Any],
    frontend_url: str | None = None,
) -> str:
    import asyncio

    repository = arguments.get("repository")

    if repository:
        # Single repo detail — fetch repo first (need ID for stats URL),
        # then branches and stats in parallel.
        encoded = quote(repository, safe="")
        repo = await client.get(f"/api/repositories/by-name/{encoded}")
        branches_data, stats = await asyncio.gather(
            client.get(f"/api/repositories/by-name/{encoded}/branches"),
            _fetch_stats_safe(client, repo["id"]),
        )
        indexed = [
            b
            for b in branches_data.get("branches", [])
            if b.get("last_indexed_commit") is not None or b.get("commit_count", 0) > 0
        ]
        commits_behind = _commits_behind_str(stats.get("is_stale"))

        lines = [f"Repository: {repo['name']}"]
        lines.append(f"  Default branch: {repo.get('default_branch', 'unknown')}")
        lines.append(f"  Indexed branches: {len(indexed)}")
        for b in indexed:
            commit = (b.get("last_indexed_commit") or "")[:7]
            count = b.get("commit_count", 0)
            lines.append(
                f"    {b['name']}: {count} commits, head: {commit}, commits_behind: {commits_behind}"
            )
        return "\n".join(lines)

    # All repos — fetch branches and stats in parallel per repo
    repos = await client.get("/api/repositories")

    async def fetch_branches(repo: dict[str, Any]) -> dict[str, Any]:
        encoded_name = quote(repo["name"], safe="")
        branches_data, stats = await asyncio.gather(
            client.get(f"/api/repositories/by-name/{encoded_name}/branches"),
            _fetch_stats_safe(client, repo["id"]),
        )
        return {
            "repo": repo,
            "branches": branches_data.get("branches", []),
            "is_stale": stats.get("is_stale"),
        }

    results = await asyncio.gather(*[fetch_branches(r) for r in repos])

    lines = [f"Repositories: {len(repos)} available"]
    for result in results:
        repo = result["repo"]
        commits_behind = _commits_behind_str(result["is_stale"])
        indexed = [
            b
            for b in result["branches"]
            if b.get("last_indexed_commit") is not None or b.get("commit_count", 0) > 0
        ]
        branch_names = ", ".join(b["name"] for b in indexed)
        lines.append(
            f"  {repo['name']} (default: {repo.get('default_branch', '?')}, "
            f"indexed branches: {branch_names or 'none'})"
        )
        for b in indexed:
            commit = (b.get("last_indexed_commit") or "")[:7]
            count = b.get("commit_count", 0)
            lines.append(
                f"    {b['name']}: {count} commits, head: {commit}, commits_behind: {commits_behind}"
            )

    return "\n".join(lines)
