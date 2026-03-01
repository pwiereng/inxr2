# Project Index: INXR2

Generated: 2026-03-01

## Overview

Cross-reference code browser for git repositories. Indexes code with Tree-sitter AST parsing, enabling symbol search, cross-references, and time-travel (browsing code at any historical commit). Self-hosted alternative to GitHub code navigation.

**Stack**: FastAPI (Python 3.11) + React 18 (TypeScript) + PostgreSQL 15 + Tree-sitter + Docker

## Project Structure

```
src/inxr2/
  domain/           # Layer 1: Frozen dataclasses, no framework deps
    entities/        # Repository, Commit, File, Symbol, Reference, IndexStatus, TextContent
    value_objects/   # SymbolKind, CommitHash, ReferenceType, QueryMode, SymbolLocation, Config
    exceptions/      # DomainException, RepositoryNotFound, SymbolNotFound, CommitNotFound, FileNotFound
    services/        # LanguageDetector (60+ languages by extension)
    constants.py     # SUPPORTED_LANGUAGES_WITH_PARSERS
  application/       # Layer 2: Use cases + ports (ABCs)
    ports/
      repositories.py  # 7 repository port ABCs (Repository, Commit, File, Symbol, Reference, IndexStatus, TextContent)
      services.py      # GitServicePort (9 methods), FileSystemPort, ParserServicePort, TextSearchPort
    use_cases/
      indexing/      # IndexLocalDirectory, DefaultIndexingOrchestrator, ProcessCommit, ProcessFile, ResolveReferences, OptimizeFileIndexing
      search/        # SearchSymbols, SearchFiles, SearchText
      files/         # GetFileContent, ResolveFile, GetFileHistory
      repositories/  # ListRepositories, GetRepositoryFiles, GetRepositoryTree, GetRepositoryStats, GetRepositoryBranches
      commits/       # ListCommits
      symbols/       # SearchSymbols, GetSymbolReferences
  adapters/          # Layer 3: Implementations
    api/routes/      # FastAPI: repositories, files, symbols, commits, search, indexing
    cli/             # Click CLI: index, status, serve commands
    persistence/
      models/        # SQLAlchemy ORM: RepositoryModel, CommitModel, FileModel, SymbolModel, ReferenceModel, etc.
      repositories/  # Postgres implementations of all 7 repository ports + PostgresTextSearch
      mappers.py     # Bidirectional Entity <-> ORM conversion
    external/
      git_service.py       # GitPython wrapper (implements GitServicePort)
      local_filesystem.py  # File I/O (implements FileSystemPort)
      plaintext_parser.py  # Regex-based fallback parser
      treesitter/          # AST parsers: python, typescript, c/cpp, java, csharp, go, ruby
    config/          # YAML config loader (Pydantic models)
  infrastructure/    # Layer 4: Framework setup
    fastapi/app.py   # create_app() factory, CORS, router registration
    database/        # AsyncSession factory, connection pooling, Alembic migrations
    config/          # Pydantic Settings
    dependencies.py  # Central DI: all FastAPI Depends providers (488 lines)

frontend/src/
  App.tsx            # Router: /, /browse/:repo/*, /search, /history, /repositories
  pages/             # Browse (main), Search, History, Repositories, Files
  hooks/
    useBrowseState.ts  # 240-line state hook: URL sync, data fetching, actions
  components/
    CodeViewer/      # Prism.js syntax highlighting, clickable symbols/refs
    DiffCodeViewer/  # Side-by-side diff with synced scroll
    FileTree/        # Hierarchical directory tree with language-colored icons
    SymbolSearch/    # Autocomplete symbol search (300ms debounce)
    ReferencesPanel/ # Symbol usages list with go-to-definition
    CodeHeader/      # Nav bar: repo/branch/commit selectors + tabs
    VersionSelector/ # Time-travel commit picker
    BranchSelector/  # Branch switcher
  lib/api.ts         # API client (579 lines): all endpoint functions, typed responses
  contexts/          # AppContext: theme + API client injection

tests/               # 71 Python test files + 27 TypeScript test files
  fixtures/
    test_doubles.py  # 13 in-memory fakes (~2700 lines), behavioral parity with Postgres
  contract/          # 24 parametrized tests: fake vs Postgres parity verification
  unit/              # Domain entities, use cases (19 files), adapters
  adapters/          # Postgres integration (savepoint isolation), CLI (truncation), Git, Tree-sitter
  integration/       # API endpoints (httpx + FastAPI TestClient), multi-adapter workflows
```

## Entry Points

- **CLI**: `src/inxr2/cli.py` -> `inxr2 index|status|serve` (Click + Rich)
- **API**: `src/inxr2/infrastructure/fastapi/app.py` -> `create_app()` on port 8000
- **Frontend**: `frontend/src/main.tsx` -> React 18 on port 5173
- **Tests**: `./scripts/run-all-tests.sh` (pytest + vitest)

## API Routes (all under /api)

| Route | Methods | Purpose |
|-------|---------|---------|
| `/repositories` | GET, POST | List/create repositories |
| `/repositories/{id}/tree` | GET | File tree (branch/commit aware) |
| `/repositories/{id}/branches` | GET | List indexed branches |
| `/repositories/{id}/stats` | GET | File/symbol/reference counts |
| `/files/{id}/content` | GET | File content with symbols & refs |
| `/files/{id}/history` | GET | File version history (time travel) |
| `/symbols/search` | GET | Symbol search (autocomplete) |
| `/symbols/{id}/references` | GET | Cross-references for symbol |
| `/commits` | GET | Commit history (branch filter) |
| `/search/text` | GET | Full-text search (keyword/phrase/regex) |
| `/search/files` | GET | File path search |
| `/indexing` | POST | Trigger indexing |
| `/health` | GET | Health check |

## Database (PostgreSQL 15)

Core tables: `repositories`, `commits`, `files`, `symbols`, `references`, `index_status`
Junction tables: `branch_commits` (M:N), `commit_files` (M:N, content-addressable)
Full-text search: `text_contents` (tsvector + GIN)

Content-addressable: files/symbols/refs linked to file versions (not directly to commits).
Commit context via `commit_files` junction table. Delta indexing: unchanged files reused across commits.

## Key Dependencies

| Package | Purpose |
|---------|---------|
| fastapi + uvicorn | Web framework |
| sqlalchemy 2.0 + asyncpg | Async PostgreSQL ORM |
| alembic | Database migrations |
| gitpython | Git operations |
| tree-sitter + 9 language grammars | AST parsing (Python, TS, JS, C, C++, Java, C#, Go, Ruby) |
| click + rich | CLI with progress bars |
| pydantic | Config validation |
| react 18 + mui | Frontend UI |
| prismjs | Syntax highlighting |
| react-router v7 | Client-side routing |
| vitest | Frontend testing |

## Configuration

- `config.yaml` - Repository definitions (11 repos), indexing settings, server settings
- `pyproject.toml` - Python deps, tool config (black, isort, ruff, mypy, pytest)
- `.env.dev` - Dev database credentials (committed)
- `.env.prod` - Prod secrets (NOT committed)
- `docker-compose.dev.yml` - 2 services: dev (with embedded PostgreSQL), playwright (QA profile)

## Testing Philosophy

- **No mocking** - 13 in-memory fake implementations instead
- **Contract tests** - Parametrized to verify fake == Postgres behavior
- **DB isolation** - Savepoint rollback (adapters), truncation (CLI), fakes (unit)
- **Coverage target** - 80% minimum
- **TDD approach** - Write failing test first, then implement

## Current Phase

Phases 1.1-1.11 complete. Next: Phase 1.12 - Remote Repository Support (clone from URLs).

## Quick Start

```bash
docker-compose -f docker-compose.dev.yml up -d    # Start services
docker exec -it inxr2-dev bash                     # Enter dev container
inxr2 index --config config.yaml                   # Index repositories
inxr2 serve --reload                               # Start backend
cd frontend && npm run dev                         # Start frontend
./scripts/run-all-tests.sh                         # Run all tests
```
