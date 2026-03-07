"""go_to_definition tool: Jump to the definition of a symbol."""

from __future__ import annotations

from typing import Any

from src.client import Inxr2Client
from src.staleness import check_staleness, prepend_warning
from src.urls import build_browse_url

TOOL_NAME = "go_to_definition"

TOOL_DESCRIPTION = (
    "Jump to the definition of a symbol. Works across repositories. "
    "Returns the file path, line number, signature, and docstring of the "
    "symbol definition. Useful for navigating to where a function, class, "
    "or variable is defined."
)

TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "Symbol name to find the definition of (e.g. 'SearchSymbolsUseCase')",
        },
        "repository": {
            "type": "string",
            "description": "Filter to a specific repository name (optional)",
        },
        "file_path": {
            "type": "string",
            "description": "Filter to a specific file path (optional)",
        },
        "commit": {
            "type": "string",
            "description": "Specific commit hash to search at (optional)",
        },
    },
    "required": ["name"],
}


async def handle(
    client: Inxr2Client,
    arguments: dict[str, Any],
    frontend_url: str | None = None,
) -> str:
    name = arguments["name"]
    repository = arguments.get("repository")
    file_path = arguments.get("file_path")
    # by-name endpoint only supports commit, not branch
    commit = arguments.get("commit")

    # commit requires repository (API returns 400 otherwise)
    if commit and not repository:
        return "Error: 'commit' requires 'repository' to be specified."

    # Resolve repository and check staleness
    staleness_warning = None
    repository_id = None
    if repository:
        staleness = await check_staleness(client, repository)
        staleness_warning = staleness.warning
        repository_id = staleness.repo_data["id"]

    # Find symbols by exact name
    params: dict[str, Any] = {}
    if repository_id is not None:
        params["repository_id"] = repository_id
    if commit:
        params["commit"] = commit
    symbols_data = await client.get(f"/api/symbols/by-name/{name}", params=params)

    items = symbols_data.get("items", [])

    # Filter by file_path if specified
    if file_path:
        items = [s for s in items if s.get("file_path", "").endswith(file_path)]

    if not items:
        return prepend_warning(f"No definition found for '{name}'.", staleness_warning)

    # Build repo_id -> name map for browse URLs
    repo_names: dict[int, str] = {}
    if frontend_url:
        if repository and repository_id is not None:
            repo_names[repository_id] = repository
        else:
            repos = await client.get("/api/repositories")
            repo_names = {r["id"]: r["name"] for r in repos}

    # Format results
    lines = [f"Definitions for '{name}': {len(items)} found"]
    for symbol in items:
        sym_file = symbol.get("file_path", "unknown")
        lines.append("")
        lines.append(f"  File: {sym_file}")
        lines.append(f"  Line: {symbol.get('start_line')}")
        lines.append(f"  Kind: {symbol.get('kind', 'unknown')}")
        if symbol.get("qualified_name"):
            lines.append(f"  Qualified: {symbol['qualified_name']}")
        if symbol.get("signature"):
            lines.append(f"  Signature: {symbol['signature']}")
        if symbol.get("docstring"):
            docstring = symbol["docstring"]
            # Truncate long docstrings
            if len(docstring) > 200:
                docstring = docstring[:200] + "..."
            lines.append(f"  Docstring: {docstring}")

        # Add browse URL
        if frontend_url:
            repo_name = repo_names.get(symbol.get("repository_id", 0))
            if repo_name and sym_file and sym_file != "unknown":
                url = build_browse_url(
                    frontend_url,
                    repo_name,
                    sym_file,
                    line=symbol.get("start_line"),
                    commit=commit,
                )
                lines.append(f"  URL: {url}")

    return prepend_warning("\n".join(lines), staleness_warning)
