"""search_code tool: Full-text/regex search across indexed repos."""

from __future__ import annotations

from typing import Any

from src.client import Inxr2Client
from src.errors import McpToolError
from src.staleness import check_staleness, prepend_warning
from src.urls import build_browse_url

TOOL_NAME = "search_code"

TOOL_DESCRIPTION = (
    "Full-text or regex search across all indexed repositories. "
    "Search code content, comments, and docstrings. "
    "Supports keyword, phrase, and regex modes. "
    "Use source_only=true to exclude documentation and config files."
)

# File extensions considered non-source (docs, config, data files).
# Used by source_only=True to filter results.
NON_SOURCE_EXTENSIONS = frozenset(
    {
        ".md",
        ".rst",
        ".txt",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".ini",
        ".cfg",
        ".html",
        ".htm",
        ".xml",
        ".csv",
        ".tsv",
        ".lock",
        ".log",
        ".env",
        ".gitignore",
        ".editorconfig",
        ".dockerignore",
    }
)

TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Search query (text or regex pattern)",
        },
        "repository": {
            "type": "string",
            "description": "Filter to a specific repository name (optional)",
        },
        "mode": {
            "type": "string",
            "description": "Search mode (default: keyword)",
            "enum": ["keyword", "phrase", "regex"],
            "default": "keyword",
        },
        "extensions": {
            "description": "File extensions to filter — comma-separated string (e.g. 'py,ts') or array (e.g. ['py','ts'])",
            "oneOf": [
                {"type": "string"},
                {"type": "array", "items": {"type": "string"}},
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
        "source_only": {
            "description": (
                "When true, exclude non-source files such as markdown docs, "
                "YAML configs, JSON, TOML, and other non-code file types. "
                "Default: false."
            ),
            "oneOf": [
                {"type": "boolean"},
                {"type": "string", "enum": ["true", "false"]},
            ],
            "default": False,
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
    mode = arguments.get("mode", "keyword")
    extensions_raw = arguments.get("extensions")
    # Accept array (["py", "ts"]) or comma-string ("py,ts"); [] → None
    if isinstance(extensions_raw, list):
        joined = ",".join(e for e in extensions_raw if e)
        extensions: str | None = joined if joined else None
    else:
        extensions = extensions_raw
    limit = min(arguments.get("limit", 20), 100)
    branch = arguments.get("branch")
    commit = arguments.get("commit")
    # Accept boolean true or string "true"
    source_only_raw = arguments.get("source_only", False)
    source_only = (
        source_only_raw
        if isinstance(source_only_raw, bool)
        else source_only_raw == "true"
    )

    # commit requires repository (API returns 400 otherwise)
    if commit and not repository:
        raise McpToolError("'commit' requires 'repository' to be specified.")

    # Resolve repository and check staleness
    staleness_warning = None
    repository_id = None
    if repository:
        staleness = await check_staleness(client, repository)
        staleness_warning = staleness.warning
        repository_id = staleness.repo_data["id"]

    # Search text
    params: dict[str, Any] = {"q": query, "mode": mode, "limit": limit}
    if repository_id is not None:
        params["repository_id"] = repository_id
    if extensions:
        ext_list = [e.strip() for e in extensions.split(",") if e.strip()]
        params["extensions"] = [e if e.startswith(".") else f".{e}" for e in ext_list]
    if branch:
        params["branch"] = branch
    if commit:
        params["commit_hash"] = commit
    search_data = await client.get("/api/search/text", params=params)

    all_results = search_data.get("results", [])
    # Only show file-backed results — skip commit messages (file_path is None)
    results = [r for r in all_results if r.get("file_path") is not None]

    # Optionally exclude non-source files (docs, configs, etc.)
    if source_only:
        results = [
            r
            for r in results
            if not any(
                (r.get("file_path") or "").endswith(ext)
                for ext in NON_SOURCE_EXTENSIONS
            )
        ]

    if not results:
        return prepend_warning(
            f"No results for '{query}' (mode: {mode}).", staleness_warning
        )

    # Format results
    lines = [f"Search results for '{query}' ({mode}): {len(results)} results"]
    for result in results:
        file_path = result.get("file_path", "unknown")
        line = result.get("source_line")
        repo_name = result.get("repository_name", "")
        content = result.get("content", "").strip()
        headline = result.get("headline", "")

        location = f"{repo_name}:{file_path}" if repo_name else file_path
        if line:
            location += f":{line}"

        lines.append(f"  {location}")
        # Prefer headline (has search term highlighting) over raw content
        display = headline if headline else content
        if display:
            # Truncate long lines
            if len(display) > 200:
                display = display[:200] + "..."
            lines.append(f"    {display}")

        # Add browse URL
        if frontend_url and repo_name and file_path and file_path != "unknown":
            url = build_browse_url(
                frontend_url,
                repo_name,
                file_path,
                line=line,
                branch=branch,
                commit=commit,
            )
            lines.append(f"    {url}")

    return prepend_warning("\n".join(lines), staleness_warning)
