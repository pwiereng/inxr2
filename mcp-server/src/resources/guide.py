"""INXR2 Agent Guide — static MCP resource at inxr2://guide."""

RESOURCE_URI = "inxr2://guide"
RESOURCE_NAME = "INXR2 Agent Guide"
RESOURCE_DESCRIPTION = (
    "Orientation for AI agents: indexing model, tool selection, "
    "staleness check, and common workflows."
)

RESOURCE_CONTENT = """\
# INXR2 Agent Guide

## How the Index Works

INXR2 pre-parses every file in every indexed repository using Tree-sitter and
stores the results in PostgreSQL.

- **Symbol queries are instant** — no scanning, just index lookups.
- **Results are semantic** — finds definitions, not string matches (e.g. won't
  match the word "class" in a comment).
- **Cross-repo by default** — references and definitions span all indexed
  repositories in one call.
- **Temporal** — every query can be scoped to a specific commit or branch.
- **Not a live watcher** — the index reflects the state at the last
  `inxr2 index` run. Only indexed branches are searchable.

## Index Staleness Check

Call `list_repositories` (no arguments needed) and check `commits_behind` per
branch in the output:

```
  inxr2 (default: main, indexed branches: main)
    main: 142 commits, head: a1b2c3d, commits_behind: 0
```

- `commits_behind: 0` — index is current, trust all results.
- `commits_behind: ? (stale) ⚠️` — newer commits exist that aren't indexed.

When stale: fall back to Grep/Read for recently changed files, and **tell the
user the index is out of date** so they can re-index. INXR2 is a local service
running in Docker — the user controls the index and can update it by running:

```
inxr2 index --config config.yaml
```

(inside the dev container, e.g. `docker exec -it inxr2-dev bash`). Don't
silently work around a stale index — surface it so the user can fix it.

## Worktree Gap

The index reflects `main` only. Files you've added or changed in a worktree
branch won't be indexed. Use MCP for existing codebase navigation; use
Grep/Read for your own changes.

## When to Use INXR2 Tools vs. Grep/Read

| Task                                          | Use                            |
|-----------------------------------------------|--------------------------------|
| Find where a class/function is defined        | `go_to_definition` or `search_symbols` |
| Find all callers of a function                | `find_references`              |
| Understand a file's structure before reading  | `get_file_structure`           |
| See what breaks if I change a symbol          | `get_change_impact`            |
| Find a string pattern, regex, or comment text | `search_code`                  |
| Read a file you've already located            | Grep/Read (skip MCP)           |
| Navigate files you added in a worktree branch | Grep/Read (not indexed)        |

## Tool Selection Guide

- **Unfamiliar symbol** → `explain_symbol` (definition + all usages in one call)
- **Find callers** → `find_references` with `ref_type="call"`
- **Before changing a type/interface** → `get_change_impact` (maps blast radius)
- **Survey a file** → `get_file_structure` (token-efficient, no full source)
- **Text/pattern search** → `search_code`
- **File you already have in context** → Grep/Read (don't use `search_code`)
- **Confirm a single known call site** → Grep/Read (don't use `find_references`)

## Common Workflows

### Audit (understand unfamiliar code)
1. `list_repositories` — see what's indexed
2. `search_symbols` — find the entry point or key class
3. `explain_symbol` — get definition + all usages in one call
4. `get_file_structure` — survey a file before reading it

### Refactor (change a type or interface)
1. `get_change_impact` — map every direct dependent before touching anything
2. `find_references` — drill into a specific reference type (e.g. `type_annotation`)
3. `go_to_definition` — jump to the definition to read context

### Navigate (trace a call chain)
1. `go_to_definition` — start at the symbol
2. `find_references` — find callers
3. Repeat from step 1 on each caller

"""
