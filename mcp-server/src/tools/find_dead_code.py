"""find_dead_code tool: Find symbols with zero references in a repository."""

from __future__ import annotations

from typing import Any

from src.client import Inxr2Client
from src.staleness import check_staleness, prepend_warning
from src.urls import build_browse_url

TOOL_NAME = "find_dead_code"

TOOL_DESCRIPTION = (
    "Find symbols with zero references (dead code) in a repository. "
    "Scans every symbol at the branch head (or at a given commit) and pages "
    "through the results. "
    "A symbol counts as referenced when any reference uses its name. "
    "Entry points run by the runtime or a test runner are excluded for Swift "
    "(@main, @Suite/@Test, XCTestCase) and Python (test_* functions, Test* "
    "classes, unittest.TestCase, pytest fixtures) only; in other languages "
    "main functions and tests are still listed. "
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
        "offset": {
            "type": "integer",
            "description": "Skip this many results, to page through (default 0)",
            "default": 0,
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
    offset = max(arguments.get("offset", 0), 0)
    branch = arguments.get("branch")
    commit = arguments.get("commit")

    # Resolve repository and check staleness
    staleness = await check_staleness(client, repository)
    staleness_warning = staleness.warning
    repository_id = staleness.repo_data["id"]

    # The backend scans every symbol in scope in one query
    params: dict[str, Any] = {
        "repository_id": repository_id,
        "limit": limit,
        "offset": offset,
    }
    if kind:
        params["kind"] = kind
    if branch:
        params["branch"] = branch
    if commit:
        params["commit"] = commit
    data = await client.get("/api/symbols/unreferenced", params=params)

    items: list[dict[str, Any]] = data.get("items", [])
    total: int = data.get("total", len(items))
    scanned: int = data.get("scanned", 0)
    entry_points: int = data.get("entry_points_excluded", 0)
    kind_str = f" {_pluralize(kind)}" if kind else " symbols"

    if scanned == 0:
        return prepend_warning(
            f"No{kind_str} found in '{repository}'.", staleness_warning
        )

    coverage = f"Scanned all {scanned}{kind_str}"
    if entry_points:
        coverage += (
            f"; {entry_points} entry points excluded"
            " (Swift @main, @Suite/@Test, XCTestCase; Python tests and fixtures)"
        )
    coverage += "."

    if total == 0:
        return prepend_warning(
            f"No dead code found in '{repository}' — all{kind_str} have references."
            f"\n{coverage}",
            staleness_warning,
        )

    header = f"Dead code in '{repository}': {total}{kind_str} with no references"
    if not items:
        return prepend_warning(
            f"{header}\nNo results at offset {offset}.\n{coverage}",
            staleness_warning,
        )
    end = offset + len(items)
    if offset > 0 or end < total:
        header += f" (showing {offset + 1}-{end}"
        if end < total:
            header += f"; pass offset={end} for more"
        header += ")"
    lines = [header, coverage]

    for symbol in items:
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

    return prepend_warning("\n".join(lines), staleness_warning)
