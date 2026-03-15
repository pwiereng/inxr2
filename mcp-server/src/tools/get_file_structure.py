"""get_file_structure tool: Get a token-efficient symbol overview of a file."""

from __future__ import annotations

from typing import Any

from src.client import Inxr2Client
from src.staleness import check_staleness, prepend_warning
from src.urls import build_browse_url

TOOL_NAME = "get_file_structure"

TOOL_DESCRIPTION = (
    "Get a token-efficient symbol structure overview of a file. "
    "Returns a hierarchical view of all symbols (classes, functions, methods, "
    "properties, etc.) without the full source code. Useful for understanding "
    "a file's structure before reading it in detail."
)

TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": (
                "File path within the repository "
                "(e.g. 'src/inxr2/domain/entities/symbol.py')"
            ),
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
        "include_signatures": {
            "type": "boolean",
            "description": "Include parameter lists in symbol names (default: true)",
        },
        "include_docstrings": {
            "type": "boolean",
            "description": "Include first line of docstrings (default: false)",
        },
    },
    "required": ["file_path", "repository"],
}


async def handle(
    client: Inxr2Client,
    arguments: dict[str, Any],
    frontend_url: str | None = None,
) -> str:
    file_path = arguments["file_path"]
    repository = arguments["repository"]
    branch = arguments.get("branch")
    commit = arguments.get("commit")
    include_signatures = arguments.get("include_signatures", True)
    include_docstrings = arguments.get("include_docstrings", False)

    # Check staleness
    staleness = await check_staleness(client, repository)
    staleness_warning = staleness.warning

    # Fetch file structure from API
    params: dict[str, Any] = {"repo": repository, "path": file_path}
    if branch:
        params["branch"] = branch
    if commit:
        params["commit"] = commit

    data = await client.get("/api/symbols/file-structure", params=params)

    actual_path = data["file_path"]
    language = data.get("language") or "unknown"
    line_count = data.get("line_count")
    symbols: list[dict[str, Any]] = data.get("symbols", [])

    # Build header
    header_parts = [f"Language: {language}"]
    if line_count is not None:
        header_parts.append(f"Lines: {line_count}")
    header = " | ".join(header_parts)

    lines = [
        f"File: {actual_path}",
        header,
        "",
        "Symbols:",
    ]

    if not symbols:
        lines.append("  (no symbols found)")
    else:
        lines.extend(
            _render_symbol_tree(symbols, include_signatures, include_docstrings)
        )

    # Add browse URL
    if frontend_url:
        url = build_browse_url(
            frontend_url, repository, actual_path, branch=branch, commit=commit
        )
        lines.append("")
        lines.append(f"Browse: {url}")

    return prepend_warning("\n".join(lines), staleness_warning)


def _render_symbol_tree(
    symbols: list[dict[str, Any]],
    include_signatures: bool,
    include_docstrings: bool,
) -> list[str]:
    """Render symbols as an indented tree (top-level + one level of children)."""
    # Keep only structural symbols — classes, methods, functions, interfaces, etc.
    _KEEP_KINDS = {
        "class",
        "method",
        "function",
        "async_function",
        "constructor",
        "property",
        "interface",
        "enum",
        "module",
        "namespace",
        "struct",
        "trait",
        "type_alias",
    }
    symbols = [s for s in symbols if s["kind"] in _KEEP_KINDS]

    # Build parent → children map
    children_by_parent: dict[int, list[dict[str, Any]]] = {}
    top_level: list[dict[str, Any]] = []

    for sym in symbols:
        pid = sym.get("parent_symbol_id")
        if pid is None:
            top_level.append(sym)
        else:
            children_by_parent.setdefault(pid, []).append(sym)

    rendered_ids: set[int] = set()
    output: list[str] = []

    for sym in top_level:
        sym_id = sym["id"]
        rendered_ids.add(sym_id)
        output.append(_format_line(sym, "  ", include_signatures, include_docstrings))

        for child in children_by_parent.get(sym_id, []):
            rendered_ids.add(child["id"])
            output.append(
                _format_line(child, "    ", include_signatures, include_docstrings)
            )

    # Render any orphaned symbols (parent not in this file's top-level)
    for sym in symbols:
        if sym["id"] not in rendered_ids:
            output.append(
                _format_line(sym, "  ", include_signatures, include_docstrings)
            )

    return output


def _format_line(
    sym: dict[str, Any],
    indent: str,
    include_signatures: bool,
    include_docstrings: bool,
) -> str:
    kind = sym["kind"]
    name = sym["name"]
    start_line = sym["start_line"]
    end_line = sym["end_line"]
    signature = sym.get("signature") or ""
    docstring = sym.get("docstring") or ""

    # Build label: "{kind_prefix}{name}{signature}"
    if kind in ("function", "constructor"):
        prefix = "def "
    elif kind == "async_function":
        prefix = "async def "
    elif kind == "method":
        prefix = "def "
    else:
        prefix = f"{kind} "

    if include_signatures and signature:
        # Signatures starting with "(" attach directly; others get a space
        if signature.startswith("("):
            label = f"{prefix}{name}{signature}"
        else:
            label = f"{prefix}{name} {signature}"
    else:
        label = f"{prefix}{name}"

    line_range = f"[L{start_line}-{end_line}]"
    # Pad label to column 52 for alignment
    result = f"{indent}{label:<50} {line_range}"

    if include_docstrings and docstring:
        first_line = docstring.split("\n")[0].strip().strip("\"'").strip()
        if first_line:
            result += f"\n{indent}  # {first_line}"

    return result
