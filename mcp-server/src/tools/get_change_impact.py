"""get_change_impact tool: analyze what needs to change when a symbol is modified."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from src.client import Inxr2Client
from src.staleness import check_staleness, prepend_warning
from src.urls import build_browse_url

TOOL_NAME = "get_change_impact"

TOOL_DESCRIPTION = (
    "Analyze the change impact of modifying a symbol: which files directly depend "
    "on it, grouped by type (source, test, config). "
    "Answers 'If I modify this symbol, what else needs to change?' "
    "Use depth=2 to include indirect (transitive) dependents."
)

TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "Symbol name to analyze (e.g. 'DatabaseConnection')",
        },
        "repository": {
            "type": "string",
            "description": "Repository name",
        },
        "branch": {
            "type": "string",
            "description": "Branch name (optional, defaults to latest indexed)",
        },
        "commit": {
            "type": "string",
            "description": "Specific commit hash (optional, overrides branch)",
        },
        "depth": {
            "type": "integer",
            "description": "Transitive dependency depth (default: 1, max: 2)",
            "default": 1,
        },
    },
    "required": ["name", "repository"],
}

_TEST_PATTERNS = (
    "/test/",
    "/tests/",
    "/spec/",
    "/specs/",
    "/test_",
    "_test.",
    ".test.",
    ".spec.",
)
_CONFIG_EXTENSIONS = frozenset(
    {".yaml", ".yml", ".toml", ".json", ".ini", ".cfg", ".env"}
)
_CONFIG_BASENAMES = frozenset(
    {"dockerfile", "makefile", "justfile", ".editorconfig", ".gitignore"}
)

_MAX_L2_SYMBOLS = 20
_MAX_REFS_PER_FILE = 10


def _classify_file(path: str) -> str:
    """Classify a file as 'test', 'config', or 'source'."""
    lower = path.lower()
    for pattern in _TEST_PATTERNS:
        if pattern in lower:
            return "test"
    _, ext = os.path.splitext(lower)
    if ext in _CONFIG_EXTENSIONS or os.path.basename(lower) in _CONFIG_BASENAMES:
        return "config"
    return "source"


async def handle(
    client: Inxr2Client,
    arguments: dict[str, Any],
    frontend_url: str | None = None,
) -> str:
    name = arguments["name"]
    repository = arguments["repository"]
    branch = arguments.get("branch")
    commit = arguments.get("commit")
    depth = min(int(arguments.get("depth", 1)), 2)

    # Step 1: Resolve repository and check staleness
    staleness = await check_staleness(client, repository)
    staleness_warning = staleness.warning
    repository_id = staleness.repo_data["id"]

    # Step 2: Find the symbol definition
    symbol_params: dict[str, Any] = {"repository_id": repository_id}
    if branch:
        symbol_params["branch"] = branch
    if commit:
        symbol_params["commit"] = commit
    symbols_data = await client.get(
        f"/api/symbols/by-name/{name}", params=symbol_params
    )

    if not symbols_data["items"]:
        return prepend_warning(
            f"No symbols found matching '{name}' in '{repository}'.",
            staleness_warning,
        )

    # Deduplicate by ID
    seen_ids: set[int] = set()
    unique_symbols: list[dict[str, Any]] = []
    for sym in symbols_data["items"]:
        if sym["id"] not in seen_ids:
            seen_ids.add(sym["id"])
            unique_symbols.append(sym)

    # Step 3: Fetch direct references
    async def fetch_refs(symbol: dict[str, Any]) -> list[dict[str, Any]]:
        ref_params: dict[str, Any] = {"by_name": "true", "limit": 200}
        if branch:
            ref_params["branch"] = branch
        if commit:
            ref_params["commit"] = commit
        refs_data = await client.get(
            f"/api/symbols/{symbol['id']}/references", params=ref_params
        )
        return refs_data.get("items", [])  # type: ignore[no-any-return]

    ref_results = await asyncio.gather(*[fetch_refs(s) for s in unique_symbols])
    all_refs: list[dict[str, Any]] = [ref for refs in ref_results for ref in refs]

    # Step 4: Group by file and classify
    file_refs: dict[str, list[dict[str, Any]]] = {}
    for ref in all_refs:
        fp = ref.get("source_file_path") or "unknown"
        file_refs.setdefault(fp, []).append(ref)

    source_files = sorted(
        fp for fp in file_refs if fp != "unknown" and _classify_file(fp) == "source"
    )
    test_files = sorted(
        fp for fp in file_refs if fp != "unknown" and _classify_file(fp) == "test"
    )
    config_files = sorted(
        fp for fp in file_refs if fp != "unknown" and _classify_file(fp) == "config"
    )
    unknown_files = [fp for fp in file_refs if fp == "unknown"]

    total_refs = len(all_refs)
    total_files = len(file_refs)

    # Step 5: Format output
    lines: list[str] = []

    lines.append(f"Change impact for '{name}' in '{repository}':")
    for sym in unique_symbols:
        kind = sym.get("kind") or "unknown"
        fp = sym.get("file_path") or "unknown"
        line_no = sym.get("start_line", "?")
        lines.append(f"  Defined in: {fp}:{line_no} [{kind}]")
        if frontend_url and fp and fp != "unknown":
            url = build_browse_url(
                frontend_url,
                repository,
                fp,
                line=sym.get("start_line"),
                branch=branch,
                commit=commit,
            )
            lines.append(f"    {url}")

    lines.append(
        f"\nDirect references: {total_refs} across "
        f"{total_files} file{'s' if total_files != 1 else ''}"
    )

    if total_refs == 0:
        lines.append("  No references found. This symbol may be unused.")
    else:

        def _append_file_group(grouped_files: list[str], label: str) -> None:
            if not grouped_files:
                return
            lines.append(f"\n  {label} ({len(grouped_files)}):")
            for file_path in grouped_files:
                refs = file_refs[file_path]
                lines.append(
                    f"    {file_path} ({len(refs)} ref{'s' if len(refs) != 1 else ''})"
                )
                for ref in refs[:_MAX_REFS_PER_FILE]:
                    ref_line = ref.get("source_line")
                    ref_type = ref.get("reference_type", "unknown")
                    ref_text = ref.get("reference_text", "")
                    location = f"{file_path}:{ref_line}" if ref_line else file_path
                    entry = f"      [{ref_type}] {location}"
                    if ref_text:
                        entry += f" — {ref_text}"
                    lines.append(entry)
                    if frontend_url and file_path != "unknown":
                        url = build_browse_url(
                            frontend_url,
                            repository,
                            file_path,
                            line=ref_line,
                            branch=branch,
                            commit=commit,
                        )
                        lines.append(f"        {url}")
                if len(refs) > _MAX_REFS_PER_FILE:
                    lines.append(f"      ... and {len(refs) - _MAX_REFS_PER_FILE} more")

        _append_file_group(source_files, "Source files")
        _append_file_group(test_files, "Test files")
        _append_file_group(config_files, "Config files")
        if unknown_files:
            _append_file_group(unknown_files, "Unknown files")

        lines.append("\nAffected files summary:")
        if source_files:
            lines.append(f"  Source ({len(source_files)}): {', '.join(source_files)}")
        if test_files:
            lines.append(f"  Tests  ({len(test_files)}): {', '.join(test_files)}")
        if config_files:
            lines.append(f"  Config ({len(config_files)}): {', '.join(config_files)}")

    # Step 6: Transitive impact (depth > 1)
    if depth > 1 and file_refs:
        lines.append(f"\nTransitive impact (depth={depth}):")
        l1_paths = set(file_refs.keys()) - {"unknown"}
        if not l1_paths:
            lines.append("  No level-1 files to analyze transitively.")
        else:
            # Paginate through symbols until all l1_paths are covered or exhausted
            _PAGE_SIZE = 500
            _MAX_SYMS = 10000
            all_syms: list[dict[str, Any]] = []
            sym_offset = 0
            while len(all_syms) < _MAX_SYMS:
                sym_params: dict[str, Any] = {
                    "q": ".",
                    "mode": "regex",
                    "limit": _PAGE_SIZE,
                    "offset": sym_offset,
                    "repository_id": repository_id,
                }
                if commit:
                    sym_params["commit"] = commit
                page_data = await client.get("/api/symbols", params=sym_params)
                page_items: list[dict[str, Any]] = page_data.get("items", [])
                all_syms.extend(page_items)
                covered = {
                    s["file_path"] for s in all_syms if s.get("file_path") in l1_paths
                }
                if covered == l1_paths or len(page_items) < _PAGE_SIZE:
                    break
                sym_offset += _PAGE_SIZE
            # Symbols in level-1 files, excluding the target itself
            l1_symbols = [
                s
                for s in all_syms
                if s.get("file_path") in l1_paths and s.get("name") != name
            ]

            if not l1_symbols:
                lines.append(
                    "  No symbols found in level-1 files for transitive analysis."
                )
            else:
                l1_sample = l1_symbols[:_MAX_L2_SYMBOLS]
                if len(l1_symbols) > _MAX_L2_SYMBOLS:
                    lines.append(
                        f"  Note: analyzing {_MAX_L2_SYMBOLS} of {len(l1_symbols)} "
                        "symbols in level-1 files."
                    )

                async def fetch_l2_refs(
                    sym: dict[str, Any],
                ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
                    rp: dict[str, Any] = {"by_name": "true", "limit": 50}
                    if branch:
                        rp["branch"] = branch
                    if commit:
                        rp["commit"] = commit
                    rd = await client.get(
                        f"/api/symbols/{sym['id']}/references", params=rp
                    )
                    items: list[dict[str, Any]] = rd.get("items", [])
                    return sym, items

                l2_raw = await asyncio.gather(*[fetch_l2_refs(s) for s in l1_sample])
                l2_results: list[tuple[dict[str, Any], list[dict[str, Any]]]] = list(
                    l2_raw
                )

                # Collect new (level-2) files not already in level-1 refs
                l2_new: dict[str, set[str]] = {}
                for sym, refs in l2_results:
                    sym_name = sym.get("name", "unknown")
                    for ref in refs:
                        l2_fp = ref.get("source_file_path") or "unknown"
                        if l2_fp not in file_refs and l2_fp != "unknown":
                            l2_new.setdefault(l2_fp, set()).add(sym_name)

                if not l2_new:
                    lines.append(
                        f"  No additional files at depth 2 "
                        f"(beyond the {total_files} direct "
                        f"file{'s' if total_files != 1 else ''})."
                    )
                else:
                    lines.append(f"  Additional files at depth 2 ({len(l2_new)}):")
                    for l2_fp in sorted(l2_new.keys()):
                        via = ", ".join(sorted(l2_new[l2_fp]))
                        cat = _classify_file(l2_fp)
                        lines.append(f"    [{cat}] {l2_fp} (via: {via})")

    return prepend_warning("\n".join(lines), staleness_warning)
