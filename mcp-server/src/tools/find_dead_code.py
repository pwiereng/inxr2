"""find_dead_code tool: Find symbols with zero references in a repository."""

from __future__ import annotations

import asyncio
from typing import Any

from src.client import Inxr2Client
from src.urls import build_browse_url

TOOL_NAME = "find_dead_code"

TOOL_DESCRIPTION = (
    "Find symbols with zero references (dead code) in a repository. "
    "Useful for identifying unused functions, classes, and methods. "
    "Requires a repository name. Optionally filter by symbol kind."
)

TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "repository": {
            "type": "string",
            "description": "Repository name to search for dead code",
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
    "required": ["repository"],
}


def _pluralize(kind: str | None) -> str:
    """Return a plural label like 'functions', 'classes', or 'symbols'."""
    if not kind:
        return "symbols"
    if kind.endswith("s"):
        return f"{kind}es"
    if kind.endswith("y") and len(kind) > 1 and kind[-2].lower() not in "aeiou":
        return f"{kind[:-1]}ies"
    return f"{kind}s"


async def handle(
    client: Inxr2Client,
    arguments: dict[str, Any],
    frontend_url: str | None = None,
) -> str:
    repository = arguments["repository"]
    kind = arguments.get("kind")
    limit = min(arguments.get("limit", 20), 100)
    branch = arguments.get("branch")
    commit = arguments.get("commit")

    # Resolve repository_id
    repo_data = await client.get(f"/api/repositories/by-name/{repository}")
    repository_id = repo_data["id"]

    # Fetch symbols (get a large batch to check for dead code)
    # Use regex mode with "." to match all symbol names
    params: dict[str, Any] = {
        "q": ".",
        "mode": "regex",
        "limit": 200,
        "repository_id": repository_id,
    }
    if kind:
        params["kind"] = kind
    if branch:
        params["branch"] = branch
    if commit:
        params["commit"] = commit
    symbols_data = await client.get("/api/symbols", params=params)

    items = symbols_data.get("items", [])
    symbols_total = symbols_data.get("total", len(items))
    scan_incomplete = symbols_total > len(items)

    if not items:
        kind_str = f" {_pluralize(kind)}" if kind else " symbols"
        return f"No{kind_str} found in '{repository}'."

    # Check references for each symbol (N+1 calls — acceptable for v1)
    async def has_references(symbol: dict[str, Any]) -> bool:
        ref_params: dict[str, Any] = {"by_name": "true", "limit": 1}
        if branch:
            ref_params["branch"] = branch
        if commit:
            ref_params["commit"] = commit
        refs_data = await client.get(
            f"/api/symbols/{symbol['id']}/references",
            params=ref_params,
        )
        return len(refs_data.get("items", [])) > 0

    results = await asyncio.gather(*[has_references(s) for s in items])
    dead_symbols = [
        s for s, has_refs in zip(items, results, strict=True) if not has_refs
    ]

    # Deduplicate by name — header declarations may appear alongside implementations
    seen_names: set[str] = set()
    unique_dead: list[dict[str, Any]] = []
    for symbol in dead_symbols:
        name = symbol.get("name", "")
        if name not in seen_names:
            seen_names.add(name)
            unique_dead.append(symbol)

    if not unique_dead:
        kind_str = f" {_pluralize(kind)}" if kind else " symbols"
        return f"No dead code found in '{repository}' — all{kind_str} have references."

    # Apply limit after dedup
    total = len(unique_dead)
    unique_dead = unique_dead[:limit]

    # Format output
    kind_str = f" {_pluralize(kind)}" if kind else " symbols"
    header = f"Dead code in '{repository}': {total}{kind_str} with no references" + (
        f" (showing {limit})" if total > limit else ""
    )
    if scan_incomplete:
        header += (
            f"\nNote: scanned {len(items)} of {symbols_total} symbols"
            " — results may be incomplete."
        )
    lines = [header]

    for symbol in unique_dead:
        file_path = symbol.get("file_path", "unknown")
        line = symbol.get("start_line", "?")
        kind_label = symbol.get("kind", "unknown")
        name = symbol.get("name", "unknown")
        sig = symbol.get("signature", "")

        lines.append(f"\n  [{kind_label}] {name}")
        lines.append(f"    {file_path}:{line}")
        if sig:
            lines.append(f"    {sig}")

        if frontend_url and file_path and file_path != "unknown":
            url = build_browse_url(
                frontend_url,
                repository,
                file_path,
                line=symbol.get("start_line"),
                branch=branch,
                commit=commit,
            )
            lines.append(f"    {url}")

    return "\n".join(lines)
