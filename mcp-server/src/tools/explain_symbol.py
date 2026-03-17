"""explain_symbol tool: Rich context about a symbol in one call."""

from __future__ import annotations

from typing import Any

from src.client import Inxr2Client
from src.staleness import check_staleness, prepend_warning
from src.urls import build_browse_url

TOOL_NAME = "explain_symbol"

TOOL_DESCRIPTION = (
    "Get rich context about a symbol in one call: definition location, docstring, "
    "signature, and all references grouped by type (imports, calls, type annotations, "
    "etc.). Ideal for understanding what a symbol is and how it's used across the "
    "codebase. Use this instead of calling search_symbols + find_references separately."
)

TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "Exact symbol name to explain (e.g. 'SearchSymbolsUseCase')",
        },
        "repository": {
            "type": "string",
            "description": "Filter to a specific repository name (optional)",
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

_MAX_REFS_PER_TYPE = 5


async def handle(
    client: Inxr2Client,
    arguments: dict[str, Any],
    frontend_url: str | None = None,
) -> str:
    name = arguments["name"]
    repository = arguments.get("repository")
    branch = arguments.get("branch")
    commit = arguments.get("commit")

    if commit and not repository:
        return "Error: 'commit' requires 'repository' to be specified."

    # Resolve repository and check staleness
    staleness_warning = None
    repository_id = None
    if repository:
        staleness = await check_staleness(client, repository)
        staleness_warning = staleness.warning
        repository_id = staleness.repo_data["id"]

    # Step 1: Find symbol by exact name
    symbol_params: dict[str, Any] = {}
    if repository_id is not None:
        symbol_params["repository_id"] = repository_id
    if commit:
        symbol_params["commit"] = commit
    symbols_data = await client.get(
        f"/api/symbols/by-name/{name}", params=symbol_params
    )

    items = symbols_data.get("items", [])
    if not items:
        return prepend_warning(f"Symbol '{name}' not found.", staleness_warning)

    # Use first match (most common case; prefer repository-scoped result)
    symbol = items[0]
    sym_file = symbol.get("file_path", "unknown")
    sym_line = symbol.get("start_line")
    sym_kind = symbol.get("kind", "unknown")
    sym_sig = symbol.get("signature", "")
    sym_doc = symbol.get("docstring", "")
    sym_id = symbol["id"]
    sym_repo_id = symbol.get("repository_id")

    # Step 2: Fetch references
    ref_params: dict[str, Any] = {"by_name": "true", "limit": 200}
    if branch:
        ref_params["branch"] = branch
    if commit:
        ref_params["commit"] = commit
    refs_data = await client.get(f"/api/symbols/{sym_id}/references", params=ref_params)
    all_refs: list[dict[str, Any]] = refs_data.get("items", [])
    total_refs = refs_data.get("total", len(all_refs))

    # Group references by type
    grouped: dict[str, list[dict[str, Any]]] = {}
    for ref in all_refs:
        ref_type = ref.get("reference_type", "usage")
        grouped.setdefault(ref_type, []).append(ref)

    # Build browse URL for definition
    repo_name_for_url: str | None = repository
    if frontend_url and not repo_name_for_url and sym_repo_id is not None:
        repos = await client.get("/api/repositories")
        repo_name_for_url = next(
            (r["name"] for r in repos if r["id"] == sym_repo_id), None
        )

    # --- Format output ---
    lines: list[str] = []

    # Header
    repo_label = f" — {repository}" if repository else ""
    lines.append(f"**{name}** ({sym_kind}){repo_label}")
    lines.append(f"Location: {sym_file}:{sym_line}")

    if sym_doc:
        doc = sym_doc if len(sym_doc) <= 200 else sym_doc[:200] + "..."
        lines.append(f"Docstring: {doc}")

    if sym_sig:
        lines.append(f"Signature: {sym_sig}")

    if frontend_url and repo_name_for_url and sym_file and sym_file != "unknown":
        url = build_browse_url(
            frontend_url,
            repo_name_for_url,
            sym_file,
            line=sym_line,
            branch=branch,
            commit=commit,
        )
        lines.append(f"URL: {url}")

    # References section
    lines.append("")
    if not all_refs:
        lines.append("References: none found")
    else:
        lines.append(f"References ({total_refs} total):")
        for ref_type, refs in sorted(grouped.items()):
            shown = refs[:_MAX_REFS_PER_TYPE]
            remainder = len(refs) - len(shown)
            entries = []
            for ref in shown:
                ref_file = ref.get("source_file_path", "unknown")
                ref_line = ref.get("source_line")
                loc = f"{ref_file}:{ref_line}" if ref_line else ref_file
                entries.append(loc)
            suffix = f" ... and {remainder} more" if remainder > 0 else ""
            lines.append(f"  {ref_type} ({len(refs)}): {', '.join(entries)}{suffix}")

    return prepend_warning("\n".join(lines), staleness_warning)
