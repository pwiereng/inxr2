# INXR2 User Guide

INXR2 is a cross-reference code browser for git repositories. It lets you browse, search, and navigate code across multiple repositories with semantic understanding and time-travel capabilities.

## Navigation Bar

The top bar is visible on every page and contains:

- **Home button** — returns to the landing page
- **Repository selector** — choose which repository to explore
- **Branch selector** — switch between indexed branches (the default branch is shown with a star)
- **Commit selector** — pick a specific commit to view code as it existed at that point in time
- **Theme toggle** — switch between light and dark mode

## Browse

The main code exploration view. Select a repository to see its file tree and source code.

**File tree** — the left panel shows the directory structure. Click any file to view it. Type in the filter box at the top to narrow the tree by file name.

**Code viewer** — displays source code with syntax highlighting. For semantically indexed languages, clicking a symbol (function, class, variable) opens the references panel on the right, showing everywhere that symbol is used.

**Navigation features:**

- **Jump to definition** — click any reference in the references panel to navigate directly to where a symbol is defined
- **Find references** — click a symbol in the code to see all of its usages across the repository
- **Line highlighting** — click a line number to highlight it and update the URL for sharing. Shift-click a second line to highlight a range.

**Blame** — toggle the blame button in the toolbar to show git blame annotations alongside the code. Each annotation shows who last modified that line and when. Click a blame commit hash to jump to that commit in the History tab.

**Diff view** — click the compare button to enter side-by-side diff mode. Select a different branch or commit on the right side to compare file versions. The diff view preserves syntax highlighting and symbol navigation. Click the swap button to reverse the comparison direction.

**Markdown rendering** — Markdown files can be toggled between rendered view and raw source using the toggle in the toolbar.

**Copy buttons** — commit hashes and branch names display copy-to-clipboard buttons on hover. Click to copy the short hash; shift-click to copy the full hash.

## Search

Search across all indexed repositories with multiple modes and filters.

**Search modes:**

- **Keyword** — matches individual words anywhere in the content (default)
- **Phrase** — matches the exact phrase as typed
- **Regex** — full regular expression pattern matching
- **File** — search by file name or path

**Source type filters** narrow results by content type. You can enable multiple filters simultaneously:

- **Definitions** — symbol definitions (functions, classes, methods, variables). These come from the semantic index.
- **References** — symbol usages (calls, imports, type annotations). Also from the semantic index.
- **Comments** — code comments
- **Docstrings** — documentation strings
- **Commit Messages** — git commit messages
- **File Content** — raw file content (full-text search)

By default, all source types except Definitions and References are selected. Enable Definitions to include semantic symbol search results alongside text results.

**Extension filter** — filter results by file extension using the dropdown. You can hide specific extensions to reduce noise, or use "Hide all" / "Show all" to quickly toggle.

**Clicking results** — file-based results navigate to the Browse tab at the matching line. Commit message results navigate to the History tab.

## History

View the git commit history for the selected repository and branch. Each entry shows the commit hash (with copy button), author, date, and commit message.

Indexed commits are highlighted and clickable — selecting one navigates to the Browse tab to view the full codebase at that commit. Non-indexed commits are shown but grayed out.

## Shareable URLs

Every view in INXR2 produces a bookmarkable, shareable URL. The URL captures:

- Repository, branch, and commit selection
- Current file and path in Browse
- Highlighted line or line range
- Search query, mode, and active filters
- Diff mode state (branch and commit being compared)

Copy the URL from your browser's address bar to share a specific view with a colleague.

## Supported Languages

**With full semantic indexing** (jump to definition, find references, symbol search):

- Python
- TypeScript / JavaScript
- C / C++
- Java
- C#
- Go
- Ruby

**All other languages** are displayed with syntax highlighting and included in text search, but do not have cross-reference navigation.

## MCP Server (AI Assistant Integration)

INXR2 includes an MCP (Model Context Protocol) server that exposes its code intelligence as tools for AI assistants like Claude Desktop, Cursor, and Claude Code. This lets your AI assistant search symbols, find references, and navigate code across all your indexed repositories.

### Available Tools

#### `list_repositories`

List all indexed repositories with their branches and statistics.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `detail` | boolean | no | Include branches and commit counts (default: false) |

**Example use:** "What repositories are indexed in INXR2?"

#### `search_symbols`

Find symbol definitions by name using semantic search. Returns functions, classes, methods, and variables matching the query.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Search query for symbol name |
| `repository` | string | no | Filter to a specific repository |
| `kind` | string | no | Filter by kind: `function`, `class`, `method`, `variable`, etc. |
| `limit` | integer | no | Max results (default: 20, max: 100) |
| `branch` | string | no | Branch to search in (defaults to latest indexed) |
| `commit` | string | no | Specific commit hash (overrides branch, requires `repository`) |

**Example use:** "Find all classes named Controller in the backend repo."

#### `find_references`

Find all usages of a symbol across all indexed repositories. Shows where a function is called, a class is instantiated, a variable is read, etc.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Symbol name to find references for |
| `repository` | string | no | Filter to a specific repository |
| `ref_type` | string | no | Filter by type: `import`, `call`, `usage`, `type_annotation` |
| `branch` | string | no | Branch to search in (defaults to latest indexed) |
| `commit` | string | no | Specific commit hash (overrides branch, requires `repository`) |

**Example use:** "Where is the `authenticate` function called?"

#### `go_to_definition`

Jump to the definition of a symbol. Works across repositories when the same symbol name exists in multiple places.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Symbol name to find |
| `repository` | string | no | Filter to a specific repository |
| `file_path` | string | no | Filter to a specific file path |
| `commit` | string | no | Specific commit hash (requires `repository`) |

**Example use:** "Where is `DatabaseConnection` defined?"

#### `search_code`

Full-text or regex search across all indexed files. Searches file content, comments, docstrings, and commit messages.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Search query or regex pattern |
| `repository` | string | no | Filter to a specific repository |
| `mode` | string | no | `keyword` (default), `phrase`, or `regex` |
| `extensions` | string | no | Comma-separated file extensions to filter (e.g., `py,ts`) |
| `limit` | integer | no | Max results (default: 20, max: 100) |
| `branch` | string | no | Branch to search in (defaults to latest indexed) |
| `commit` | string | no | Specific commit hash (overrides branch, requires `repository`) |

**Example use:** "Search for TODO comments in Python files."

#### `find_dead_code`

Find symbol definitions that have zero references anywhere in the repository. Useful for identifying unused functions, classes, or variables that may be safe to remove.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `repository` | string | yes | Repository name to analyze |
| `kind` | string | no | Filter by kind: `function`, `class`, `method`, `variable`, etc. |
| `limit` | integer | no | Max results (default: 20, max: 100) |

**Example use:** "Find unused functions in the backend repo."

#### `review_helper`

Analyze the blast radius of a specific commit. Shows which files were changed, what symbols are defined in those files, and what other code references those symbols. Useful for understanding the downstream impact of a change.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `repository` | string | yes | Repository name to analyze |
| `commit` | string | yes | Commit hash (short or full) to analyze |
| `limit` | integer | no | Max symbols to analyze for references (default: 30, max: 100) |

**Example use:** "What's the blast radius of commit abc1234?"

### Setting Up MCP

#### Claude Desktop

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

#### Claude Code

Add a `.mcp.json` file to your project root:

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

#### Cursor

Add the following in Cursor settings under MCP Servers:

```json
{
  "inxr2": {
    "command": "python",
    "args": ["-m", "src.server"],
    "cwd": "/path/to/inxr2/mcp-server",
    "env": {
      "INXR2_API_URL": "http://localhost:8000"
    }
  }
}
```

#### SSE Transport (Docker)

If INXR2 is running in Docker, the MCP server is also available via SSE at `http://localhost:3000/sse`. You can configure your AI assistant to connect to this URL instead of using the stdio transport shown above.

#### Verifying the Connection

Once configured, ask your AI assistant to "list repositories in INXR2" to verify the MCP connection is working. It should return a list of your indexed repositories.

### Staleness Warnings

All MCP tools automatically detect when the indexed data is behind the latest git commits and include a warning in the response, along with the hash of the last indexed commit.
