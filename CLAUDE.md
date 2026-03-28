# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

INXR2 is a cross-reference code browser for git repositories, similar to LXR but designed for modern git-based workflows. It enables semantic code navigation, temporal browsing (code at any point in time), and cross-repository search.

**Tech Stack:** FastAPI (Python) + React (TypeScript) + PostgreSQL + Tree-sitter + Docker

**Architecture:** Clean Architecture (Hexagonal/Ports & Adapters) — dependencies point INWARD only. See "Architecture" section below.

## Using the INXR2 MCP Server

When the MCP server is running (`http://localhost:3000`), **use it as the first choice** for exploring the inxr2 codebase — symbol search, reference lookups, definition jumping, and code search. Fall back to direct file reads/grep when MCP doesn't cover the need.

**Available MCP tools:** `list_repositories`, `search_symbols`, `find_references`, `go_to_definition`, `search_code`, `find_dead_code`, `review_helper`, `get_file_structure`, `get_change_impact`, `explain_symbol`

**Calling MCP tools** (via the SSE server at `http://localhost:3000`):
```bash
docker exec inxr2-dev bash -c '
cd /workspace/mcp-server && python -c "
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def call(tool, args):
    async with sse_client(\"http://localhost:3000/sse\") as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool(tool, args)
            print(res.content[0].text)

asyncio.run(call(\"search_symbols\", {\"query\": \"MySymbol\", \"repository\": \"inxr2\"}))
"'
```

Replace `search_symbols` and its args with any tool: `list_repositories`, `find_references`, `go_to_definition`, `search_code`, `find_dead_code`, `review_helper`, `get_file_structure`, `get_change_impact`, `explain_symbol`. Use `localhost:3000` for main; use the worktree's MCP port for worktrees (see port table below).

**Index staleness check:** Before relying on MCP results for source code decisions, verify the index is current:
```bash
asyncio.run(call("list_repositories", {"detail": True}))
# Compare "last_indexed_commit" against: git log main --oneline -1
```
Rule: if only docs/test commits are missing, trust the index. If source files are missing (e.g. a new module you're about to reference), fall back to Grep/Read for those files.

**Worktree gap:** The index reflects `main` only. Files you've added or changed in your worktree branch won't be indexed. Use MCP for existing codebase navigation; use Grep/Read for your own changes.

**When NOT to use MCP:**
- Don't use `search_code` to find open files you already have in context — just read them.
- Don't use `find_references` to confirm a single known call site — you already know it.
- Do use `get_change_impact` **before** any type signature or interface change — it maps the blast radius in one call.

**Reporting:** Whenever you use an MCP tool during your work, briefly mention it to the user using this format:
```
// inxr2: <tool_name> "<query>" → <summary of result> (<helpful/not helpful>)
// Example: inxr2: get_change_impact "SymbolRepository" → 12 direct dependents in 5 files (helpful)
```

## Critical Development Guidelines

⚠️ **BEFORE making any changes:**

1. **Docker-Only Development**
   - ❌ NEVER run `npm install` or `pip install` on host machine
   - ✅ ALWAYS run inside Docker containers (`inxr2-dev` or `inxr2-<branch>-dev` for worktrees)
   - PostgreSQL is embedded inside the dev container (no separate postgres service)
   - **Prefer `docker exec` over `bash -c`** — default working dir is `/workspace`, use `-w` only for subdirectories
   - Use `-d` for background/daemon processes (servers)

2. **Testing Requirements**
   - ✅ MANDATORY: Run `./scripts/run-all-tests.sh` before EVERY commit
   - All code changes MUST include tests — use dependency injection with fakes, NOT mocking
   - Minimum 80% test coverage
   - **Test Independence**: Tests MUST be self-contained — no dependency on filesystem repos, workspace git history, or external data. Use `tmp_path` fixtures.
   - **TDD**: Write failing test first → implement minimum to pass → refactor
   - **Bug Fixes**: Every bug fix MUST include a regression test that fails before the fix
   - **Failing Tests**: Investigate root cause — fix the actual bug, don't just make the test pass
   - **Database Isolation**: Tests MUST use `TEST_DATABASE_URL` (`inxr2_test` DB) — NEVER touch live database

3. **Code Quality**
   - Zero tolerance for linting errors: black, isort, ruff, mypy (Python) and eslint, prettier (TypeScript)
   - ⚠️ Run `mypy src/ tests/` on ALL Python files before committing
   - ❌ NEVER suppress errors or warnings — fix root cause or ask user

4. **Git Commits**
   - ❌ NEVER use `git commit --amend` — always create new commits
   - ✅ `git push` is allowed — run it after committing
   - ❌ NEVER force push (`git push --force` or `--force-with-lease`) — if a rebase would require force push, use merge instead
   - ✅ Prefer rebase over merge for resolving conflicts on feature branches
   - ✅ If rebase gets complicated (conflicts in many files, risk of force push), fall back to merge
   - ⚠️ ALWAYS ask the user if they want to test before committing

## Common Commands

```bash
# Start dev container
docker compose -f docker-compose.dev.yml up -d --build
docker exec -it inxr2-dev bash    # or ./scripts/dev-shell.sh

# Tests (inside container)
./scripts/run-all-tests.sh        # ALL tests (backend + frontend)
pytest --cov=src                  # Backend only
cd frontend && npm test           # Frontend only

# Code quality (inside container)
black . && isort .                # Format Python
mypy src/ tests/                  # Type check Python
cd frontend && npm run format     # Format TypeScript
cd frontend && npm run lint       # Lint TypeScript

# Database (inside container)
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1

# Running apps (inside container)
inxr2 serve --reload              # Backend (localhost:8000)
cd frontend && npm run dev        # Frontend (localhost:5173)

# Indexing (ALWAYS use config file, NEVER --path /workspace)
inxr2 index --config config.yaml              # Index all repos
inxr2 index --config config.yaml --repo X     # Index specific repo
```

## Architecture

### Clean Architecture Layers

```
┌─────────────────────────────────────────┐
│  Layer 4: Infrastructure (outermost)    │
│  FastAPI, SQLAlchemy, Tree-sitter, Git  │
│   ┌─────────────────────────────┐       │
│   │  Layer 3: Adapters          │       │
│   │  Controllers, CLI, Repos    │       │
│   │   ┌─────────────────┐       │       │
│   │   │  Layer 2: App   │       │       │
│   │   │  Use Cases      │       │       │
│   │   │   ┌────────┐    │       │       │
│   │   │   │ Layer 1│    │       │       │
│   │   │   │ Domain │    │       │       │
│   │   │   └────────┘    │       │       │
│   │   └─────────────────┘       │       │
│   └─────────────────────────────┘       │
└─────────────────────────────────────────┘
```

- **Domain** (`src/inxr2/domain/`): Pure business logic — entities, value objects. NO framework imports.
- **Application** (`src/inxr2/application/`): Use cases, ports (interfaces), DTOs.
- **Adapters** (`src/inxr2/adapters/`): API controllers, CLI, PostgreSQL repositories, Git/Tree-sitter clients.
- **Infrastructure** (`src/inxr2/infrastructure/`): FastAPI config, DB connection, DI container, logging.

### Domain Entities vs ORM Models

**CRITICAL:** These are SEPARATE — use mappers for conversion:
- **Domain Entities** (`domain/entities/`): Python dataclasses. Field: `metadata` (dict)
- **ORM Models** (`adapters/persistence/models/`): SQLAlchemy. Field: `extra_metadata` (JSONB)
- **Mappers** (`adapters/persistence/mappers.py`): Bidirectional `to_domain()` / `to_model()`

### Database: Temporal Data Model

All entities tied to **specific commits** for time-travel. Core tables: `repositories`, `commits`, `files`, `symbols`, `references`, `index_status`. Files/symbols/references all have `commit_id`. See `docs/database-schema.md` for details.

## Project Structure

```
src/inxr2/
├── domain/           # Layer 1: entities, value_objects, exceptions, services
├── application/      # Layer 2: use_cases/, ports/, dtos/
├── adapters/         # Layer 3: api/, cli/, persistence/, external/
└── infrastructure/   # Layer 4: fastapi/, database/, config/, logging/

frontend/src/         # React + TypeScript: components/, lib/, contexts/
tests/                # unit/, integration/, adapters/
mcp-server/           # MCP tools for AI assistants
qa-agent/             # Playwright browser automation
```

## Special Considerations

### Type Hints

Strict type checking enabled:
- Python: mypy with strict settings
- TypeScript: `"strict": true` plus `noUncheckedIndexedAccess`

**TypeScript rules:** No `any` — use proper types. Handle `undefined` from indexed access. No `@ts-ignore` — use `@ts-expect-error` with explanation if unavoidable. Prefer `interface` for objects, `type` for unions.

### isort/black Compatibility

isort configured with `profile = "black"` in `pyproject.toml`.

### Error Handling

Domain exceptions for business rules: `from inxr2.domain.exceptions import InvalidRepositoryError`

## Indexing Test Repositories

⚠️ **CRITICAL:** NEVER index the working directory (`/workspace` or `.`).

Test repos live at `/repos/test-repos/` (separate from `/workspace`). Always use `--config config.yaml` for indexing. Indexing `/workspace` creates duplicates with wrong paths.

## Common Pitfalls

1. Don't import framework code in domain layer
2. Don't confuse domain entities (`metadata`) with ORM models (`extra_metadata`) — use mappers
3. Don't use mocking in tests — create fake implementations
4. Don't run package managers on host — use Docker container
5. Don't skip tests before commit — `./scripts/run-all-tests.sh` is mandatory
6. Don't index the working directory — ALWAYS use `--config config.yaml`
7. Don't amend commits — create new commits instead
8. Don't install Playwright in `inxr2-dev` — use `inxr2-playwright` container

## Session Startup

Set iTerm2 tab title to the branch name and frontend port via AppleScript (escape sequences don't work from inside Claude Code because the pty captures them):
```bash
# Format: "branch-name :port"
# Port is from the .env file (FRONTEND_PORT) — main=5173, slot1=5183, slot2=5193, slot3=5203
BRANCH=$(git branch --show-current)
PORT=$(grep FRONTEND_PORT .env 2>/dev/null | cut -d= -f2)
PORT=${PORT:-5173}
osascript -e "tell application \"iTerm2\" to tell current session of current tab of current window to set name to \"${BRANCH} :${PORT}\""
```

## Skills Reference

Use these slash commands for on-demand workflows:
- `/pr-review` — Full PR lifecycle: tests, commit, push, create PR, or check comments
- `/regression-test` — Run full regression suite (indexing + browser + MCP)
- `/qa-testing` — Exploratory UI testing via QA Agent (Playwright)
- `/new-feature` — Step-by-step Clean Architecture feature workflow with examples

## Environment Configuration

- `.env.dev` — Development defaults (committed, safe values)
- `.env.prod` — Production secrets (NOT committed — create from `.env.prod.example`)
- NEVER commit `.env.prod` — change `POSTGRES_PASSWORD` and `SECRET_KEY` in production
- See `.env.example` for complete variable reference

**Services:** Backend `localhost:8000`, Frontend `localhost:5173`, API Docs `localhost:8000/docs`, MCP `localhost:3000`

## Parallel Development with Git Worktrees

Multiple Claude Code agents can work on separate branches simultaneously, each with isolated Docker stack (own container, PostgreSQL, ports).

### Port Allocation

| Service    | Slot 0 (main) | Slot 1 | Slot 2 | Slot 3 |
|------------|---------------|--------|--------|--------|
| Backend    | 8000          | 8010   | 8020   | 8030   |
| Frontend   | 5173          | 5183   | 5193   | 5203   |
| Playwright | 9222          | 9232   | 9242   | 9252   |
| MCP        | 3000          | 3010   | 3020   | 3030   |

### Commands (run on host)

```bash
./scripts/worktree-create.sh <branch-name>   # Create worktree + Docker stack
./scripts/worktree-remove.sh <branch-name>   # Tear down
./scripts/worktree-list.sh                   # Show all worktrees
```

### Key Rules

- **Pre-creation:** Ensure main is in sync with GitHub (`git fetch origin main && git status`)
- **Create worktrees sequentially, never in parallel** — slot allocation is not race-safe; parallel creates will collide on the same slot number
- **Cleanup (closing a worktree):**
  1. Verify the PR is merged on GitHub
  2. `worktree-remove.sh <branch-name>` to tear down Docker stack and remove worktree
  3. `git pull --rebase` on main to pull in the merged changes
  4. `docker exec inxr2-dev ./scripts/run-all-tests.sh` to verify everything passes on main
- **Container naming:** Main: `inxr2-dev` / Worktree: `inxr2-<branch>-dev`
- **instructions.txt:** Always write a prompt file in the worktree root, starting with tab title command. Do NOT commit (in `.gitignore`).
- **Temporary files:** Save screenshots, curl downloads, and other scratch files to `.tmp/` in the project root (gitignored) — NOT `/tmp`. This keeps temp files contained and they get cleaned up automatically with `worktree-remove.sh`. Create the directory if it doesn't exist: `mkdir -p .tmp`
- **MCP from worktrees:** Use `docker exec inxr2-dev` for MCP queries (main has indexed data). Use worktree container only for testing MCP code changes.

## Important Files

- `CONTRIBUTING.md` — Coding standards, testing philosophy, git workflow
- `docs/database-schema.md` — Complete database schema with design rationale
- `docs/regression-tests.md` — Full regression test plan (75 test cases)
- `docs/archived/2026-01-24-IMPLEMENTATION_PLAN.md` — Original phase-by-phase roadmap
- `qa-agent/README.md` — QA agent API documentation
