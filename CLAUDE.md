# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

INXR2 is a cross-reference code browser for git repositories, similar to LXR but designed for modern git-based workflows. It enables semantic code navigation, temporal browsing (code at any point in time), and cross-repository search.

**Tech Stack:** FastAPI (Python) + React (TypeScript) + PostgreSQL + Tree-sitter + Docker

**Architecture:** Clean Architecture (Hexagonal/Ports & Adapters) - see "Architecture" section below.

## Using the INXR2 MCP Server

When the MCP server is running (`http://localhost:3000`), **use it as the first choice** for exploring the inxr2 codebase — symbol search, reference lookups, definition jumping, and code search. Fall back to direct file reads/grep when MCP doesn't cover the need.

**Available MCP tools:** `list_repositories`, `search_symbols`, `find_references`, `go_to_definition`, `search_code`

**Calling MCP tools** (from inside the dev container):
```bash
docker exec inxr2-dev bash -c '
cd /workspace/mcp-server
INXR2_API_URL=http://localhost:8000 python -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_symbols  # or find_references, go_to_definition, etc.

async def main():
    client = HttpInxr2Client(\"http://localhost:8000\")
    result = await search_symbols.handle(client, {\"query\": \"MySymbol\", \"repository\": \"inxr2\"})
    print(result)
    await client.close()

asyncio.run(main())
"'
```

**Reporting:** Whenever you use an MCP tool during your work, briefly mention it to the user — what tool was used, what you found, and whether it was helpful. This helps evaluate the MCP's usefulness in practice.

## Critical Development Guidelines

⚠️ **BEFORE making any changes:**

1. **Docker-Only Development**
   - ❌ NEVER run `npm install` or `pip install` on host machine
   - ✅ ALWAYS run package management inside Docker containers
   - All development must be done inside the dev container (`inxr2-dev` for main, or `inxr2-<branch>-dev` for worktrees)
   - PostgreSQL is embedded inside the dev container (no separate postgres service)
   - **Prefer `docker exec` over `bash -c`** when suggesting commands to the user:
     - ✅ `docker exec <container> inxr2 index --config config.yaml`
     - ❌ `docker exec <container> bash -c "cd /workspace && inxr2 index --config config.yaml"`
     - The default working directory is `/workspace`, so `-w` is only needed for subdirectories (e.g., `-w /workspace/frontend` for frontend commands)
     - Use `-d` for background/daemon processes (servers)

2. **Testing Requirements**
   - ✅ MANDATORY: Run `./scripts/run-all-tests.sh` before EVERY commit
   - All code changes MUST include tests
   - Use dependency injection, NOT mocking (see test examples)
   - Minimum 80% test coverage
   - ⚠️ **Test Independence**: Tests MUST be self-contained and NOT depend on:
     - Specific test repositories in `/repos/test-repos/`
     - Any repositories that exist on the filesystem (e.g., `../test-repos/`, `/repos/`)
     - The actual workspace git history
     - Any external data that could change
   - Use `tmp_path` fixtures and create controlled test data (e.g., temp git repos)
   - Tests must pass regardless of which repositories are configured or present on disk
   - **TDD Approach**: Follow Test-Driven Development where practical:
     1. Write a failing test first
     2. Implement the minimum code to pass
     3. Refactor while keeping tests green
   - **Bug Fix Testing**: Every bug fix MUST include a regression test
     - Write a test that reproduces the bug BEFORE fixing it
     - The test should fail before the fix and pass after
     - If a regression test is complex or hard to write, ask the user if it's worth the effort
   - **Fixing Failing Tests**: When a test fails, ALWAYS investigate the root cause:
     - ❌ DON'T just make the test pass with a quick workaround
     - ✅ DO investigate whether the bug is in the test or in the code being tested
     - ✅ DO fix the actual root cause, not the symptom
     - If the test is wrong, fix the test and explain why
     - If the code is wrong, fix the code properly
     - Always fix test failures immediately, even if unrelated to current work
   - **Database Isolation**: Tests MUST NEVER touch the live database:
     - Unit tests: Use `TEST_DATABASE_URL` (PostgreSQL test database `inxr2_test`) via fixtures in `tests/adapters/persistence/conftest.py`
     - CLI tests: Use CliRunner's `env` parameter to set `DATABASE_URL` to test database
     - Integration tests: Use proper test database fixtures
     - If a test needs database access, it MUST use the isolated test database fixtures
     - ❌ NEVER let tests hit the production/development PostgreSQL database

3. **Code Quality**
   - Zero tolerance for linting errors
   - All code must pass: black, isort, ruff, mypy (Python) and eslint, prettier (TypeScript)
   - ⚠️ **MANDATORY**: Run `mypy src/ tests/` to check ALL Python files before committing
   - Run formatters BEFORE committing
   - ❌ NEVER suppress errors or warnings - always fix the root cause or ask the user for guidance
   - If a warning seems unavoidable, discuss with user before adding any suppression

4. **Package Management**
   - Only use well-supported, actively maintained packages
   - No deprecated or vulnerable packages
   - Run `npm audit` regularly (zero vulnerabilities required)

5. **Git Commits**
   - ❌ NEVER use `git commit --amend` - always create new commits for fixes
   - ❌ NEVER run `git push` - the user will manually push all changes
   - ✅ Rebase is OK for resolving conflicts on feature branches
   - Keep commits simple and straightforward
   - ⚠️ **ALWAYS ask the user** if they want to test before committing - don't assume

## Exploratory Testing with QA Agent

For interactive UI testing, use the **`inxr2-playwright`** container. This is a Claude-driven testing approach where:

- **Claude Code** (you) decides what to test and issues commands
- **QA Agent** executes browser actions via Playwright
- **Claude Code** interprets results and continues testing

### Why Separate Containers?

- **`inxr2-dev`**: Development container for coding, running tests, database operations
- **`inxr2-playwright`**: Browser automation container with Playwright and Chromium

⚠️ **NEVER install Playwright/Chromium in `inxr2-dev`** - use the dedicated QA container.

### Starting the QA Agent

```bash
# Start the playwright container (requires --profile qa)
docker compose -f docker-compose.dev.yml --profile qa up -d playwright

# Verify it's running
curl http://localhost:9222/health
```

### Using curl for Browser Control

Control the browser by issuing curl commands:

```bash
# Navigate to a page
curl "http://localhost:9222/navigate?url=http://localhost:5173/browse/inxr2"

# Click an element
curl "http://localhost:9222/click?selector=span.symbol-name"

# Get text content
curl "http://localhost:9222/text?selector=.references-panel"

# List matching elements
curl "http://localhost:9222/elements?selector=a&limit=10"

# Take a screenshot
curl "http://localhost:9222/screenshot/save?path=/tmp/screenshot.png"
```

### Exploratory Testing Workflow

1. Ensure frontend is running: `cd frontend && npm run dev` (in `inxr2-dev`)
2. Ensure backend is running: `inxr2 serve --reload` (in `inxr2-dev`)
3. Use curl commands to navigate and interact with the UI
4. Keep a log of steps to reproduce any bugs found
5. Verify behavior matches expectations

See `qa-agent/README.md` for complete API documentation.

## Common Commands

### Starting Development Environment

```bash
# Start dev container (includes embedded PostgreSQL)
docker compose -f docker-compose.dev.yml up -d --build

# Or use helper script
./scripts/dev-start.sh

# Open shell in dev container
docker exec -it inxr2-dev bash

# Or use helper script
./scripts/dev-shell.sh
```

### Running Tests

```bash
# Inside dev container - run ALL tests (backend + frontend)
./scripts/run-all-tests.sh

# Backend tests only
pytest --cov=src --cov-report=term-missing

# Single test file
pytest tests/unit/domain/test_entities.py

# Single test
pytest tests/unit/domain/test_entities.py::TestRepository::test_repository_creation

# Frontend tests
cd frontend && npm test

# Frontend tests (watch mode)
cd frontend && npm test -- --watch
```

### Code Quality

```bash
# Inside dev container

# Format Python code
black .
isort .

# Lint Python
ruff check .

# Type check Python
mypy src/

# Format TypeScript
cd frontend && npm run format

# Lint TypeScript
cd frontend && npm run lint

# Type check TypeScript
cd frontend && npm run type-check
```

### Database Operations

```bash
# Inside dev container

# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# View migration history
alembic history

# Reset database (WARNING: deletes all data)
./scripts/dev-reset-db.sh
```

### Running the Application

```bash
# Inside dev container

# Start backend (with hot reload)
inxr2 serve --reload

# Start frontend (with hot reload)
cd frontend && npm run dev

# Access services:
# Backend API: http://localhost:8000
# Frontend: http://localhost:5173
# API Docs: http://localhost:8000/docs
```

### Production Build

```bash
# Build production images
docker-compose build

# Start production
docker-compose up -d

# View logs
docker-compose logs -f

# Stop production
docker-compose down
```

## Architecture

### Clean Architecture (Hexagonal/Ports & Adapters)

The Python backend follows Clean Architecture with strict dependency rules:

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

**Dependency Rule:** Dependencies point INWARD only. Domain has NO dependencies on outer layers.

**Layer Responsibilities:**
- **Domain** (`src/inxr2/domain/`): Pure business logic - entities, value objects, domain services
  - NO framework dependencies (no FastAPI, no SQLAlchemy)
  - Only standard Python and business rules
  - Example: `domain/entities/repository.py`, `domain/value_objects/symbol_kind.py`

- **Application** (`src/inxr2/application/`): Use cases and ports (interfaces)
  - Use cases: Business workflows (e.g., `SearchSymbolsUseCase`)
  - Ports: Abstract interfaces for external dependencies (e.g., `SymbolRepositoryPort`)
  - DTOs: Request/response objects

- **Adapters** (`src/inxr2/adapters/`): Implementations of ports
  - API controllers (FastAPI routes)
  - CLI commands
  - Repository implementations (PostgreSQL)
  - External service clients (Git, Tree-sitter)

- **Infrastructure** (`src/inxr2/infrastructure/`): Framework setup
  - FastAPI app configuration
  - Database connection management
  - Dependency injection container
  - Logging setup

### Database Schema: Temporal Data Model

All entities are tied to **specific commits** for time-travel capabilities:

**Core Tables:**
- `repositories` - Repository metadata
- `commits` - Git commit history (with branch, author, dates)
- `files` - File snapshots at each commit (same file at different commits = different rows)
- `symbols` - Code symbols (functions, classes, etc.) at specific file versions
- `references` - Cross-references between symbols
- `index_status` - Indexing progress per repository/branch

**Key Design:**
- Files, symbols, and references all have `commit_id` - enables browsing code at any point in history
- `content_hash` in files enables detecting unchanged files between commits
- Full-text search via `tsvector` fields with GIN indexes
- JSONB for language-specific metadata (flexible schema)

See `docs/database-schema.md` for complete schema details.

### Domain Entities vs ORM Models

**CRITICAL:** Domain entities and ORM models are SEPARATE:

- **Domain Entities** (`src/inxr2/domain/entities/`): Python dataclasses, framework-agnostic
  - Example: `Repository(id=1, name="test-repo", url="...")`
  - Field: `metadata` (dict)

- **ORM Models** (`src/inxr2/adapters/persistence/models/`): SQLAlchemy models
  - Example: `RepositoryModel(id=1, name="test-repo", url="...")`
  - Field: `extra_metadata` (JSONB) - renamed to avoid SQLAlchemy reserved word

- **Mappers** (`src/inxr2/adapters/persistence/mappers.py`): Bidirectional conversion
  - `RepositoryMapper.to_domain(model)` → Domain entity
  - `RepositoryMapper.to_model(entity)` → ORM model
  - Handles field name differences (metadata ↔ extra_metadata)

### Repository Pattern

All data access goes through repository interfaces (ports):

```python
# Define interface in application layer
class SymbolRepositoryPort(ABC):
    @abstractmethod
    async def save(self, symbol: Symbol) -> Symbol: ...

    @abstractmethod
    async def find_by_id(self, symbol_id: int) -> Symbol | None: ...

# Implement in adapters layer
class PostgresSymbolRepository(SymbolRepositoryPort):
    def __init__(self, session: AsyncSession):
        self.session = session
        self.mapper = SymbolMapper()

    async def save(self, symbol: Symbol) -> Symbol:
        model = self.mapper.to_model(symbol)
        self.session.add(model)
        await self.session.flush()
        return self.mapper.to_domain(model)
```

**Testing with Fakes (NOT Mocks):**
```python
# Create fake implementation for tests
class FakeSymbolRepository(SymbolRepositoryPort):
    def __init__(self):
        self._symbols: dict[int, Symbol] = {}

    async def save(self, symbol: Symbol) -> Symbol:
        self._symbols[symbol.id] = symbol
        return symbol

# Use in tests
def test_search_symbols():
    fake_repo = FakeSymbolRepository()
    use_case = SearchSymbolsUseCase(symbol_repository=fake_repo)
    # Test use case without database
```

See `tests/unit/application/test_resolve_references_use_case.py` for complete examples.

## Project Structure

```
src/inxr2/
├── domain/                    # Layer 1: Pure business logic
│   ├── entities/             # Repository, Commit, File, Symbol, Reference
│   ├── value_objects/        # SymbolKind, CommitHash, SymbolLocation
│   ├── exceptions/           # Domain-specific exceptions
│   └── services/             # Domain services
├── application/               # Layer 2: Use cases & ports
│   ├── use_cases/            # Business workflows
│   │   ├── indexing/        # IndexRepository, IncrementalIndex
│   │   └── search/          # SearchSymbols, FindDefinition
│   ├── ports/                # Interfaces (ABC)
│   │   ├── repositories/    # Repository pattern interfaces
│   │   └── services/        # External service interfaces
│   └── dtos/                 # Data Transfer Objects
├── adapters/                  # Layer 3: Interface adapters
│   ├── api/                  # FastAPI controllers & serializers
│   ├── cli/                  # CLI commands
│   ├── persistence/          # Database adapters
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── repositories/    # Repository implementations
│   │   └── mappers.py       # Entity ↔ Model conversion
│   └── external/             # External service clients
└── infrastructure/            # Layer 4: Framework setup
    ├── fastapi/              # FastAPI app configuration
    ├── database/             # Database connection & migrations
    ├── config/               # Settings & DI container
    └── logging/              # Logging configuration

frontend/                      # React + TypeScript
├── src/
│   ├── components/           # React components
│   ├── lib/                  # API client, utilities
│   ├── contexts/             # Context API for state
│   └── App.tsx              # Main app component
└── tests/                    # Frontend tests (vitest)

tests/                         # Backend tests
├── unit/                     # Unit tests (domain, application)
├── integration/              # Integration tests (API, database)
└── adapters/                 # Adapter tests (repositories, mappers)

qa-agent/                      # Browser automation for exploratory testing
├── src/
│   ├── server.py             # HTTP API server (curl-based control)
│   └── repl.py               # JSON REPL for scripted testing
├── Dockerfile                # Playwright + Chromium container
└── README.md                 # API documentation
```

## Important Files

- **docs/archived/2026-01-31-design.md** - Original design document (archived, for historical reference)
- **docs/archived/2026-01-24-IMPLEMENTATION_PLAN.md** - Phase-by-phase implementation plan (currently in Phase 1.12)
- **CONTRIBUTING.md** - Coding standards, testing philosophy, git workflow
- **docs/database-schema.md** - Complete database schema with design rationale
- **qa-agent/README.md** - QA agent API documentation for exploratory testing

## Development Workflow

### Adding a New Feature

1. **Plan** - Identify which layer(s) the feature touches
2. **Domain First** - Start with domain entities and use cases
3. **Ports** - Define interfaces for external dependencies
4. **Tests** - Write tests using fake implementations
5. **Adapters** - Implement adapters (API, database, etc.)
6. **Integration** - Wire up with dependency injection

Example: Adding symbol search

```python
# 1. Domain entity already exists (Symbol)

# 2. Use case (application layer)
class SearchSymbolsUseCase:
    def __init__(self, symbol_repository: SymbolRepositoryPort):
        self._symbol_repository = symbol_repository

    async def execute(self, request: SearchSymbolsRequest) -> SearchSymbolsResponse:
        symbols = await self._symbol_repository.search_by_name(request.query)
        return SearchSymbolsResponse(symbols=symbols, total_count=len(symbols))

# 3. Port (application layer)
class SymbolRepositoryPort(ABC):
    @abstractmethod
    async def search_by_name(self, name: str) -> list[Symbol]: ...

# 4. Tests (with fake)
def test_search_symbols():
    fake_repo = FakeSymbolRepository()
    fake_repo.add_test_symbol(Symbol(...))
    use_case = SearchSymbolsUseCase(symbol_repository=fake_repo)
    result = await use_case.execute(SearchSymbolsRequest(query="test"))
    assert len(result.symbols) == 1

# 5. Adapter implementation
class PostgresSymbolRepository(SymbolRepositoryPort):
    async def search_by_name(self, name: str) -> list[Symbol]:
        models = await self.session.execute(
            select(SymbolModel).where(SymbolModel.name.contains(name))
        )
        return [self.mapper.to_domain(m) for m in models.scalars()]

# 6. API controller (adapters layer)
@router.get("/symbols/search")
async def search_symbols(q: str, repo: SymbolRepositoryPort = Depends()):
    use_case = SearchSymbolsUseCase(symbol_repository=repo)
    result = await use_case.execute(SearchSymbolsRequest(query=q))
    return result
```

### Database Migrations

When adding/modifying database schema:

1. Update domain entity if needed
2. Update ORM model in `adapters/persistence/models/`
3. Update mapper if field names changed
4. Generate migration: `alembic revision --autogenerate -m "description"`
5. Review generated migration (fix any issues)
6. Apply migration: `alembic upgrade head`
7. Update tests

**Common Issues:**
- Field name conflicts: Use `extra_metadata` not `metadata` in ORM models
- Relationship ambiguity: Specify `foreign_keys` parameter explicitly

### Testing Philosophy

**Use Dependency Injection, NOT Mocking:**

❌ **DON'T:**
```python
from unittest.mock import Mock

def test_with_mock():
    mock_repo = Mock(spec=SymbolRepositoryPort)
    mock_repo.search_by_name.return_value = [...]  # Brittle!
    # Test breaks if implementation changes
```

✅ **DO:**
```python
class FakeSymbolRepository(SymbolRepositoryPort):
    def __init__(self):
        self._symbols = {}

    async def search_by_name(self, name: str) -> list[Symbol]:
        return [s for s in self._symbols.values() if name in s.name]

def test_with_fake():
    fake_repo = FakeSymbolRepository()
    fake_repo._symbols[1] = Symbol(...)  # Clear test data
    # Test remains valid even if implementation changes
```

**Benefits:**
- Tests survive refactoring
- Explicit test data setup
- No framework overhead
- Fake follows real interface contract

**Avoid Low-Value Tests:**
- Don't test language features (e.g., Python enum behavior, dataclass immutability)
- Don't write tests that just verify static values exist
- Tests should verify actual behavior, not that Python works correctly
- If a test would pass even with broken business logic, it's low-value

See `tests/unit/application/test_default_indexing_orchestrator.py` for complete examples.

## Environment Configuration

### Environment Files

The project uses `.env` files for configuration:

- **`.env.dev`** - Development defaults (committed to repo, safe values)
- **`.env.prod`** - Production secrets (NOT committed, create from template)
- **`.env.prod.example`** - Production template
- **`.env.example`** - Complete variable reference

**CRITICAL:**
- `.env.dev` is used automatically in development
- `.env.prod` must be created manually for production
- NEVER commit `.env.prod` to version control (already in `.gitignore`)
- Change `POSTGRES_PASSWORD` and `SECRET_KEY` in production!

**Key Variables:**
```bash
# Database
POSTGRES_DB=inxr2_dev
POSTGRES_USER=inxr2_user
POSTGRES_PASSWORD=inxr2_dev_password  # CHANGE in production!
DATABASE_URL=postgresql://user:pass@host:port/db

# Application
ENVIRONMENT=development  # or production
DEBUG=true  # false in production
LOG_LEVEL=DEBUG  # INFO in production
APP_PORT=8000

# Security (production only)
SECRET_KEY=generate_random_key  # python -c "import secrets; print(secrets.token_urlsafe(32))"
ALLOWED_HOSTS=yourdomain.com
CORS_ORIGINS=https://yourdomain.com
```

### Environment & Services

**Development Environment:**
- PostgreSQL: Embedded inside dev container (`localhost:5432` from within container)
  - Database: `inxr2_dev`
  - User: `inxr2_user`
  - Password: `inxr2_dev_password` (from `.env.dev`)
  - Data persisted in `pgdata` Docker volume

- Backend API: `http://localhost:8000`
- Frontend Dev Server: `http://localhost:5173`
- API Documentation: `http://localhost:8000/docs`

**Production Environment:**
- Single Docker container with PostgreSQL + FastAPI + React static files
- Backend serves frontend at `/`, API at `/api/*`
- PostgreSQL data persisted in Docker volume
- Configuration from `.env.prod` (must be created)

## Current Status

**Phase 1.3: Database Foundation** - ✅ COMPLETED (2026-01-04)

Recent achievements:
- Complete database schema designed (6 core tables)
- Alembic migration system configured
- SQLAlchemy ORM models created (separate from domain entities)
- Repository ports defined (6 interfaces)
- Repository adapters implemented with mappers
- All tests passing (45 backend + 17 frontend)
- Database migration applied to PostgreSQL
- Live integration test verified CRUD operations

**Phase 1.4: Vertical Slice - Basic File Indexing** - ✅ COMPLETED (2026-01-05)

Recent achievements:
- Backend file indexing use case (IndexLocalDirectoryUseCase)
- Language detector service (60+ languages)
- API routes (repositories, files, indexing)
- Frontend repositories and files pages
- Comprehensive test suite (47 new tests)
- Test coverage: 85% (92 tests passing)

**Phase 1.5: CLI Indexing Engine** - ✅ COMPLETED (2026-01-10)

Recent achievements:
- CLI framework with Click (`inxr2 index|status`)
- Git integration via GitPython (commit tracking, file diffs)
- Unified indexing workflow (always incremental)
- Rich progress bars for excellent UX
- Database adapters: SymbolRepository, ReferenceRepository, IndexStatusRepository
- Successfully indexed INXR2 itself: 108 files, 440 symbols, 473 references

**Phase 1.6: Cross-Reference Code Browser UI** - ✅ COMPLETED (2026-01-11)

Recent achievements:
- Web UI for browsing indexed code
- Symbol search with autocomplete
- File tree navigation
- Code viewer with syntax highlighting
- References panel showing usages

**Phase 1.7: Configuration System** - ✅ COMPLETED (2026-01-13)

Recent achievements:
- YAML configuration for multi-repository support
- Pydantic-based configuration validation
- CLI integration with config files
- UI updates for repository selection

**Phase 1.8: Tree-sitter Integration** - ✅ COMPLETED (2026-01-14)

Recent achievements:
- Tree-sitter AST parsing (initially Python, TypeScript, JavaScript; later expanded to 9 languages)
- Replaced regex-based extraction with proper AST traversal
- New symbol types: properties, staticmethods, classmethods, interface properties, enums
- Proper scope tracking for nested symbols (class → method relationships)
- 28 comprehensive Tree-sitter tests

**Phase 1.9: Time Travel & Temporal Navigation** - ✅ COMPLETED (2026-01-17)

Recent achievements:
- Browse code at any indexed commit
- Version selector showing all commits that modified a file
- Commit-aware file tree
- Side-by-side diff viewer with syntax highlighting

**Phase 1.10: URL State & Permalinks** - ✅ COMPLETED (2026-01-20)

Recent achievements:
- Full URL state management for bookmarkable views
- Line number, commit, diff mode, search query all in URL
- Click line numbers to update URL
- Scroll to line on page load
- Comprehensive useBrowseState hook with tests

**Phase 1.11: Multi-Branch Support** - ✅ COMPLETED (2026-01-24)

Recent achievements:
- BranchSelector component for switching between indexed branches
- Branch parameter in URL for bookmarkable branch views
- Cross-branch diff comparison
- File history filtered by branch
- Live branch listing from git repository

**Post-Phase Work (2026-02 to present):**
- Content-addressable file versioning (commit_files junction table)
- Full-text search (text_contents table, keyword/phrase/regex)
- Git blame integration
- Light/dark theme support
- C, C++, Java, C#, Go, Ruby parser support (9 languages total)
- Resilient per-language parser initialization
- Performance indexing optimizations

See `docs/archived/2026-01-24-IMPLEMENTATION_PLAN.md` for original roadmap.

## Special Considerations

### isort and black Compatibility

In `pyproject.toml`, isort is configured with `profile = "black"` to ensure compatibility:

```toml
[tool.isort]
profile = "black"
line_length = 88
```

### Async Database Operations

All repository methods are async:

```python
async with db.session() as session:
    repo = PostgresSymbolRepository(session)
    symbol = await repo.find_by_id(123)
```

### Type Hints

Strict type checking enabled:
- Python: mypy with strict settings
- TypeScript: `"strict": true` in tsconfig.json plus `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`, `noUncheckedIndexedAccess`

**TypeScript strict rules — all new code MUST:**
- Never use `any` — use proper types, `unknown`, or generics instead
- Handle `undefined` from indexed access (enabled via `noUncheckedIndexedAccess`)
- Explicitly type all function parameters and return types for public/exported functions
- Use type narrowing (type guards, discriminated unions) instead of type assertions (`as`)
- Prefer `interface` for object shapes and `type` for unions/intersections
- Never suppress with `@ts-ignore` — use `@ts-expect-error` with explanation only if truly unavoidable

### Error Handling

Domain exceptions for business rule violations:
```python
from inxr2.domain.exceptions import InvalidRepositoryError

if not repository.name:
    raise InvalidRepositoryError("Repository name cannot be empty")
```

## Indexing Test Repositories

⚠️ **CRITICAL: Working Directory vs Test Repos**

The working directory (`/workspace` or `.`) is where you develop code - it must **NEVER** be indexed.

Test repositories live in a **separate location** (`../test-repos`, mounted as `/repos/test-repos` in the container). Even if a repo like `inxr2` exists in both places, they are **completely separate**:

- `/workspace` = Live codebase you're editing (NEVER index this)
- `/repos/test-repos/inxr2` = Test copy for indexing (index this one)

**Always use the config file for indexing:**

```bash
# ✅ CORRECT: Index via config file
inxr2 index --config config.yaml --repo inxr2

# ✅ CORRECT: Index all configured repos
inxr2 index --config config.yaml

# ❌ WRONG: Never index working directory
inxr2 index --path /workspace
inxr2 index --path .
```

**Why this matters:**
- Indexing creates database records tied to a specific path
- Indexing `/workspace` creates a duplicate repo with wrong path
- The frontend looks up repos by name, so duplicates cause stale data issues
- Each repository should exist exactly once in the database

**Config file (`config.yaml`) defines:**
- Repository names and paths under `/repos/test-repos/`
- Branches to index

See `config.yaml` for the current repository configuration.

## Common Pitfalls

1. **Don't import framework code in domain layer**
   - Domain entities should NOT import FastAPI, SQLAlchemy, etc.

2. **Don't confuse domain entities with ORM models**
   - Use mappers for conversion
   - Domain entities use `metadata`, ORM uses `extra_metadata`

3. **Don't use mocking in tests**
   - Create fake implementations instead

4. **Don't run package managers on host**
   - Always use Docker container

5. **Don't skip tests before commit**
   - Run `./scripts/run-all-tests.sh` - it's mandatory

6. **Don't commit without formatting or type checking**
   - Run black, isort, prettier before commit
   - ⚠️ Run `mypy src/ tests/` on ALL Python files before commit (not just modified files)

7. **Don't index the working directory**
   - NEVER use `--path /workspace` or `--path .`
   - ALWAYS use `--config config.yaml` for indexing
   - Test repos are at `/repos/test-repos/`, not the current codebase

8. **Don't amend commits**
   - NEVER use `git commit --amend` - create a new commit instead
   - Rebase is OK for resolving conflicts on feature branches

9. **Don't install Playwright in inxr2-dev**
   - Use the `inxr2-playwright` container for browser automation
   - Access via curl: `curl http://localhost:9222/navigate?url=...`
   - See `qa-agent/README.md` for API documentation

## Session Startup

At the start of every session, set the iTerm2 terminal tab title to the **current git branch name**. This is the most reliable way to identify which worktree/task a terminal belongs to.

```bash
echo -ne "\033]0;$(git branch --show-current)\007"
```

Examples:
- `main` — the main orchestration session
- `abstract-git-exceptions` — worktree for issue #107
- `extract-resolution-helper` — worktree for issue #108

Do NOT use task descriptions or other text — just the branch name, always.

## PR Review Workflow

When the user says **"check comments"** on a PR, this means:
1. **Read** all comments on the PR using `gh api repos/<owner>/<repo>/pulls/<number>/comments` and `gh pr view <number> --comments`
2. **Review** the comments — understand what reviewers are asking for or pointing out
3. **Summarize** the comments concisely for the user
4. **Advise** on next steps — what changes are needed, whether comments are actionable, and recommended approach

Do NOT take any action (push code, make changes, etc.) until the user has reviewed the summary and decided on next steps.

## Getting Help

- **Architecture questions:** See this file (CLAUDE.md) — Architecture section
- **Implementation plan:** See docs/archived/2026-01-24-IMPLEMENTATION_PLAN.md
- **Database schema:** See docs/database-schema.md
- **Coding standards:** See CONTRIBUTING.md
- **Development tasks:** See README.md

## Parallel Development with Git Worktrees

Multiple Claude Code agents can work on separate branches simultaneously, each with a fully isolated environment (own container, own PostgreSQL, own ports).

### Architecture

- PostgreSQL is **embedded** inside each dev container (no separate postgres service)
- Each worktree gets its own Docker stack with unique ports
- Slot 0 = main worktree (default ports), slots 1-3 = worktrees

### Port Allocation

| Service    | Slot 0 (main) | Slot 1 | Slot 2 | Slot 3 |
|------------|---------------|--------|--------|--------|
| Backend    | 8000          | 8010   | 8020   | 8030   |
| Frontend   | 5173          | 5183   | 5193   | 5203   |
| Playwright | 9222          | 9232   | 9242   | 9252   |
| MCP        | 3000          | 3010   | 3020   | 3030   |

### Pre-Creation Check

Before creating a worktree, ensure the source branch (usually main) is fully in sync with GitHub. There must be no pending commits that haven't been pushed, and no remote commits that haven't been pulled. Otherwise the worktree will be based on stale code and will hit unnecessary conflicts when rebasing later.

```bash
git fetch origin main
git status  # should show "up to date with 'origin/main'"
```

### Worktree Commands

```bash
# Create a worktree with isolated Docker stack (runs on host)
./scripts/worktree-create.sh <branch-name>

# Remove a worktree and its Docker stack
./scripts/worktree-remove.sh <branch-name>

# List all worktrees with status
./scripts/worktree-list.sh
```

### Worktree Cleanup Procedure

When cleaning up a worktree (after its PR is merged), follow this sequence:
1. Verify PR is merged and issue is closed
2. Run `./scripts/worktree-remove.sh <branch-name>`
3. Pull latest main: `git pull --rebase origin main`
4. Run all checks and tests on the updated main: `docker exec inxr2-dev ./scripts/run-all-tests.sh`

### How It Works

1. `worktree-create.sh feature-x` creates:
   - Git worktree at `<parent-of-repo>/wt-inxr2-feature-x/`
   - `.env` file with unique ports and container prefix
   - Docker stack: `inxr2-feature-x-dev` container
2. Each container has its own embedded PostgreSQL (data in `pgdata` volume)
3. The main worktree needs no `.env` — defaults work (ports 8000/5173/9222)
4. All scripts (`dev-shell.sh`, `run-all-tests.sh`, etc.) auto-detect the container name from `.env`

### Worktree Prompt Files

When creating a worktree and crafting a prompt for a new Claude instance, **always write the prompt to a file** in the worktree directory:
- File name: `instructions.txt` (always the same name)
- Location: root of the worktree directory (e.g., `../wt-inxr2-<branch>/instructions.txt`)
- Content: the full prompt/summary that would be given to the new Claude instance
- **IMPORTANT**: Always start `instructions.txt` with:
  ```
  FIRST: Set your terminal tab title to the branch name:
    echo -ne "\033]0;<branch-name>\007"
  ```
  This ensures spawned Claude sessions set their tab title immediately so the user can identify which worktree each terminal belongs to.

This ensures the prompt is preserved and easily accessible when opening a new Claude Code session in the worktree.

- **Do NOT commit `instructions.txt`** — it is a local-only file for session bootstrapping. It is listed in `.gitignore`.

### Container Naming

- Main: `inxr2-dev`, `inxr2-playwright`
- Worktree: `inxr2-<branch>-dev`, `inxr2-<branch>-playwright`

### Using the Main MCP from Worktrees

Worktree sessions should use the **main MCP server** (on `inxr2-dev`) for code exploration — it has all the indexed data. Since Claude Code runs on the host, any worktree can reach the main container:

```bash
# From ANY worktree session — use main container for MCP queries
docker exec inxr2-dev bash -c '
cd /workspace/mcp-server
INXR2_API_URL=http://localhost:8000 python -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_symbols

async def main():
    client = HttpInxr2Client(\"http://localhost:8000\")
    result = await search_symbols.handle(client, {\"query\": \"MySymbol\", \"repository\": \"inxr2\"})
    print(result)
    await client.close()

asyncio.run(main())
"'
```

- ✅ **Read/explore code:** Always use `docker exec inxr2-dev` (main MCP with indexed data)
- ✅ **Test MCP changes:** Use worktree's own container if working on MCP code specifically
- The main `inxr2-dev` container must be running for worktree MCP access to work

## Regression Testing

On-demand regression suite covering indexing pipeline and browser UI.
Run when the user asks (e.g., "run regression tests"). Can be run on any branch — main, worktree, or before merging.

**Full test plan:** See `docs/regression-tests.md` for all 48 test cases.

**Testing philosophy:** No hardcoded expected data. Each test discovers what to expect by querying git or the API first, then verifies the UI matches. See "Discover → Navigate → Verify" pattern in the test plan.

### Phase 1: Indexing

Re-index all repos from `config.yaml` (last 10 days) to verify the full indexing pipeline:

```bash
# Reset DB and re-index all repos
docker exec inxr2-dev inxr2 index --config config.yaml --reset-db --yes --days 10

# Verify status
docker exec inxr2-dev inxr2 status
```

Run IX-01 through IX-05 from `docs/regression-tests.md`:
- IX-01: Reset DB and index all repos
- IX-02: Verify indexing status (all repos, non-zero counts)
- IX-03: Verify API serves indexed data (matches config.yaml)
- IX-04: Verify multi-language symbol extraction (discover from git, verify via API)
- IX-05: Compare indexing times/counts against `index.log` history (flag >20% slowdowns or count drops)

### Phase 2: QA Browser

Start backend, frontend, and QA agent, then run browser tests:

```bash
# Start backend + frontend (if not running)
docker exec -d inxr2-dev inxr2 serve --reload
docker exec -d -w /workspace/frontend inxr2-dev npm run dev

# Start QA agent
docker compose -f docker-compose.dev.yml --profile qa up -d playwright
curl http://localhost:9222/health  # verify
```

Run RT-01 through RT-23 from `docs/regression-tests.md`:

| Area | Tests | Validated Against |
|------|-------|-------------------|
| Home | RT-01 to RT-03 | API repo count and stats |
| Browse | RT-04 to RT-12 | `git ls-tree`, `git blame`, file content |
| Search | RT-13 to RT-16 | `git ls-files`, `grep` patterns from repos |
| History | RT-17 to RT-18 | `git log --oneline` |
| Navigation | RT-19 to RT-20 | URL params, `config.yaml` branches |
| Cross-cutting | RT-21 to RT-23 | URL state, color change, `grep '^#'` heading |

### Phase 3: MCP Server

Verify MCP tools return correct data by calling handlers directly against the live INXR2 API:

```bash
# Ensure MCP dependencies are installed
docker exec inxr2-dev pip install -e "/workspace/mcp-server[dev]"
```

Run MCP-01 through MCP-12 from `docs/regression-tests.md`:

| Area | Tests | Validated Against |
|------|-------|-------------------|
| Discovery | MCP-01 to MCP-02 | API repo/branch listing |
| Symbols | MCP-03 to MCP-05 | API symbols endpoints |
| References | MCP-06 to MCP-07 | API references endpoint |
| Code Search | MCP-08 to MCP-09 | API search/text endpoint |
| Error Handling | MCP-10 | Graceful no-match messages |
| Unit Tests | MCP-11 | pytest test suite |
| Browse URLs | MCP-12 | QA agent navigation + page content |

### Interpreting Results

For each test:
1. **Discover** what data exists via git or API
2. **Navigate** the UI with QA agent curl commands
3. **Verify** UI output matches discovered data
4. If a test fails, take a screenshot: `curl "http://localhost:9222/screenshot/save?path=/tmp/rt-fail-<ID>.png"`

### Reporting

After the full suite, report a summary to the user:

```
Regression Test Results:
- Indexing: X/7 passed
- Browser:  X/29 passed
- MCP:      X/12 passed
- Total:    X/48 passed
- Failed:   [list any failures with ID and brief reason]
```

If all pass, report: **"Regression suite: 48/48 passed (7 indexing + 29 browser + 12 MCP)."**

### When to Run

- **On demand** when the user asks to "run regression tests" or "run QA tests"
- Can target any branch — main, a worktree, or pre-merge verification
- Before any release or deployment

## Key Commands Reference

```bash
# Quick start
docker compose -f docker-compose.dev.yml up -d --build
docker exec -it inxr2-dev bash

# Development
./scripts/run-all-tests.sh        # Run ALL tests
pytest --cov=src                  # Backend tests
cd frontend && npm test           # Frontend tests

# Code quality
black . && isort .                # Format Python
cd frontend && npm run format     # Format TypeScript

# Database
alembic upgrade head              # Apply migrations
alembic revision --autogenerate   # Create migration

# Indexing (ALWAYS use config file, NEVER --path /workspace)
inxr2 index --config config.yaml              # Index all repos
inxr2 index --config config.yaml --repo X     # Index specific repo

# Running apps
inxr2 serve --reload              # Backend
cd frontend && npm run dev        # Frontend

# Worktrees (run on host)
./scripts/worktree-create.sh feature-x    # Create isolated worktree
./scripts/worktree-remove.sh feature-x    # Tear down worktree
./scripts/worktree-list.sh                # Show all worktrees

# Production
docker compose build              # Build
docker compose up -d              # Start
docker compose logs -f            # Logs
```
