# INXR2 MCP Server

MCP (Model Context Protocol) server that exposes INXR2's code intelligence as tools for AI assistants (Claude Desktop, Cursor, etc.).

## How INXR2 Indexing Works

INXR2 pre-parses every file in every indexed repository using Tree-sitter and stores the results in PostgreSQL. This means:

- **Symbol queries are instant** — no scanning, just index lookups.
- **Results are semantic** — `search_symbols` finds a class definition, not the string `"class Foo"` in comments.
- **Cross-repo by default** — references and definitions span all indexed repositories in one call.
- **Temporal** — every query can be scoped to a specific commit or branch.

**What is indexed:** Symbols (definitions), references (usages), file metadata, and full-text content for `search_code`. The index reflects the state at the last `inxr2 index` run — it is not a live file watcher.

**When to use INXR2 tools vs. Grep/Read:**

| Task | Use |
|------|-----|
| Find where a class/function is defined | `go_to_definition` or `search_symbols` |
| Find all callers of a function | `find_references` |
| Understand a file's structure before reading it | `get_file_structure` |
| See what breaks if I change a symbol | `get_change_impact` |
| Find a string pattern, regex, or comment text | `search_code` |
| Read a file you've already located | Grep/Read (skip MCP) |
| Navigate files you added in a worktree branch | Grep/Read (not indexed) |

## Start Here

Three common workflows:

**Audit (understand unfamiliar code):**
1. `list_repositories` — see what's indexed
2. `search_symbols` — find the entry point or key class
3. `explain_symbol` — get definition + all usages in one call
4. `get_file_structure` — survey a file before reading it

**Refactor (change a type or interface):**
1. `get_change_impact` — map every direct dependent before touching anything
2. `find_references` — drill into a specific reference type (e.g. `type_annotation`)
3. `go_to_definition` — jump to the definition to read context

**Navigate (trace a call chain):**
1. `go_to_definition` — start at the symbol
2. `find_references` — find callers
3. Repeat from step 1 on each caller

## Tools

### `list_repositories`
List all indexed repositories with their branches and statistics.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `detail` | boolean | no | Include branches and commit counts (default false) |

### `search_symbols`
Find symbol definitions by name (semantic, not text).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Search query for symbol name |
| `repository` | string | no | Filter to a specific repository |
| `kind` | string | no | Filter by kind: `function`, `class`, `method`, `variable`, etc. |
| `limit` | integer | no | Max results (default 20, max 100) |
| `branch` | string | no | Branch to search in (defaults to latest indexed) |
| `commit` | string | no | Specific commit hash (overrides branch, requires `repository`) |

### `find_references`
Find all usages of a symbol across all indexed repositories.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Symbol name to find references for |
| `repository` | string | no | Filter to a specific repository |
| `ref_type` | string | no | Filter by type: `import`, `call`, `usage`, `type_annotation` |
| `branch` | string | no | Branch to search in (defaults to latest indexed) |
| `commit` | string | no | Specific commit hash (overrides branch, requires `repository`) |

### `go_to_definition`
Jump to the definition of a symbol (works cross-repo).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Symbol name to find |
| `repository` | string | no | Filter to a specific repository |
| `file_path` | string | no | Filter to a specific file path |
| `commit` | string | no | Specific commit hash (requires `repository`) |

### `search_code`
Full-text or regex search across all indexed repos. Searches file body content — useful for finding string literals, patterns, comments, or any text that isn't a symbol definition or reference.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Search query or regex pattern |
| `repository` | string | no | Filter to a specific repository |
| `mode` | string | no | `keyword` (default), `phrase`, or `regex` |
| `extensions` | string | no | Comma-separated file extensions (e.g. `py,ts`) |
| `source_only` | boolean | no | Exclude test files from results (default: false) |
| `limit` | integer | no | Max results (default 20, max 100) |
| `branch` | string | no | Branch to search in (defaults to latest indexed) |
| `commit` | string | no | Specific commit hash (overrides branch, requires `repository`) |

Example — find all places a deprecated constant is referenced in source files:
```python
asyncio.run(call("search_code", {
    "query": "LEGACY_API_KEY",
    "repository": "inxr2",
    "source_only": True
}))
# → 3 matches: config/settings.py:14, adapters/api/auth.py:31, tests/…
```

### `get_file_structure`
Get a token-efficient symbol overview of a file — classes, functions, methods, and their children — without the full source code. Useful for surveying a file's shape before deciding what to read.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | yes | File path within the repository (e.g. `src/inxr2/domain/entities/symbol.py`) |
| `repository` | string | yes | Repository name |
| `branch` | string | no | Branch to search in (defaults to latest indexed) |
| `commit` | string | no | Specific commit hash (overrides branch) |
| `include_signatures` | boolean | no | Include parameter lists in symbol names (default: true) |
| `include_docstrings` | boolean | no | Include first line of docstrings (default: false) |

### `get_change_impact`
Analyze what needs to change when a symbol is modified: which files directly depend on it, grouped by type (source, test, config). Use before touching any type signature or interface.

Returns all symbols that **directly** reference the queried symbol — one level deep by default. Use `depth=2` for transitive dependents, but expect more noise.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Symbol name to analyze (e.g. `DatabaseConnection`) |
| `repository` | string | yes | Repository name |
| `branch` | string | no | Branch to search in (defaults to latest indexed) |
| `commit` | string | no | Specific commit hash (overrides branch) |
| `depth` | integer | no | Transitive dependency depth (default: 1, max: 2) |

Example output:
```
get_change_impact "SymbolRepository" → 12 direct dependents across 5 files
  source: adapters/persistence/postgres_symbol_repo.py, application/use_cases/…
  test:   tests/integration/…, tests/unit/…
```

### `explain_symbol`
Rich context about a symbol in one call: definition location, docstring, signature, and references grouped by type (imports, calls, type annotations). Shows up to 500 references total, up to 5 per type in the summary output.

Use this instead of calling `search_symbols` + `find_references` separately. The `branch` parameter filters **references only** — it does not affect the definition lookup.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Exact symbol name (e.g. `SearchSymbolsUseCase`) |
| `repository` | string | no | Filter to a specific repository |
| `branch` | string | no | Filter references by branch (does not affect definition lookup) |
| `commit` | string | no | Specific commit hash (overrides branch) |

Example output:
```
SearchSymbolsUseCase
  Defined in: src/inxr2/application/use_cases/symbols/search_symbols.py:42
  Kind: class
  References: 8 total
    imports (3): adapters/api/routes/symbols.py, adapters/cli/…, …
    calls (2): routes/symbols.py:88, routes/symbols.py:102
    type_annotations (3): …
```

### `find_dead_code`
Find symbol definitions with zero references (potential dead code).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `repository` | string | yes | Repository name to analyze |
| `kind` | string | no | Filter by kind: `function`, `class`, `method`, `variable`, etc. |
| `limit` | integer | no | Max results (default 20, max 100) |

### `review_helper`
Analyze the blast radius of a commit: changed files, symbols in those files, and downstream references.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `repository` | string | yes | Repository name to analyze |
| `commit` | string | yes | Commit hash (short or full) to analyze |
| `limit` | integer | no | Max symbols to analyze for references (default 30, max 100) |

## Features

### Staleness Warnings
All tools automatically detect when the indexed data is behind the latest git commits and prepend a warning to the output, including the hash of the last indexed commit.

### Browse URLs
When `INXR2_FRONTEND_URL` is set, tool responses include clickable links to the INXR2 web UI for each file, symbol, and reference location.

## Architecture

```
AI Assistant (Claude/Cursor)
    | MCP protocol (stdio or SSE)
MCP Server (this)
    | HTTP requests (httpx)
INXR2 API (FastAPI, port 8000)
    | SQL
PostgreSQL
```

The MCP server does **not** access the database directly. It calls INXR2's existing HTTP API via httpx.

## Running

The MCP server runs inside the `inxr2-dev` container automatically (SSE transport on port 3000). It starts as a background process during container startup.

```bash
# Start the dev container (MCP server starts automatically)
docker compose -f docker-compose.dev.yml up -d --build

# Verify MCP server is running
curl http://localhost:3000/sse

# View MCP server logs (inside container)
docker exec inxr2-dev cat /tmp/mcp-server.log
```

> **Hitting `-32602 Invalid request parameters` on every tool call** (including
> parameter-less ones like `list_repositories`)? That's a stale connection after
> a server restart, not a parameter problem — see
> [MCP troubleshooting](../docs/mcp-troubleshooting.md).

### Local (stdio transport)

```bash
cd mcp-server
pip install -e .
INXR2_API_URL=http://localhost:8000 python -m src.server
```

### Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "inxr2": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/inxr2/mcp-server",
      "env": {
        "INXR2_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

### Claude Code Configuration

Add to `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "inxr2": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/inxr2/mcp-server",
      "env": {
        "INXR2_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `INXR2_API_URL` | `http://localhost:8000` | INXR2 API base URL |
| `MCP_TRANSPORT` | `stdio` | Transport mode: `stdio` or `sse` |
| `MCP_PORT` | `3000` | Port for SSE transport |
| `INXR2_FRONTEND_URL` | _(unset)_ | Frontend URL for browse links (e.g., `http://localhost:5173`) |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
cd mcp-server && pytest tests/

# Tests use FakeInxr2Client (no HTTP calls needed)
```
