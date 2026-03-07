"""search_symbols tool: Find symbol definitions by name."""

from __future__ import annotations

from typing import Any

from src.client import Inxr2Client
from src.urls import build_browse_url

TOOL_NAME = "search_symbols"

TOOL_DESCRIPTION = (
    "Search for symbol definitions (functions, classes, methods, variables) "
    "by name across all indexed repositories. Supports fuzzy matching. "
    "Use this to discover symbols without knowing their exact name."
)

TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Search query for symbol name (e.g. 'search', 'Repository')",
        },
        "repository": {
            "type": "string",
            "description": "Filter to a specific repository name (optional)",
        },
        "kind": {
            "type": "string",
            "description": "Filter by symbol kind (optional)",
            "enum": [
                "function",
                "class",
                "method",
                "variable",
                "property",
                "interface",
                "enum",
                "module",
            ],
        },
        "limit": {
            "type": "integer",
            "description": "Max results to return (default 20, max 100)",
            "default": 20,
        },
        "branch": {
            "type": "string",
            "description": "Branch name to search in (optional, defaults to latest indexed)",
        },
        "commit": {
            "type": "string",
            "description": "Specific commit hash to search at (optional, overrides branch)",
        },
    },
    "required": ["query"],
}


async def handle(
    client: Inxr2Client,
    arguments: dict[str, Any],
    frontend_url: str | None = None,
) -> str:
    query = arguments["query"]
    repository = arguments.get("repository")
    kind = arguments.get("kind")
    limit = min(arguments.get("limit", 20), 100)
    branch = arguments.get("branch")
    commit = arguments.get("commit")

    # commit requires repository (API returns 400 otherwise)
    if commit and not repository:
        return "Error: 'commit' requires 'repository' to be specified."

    # Resolve repository_id if repository name given
    repository_id = None
    if repository:
        repo_data = await client.get(f"/api/repositories/by-name/{repository}")
        repository_id = repo_data["id"]

    # Search symbols
    params: dict[str, Any] = {"q": query, "limit": limit}
    if repository_id is not None:
        params["repository_id"] = repository_id
    if kind:
        params["kind"] = kind
    if branch:
        params["branch"] = branch
    if commit:
        params["commit"] = commit
    symbols_data = await client.get("/api/symbols", params=params)

    items = symbols_data.get("items", [])
    total = symbols_data.get("total", len(items))

    if not items:
        return f"No symbols found matching '{query}'."

    # Build repo_id -> name map for browse URLs
    repo_names: dict[int, str] = {}
    if frontend_url:
        if repository and repository_id is not None:
            repo_names[repository_id] = repository
        else:
            repos = await client.get("/api/repositories")
            repo_names = {r["id"]: r["name"] for r in repos}

    # Format results
    lines = [f"Symbols matching '{query}': {len(items)} shown (of {total} total)"]
    for symbol in items:
        file_path = symbol.get("file_path", "unknown")
        line = symbol.get("start_line", "?")
        kind_str = symbol.get("kind", "unknown")
        name = symbol.get("name", "unknown")
        sig = symbol.get("signature", "")

        lines.append(f"  [{kind_str}] {name}")
        lines.append(f"    {file_path}:{line}")
        if sig:
            lines.append(f"    {sig}")

        # Add browse URL
        if frontend_url:
            repo_name = repo_names.get(symbol.get("repository_id", 0))
            if repo_name and file_path != "unknown":
                url = build_browse_url(
                    frontend_url,
                    repo_name,
                    file_path,
                    line=symbol.get("start_line"),
                    branch=branch,
                    commit=commit,
                )
                lines.append(f"    {url}")

    return "\n".join(lines)
