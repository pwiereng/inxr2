"""list_repositories tool: List available repos and their indexed branches."""

from __future__ import annotations

from typing import Any

from src.client import Inxr2Client

TOOL_NAME = "list_repositories"

TOOL_DESCRIPTION = (
    "List all indexed repositories and their available branches. "
    "Use this to discover what repositories and branches are available "
    "before querying with other tools. Only shows branches that have "
    "been indexed (have data available)."
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


async def handle(
    client: Inxr2Client,
    arguments: dict[str, Any],
    frontend_url: str | None = None,
) -> str:
    import asyncio

    repository = arguments.get("repository")

    if repository:
        # Single repo detail
        repo = await client.get(f"/api/repositories/by-name/{repository}")
        branches_data = await client.get(
            f"/api/repositories/by-name/{repository}/branches"
        )
        indexed = [
            b for b in branches_data.get("branches", []) if b.get("commit_count", 0) > 0
        ]

        lines = [f"Repository: {repo['name']}"]
        lines.append(f"  Default branch: {repo.get('default_branch', 'unknown')}")
        lines.append(f"  Indexed branches: {len(indexed)}")
        for b in indexed:
            commit = (b.get("last_indexed_commit") or "")[:12]
            count = b.get("commit_count", 0)
            lines.append(f"    {b['name']} ({count} commits, head: {commit})")
        return "\n".join(lines)

    # All repos — fetch branches in parallel
    repos = await client.get("/api/repositories")

    async def fetch_branches(repo: dict[str, Any]) -> dict[str, Any]:
        branches_data = await client.get(
            f"/api/repositories/by-name/{repo['name']}/branches"
        )
        return {"repo": repo, "branches": branches_data.get("branches", [])}

    results = await asyncio.gather(*[fetch_branches(r) for r in repos])

    lines = [f"Repositories: {len(repos)} available"]
    for result in results:
        repo = result["repo"]
        indexed = [b for b in result["branches"] if b.get("commit_count", 0) > 0]
        branch_names = ", ".join(b["name"] for b in indexed)
        lines.append(
            f"  {repo['name']} (default: {repo.get('default_branch', '?')}, "
            f"indexed branches: {branch_names or 'none'})"
        )

    return "\n".join(lines)
