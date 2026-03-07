"""find_references tool: Find all usages of a symbol across indexed repos."""

from __future__ import annotations

from typing import Any

from src.client import Inxr2Client
from src.urls import build_browse_url

TOOL_NAME = "find_references"

TOOL_DESCRIPTION = (
    "Find all usages of a symbol across all indexed repositories. "
    "Returns cross-repo references including imports, calls, type annotations, "
    "and other usages. This is useful for understanding how a function, class, "
    "or variable is used across the codebase."
)

TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "Symbol name to find references for (e.g. 'DatabaseConnection')",
        },
        "repository": {
            "type": "string",
            "description": "Filter to a specific repository name (optional)",
        },
        "ref_type": {
            "type": "string",
            "description": "Filter by reference type (optional)",
            "enum": ["import", "call", "usage", "type_annotation"],
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
    "required": ["name"],
}


async def handle(
    client: Inxr2Client,
    arguments: dict[str, Any],
    frontend_url: str | None = None,
) -> str:
    import asyncio

    name = arguments["name"]
    repository = arguments.get("repository")
    ref_type = arguments.get("ref_type")
    branch = arguments.get("branch")
    commit = arguments.get("commit")

    # commit requires repository (API returns 400 otherwise)
    if commit and not repository:
        return "Error: 'commit' requires 'repository' to be specified."

    # Step 1: Resolve repository_id if repository name given
    repository_id = None
    if repository:
        repo_data = await client.get(f"/api/repositories/by-name/{repository}")
        repository_id = repo_data["id"]

    # Step 2: Find matching symbols by exact name
    symbol_params: dict[str, Any] = {}
    if repository_id is not None:
        symbol_params["repository_id"] = repository_id
    if branch:
        symbol_params["branch"] = branch
    if commit:
        symbol_params["commit"] = commit
    symbols_data = await client.get(
        f"/api/symbols/by-name/{name}", params=symbol_params
    )

    if not symbols_data["items"]:
        return f"No symbols found matching '{name}'."

    # Step 3: Get references for matching symbols (by_name=true for cross-repo)
    seen_symbol_ids: set[int] = set()
    unique_symbols = []
    for symbol in symbols_data["items"]:
        if symbol["id"] not in seen_symbol_ids:
            seen_symbol_ids.add(symbol["id"])
            unique_symbols.append(symbol)

    async def fetch_refs(symbol: dict[str, Any]) -> list[dict[str, Any]]:
        ref_params: dict[str, Any] = {"by_name": "true", "limit": 100}
        if branch:
            ref_params["branch"] = branch
        if commit:
            ref_params["commit"] = commit
        refs_data = await client.get(
            f"/api/symbols/{symbol['id']}/references",
            params=ref_params,
        )
        return [
            {
                "file": ref.get("source_file_path", "unknown"),
                "line": ref.get("source_line"),
                "type": ref.get("reference_type", "unknown"),
                "context": ref.get("reference_text", ""),
            }
            for ref in refs_data["items"]
        ]

    results = await asyncio.gather(*[fetch_refs(s) for s in unique_symbols])
    all_references: list[dict[str, Any]] = [ref for refs in results for ref in refs]

    # Step 4: Filter by ref_type if specified
    if ref_type:
        all_references = [r for r in all_references if r["type"] == ref_type]

    # Step 5: Format output
    lines = [f"References for '{name}': {len(all_references)} found"]
    if not all_references:
        lines.append("No references found.")
        return "\n".join(lines)

    for ref in all_references:
        location = f"{ref['file']}:{ref['line']}" if ref["line"] else ref["file"]
        lines.append(f"  [{ref['type']}] {location}")
        if ref["context"]:
            lines.append(f"    {ref['context']}")

        # Add browse URL when repository is known
        if frontend_url and repository and ref["file"] != "unknown":
            url = build_browse_url(
                frontend_url,
                repository,
                ref["file"],
                line=ref["line"],
                branch=branch,
                commit=commit,
            )
            lines.append(f"    {url}")

    return "\n".join(lines)
