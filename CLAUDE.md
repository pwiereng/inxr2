# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

INXR2 is a cross-reference code browser for git repositories, similar to LXR but designed for modern git-based workflows. It enables semantic code navigation, temporal browsing (code at any point in time), and cross-repository search.

**Tech Stack:** FastAPI (Python) + React (TypeScript) + PostgreSQL + Tree-sitter + Docker

**Architecture:** Clean Architecture (Hexagonal/Ports & Adapters) - see "Architecture" section below.

## Critical Development Guidelines

⚠️ **BEFORE making any changes:**

1. **Docker-Only Development**
   - ❌ NEVER run `npm install`, `pip install`, or `uv pip install` on host machine
   - ✅ ALWAYS run package management inside Docker containers
   - All development must be done inside `inxr2-dev` container

2. **Testing Requirements**
   - ✅ MANDATORY: Run `./scripts/run-all-tests.sh` before EVERY commit
   - All code changes MUST include tests
   - Use dependency injection, NOT mocking (see test examples)
   - Minimum 80% test coverage
   - ⚠️ **Test Independence**: Tests MUST be self-contained and NOT depend on:
     - Specific test repositories in `/repos/test-repos/`
     - The actual workspace git history
     - Any external data that could change
   - Use `tmp_path` fixtures and create controlled test data (e.g., temp git repos)
   - Tests must pass regardless of which repositories are configured

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

## Common Commands

### Starting Development Environment

```bash
# Start all services
docker-compose -f docker-compose.dev.yml up -d

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

See `tests/unit/application/test_use_cases.py` for complete examples.

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
```

## Important Files

- **DESIGN.md** - Complete design document with architecture decisions
- **IMPLEMENTATION_PLAN.md** - Phase-by-phase implementation plan (currently in Phase 1.12)
- **CONTRIBUTING.md** - Coding standards, testing philosophy, git workflow
- **docs/database-schema.md** - Complete database schema with design rationale

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
- SQLite compatibility: Use JSON not ARRAY, Text not TSVECTOR
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

See `tests/unit/application/test_use_cases.py` for complete examples.

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
- PostgreSQL: `localhost:5432` (from dev container: `postgres:5432`)
  - Database: `inxr2_dev`
  - User: `inxr2_user`
  - Password: `inxr2_dev_password` (from `.env.dev`)

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
- CLI framework with Click (`inxr2 index full|incremental|status`)
- Git integration via GitPython (commit tracking, file diffs)
- Full and incremental indexing workflows
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
- Tree-sitter AST parsing for Python, TypeScript, and JavaScript
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

**Next Phase:** 1.12 Remote Repository Support - Clone and index repositories from URLs

See `IMPLEMENTATION_PLAN.md` for complete roadmap.

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
- TypeScript: `"strict": true` in tsconfig.json

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
inxr2 index full --config config.yaml --repo inxr2

# ✅ CORRECT: Index all configured repos
inxr2 index full --config config.yaml

# ❌ WRONG: Never index working directory
inxr2 index full --path /workspace
inxr2 index full --path .
```

**Why this matters:**
- Indexing creates database records tied to a specific path
- Indexing `/workspace` creates a duplicate repo with wrong path
- The frontend looks up repos by name, so duplicates cause stale data issues
- Each repository should exist exactly once in the database

**Config file (`config.yaml`) defines:**
- Repository names and paths under `/repos/test-repos/`
- Branches to index
- Languages to parse

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

## Getting Help

- **Architecture questions:** See DESIGN.md
- **Implementation plan:** See IMPLEMENTATION_PLAN.md
- **Database schema:** See docs/database-schema.md
- **Coding standards:** See CONTRIBUTING.md
- **Development tasks:** See README.md

## Key Commands Reference

```bash
# Quick start
docker-compose -f docker-compose.dev.yml up -d
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
inxr2 index full --config config.yaml              # Index all repos
inxr2 index full --config config.yaml --repo X     # Index specific repo
inxr2 index incremental --config config.yaml       # Incremental update

# Running apps
inxr2 serve --reload              # Backend
cd frontend && npm run dev        # Frontend

# Production
docker-compose build              # Build
docker-compose up -d              # Start
docker-compose logs -f            # Logs
```
