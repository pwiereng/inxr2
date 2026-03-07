# INXR2 MCP Server

MCP (Model Context Protocol) server that exposes INXR2's code intelligence as tools for AI assistants (Claude Desktop, Cursor, etc.).

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
Full-text or regex search across all indexed repos.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Search query or regex pattern |
| `repository` | string | no | Filter to a specific repository |
| `mode` | string | no | `keyword` (default), `phrase`, or `regex` |
| `extensions` | string | no | Comma-separated file extensions (e.g. `py,ts`) |
| `limit` | integer | no | Max results (default 20, max 100) |
| `branch` | string | no | Branch to search in (defaults to latest indexed) |
| `commit` | string | no | Specific commit hash (overrides branch, requires `repository`) |

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

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
cd mcp-server && pytest tests/

# Tests use FakeInxr2Client (no HTTP calls needed)
```
