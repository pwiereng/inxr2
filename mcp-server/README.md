# INXR2 MCP Server

MCP (Model Context Protocol) server that exposes INXR2's code intelligence as tools for AI assistants (Claude Desktop, Cursor, etc.).

## Tools

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

### Docker (SSE transport)

```bash
# Start with the mcp profile
docker compose -f docker-compose.dev.yml --profile mcp up -d mcp

# Verify
curl http://localhost:3000/sse
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
