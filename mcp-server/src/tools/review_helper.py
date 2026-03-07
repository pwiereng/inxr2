"""review_helper tool: Blast radius analysis for commits."""

from __future__ import annotations

import asyncio
from typing import Any

from src.client import Inxr2Client
from src.staleness import check_staleness, prepend_warning
from src.urls import build_browse_url

TOOL_NAME = "review_helper"

TOOL_DESCRIPTION = (
    "Analyze the blast radius of a commit: what files changed, what symbols "
    "are in those files, and what references those symbols across the codebase. "
    "Useful for understanding the impact of a change during code review."
)

TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "repository": {
            "type": "string",
            "description": "Repository name to analyze",
        },
        "commit": {
            "type": "string",
            "description": "Commit hash (short or full) to analyze",
        },
        "limit": {
            "type": "integer",
            "description": "Max symbols to analyze for references (default 30, max 100)",
            "default": 30,
        },
    },
    "required": ["repository", "commit"],
}


def _flatten_tree(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten a nested tree structure into a list of file nodes."""
    files: list[dict[str, Any]] = []
    for node in nodes:
        if node.get("type") == "file":
            files.append(node)
        children = node.get("children")
        if children:
            files.extend(_flatten_tree(children))
    return files


async def handle(
    client: Inxr2Client,
    arguments: dict[str, Any],
    frontend_url: str | None = None,
) -> str:
    repository = arguments["repository"]
    commit_prefix = arguments["commit"]
    limit = min(arguments.get("limit", 30), 100)

    # Step 1: Resolve repository and check staleness
    staleness = await check_staleness(client, repository)
    staleness_warning = staleness.warning
    repository_id = staleness.repo_data["id"]

    # Step 2: Find the commit by matching prefix
    commits_data = await client.get(
        "/api/commits", params={"repo": repository, "limit": 5000}
    )
    matching_commits = [
        c
        for c in commits_data.get("commits", [])
        if c["hash"].startswith(commit_prefix) or c["short_hash"] == commit_prefix
    ]

    if not matching_commits:
        return prepend_warning(
            f"Commit '{commit_prefix}' not found in '{repository}'.",
            staleness_warning,
        )

    if len(matching_commits) > 1:
        candidates = ", ".join(c["short_hash"] for c in matching_commits[:10])
        return prepend_warning(
            f"Commit prefix '{commit_prefix}' is ambiguous in '{repository}'. "
            f"Matching commits: {candidates}. "
            "Please provide a longer prefix or a full hash.",
            staleness_warning,
        )

    matching_commit = matching_commits[0]

    full_hash = matching_commit["hash"]
    short_hash = matching_commit["short_hash"]
    message = matching_commit.get("message", "")

    # Step 3: Get changed files at this commit
    tree_data = await client.get(
        f"/api/repositories/by-name/{repository}/tree",
        params={"commit": full_hash, "changed_only": "true"},
    )
    changed_files = _flatten_tree(tree_data.get("root", []))
    changed_paths = {f["path"] for f in changed_files}

    if not changed_files:
        lines = [
            f"Blast radius for commit {short_hash} in '{repository}':",
            f'  "{message}"',
            "",
            "Changed files: 0",
            "No changed files found at this commit.",
        ]
        return prepend_warning("\n".join(lines), staleness_warning)

    # Step 4: Get symbols in changed files
    # Fetch symbols for this repo and filter by changed file paths
    symbols_data = await client.get(
        "/api/symbols",
        params={
            "q": ".",
            "mode": "regex",
            "limit": 200,
            "repository_id": repository_id,
            "commit": full_hash,
        },
    )
    all_symbols = symbols_data.get("items", [])
    symbols_total = symbols_data.get("total", len(all_symbols))
    scan_incomplete = symbols_total > len(all_symbols)
    changed_symbols = [s for s in all_symbols if s.get("file_path") in changed_paths]

    # Deduplicate symbols by name+file_path
    seen: set[tuple[str, str]] = set()
    unique_symbols: list[dict[str, Any]] = []
    for s in changed_symbols:
        key = (s.get("name", ""), s.get("file_path", ""))
        if key not in seen:
            seen.add(key)
            unique_symbols.append(s)

    # Apply limit for reference lookups
    symbols_to_check = unique_symbols[:limit]

    # Step 5: Get downstream references for each symbol
    async def fetch_refs(symbol: dict[str, Any]) -> list[dict[str, Any]]:
        ref_params: dict[str, Any] = {
            "by_name": "true",
            "limit": 50,
            "commit": full_hash,
        }
        refs_data = await client.get(
            f"/api/symbols/{symbol['id']}/references",
            params=ref_params,
        )
        items: list[dict[str, Any]] = refs_data.get("items", [])
        return items

    ref_results = await asyncio.gather(*[fetch_refs(s) for s in symbols_to_check])

    # Build symbol -> references mapping
    symbol_refs: list[tuple[dict[str, Any], list[dict[str, Any]]]] = list(
        zip(symbols_to_check, ref_results, strict=True)
    )

    total_refs = sum(len(refs) for _, refs in symbol_refs)

    # Step 6: Format output
    lines = [
        f"Blast radius for commit {short_hash} in '{repository}':",
        f'  "{message}"',
    ]

    # Changed files section
    lines.append(f"\nChanged files: {len(changed_files)}")
    for f in changed_files:
        path = f["path"]
        line_entry = f"  {path}"
        if frontend_url:
            url = build_browse_url(frontend_url, repository, path, commit=full_hash)
            line_entry += f"\n    {url}"
        lines.append(line_entry)

    # Symbols section
    lines.append(f"\nSymbols in changed files: {len(unique_symbols)}")
    if scan_incomplete:
        lines.append(
            f"  Note: scanned {len(all_symbols)} of {symbols_total} symbols"
            " — results may be incomplete."
        )
    if len(unique_symbols) > limit:
        lines.append(f"  (showing first {limit} for reference analysis)")
    for s in symbols_to_check:
        kind = s.get("kind", "unknown")
        name = s.get("name", "unknown")
        file_path = s.get("file_path", "unknown")
        start_line = s.get("start_line", "?")
        lines.append(f"  [{kind}] {name} ({file_path}:{start_line})")

    # Downstream references section
    lines.append(f"\nDownstream references: {total_refs}")
    if total_refs == 0:
        lines.append("  No downstream references found.")
    else:
        for symbol, refs in symbol_refs:
            if not refs:
                continue
            name = symbol.get("name", "unknown")
            lines.append(
                f"  [{symbol.get('kind', 'unknown')}] {name} "
                f"— referenced from {len(refs)} location{'s' if len(refs) != 1 else ''}"
            )
            for ref in refs:
                ref_file = ref.get("source_file_path", "unknown")
                ref_line = ref.get("source_line")
                ref_type = ref.get("reference_type", "unknown")
                location = f"{ref_file}:{ref_line}" if ref_line else ref_file
                lines.append(f"    [{ref_type}] {location}")

                if frontend_url and ref_file and ref_file != "unknown":
                    url = build_browse_url(
                        frontend_url,
                        repository,
                        ref_file,
                        line=ref_line,
                        commit=full_hash,
                    )
                    lines.append(f"    {url}")

    return prepend_warning("\n".join(lines), staleness_warning)
