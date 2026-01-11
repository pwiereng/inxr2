# INXR2 Implementation Plan

This document outlines the step-by-step implementation plan for building INXR2, a cross-reference code browser for git repositories.

## Overview

INXR2 is a modern code browser similar to LXR but designed specifically for git-based workflows. It provides semantic code navigation, temporal browsing, and cross-repository search capabilities.

**Tech Stack**: FastAPI (Python) + React (TypeScript) + PostgreSQL + Tree-sitter + Docker

**Architecture**: Clean Architecture (Hexagonal/Ports & Adapters)

**Current Status**: Phase 1.6 Next (Cross-Reference Code Browser UI)
- ✅ Phase 1.1: Project Setup (COMPLETED)
- ✅ Phase 1.2: React Frontend and Development Infrastructure (COMPLETED)
- ✅ Phase 1.3: Database Foundation and Environment Configuration (COMPLETED 2026-01-04)
- ✅ Phase 1.4: Vertical Slice - Basic File Indexing (COMPLETED 2026-01-05)
- ✅ Phase 1.5: CLI Indexing Engine - Python & TypeScript (COMPLETED 2026-01-10)
- 🚧 Phase 1.6: Cross-Reference Code Browser UI (NEXT)
- ⏭️  Phase 2: Additional Language Support (Java, C#, Go, C/C++)
- ⏭️  Phase 3: Advanced Indexing Features

---

## Architecture Principles

### Clean Architecture Overview

The Python backend follows **Clean Architecture** principles (also known as Hexagonal Architecture or Ports & Adapters):

```
┌─────────────────────────────────────────────────────────────┐
│                    Clean Architecture Layers                 │
│                                                               │
│   ┌───────────────────────────────────────────────┐          │
│   │  Layer 4: Infrastructure (outermost)          │          │
│   │  FastAPI, SQLAlchemy, Tree-sitter, Git        │          │
│   │   ┌───────────────────────────────────┐       │          │
│   │   │  Layer 3: Adapters                │       │          │
│   │   │  Controllers, CLI, Repositories   │       │          │
│   │   │   ┌───────────────────────┐       │       │          │
│   │   │   │  Layer 2: Application │       │       │          │
│   │   │   │  Use Cases, Ports     │       │       │          │
│   │   │   │   ┌──────────────┐    │       │       │          │
│   │   │   │   │   Layer 1:   │    │       │       │          │
│   │   │   │   │   Domain     │    │       │       │          │
│   │   │   │   │   (Entities) │    │       │       │          │
│   │   │   │   └──────────────┘    │       │       │          │
│   │   │   └───────────────────────┘       │       │          │
│   │   └───────────────────────────────────┘       │          │
│   └───────────────────────────────────────────────┘          │
│                                                               │
│   Dependencies flow inward: Infrastructure → Domain          │
└─────────────────────────────────────────────────────────────┘
```

**Key Principles:**
1. **Dependency Rule**: Source code dependencies point inward only
2. **Domain Independence**: Business logic has no dependencies on frameworks or databases
3. **Ports & Adapters**: Use interfaces (ports) to decouple from external concerns
4. **Testability**: Test business logic without infrastructure (no mocking needed)

**Layer Responsibilities:**
- **Domain**: Pure business entities and rules (Repository, Symbol, Commit)
- **Application**: Use cases and business workflows (IndexRepository, SearchSymbols)
- **Adapters**: Connect use cases to external systems (API controllers, DB repositories)
- **Infrastructure**: Framework configuration and external dependencies

---

## Phase 1: Development Environment & Core Infrastructure

### 1.1 Docker Development Environment

**Objectives:**
- Set up Docker-based development environment
- Enable consistent development across all platforms
- Configure VS Code Dev Container for seamless development
- Establish multi-container architecture for services

**Tasks:**
- [x] Create development `Dockerfile.dev`:
  - [x] Base image: Python 3.11+ with Node.js 18+
  - [x] Install system dependencies: git, postgresql-client, build-essential
  - [x] Install tree-sitter build dependencies
  - [x] Set up working directory structure
  - [x] Configure non-root user for development
  - [x] Install development tools (debugger, linters)
  - [x] Install uv package manager for fast installs
  - [x] Create virtual environment for Python packages
  - [x] Set up entrypoint script for auto-dependency installation
- [x] Create `docker-compose.dev.yml`:
  - [x] **Backend service** (FastAPI development server):
    - [x] Build from Dockerfile.dev
    - [x] Mount source code volumes for hot reload
    - [x] Expose port 8000 for API
    - [x] Environment variables for development
    - [x] Depends on PostgreSQL service
  - [x] **Frontend service** (Vite/React dev server):
    - [x] Combined with backend in single dev container
    - [x] Mount frontend source for hot reload
    - [x] Expose port 5173 for Vite dev server
    - [x] Backend CORS configured for frontend
  - [x] **PostgreSQL service**:
    - [x] Use official PostgreSQL 15 image
    - [x] Configure persistent volume for data
    - [x] Set development credentials
    - [x] Expose port 5432
    - [x] Health check configuration
  - [x] **Networks**: Create shared network for inter-service communication
  - [x] **Volumes**: Define named volumes for persistence
- [x] Create production `Dockerfile`:
  - [x] Multi-stage build:
    - [x] Stage 1: Build frontend (Node.js)
    - [x] Stage 2: Build backend (Python)
    - [x] Stage 3: Final image with both frontend and backend
  - [x] Non-root user for security
  - [x] Health check configured
  - [x] Optimized for smaller image size
- [x] Create `docker-compose.yml` (production):
  - [x] PostgreSQL service (separate container)
  - [x] App service with backend+frontend
  - [x] Volume mounts for database persistence
  - [x] Port exposure (8000)
  - [x] Health checks for both services
  - [x] Environment variables with defaults
- [x] Configure VS Code Dev Container (`.devcontainer/devcontainer.json`):
  - [x] Use docker-compose.dev.yml as base
  - [x] Configure VS Code extensions:
    - [x] Python (with Pylance, debugger, black-formatter, ruff)
    - [x] ESLint, Prettier
    - [x] Docker extension
    - [x] GitLens
    - [x] Thunder Client (API testing)
  - [x] Set up workspace settings
  - [x] Configure integrated terminal
  - [x] Port forwarding configuration
  - [x] Post-create commands (install dependencies)
- [x] Create `.dockerignore`:
  - [x] Exclude node_modules, venv, __pycache__
  - [x] Exclude .git, .github
  - [x] Exclude test artifacts, coverage reports
  - [x] Exclude local data directories
- [x] Add development scripts:
  - [x] `scripts/dev-start.sh` - Start development environment
  - [x] `scripts/dev-stop.sh` - Stop all services
  - [x] `scripts/dev-logs.sh` - View logs
  - [x] `scripts/dev-shell.sh` - Open shell in container
  - [x] `scripts/dev-reset-db.sh` - Reset database
  - [x] `scripts/docker-entrypoint.sh` - Auto-install dependencies on startup
- [x] Document Docker setup:
  - [x] Update DEVELOPMENT.md with Docker instructions
  - [x] Update README.md with Quick Start guide
  - [x] Quick start guide for Docker Desktop
  - [x] Troubleshooting common Docker issues
  - [x] Port mapping reference
  - [x] Helper scripts documentation

**Deliverables:**
- ✅ Docker development environment fully configured
- ✅ Dev container working in VS Code/Cursor
- ✅ All services start with single command
- ✅ Hot reload working for backend and frontend
- ✅ Database persistence configured
- ✅ Development documentation updated
- ✅ Automatic dependency installation via entrypoint
- ✅ Hello world apps deployed and tested
- ✅ Production Docker build and deployment verified

**Status:** ✅ **COMPLETED**

**Date Completed:** 2025-12-31

**Notes:**
- Used uv package manager for 10-100x faster Python installs
- Combined backend+frontend in single dev container for simplicity
- Entrypoint script ensures dependencies install regardless of launch method
- Both VS Code/Cursor and docker-compose workflows supported

---

### 1.1.1 Hello World Applications (Verification)

**Objectives:**
- Verify full stack is working end-to-end
- Test container networking and CORS
- Validate development workflow

**Tasks:**
- [x] Create FastAPI hello world app (`src/inxr2/main.py`):
  - [x] Root endpoint (/) returning API info
  - [x] Health check endpoint (/api/health)
  - [x] Interactive hello endpoint (/api/hello?name=X)
  - [x] CORS middleware configured for frontend
- [x] Update CLI serve command:
  - [x] Run uvicorn server
  - [x] Support --host, --port, --reload flags
- [x] Create React hello world app:
  - [x] index.html entry point
  - [x] main.tsx with React root
  - [x] App.tsx with interactive UI
  - [x] Backend status checking
  - [x] API call demonstration
  - [x] Styled components with gradient design
- [x] Configure Vite for Docker:
  - [x] Listen on 0.0.0.0 for container access
  - [x] Proper port configuration
- [x] Test full stack:
  - [x] Backend serves on port 8000
  - [x] Frontend serves on port 5173
  - [x] Frontend successfully calls backend
  - [x] CORS working correctly

**Deliverables:**
- ✅ Working FastAPI backend with 3 endpoints
- ✅ Working React frontend with backend integration
- ✅ Full stack communication verified
- ✅ Development workflow validated

**Status:** ✅ **COMPLETED**

**Date Completed:** 2025-12-31

**Commands to run:**
```bash
# Start backend
docker exec -d inxr2-dev inxr2 serve --reload

# Start frontend
docker exec -d inxr2-dev bash -c "cd frontend && npm run dev"

# Access apps
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
# API Docs: http://localhost:8000/docs
```

---

### 1.1.2 Production Deployment (Verification)

**Objectives:**
- Verify production Docker build works correctly
- Test multi-stage build process
- Validate static file serving in production
- Confirm database connectivity

**Tasks:**
- [x] Create multi-stage production Dockerfile:
  - [x] Frontend build stage (Node.js 18)
  - [x] Backend build stage (Python 3.11)
  - [x] Final runtime image with both
  - [x] Static file serving configured
- [x] Update FastAPI to serve static frontend:
  - [x] Serve built frontend at root (/)
  - [x] API endpoints at /api/*
  - [x] Proper route ordering
- [x] Fix frontend build configuration:
  - [x] Remove TypeScript check from production build
  - [x] Vite build outputs to dist/
- [x] Test production deployment:
  - [x] Build production images
  - [x] Start containers via docker-compose.yml
  - [x] Verify frontend HTML served at root
  - [x] Test all API endpoints
  - [x] Confirm database connection

**Deliverables:**
- ✅ Production Dockerfile with multi-stage build
- ✅ Production docker-compose.yml with postgres + app
- ✅ Frontend served as static files in production
- ✅ All endpoints working (/, /api, /api/health, /api/hello)
- ✅ Database service running and healthy

**Status:** ✅ **COMPLETED**

**Date Completed:** 2026-01-01

**Commands to run:**
```bash
# Build and start production
docker-compose build
docker-compose up -d

# Test endpoints
curl http://localhost:8000/              # Frontend HTML
curl http://localhost:8000/api           # API info
curl http://localhost:8000/api/health    # Health check
curl http://localhost:8000/api/hello     # Hello endpoint

# Stop production
docker-compose down
```

**Notes:**
- Production uses multi-stage build to optimize image size
- Frontend and backend combined in single app container
- PostgreSQL runs in separate container for production
- Static files served via FastAPI StaticFiles middleware
- Route ordering critical: /api routes before catch-all route

---

### 1.2 Project Setup

**Objectives:**
- Establish Python project structure following **Clean Architecture** (inside Docker)
- Set up TypeScript/React frontend (inside Docker)
- Configure all development tooling
- Enable automated code quality checks

**Tasks:**
- [x] Create Python package structure following Clean Architecture (`src/inxr2/`)
  - [x] **Layer 1 - Domain** (innermost, pure business logic):
    - [x] `domain/entities/` - Core business objects (Repository, Commit, File, Symbol, Reference)
    - [x] `domain/value_objects/` - Immutable value objects (SymbolLocation, CommitHash, SymbolKind)
    - [x] `domain/exceptions/` - Domain-specific exceptions
    - [x] `domain/services/` - Domain services (symbol resolution logic)
  - [x] **Layer 2 - Application** (use cases):
    - [x] `application/use_cases/indexing/` - Indexing use cases (IndexRepository, IncrementalIndex)
    - [x] `application/use_cases/search/` - Search use cases (SearchSymbols, FindDefinition, FindReferences)
    - [x] `application/use_cases/repository_browsing/` - Browsing use cases (GetFileContent, GetFileHistory, CompareCommits)
    - [x] `application/ports/repositories/` - Repository pattern interfaces (SymbolRepositoryPort, FileRepositoryPort)
    - [x] `application/ports/services/` - External service interfaces (ParserServicePort, GitServicePort, ConfigServicePort)
    - [x] `application/dtos/` - Data Transfer Objects (requests/, responses/)
  - [x] **Layer 3 - Adapters** (interface adapters):
    - [x] `adapters/api/controllers/` - FastAPI route handlers (SymbolController, SearchController)
    - [x] `adapters/api/serializers/` - Response serializers
    - [x] `adapters/cli/commands/` - CLI commands (IndexCommand, ServeCommand)
    - [x] `adapters/persistence/repositories/` - Repository implementations (PostgresSymbolRepository, PostgresFileRepository)
    - [x] `adapters/persistence/models/` - SQLAlchemy ORM models
    - [x] `adapters/external/` - External service implementations (TreeSitterParser, GitClient)
  - [x] **Layer 4 - Infrastructure** (frameworks & drivers, outermost):
    - [x] `infrastructure/fastapi/` - FastAPI app setup
    - [x] `infrastructure/database/` - Database connection, migrations
    - [x] `infrastructure/config/` - Settings and dependency injection container
    - [x] `infrastructure/logging/` - Logging configuration
  - [x] Test directory structure: `tests/unit/`, `tests/integration/`, `tests/fixtures/`
- [x] Set up dependency injection:
  - [x] Create DI container in `infrastructure/config/dependency_injection.py`
  - [x] Define all ports (interfaces) using Python ABC in `application/ports/`
  - [x] Wire up dependencies: adapters implement ports, inject into use cases
  - [x] Configure container for both API and CLI entry points
- [x] Configure `pyproject.toml` with dependencies:
  - [x] FastAPI, uvicorn, pydantic
  - [x] SQLAlchemy, alembic, psycopg2
  - [x] tree-sitter and language bindings
  - [x] GitPython or pygit2
  - [x] PyYAML for configuration
  - [x] Dev dependencies: pytest, pytest-cov, black, ruff, mypy
- [x] Set up React frontend:
  - [x] Initialize with Vite (recommended) in `frontend/` directory
  - [x] Configure TypeScript with strict mode
  - [x] Add dependencies: React Router, MUI, Prism.js, state management
  - [x] Set up testing: vitest, React Testing Library
  - [x] Configure Vite proxy to backend API
- [x] Configure development tooling:
  - [x] Verify pre-commit hooks work (already configured in `.pre-commit-config.yaml`)
  - [x] Set up VS Code/IDE configurations (via devcontainer.json)
  - [x] Add `.editorconfig` for consistency
- [x] Create initial test infrastructure:
  - [x] Backend: pytest fixtures, test database setup
  - [x] Frontend: test utilities, mock data helpers, vitest setup
- [x] Verify Docker environment:
  - [x] Run tests in container
  - [x] Verify hot reload works
  - [x] Test database connectivity
  - [x] Verify frontend dev server

**Deliverables:**
- ✅ Working development environment inside Docker
- ✅ All tooling configured and verified
- ✅ Clean Architecture project structure in place (backend)
- ✅ Dependency injection container configured (backend)
- ✅ React frontend with TypeScript, MUI, React Router
- ✅ API client with dependency injection pattern
- ✅ Context API for app-wide state
- ✅ Comprehensive test infrastructure (backend + frontend)
- ✅ Tests can be run (even if minimal)
- ✅ Hot reload functional for development

**Clean Architecture Benefits:**
- **Testability**: Domain and application layers can be tested without databases or frameworks
- **Flexibility**: Easy to swap implementations (e.g., switch from PostgreSQL to another DB)
- **Maintainability**: Clear separation of concerns, business logic isolated from infrastructure
- **Dependency Rule**: Dependencies point inward, domain has no external dependencies

**Status:** ✅ **COMPLETED**

**Date Completed:** 2026-01-02

**Notes:**
- Backend: Clean Architecture with all 4 layers implemented
- Frontend: React + TypeScript with strict mode, MUI component library
- Dependency injection used throughout (no mocking in tests)
- API client designed for DI with injectable fetch function
- Context API provides app-wide services and state
- Comprehensive test infrastructure with vitest + React Testing Library
- Hybrid project structure (shared folders + features/ for later)
- **Development scripts created**: clean.sh, build.sh, run-all-tests.sh, clean-rebuild.sh
- **Documentation updated**: CONTRIBUTING.md, README.md, DESIGN.md with Docker-only workflow
- **Guidelines established**: .claude-guidelines created for AI assistant reference
- **isort/black compatibility**: Configured with `profile = "black"` in pyproject.toml
- **Package quality standards**: No deprecated/vulnerable packages policy enforced
- **All tests passing**: 21 backend + 17 frontend tests, 0 vulnerabilities

**Estimated Complexity:** Medium-High (increased due to Clean Architecture setup)

---

### 1.3 Database Foundation

**Objectives:**
- Design complete database schema
- Set up migration system
- Create data access layer following Clean Architecture (Repository pattern)
- Enable temporal querying
- Configure environment variables for database credentials

**Clean Architecture Note:**
- Domain entities (in `domain/entities/`) are pure Python dataclasses/Pydantic models
- SQLAlchemy ORM models (in `adapters/persistence/models/`) are separate from domain entities
- Repository implementations map between domain entities and ORM models

**Tasks:**
- [x] Define domain entities (in `domain/entities/`):
  - [x] `Repository` entity - domain model for git repository
  - [x] `Commit` entity - domain model for commit
  - [x] `File` entity - domain model for source file
  - [x] `Symbol` entity - domain model for code symbol
  - [x] `Reference` entity - domain model for symbol reference
  - [x] `IndexStatus` entity - domain model for indexing status
- [x] Design PostgreSQL schema:
  - [x] `repositories` table (id, name, url, config, timestamps)
  - [x] `commits` table (hash, repo_id, branch, author info, timestamps, parent_hashes)
  - [x] `files` table (id, repo_id, commit_id, path, content_hash, language, metadata)
  - [x] `symbols` table (id, name, kind, file_id, location, scope, metadata JSONB, tsvector)
  - [x] `references` table (id, source_file_id, location, target_symbol_id, ref_type, metadata)
  - [x] `index_status` table (repo_id, branch, last_indexed_commit, status, statistics)
- [x] Create indexes:
  - [x] B-tree on symbol names, file paths, commit hashes
  - [x] GIN for full-text search on symbol names (tsvector)
  - [x] Composite indexes for common queries (repo_id + name + kind)
  - [x] Foreign key indexes for relationships
- [x] Set up Alembic (in `infrastructure/database/migrations/`):
  - [x] Initialize alembic configuration with environment variables
  - [x] Create initial migration (edc605da5d0a)
  - [x] Configure autogenerate with black formatting
- [x] Implement database infrastructure (in `infrastructure/database/`):
  - [x] DatabaseConnection class with async engine
  - [x] Session factory with connection pooling (configurable via env vars)
  - [x] FastAPI dependency injection support
- [x] Create SQLAlchemy ORM models (in `adapters/persistence/models/`):
  - [x] `RepositoryModel`, `CommitModel`, `FileModel`, `SymbolModel`, `ReferenceModel`, `IndexStatusModel`
  - [x] Define relationships with proper foreign keys
  - [x] Handle field name conflicts (metadata → extra_metadata)
  - [x] SQLite compatibility (JSON instead of ARRAY, Text instead of TSVECTOR)
- [x] Create mappers (in `adapters/persistence/mappers.py`):
  - [x] Bidirectional conversion between domain entities and ORM models
  - [x] 6 mapper classes: RepositoryMapper, CommitMapper, FileMapper, SymbolMapper, ReferenceMapper, IndexStatusMapper
  - [x] Handle field name mapping and type conversions
- [x] Define repository ports/interfaces (in `application/ports/repositories.py`):
  - [x] `RepositoryPort` - Repository CRUD operations
  - [x] `CommitRepositoryPort` - Commit operations and queries
  - [x] `FileRepositoryPort` - File operations and temporal queries
  - [x] `SymbolRepositoryPort` - Symbol CRUD, search, and queries
  - [x] `ReferenceRepositoryPort` - Reference operations
  - [x] `IndexStatusRepositoryPort` - Indexing status tracking
  - [x] Define methods: CRUD operations, temporal queries, search
- [x] Implement repository adapters (in `adapters/persistence/repositories/`):
  - [x] `PostgresRepositoryAdapter` implements `RepositoryPort`
  - [x] Use mappers for entity ↔ model conversion
  - [x] Implement async CRUD operations with proper session management
- [x] Write comprehensive tests:
  - [x] Mapper tests (12 tests) - bidirectional conversion and round-trip
  - [x] Repository adapter tests (12 tests) - CRUD operations with real database
  - [x] Update existing use case tests with new signatures
  - [x] All 45 backend tests passing
  - [x] All 17 frontend tests passing
- [x] Environment configuration:
  - [x] Create .env.dev with development defaults
  - [x] Create .env.prod.example for production
  - [x] Create .env.example with all variables documented
  - [x] Update docker-compose.dev.yml to use env_file
  - [x] Update docker-compose.yml to use env_file
  - [x] Update .gitignore to exclude .env.prod
- [x] Database management scripts:
  - [x] `scripts/reset-database.sh` - Reset database from scratch
  - [x] `scripts/full-rebuild-test.sh` - Complete rebuild and test
  - [x] `scripts/verify-setup.sh` - Quick verification
- [x] Documentation:
  - [x] `docs/database-schema.md` - Complete schema design (600+ lines)
  - [x] `docs/ENV_SETUP.md` - Environment configuration guide
  - [x] `CLAUDE.md` - Guide for future Claude instances
  - [x] Update README.md with environment instructions
  - [x] `README.env` - Quick reference card
  - [x] `ENVIRONMENT_SETUP_SUMMARY.md` - Setup summary

**Deliverables:**
- ✅ Complete database schema with migrations
- ✅ Domain entities defined (framework-agnostic)
- ✅ Repository ports (interfaces) defined
- ✅ SQLAlchemy models in adapters layer
- ✅ Repository implementations with entity mapping
- ✅ Data access layer fully tested
- ✅ Environment configuration with .env files
- ✅ Database scripts (reset, rebuild, verify)

**Status:** ✅ **COMPLETED**

**Date Completed:** 2026-01-04

**Notes:**
- Temporal data model implemented - all entities tied to commits
- Complete separation of domain entities from ORM models
- Bidirectional mappers for entity ↔ model conversion
- Environment variables managed via .env files
- All 45 backend tests + 17 frontend tests passing
- Database migration applied and verified
- Created comprehensive database documentation (docs/database-schema.md)
- Created environment configuration guide (docs/ENV_SETUP.md)
- Added database management scripts:
  - `scripts/reset-database.sh` - Reset database from scratch
  - `scripts/full-rebuild-test.sh` - Complete rebuild and test
  - `scripts/verify-setup.sh` - Quick verification
- Updated docker-compose files to use .env.dev and .env.prod

**Estimated Complexity:** High (achieved)

---

### 1.4 Vertical Slice - Basic File Indexing

**Status:** ✅ COMPLETED (2026-01-05)

**Objective:** Implement minimal end-to-end feature demonstrating complete stack from database to UI.

**What Was Completed:**

**Backend:**
- IndexLocalDirectoryUseCase with full file indexing logic
- LanguageDetector service (60+ language support)
- API routes:
  - POST /api/index/local (trigger indexing)
  - GET /api/repositories (list all repositories)
  - GET /api/repositories/{id} (get repository details)
  - GET /api/repositories/{id}/files (list repository files)
- Repository adapters (PostgresRepositoryAdapter, PostgresCommitRepository, PostgresFileRepository)

**Frontend:**
- Repositories listing page (Material-UI)
- Files listing page with search and filtering
- Updated Home page with navigation

**Testing:**
- 47 new tests added
- Test coverage: 85% (up from 58%)
- Total: 92 tests passing
- Unit tests: LanguageDetector, Repository use cases, IndexLocalDirectory
- Integration tests: Repository adapters, API endpoints
- Custom StringArray type for PostgreSQL/SQLite compatibility

**Development Dependencies:**
- Added httpx for async API testing

**Key Files:**
- `src/inxr2/application/use_cases/indexing/index_local_directory.py`
- `src/inxr2/domain/services/language_detector.py`
- `src/inxr2/adapters/api/routes/indexing.py`
- `src/inxr2/adapters/api/routes/repositories.py`
- `frontend/src/pages/Repositories.tsx`
- `frontend/src/pages/Files.tsx`
- `tests/unit/application/test_index_local_directory.py` (9 tests)
- `tests/unit/domain/test_language_detector.py` (14 tests)
- `tests/integration/adapters/test_repository_adapters.py` (14 tests)
- `tests/integration/api/test_api_endpoints.py` (4 tests)

**Limitations (By Design - MVP):**
- No Git integration (dummy commits with timestamp hashes)
- No Tree-sitter parsing (no symbol extraction)
- No authentication/authorization
- No path validation in API
- Serial file processing (not async)

**Estimated Complexity:** Medium (achieved)

---

### 1.5 CLI Indexing Engine (Python & TypeScript)

**Status:** ✅ COMPLETED (2026-01-10)

**Objectives:**
- Build CLI-driven indexing for Python and TypeScript
- Integrate Git for commit tracking and incremental updates
- Use Tree-sitter for semantic symbol extraction
- Store indexed data in PostgreSQL using existing schema
- Support both full and incremental indexing modes
- Test by indexing the INXR2 project itself

**Scope Decisions:**
- **Languages**: Python and TypeScript/JavaScript only (others deferred)
- **Configuration**: CLI arguments only (YAML config deferred to later phase)
- **Scheduling**: Manual CLI invocation only (batch/scheduled indexing deferred)
- **Frontend**: Not connected yet (DB queries for verification)

---

#### 1.5.1 CLI Framework

**Tasks:**
- [x] Set up Click-based CLI:
  - [x] `inxr2 index` command with subcommands
  - [x] `inxr2 index full --path <dir>` - Full indexing from scratch
  - [x] `inxr2 index incremental --path <dir>` - Incremental update
  - [x] `inxr2 index status --path <dir>` - Show indexing status
  - [x] Global options: `--verbose`, `--log-level`, `--branch`
- [x] Add path validation:
  - [x] Verify directory exists
  - [x] Verify .git directory exists
  - [x] Handle relative and absolute paths
- [x] Implement logging:
  - [x] Progress output with Rich progress bars
  - [x] Error reporting with context
  - [x] Verbose mode for debugging

**CLI Interface:**
```bash
# Full index of a repository
inxr2 index full --path /path/to/repo --branch main

# Incremental update (only new commits)
inxr2 index incremental --path /path/to/repo --branch main

# Check indexing status
inxr2 index status --path /path/to/repo

# Options
--verbose, -v       Enable verbose output
--log-level         Set log level (DEBUG, INFO, WARNING, ERROR)
--branch, -b        Branch to index (default: current branch)
--languages         Languages to index (default: python,typescript)
```

---

#### 1.5.2 Git Integration

**Tasks:**
- [x] Install and configure GitPython:
  - [x] Add gitpython to dependencies
  - [x] Create `GitService` adapter implementing `GitServicePort`
- [x] Implement GitService class:
  - [x] `get_repository_info(path)` - Get repo name, URL, current branch
  - [x] `get_current_commit(path, branch)` - Get HEAD commit hash
  - [x] `get_commits_since(path, since_commit, branch)` - List new commits
  - [x] `get_commit_info(path, commit_hash)` - Get commit metadata
  - [x] `get_changed_files(path, from_commit, to_commit)` - Diff between commits
  - [x] `get_file_content(path, commit_hash, file_path)` - File at specific commit
  - [x] `list_files(path, commit_hash)` - All files at commit
- [x] Handle edge cases:
  - [x] First-time indexing (no previous commit)
  - [x] Detached HEAD state
  - [x] Missing or invalid .git directory
  - [x] Binary files (skip)
- [x] Add Git integration tests:
  - [x] Test with real git repository (INXR2 itself)
  - [x] Test commit traversal
  - [x] Test file diff detection

---

#### 1.5.3 Tree-sitter Setup

**Tasks:**
- [x] Symbol extraction implemented:
  - [x] Regex-based extraction as placeholder (Tree-sitter integration deferred)
  - [x] Pattern matching for Python and TypeScript
  - [x] Works with existing file content
- [x] Implement parser factory:
  - [x] Select parser based on file extension
  - [x] `.py` → Python extractor
  - [x] `.ts`, `.tsx` → TypeScript extractor
  - [x] `.js`, `.jsx` → JavaScript extractor
  - [x] Return None for unsupported languages
- [x] Add extraction tests:
  - [x] Parse sample Python file
  - [x] Parse sample TypeScript file
  - [x] Verify symbol extraction

**Note:** Used regex-based symbol extraction as a placeholder. Full Tree-sitter integration can be added later for more accurate AST-based parsing.

---

#### 1.5.4 Symbol Extraction - Python

**Tasks:**
- [x] Create `PythonSymbolExtractor` class:
  - [x] Implement `SymbolExtractorPort` interface
  - [x] Extract symbols using regex patterns
- [x] Extract symbol definitions:
  - [x] Function definitions (`def function_name`)
  - [x] Async function definitions (`async def`)
  - [x] Class definitions (`class ClassName`)
  - [x] Method definitions (functions inside classes)
  - [x] Module-level variable assignments
  - [x] Constants (UPPER_CASE assignments)
- [x] Extract symbol metadata:
  - [x] Name and qualified name (module.class.method)
  - [x] Kind (function, class, method, variable, constant)
  - [x] Location (start_line, start_column, end_line, end_column)
  - [x] Parent symbol (for nested definitions)
  - [x] Scope path
- [x] Extract references:
  - [x] Import statements (`import x`, `from x import y`)
  - [x] Function/method calls
  - [x] Class instantiations
- [x] Add comprehensive tests:
  - [x] Test with various Python patterns
  - [x] Test with INXR2's own Python code
  - [x] Verify line/column accuracy

---

#### 1.5.5 Symbol Extraction - TypeScript

**Tasks:**
- [x] Create `TypeScriptSymbolExtractor` class:
  - [x] Implement `SymbolExtractorPort` interface
  - [x] Extract symbols using regex patterns
- [x] Extract symbol definitions:
  - [x] Function declarations (`function name()`)
  - [x] Arrow functions (`const name = () => {}`)
  - [x] Class declarations
  - [x] Interface declarations
  - [x] Type aliases (`type Name = ...`)
  - [x] Variable declarations (const, let, var)
  - [x] Method definitions
- [x] Extract symbol metadata:
  - [x] Name and qualified name
  - [x] Kind (function, class, interface, type, variable, method)
  - [x] Location (line, column)
  - [x] Export status (exported, default export)
- [x] Extract references:
  - [x] Import statements (ES6 imports)
  - [x] Function calls
  - [x] Type references
  - [x] JSX component usage
- [x] Add comprehensive tests:
  - [x] Test with various TypeScript patterns
  - [x] Test with INXR2's frontend code
  - [x] Test JSX/TSX handling

---

#### 1.5.6 Indexing Pipeline

**Tasks:**
- [x] Create `IndexingService` use case:
  - [x] Orchestrate Git, parsing, and database operations
  - [x] Implemented in `index_command.py`
- [x] Implement full indexing workflow:
  1. Read repository info from Git
  2. Create/update repository record in DB
  3. Get current commit, create commit record
  4. List all files at current commit
  5. For each supported file:
     - Create file record
     - Parse with symbol extractor
     - Extract symbols and references
     - Store in database
  6. Update index_status with success
- [x] Implement incremental indexing workflow:
  1. Read repository info from Git
  2. Get last indexed commit from index_status
  3. Get list of changed files since last commit
  4. For added/modified files:
     - Delete old symbols/references for that file
     - Re-parse and re-index
  5. For deleted files:
     - Delete associated symbols/references
  6. Update index_status with new commit hash
- [x] Add batch processing:
  - [x] Batch database inserts
  - [x] Transaction per commit
  - [x] Rollback on errors
- [x] Add progress reporting:
  - [x] Rich progress bars with live statistics
  - [x] Total files to process
  - [x] Current file being processed
  - [x] Symbols/references found

---

#### 1.5.7 Database Integration

**Tasks:**
- [x] Enhance existing repository adapters:
  - [x] `PostgresSymbolRepository` - bulk insert support via `save_many()`
  - [x] `PostgresReferenceRepository` - bulk insert support via `save_many()`
  - [x] `PostgresIndexStatusRepository` - update tracking
- [x] Add new repository methods:
  - [x] `delete_by_file(file_id)` - For re-indexing symbols
  - [x] `delete_by_file(file_id)` - For re-indexing references
  - [x] `save_many(symbols)` - Batch insert symbols
  - [x] `save_many(references)` - Batch insert references
- [x] Schema enhancements:
  - [x] Removed `name_tsvector` from ORM (managed by DB triggers)
  - [x] Fixed timezone handling for Git dates (`_to_naive_utc()`)
  - [x] All indexes working correctly
- [x] Add database tests:
  - [x] Test bulk insert operations
  - [x] Test transaction handling
  - [x] Test incremental update logic

---

#### 1.5.8 Testing & Verification

**Tasks:**
- [x] Create test fixtures:
  - [x] Sample Python files with various patterns
  - [x] Sample TypeScript files with various patterns
  - [x] Edge cases (empty files, syntax errors)
- [x] Integration tests:
  - [x] Full index of test repository
  - [x] Incremental index after file changes
  - [x] Verify database contents match expectations
- [x] Self-indexing test:
  - [x] Run `inxr2 index full --path .` on INXR2 itself
  - [x] Query database to verify:
    - [x] All Python files indexed (68 files)
    - [x] All TypeScript files indexed (40 files)
    - [x] Symbols extracted correctly (440 total)
    - [x] References linked properly (473 total)
- [x] Verification queries:
  ```sql
  -- Count indexed items (actual results from INXR2)
  SELECT 'repositories' as table_name, COUNT(*) FROM repositories;  -- 1
  SELECT 'commits', COUNT(*) FROM commits;                          -- 1
  SELECT 'files', COUNT(*) FROM files;                              -- 108
  SELECT 'symbols', COUNT(*) FROM symbols;                          -- 440
  SELECT 'references', COUNT(*) FROM "references";                  -- 473

  -- Symbol breakdown by kind
  SELECT kind, COUNT(*) FROM symbols GROUP BY kind;
  -- class: 97, function: 48, method: 257, interface: 12, type: 6, ...
  ```
- [x] All 133 tests passing (SQLite compatibility verified)

---

**Deliverables:**
- ✅ Working CLI: `inxr2 index full|incremental|status --path <dir>`
- ✅ Git integration via GitPython
- ✅ Symbol extraction for Python and TypeScript (regex-based placeholder)
- ✅ Incremental indexing based on git commits
- ✅ Database population verified via queries
- ✅ Test coverage: 133 tests passing, SQLite + PostgreSQL compatible

**Success Criteria:**
- [x] Can run `inxr2 index full --path .` on INXR2 project
- [x] Database contains symbols from Python backend code (68 files, 280+ symbols)
- [x] Database contains symbols from TypeScript frontend code (40 files, 160+ symbols)
- [x] Incremental index only processes changed files
- [x] All tests pass including new indexing tests (133 total)

**Key Files:**
- `src/inxr2/adapters/cli/commands/index_command.py` - Main CLI command
- `src/inxr2/adapters/external/git_service.py` - GitPython integration
- `src/inxr2/adapters/external/symbol_extractors/` - Python/TypeScript extractors
- `src/inxr2/adapters/persistence/repositories/` - All repository adapters

**Notes:**
- Used regex-based symbol extraction as placeholder (Tree-sitter can be added later)
- Fixed timezone-aware datetime handling for Git dates
- Removed `name_tsvector` from ORM (PostgreSQL TSVECTOR managed by triggers)
- Rich progress bars provide excellent UX during indexing
- Cross-database compatibility: works with both PostgreSQL and SQLite

**Estimated Complexity:** High (achieved)

**Dependencies:**
- Phase 1.4 complete (database schema, repository adapters)
- GitPython package
- Rich package for progress bars

---

### 1.6 Cross-Reference Code Browser UI

**Status:** 🚧 NEXT

**Objectives:**
- Build a functional web UI to browse indexed code
- Enable symbol search and navigation
- Implement "Go to Definition" and "Find References" features
- Display code with syntax highlighting
- Provide file tree navigation

**Prerequisites:**
- Phase 1.5 complete (indexed data in database)
- INXR2 indexed: 108 files, 440 symbols, 473 references

---

#### 1.6.1 Backend API Endpoints

**Tasks:**
- [ ] Symbol endpoints:
  - [ ] `GET /api/symbols` - List/search symbols with filters
    - Query params: `q` (search), `kind`, `repository_id`, `limit`, `offset`
    - Returns: List of symbols with file path and location
  - [ ] `GET /api/symbols/{id}` - Get symbol details
    - Returns: Symbol with full metadata, file info, location
  - [ ] `GET /api/symbols/{id}/references` - Find all references to a symbol
    - Returns: List of references with source file and location
- [ ] File content endpoints:
  - [ ] `GET /api/files/{id}/content` - Get file content
    - Returns: File content as text, language, line count
  - [ ] `GET /api/files/{id}/symbols` - Get all symbols in a file
    - Returns: List of symbols with locations for highlighting
- [ ] Repository tree endpoint:
  - [ ] `GET /api/repositories/{id}/tree` - Get file tree structure
    - Query params: `commit_id` (optional, defaults to latest)
    - Returns: Nested tree structure of directories and files
- [ ] Add Pydantic response models for all endpoints
- [ ] Add OpenAPI documentation

**API Response Examples:**
```json
// GET /api/symbols?q=Repository&kind=class
{
  "items": [
    {
      "id": 123,
      "name": "Repository",
      "kind": "class",
      "qualified_name": "inxr2.domain.entities.Repository",
      "file_path": "src/inxr2/domain/entities/repository.py",
      "start_line": 15,
      "end_line": 45
    }
  ],
  "total": 1
}

// GET /api/symbols/123/references
{
  "items": [
    {
      "id": 456,
      "source_file": "src/inxr2/application/use_cases/indexing.py",
      "source_line": 23,
      "source_column": 12,
      "reference_kind": "import"
    }
  ],
  "total": 15
}
```

---

#### 1.6.2 Code Viewer Component

**Tasks:**
- [ ] Install syntax highlighting library:
  - [ ] Add Prism.js or highlight.js to frontend
  - [ ] Configure for Python, TypeScript, and common languages
- [ ] Create `CodeViewer` component:
  - [ ] Display file content with syntax highlighting
  - [ ] Show line numbers (clickable)
  - [ ] Support line highlighting (for navigation)
  - [ ] Scroll to specific line on load
- [ ] Add symbol interaction:
  - [ ] Highlight symbols on hover (using symbol locations from API)
  - [ ] Show tooltip with symbol info (kind, qualified name)
  - [ ] Click symbol → trigger navigation (Go to Definition)
- [ ] Add line selection:
  - [ ] Click line number → update URL hash (#L42)
  - [ ] Shift+click → select range (#L10-L20)
  - [ ] Highlight selected lines
  - [ ] Parse URL hash on load → scroll to line
- [ ] Responsive design:
  - [ ] Horizontal scroll for long lines
  - [ ] Configurable font size
  - [ ] Dark/light theme support (optional)

**Component Structure:**
```
CodeViewer/
├── CodeViewer.tsx        # Main component
├── LineNumbers.tsx       # Line number gutter
├── SymbolOverlay.tsx     # Clickable symbol regions
├── useCodeHighlight.ts   # Prism.js hook
└── CodeViewer.css        # Styles
```

---

#### 1.6.3 Symbol Search & Browser

**Tasks:**
- [ ] Create `SymbolSearch` component:
  - [ ] Search input with debounced API calls
  - [ ] Autocomplete dropdown showing matches
  - [ ] Show symbol kind icons (class, function, method, etc.)
  - [ ] Keyboard navigation (arrow keys, Enter to select)
- [ ] Create `SymbolList` component:
  - [ ] Display search results as list
  - [ ] Group by file or show flat list
  - [ ] Show file path and line number
  - [ ] Click to navigate to symbol
- [ ] Add filters:
  - [ ] Filter by symbol kind (dropdown/chips)
  - [ ] Filter by repository (if multiple)
  - [ ] Filter by file path pattern (optional)
- [ ] Create `SymbolDetail` panel:
  - [ ] Show symbol metadata (name, kind, signature)
  - [ ] Show docstring if available
  - [ ] List incoming references ("Who calls this?")
  - [ ] List outgoing references ("What does this call?")

**UI Layout:**
```
┌─────────────────────────────────────────────────────┐
│  🔍 Search symbols...                    [Filters ▼]│
├─────────────────────────────────────────────────────┤
│  class Repository          domain/entities/repo.py:15│
│  class RepositoryModel     persistence/models/repo.py:8│
│  func  get_repository      use_cases/indexing.py:42  │
└─────────────────────────────────────────────────────┘
```

---

#### 1.6.4 File Tree Navigation

**Tasks:**
- [ ] Create `FileTree` component:
  - [ ] Fetch tree structure from API
  - [ ] Render as expandable/collapsible tree
  - [ ] Show folder and file icons
  - [ ] Highlight current file
- [ ] Add tree interactions:
  - [ ] Click folder → expand/collapse
  - [ ] Click file → load in CodeViewer
  - [ ] Right-click context menu (optional)
- [ ] Add tree state management:
  - [ ] Remember expanded folders in session
  - [ ] Auto-expand path to current file
- [ ] Create `RepositorySelector` (if multiple repos):
  - [ ] Dropdown to switch repositories
  - [ ] Show repository name and stats

**Component Structure:**
```
FileTree/
├── FileTree.tsx          # Main tree component
├── TreeNode.tsx          # Single tree node (folder/file)
├── useFileTree.ts        # Data fetching hook
└── FileTree.css          # Styles
```

---

#### 1.6.5 Cross-Reference Features

**Tasks:**
- [ ] Implement "Go to Definition":
  - [ ] Click symbol in CodeViewer → navigate to definition
  - [ ] Handle symbols in same file (scroll)
  - [ ] Handle symbols in different file (navigate + scroll)
  - [ ] Handle unresolved symbols (show message)
- [ ] Implement "Find References":
  - [ ] Right-click symbol → "Find References" option
  - [ ] Or button/keyboard shortcut (Shift+F12 style)
  - [ ] Show references in side panel or modal
  - [ ] Click reference → navigate to location
- [ ] Create `ReferencesPanel` component:
  - [ ] List all references to selected symbol
  - [ ] Group by file
  - [ ] Show code snippet context (line preview)
  - [ ] Click to navigate
- [ ] Add breadcrumb navigation:
  - [ ] Show: Repository > path/to/file.py > ClassName > method_name
  - [ ] Each segment clickable
  - [ ] Update as user navigates

**Navigation Flow:**
```
Symbol Click → Check if definition exists
  ├─ Same file → Scroll to line
  ├─ Different file → Navigate to file, scroll to line
  └─ Not found → Show "Definition not found" tooltip
```

---

#### 1.6.6 Main Layout & Routing

**Tasks:**
- [ ] Create main application layout:
  - [ ] Left sidebar: FileTree (collapsible)
  - [ ] Main area: CodeViewer
  - [ ] Right sidebar: SymbolDetail/References (collapsible)
  - [ ] Top bar: Search, repository selector, breadcrumbs
- [ ] Set up React Router routes:
  - [ ] `/` - Home/repository list
  - [ ] `/repo/:repoId` - Repository view with file tree
  - [ ] `/repo/:repoId/file/:fileId` - File view
  - [ ] `/repo/:repoId/file/:fileId#L42` - File at specific line
  - [ ] `/repo/:repoId/symbol/:symbolId` - Symbol detail view
  - [ ] `/search?q=...` - Search results page
- [ ] Add URL state management:
  - [ ] Sync selected file/symbol with URL
  - [ ] Support browser back/forward
  - [ ] Shareable URLs

**Layout Structure:**
```
┌──────────────────────────────────────────────────────────┐
│  INXR2  │ 🔍 Search...              │ repo: inxr2 ▼     │
├─────────┼────────────────────────────┼───────────────────┤
│ 📁 src  │  1│ """Repository entity."""  │ Symbol: Repo   │
│  └📁domain│  2│                          │ Kind: class    │
│   └📄repo│  3│ from dataclasses import  │                │
│  └📁app │  4│                          │ References (15)│
│         │  5│ @dataclass               │ ├ indexing.py:23│
│         │  6│ class Repository:        │ ├ api/routes:45 │
│         │  7│     """A git repo."""    │ └ ...          │
└─────────┴────────────────────────────┴───────────────────┘
```

---

#### 1.6.7 Testing

**Tasks:**
- [ ] Backend API tests:
  - [ ] Test all new endpoints with pytest
  - [ ] Test query parameters and filters
  - [ ] Test pagination
  - [ ] Test error cases (404, invalid params)
- [ ] Frontend component tests:
  - [ ] CodeViewer unit tests
  - [ ] SymbolSearch tests with mock API
  - [ ] FileTree tests
  - [ ] Navigation integration tests
- [ ] End-to-end tests (optional):
  - [ ] Search for symbol → click → view definition
  - [ ] Find references workflow
  - [ ] File tree navigation

---

**Deliverables:**
- Backend API endpoints for symbols, files, and tree
- Code viewer with syntax highlighting and symbol interaction
- Symbol search with autocomplete and filters
- File tree navigation sidebar
- "Go to Definition" and "Find References" features
- Responsive layout with collapsible panels
- URL-based navigation (shareable links)

**Success Criteria:**
- [ ] Can search for "Repository" and see all matching symbols
- [ ] Can click a symbol to jump to its definition
- [ ] Can find all references to a class/function
- [ ] Can navigate file tree and view any indexed file
- [ ] URLs are shareable and link directly to file+line

**Estimated Complexity:** High

**Dependencies:**
- Phase 1.5 complete (indexed data available)
- Prism.js or highlight.js for syntax highlighting

---

### 1.7 Configuration System (Deferred)

**Note:** YAML configuration parsing deferred. CLI uses command-line arguments. Configuration file support will be added after core browsing UI is working.

**Tasks (Future):**
- [ ] Define configuration schema (Pydantic models)
- [ ] Implement YAML parser with validation
- [ ] Support environment variable substitution
- [ ] Add configuration-driven indexing

**Estimated Complexity:** Low-Medium

---

## Phase 2: Additional Language Support

**Note:** Phase 2 now focuses on adding languages beyond Python and TypeScript, since those are implemented in Phase 1.5.

### 2.1 Java Symbol Extraction

**Objectives:**
- Extend symbol extraction to Java
- Handle Java-specific patterns

**Tasks:**
- [ ] Install tree-sitter-java grammar
- [ ] Create `JavaSymbolExtractor` class:
  - [ ] Method definitions
  - [ ] Class/interface/enum definitions
  - [ ] Field declarations
  - [ ] Package/import statements
  - [ ] Annotations
  - [ ] Generics
- [ ] Add Java tests

**Estimated Complexity:** Medium

---

### 2.2 C# Symbol Extraction

**Tasks:**
- [ ] Install tree-sitter-c-sharp grammar
- [ ] Create `CSharpSymbolExtractor` class:
  - [ ] Method/property definitions
  - [ ] Class/struct/interface definitions
  - [ ] Using statements
  - [ ] Namespace handling
  - [ ] Attributes
  - [ ] LINQ expressions
- [ ] Add C# tests

**Estimated Complexity:** Medium

---

### 2.3 Go Symbol Extraction

**Tasks:**
- [ ] Install tree-sitter-go grammar
- [ ] Create `GoSymbolExtractor` class:
  - [ ] Function definitions
  - [ ] Type/struct/interface definitions
  - [ ] Import statements
  - [ ] Package declarations
  - [ ] Method receivers
- [ ] Add Go tests

**Estimated Complexity:** Medium

---

### 2.4 C/C++ Symbol Extraction

**Tasks:**
- [ ] Install tree-sitter-c and tree-sitter-cpp grammars
- [ ] Create `CSymbolExtractor` and `CppSymbolExtractor` classes:
  - [ ] Function declarations/definitions
  - [ ] Struct/class/enum definitions
  - [ ] Include directives
  - [ ] Namespace handling (C++)
  - [ ] Templates (C++)
  - [ ] Preprocessor macros
- [ ] Add C/C++ tests

**Estimated Complexity:** Medium-High

---

## Phase 3: Advanced Indexing Features

### 3.1 Cross-File Reference Resolution

**Objectives:**
- Link references to definitions across files
- Handle imports and module resolution

**Tasks:**
- [ ] Implement cross-file symbol resolution:
  - [ ] Resolve Python imports to symbol definitions
  - [ ] Resolve TypeScript/JavaScript imports
  - [ ] Handle relative and absolute imports
- [ ] Create resolution strategies per language
- [ ] Update reference records with resolved target_symbol_id
- [ ] Handle unresolved references gracefully

**Estimated Complexity:** High

---

### 3.2 Remote Repository Support

**Objectives:**
- Support indexing repositories from remote URLs
- Handle repository cloning and caching
- Support authentication for private repositories

**Tasks:**
- [ ] Implement repository cloning:
  - [ ] Clone repository to local cache directory
  - [ ] Support HTTPS and SSH URLs
  - [ ] Handle authentication (tokens, SSH keys)
- [ ] Create repository cache manager:
  - [ ] Manage local repository cache
  - [ ] Handle concurrent access safely
  - [ ] Clean up old/unused repos
  - [ ] Configurable cache location and size
- [ ] Add remote update support:
  - [ ] Fetch updates from remote
  - [ ] Handle force pushes and history rewrites
  - [ ] Track multiple remotes
- [ ] Tests:
  - [ ] Test cloning public repositories
  - [ ] Test authentication (with test credentials)
  - [ ] Test cache management

**Estimated Complexity:** Medium

---

### 3.3 Parallel Indexing

**Objectives:**
- Speed up indexing with parallel processing
- Optimize for multi-core systems

**Tasks:**
- [ ] Implement parallel file processing:
  - [ ] Process multiple files concurrently
  - [ ] Thread pool or async processing
  - [ ] Configurable parallelism level
- [ ] Add batch database operations:
  - [ ] Bulk inserts for symbols and references
  - [ ] Connection pooling optimization
- [ ] Performance benchmarks:
  - [ ] Compare single vs parallel indexing
  - [ ] Optimize batch sizes

**Estimated Complexity:** Medium

---

## Phase 4: Backend API (FastAPI)

### 4.1 Core API Endpoints

**Objectives:**
- Build REST API for code browsing
- Support symbol navigation
- Serve file content

**Tasks:**
- [ ] Set up FastAPI application:
  - [ ] Create app structure
  - [ ] Configure CORS
  - [ ] Add request logging
  - [ ] Set up error handlers
- [ ] Implement symbol endpoints:
  - [ ] `GET /api/symbols/search?q={query}` - Search symbols
  - [ ] `GET /api/symbols/{id}` - Get symbol details
  - [ ] `GET /api/symbols/{id}/definition` - Jump to definition
  - [ ] `GET /api/symbols/{id}/references` - Find all references
- [ ] Implement file endpoints:
  - [ ] `GET /api/repos/{repo}/files?commit={hash}&path={path}` - Get file content
  - [ ] `GET /api/repos/{repo}/tree?commit={hash}&path={path}` - List directory
  - [ ] `GET /api/repos/{repo}/blob/{commit}/{path}` - Get file with symbols
- [ ] Implement repository endpoints:
  - [ ] `GET /api/repos` - List all repositories
  - [ ] `GET /api/repos/{repo}` - Get repository details
  - [ ] `GET /api/repos/{repo}/branches` - List branches
- [ ] Add response models:
  - [ ] Pydantic models for all responses
  - [ ] Consistent error response format
  - [ ] Pagination support
- [ ] Tests:
  - [ ] API integration tests
  - [ ] Test all endpoints
  - [ ] Verify response formats
  - [ ] Test error cases

**Deliverables:**
- Core API endpoints functional
- OpenAPI documentation auto-generated
- API tests passing
- Consistent response format

**Estimated Complexity:** Medium-High

---

### 4.2 Temporal Navigation API

**Objectives:**
- Support browsing code at any point in history
- Enable commit comparison
- Generate diffs

**Tasks:**
- [ ] Implement history endpoints:
  - [ ] `GET /api/repos/{repo}/commits?branch={branch}` - List commits
  - [ ] `GET /api/repos/{repo}/commits/{hash}` - Get commit details
  - [ ] `GET /api/repos/{repo}/history/{path}` - Get file history
- [ ] Implement diff endpoints:
  - [ ] `GET /api/repos/{repo}/diff/{commit1}...{commit2}` - Compare commits
  - [ ] `GET /api/repos/{repo}/diff/{commit1}...{commit2}/{path}` - Compare file
  - [ ] Support unified and side-by-side formats
- [ ] Add temporal query support:
  - [ ] Query symbols at specific commit
  - [ ] Filter by date/time
  - [ ] Navigate between versions
- [ ] Generate diffs:
  - [ ] Compute file diffs
  - [ ] Add syntax highlighting to diffs
  - [ ] Show added/deleted/modified lines
  - [ ] Include context lines
- [ ] Tests:
  - [ ] Test history queries
  - [ ] Verify diff generation
  - [ ] Test temporal symbol lookup
  - [ ] Edge cases (first commit, merges)

**Deliverables:**
- Temporal navigation API complete
- Diff generation working
- History queries functional
- Tests passing

**Estimated Complexity:** Medium-High

---

### 4.3 Search APIs

**Objectives:**
- Implement full-text search
- Support symbol autocomplete
- Enable advanced filtering

**Tasks:**
- [ ] Implement search endpoints:
  - [ ] `GET /api/search/symbols?q={query}` - Symbol search
  - [ ] `GET /api/search/text?q={query}` - Full-text search
  - [ ] `GET /api/search/autocomplete?q={query}` - Autocomplete symbols
- [ ] Add filtering support:
  - [ ] Filter by repository
  - [ ] Filter by language
  - [ ] Filter by file type
  - [ ] Filter by symbol kind (function, class, etc.)
- [ ] Implement result ranking:
  - [ ] Exact matches first
  - [ ] Prefix matches
  - [ ] Fuzzy matches
  - [ ] Rank by usage frequency
- [ ] Add pagination:
  - [ ] Limit results per page
  - [ ] Support offset/cursor pagination
  - [ ] Include total count
- [ ] Optimize performance:
  - [ ] Use PostgreSQL full-text search
  - [ ] Add query result caching
  - [ ] Index optimization
- [ ] Tests:
  - [ ] Test search accuracy
  - [ ] Verify ranking
  - [ ] Test filters
  - [ ] Performance benchmarks

**Deliverables:**
- Search endpoints functional
- Filtering and ranking working
- Performance meets targets (<1s)
- Tests passing

**Estimated Complexity:** Medium

---

## Phase 5: Frontend (React)

### 5.1 Core UI Components

**Objectives:**
- Build code browsing interface
- Implement syntax highlighting
- Enable symbol navigation

**Tasks:**
- [ ] Set up React application:
  - [ ] Configure routing (React Router)
  - [ ] Set up state management (Context API or Redux)
  - [ ] Configure API client (axios/fetch)
  - [ ] Add TypeScript types for API responses
- [ ] Create repository browser:
  - [ ] Repository list view
  - [ ] File tree component
  - [ ] Branch/commit selector
  - [ ] Breadcrumb navigation
- [ ] Build code viewer:
  - [ ] Syntax highlighting (choose: Prism.js vs highlight.js)
  - [ ] Line numbers with click handlers
  - [ ] Symbol highlighting on hover
  - [ ] Click-to-jump on symbols
  - [ ] Code formatting and wrapping options
- [ ] Implement navigation:
  - [ ] Breadcrumbs for current location
  - [ ] Back/forward browser navigation
  - [ ] Keyboard shortcuts (j/k for line navigation)
- [ ] Add permalink support:
  - [ ] Update URL on line click
  - [ ] Parse URL hash for line numbers (#L42)
  - [ ] Support line ranges (#L10-L20)
  - [ ] Copy permalink button
- [ ] Create loading states:
  - [ ] Skeleton screens
  - [ ] Loading spinners
  - [ ] Progress indicators
- [ ] Add error handling:
  - [ ] Error boundaries
  - [ ] User-friendly error messages
  - [ ] Retry mechanisms
- [ ] Tests:
  - [ ] Component unit tests
  - [ ] Integration tests
  - [ ] Accessibility tests
  - [ ] Visual regression tests

**Deliverables:**
- Core UI components built
- Code viewer functional with syntax highlighting
- Symbol navigation working
- Permalink support implemented

**Estimated Complexity:** High

---

### 5.2 Search Interface

**Objectives:**
- Build intuitive search UI
- Support autocomplete
- Display results with context

**Tasks:**
- [ ] Create search components:
  - [ ] Search input with autocomplete
  - [ ] Search results list
  - [ ] Result preview/snippet
  - [ ] Filter controls
- [ ] Implement symbol search:
  - [ ] Autocomplete as user types
  - [ ] Keyboard navigation (arrow keys, enter)
  - [ ] Click to navigate to definition
  - [ ] Show symbol kind icons
- [ ] Implement text search:
  - [ ] Full-text search input
  - [ ] Results with context snippets
  - [ ] Highlight matching text
  - [ ] Show file path and line number
- [ ] Add filter UI:
  - [ ] Repository selector
  - [ ] Language filter
  - [ ] File type filter
  - [ ] Symbol kind filter
- [ ] Implement pagination:
  - [ ] Load more button
  - [ ] Infinite scroll (optional)
  - [ ] Page navigation
- [ ] Add search state:
  - [ ] Preserve search in URL
  - [ ] Search history
  - [ ] Recent searches
- [ ] Tests:
  - [ ] Test search interactions
  - [ ] Verify autocomplete
  - [ ] Test filters
  - [ ] Accessibility tests

**Deliverables:**
- Search interface complete
- Autocomplete working
- Filters functional
- Tests passing

**Estimated Complexity:** Medium

---

### 5.3 Temporal Navigation UI

**Objectives:**
- Enable browsing code at different points in time
- Visualize history
- Support diff viewing

**Tasks:**
- [ ] Create history components:
  - [ ] Branch selector dropdown
  - [ ] Commit selector (dropdown or timeline)
  - [ ] Commit list view
  - [ ] Commit details panel
- [ ] Build timeline UI:
  - [ ] Timeline slider for date selection
  - [ ] Visual commit markers
  - [ ] Navigate by clicking timeline
  - [ ] Show current position
- [ ] Implement diff viewer:
  - [ ] Side-by-side diff view
  - [ ] Unified diff view (optional)
  - [ ] Syntax highlighting in diffs
  - [ ] Navigate between changes (prev/next)
  - [ ] Expand/collapse context
- [ ] Add file history view:
  - [ ] List all commits that modified file
  - [ ] Show commit message and author
  - [ ] Click to view file at that commit
  - [ ] Quick diff from previous version
- [ ] Create comparison UI:
  - [ ] Select two commits to compare
  - [ ] Show all changed files
  - [ ] View diffs for each file
- [ ] Update URL for temporal state:
  - [ ] Include commit hash in URL
  - [ ] Preserve branch selection
  - [ ] Deep link to specific commit
- [ ] Tests:
  - [ ] Test temporal navigation
  - [ ] Verify diff rendering
  - [ ] Test URL state
  - [ ] Component tests

**Deliverables:**
- Temporal navigation UI complete
- Diff viewer functional
- Timeline/history working
- Tests passing

**Estimated Complexity:** High

---

### 5.4 Shareable Permalinks

**Objectives:**
- Every code location has a permanent URL
- Support line and range selection
- Enable easy sharing

**Tasks:**
- [ ] Implement URL structure:
  - [ ] `/repo/{name}/blob/{commit}/{path}` - File view
  - [ ] `/repo/{name}/blob/{commit}/{path}#L{line}` - Specific line
  - [ ] `/repo/{name}/blob/{commit}/{path}#L{start}-L{end}` - Line range
  - [ ] `/repo/{name}/symbol/{symbol-id}` - Symbol view
  - [ ] `/repo/{name}/compare/{commit1}...{commit2}/{path}` - Diff view
- [ ] Add line number interaction:
  - [ ] Click line number to update URL
  - [ ] Shift+click for range selection
  - [ ] Update hash without page reload
  - [ ] Highlight selected lines
- [ ] Create copy permalink feature:
  - [ ] Copy button in UI
  - [ ] Copy current URL to clipboard
  - [ ] Show confirmation toast
  - [ ] Keyboard shortcut (Ctrl+Shift+C)
- [ ] Handle URL parsing:
  - [ ] Parse line numbers from hash
  - [ ] Scroll to line on page load
  - [ ] Highlight line range
  - [ ] Handle invalid line numbers
- [ ] Add sharing features:
  - [ ] Share button with copy link
  - [ ] QR code generation (optional)
  - [ ] Social media meta tags
- [ ] Tests:
  - [ ] Test URL generation
  - [ ] Test URL parsing
  - [ ] Test line selection
  - [ ] Test copy functionality

**Deliverables:**
- Permalink system complete
- Line selection working
- Copy functionality implemented
- URL parsing robust

**Estimated Complexity:** Medium

---

## Phase 6: Integration & Polish

### 6.1 End-to-End Integration

**Objectives:**
- Connect all components
- Ensure seamless user experience
- Optimize performance

**Tasks:**
- [ ] Integrate frontend with backend:
  - [ ] Configure API base URL
  - [ ] Add authentication headers (if needed)
  - [ ] Handle CORS properly
- [ ] Implement cross-repository navigation:
  - [ ] Jump between repositories
  - [ ] Follow cross-repo symbol references
  - [ ] Handle missing references gracefully
- [ ] Add comprehensive error handling:
  - [ ] Network errors
  - [ ] 404s for missing files/symbols
  - [ ] 500s for server errors
  - [ ] User-friendly error messages
- [ ] Implement loading states:
  - [ ] Skeleton screens for initial load
  - [ ] Progress indicators for long operations
  - [ ] Optimistic updates where appropriate
- [ ] Add caching:
  - [ ] API response caching
  - [ ] Browser caching for static assets
  - [ ] Cache invalidation strategies
- [ ] Optimize API calls:
  - [ ] Batch requests where possible
  - [ ] Debounce search queries
  - [ ] Prefetch likely next pages
- [ ] Tests:
  - [ ] End-to-end tests with Playwright/Cypress
  - [ ] Test critical user flows
  - [ ] Test error scenarios
  - [ ] Cross-browser testing

**Deliverables:**
- Fully integrated application
- All user flows working
- Error handling comprehensive
- E2E tests passing

**Estimated Complexity:** Medium-High

---

### 6.2 Performance Optimization

**Objectives:**
- Meet performance targets
- Optimize database queries
- Improve frontend responsiveness

**Tasks:**
- [ ] Database optimization:
  - [ ] Analyze slow queries with EXPLAIN
  - [ ] Add missing indexes
  - [ ] Optimize JOIN operations
  - [ ] Use query result caching
  - [ ] Configure connection pooling
- [ ] Backend optimization:
  - [ ] Profile API endpoints
  - [ ] Optimize serialization
  - [ ] Add response compression (gzip)
  - [ ] Implement HTTP caching headers
  - [ ] Use async operations where appropriate
- [ ] Frontend optimization:
  - [ ] Code splitting by route
  - [ ] Lazy load components
  - [ ] Optimize bundle size
  - [ ] Use React.memo for expensive components
  - [ ] Implement virtual scrolling for long lists
- [ ] Asset optimization:
  - [ ] Minify JavaScript/CSS
  - [ ] Optimize images
  - [ ] Use CDN for static assets (optional)
- [ ] Performance monitoring:
  - [ ] Add performance metrics
  - [ ] Track API response times
  - [ ] Monitor frontend render times
  - [ ] Set up alerts for regressions
- [ ] Benchmarks:
  - [ ] Symbol search < 1 second
  - [ ] File rendering < 5 seconds
  - [ ] Incremental indexing significantly faster than full
- [ ] Tests:
  - [ ] Performance regression tests
  - [ ] Load testing with realistic data
  - [ ] Verify targets met

**Deliverables:**
- Performance targets met
- Database queries optimized
- Frontend responsive
- Benchmarks documented

**Estimated Complexity:** Medium

---

### 6.3 Testing

**Objectives:**
- Achieve >80% code coverage
- Ensure quality and reliability
- Prevent regressions

**Tasks:**
- [ ] Backend testing:
  - [ ] Unit tests for all modules
  - [ ] Integration tests for API endpoints
  - [ ] Database tests with test database
  - [ ] Git integration tests with mock repos
  - [ ] Parser tests with comprehensive fixtures
- [ ] Frontend testing:
  - [ ] Component unit tests
  - [ ] Integration tests for user flows
  - [ ] API mock tests
  - [ ] Accessibility tests (axe-core)
- [ ] End-to-end testing:
  - [ ] Critical user paths (Playwright/Cypress)
  - [ ] Cross-browser compatibility
  - [ ] Mobile responsiveness
- [ ] Add test coverage reporting:
  - [ ] Generate coverage reports
  - [ ] Set coverage thresholds (80%+)
  - [ ] Fail CI if coverage drops
- [ ] Create test fixtures:
  - [ ] Sample repositories for each language
  - [ ] Edge case code samples
  - [ ] Real-world code examples
- [ ] Performance tests:
  - [ ] Benchmark critical operations
  - [ ] Load tests for API
  - [ ] Indexing performance tests
- [ ] Documentation tests:
  - [ ] Verify code examples work
  - [ ] Test configuration samples

**Deliverables:**
- >80% test coverage (backend and frontend)
- Comprehensive test suite
- CI/CD tests passing
- Test fixtures complete

**Estimated Complexity:** High

---

## Phase 7: Docker & Deployment

**Note:** Development Docker setup (Dockerfile.dev, docker-compose.dev.yml, devcontainer) was completed in Phase 1.1. This phase focuses on optimizing and finalizing production containers for deployment.

### 7.1 Docker Container (Production Optimization)

**Objectives:**
- Optimize production container for deployment
- Finalize single-container packaging
- Ensure production-ready configuration

**Tasks:**
- [ ] Optimize production Dockerfile (basic version created in Phase 1.1):
  - [ ] Refine multi-stage build for minimal image size
  - [ ] Optimize layer caching
  - [ ] Remove unnecessary build dependencies
  - [ ] Verify all tree-sitter grammars included
  - [ ] Test entrypoint script thoroughly
  - [ ] Add security hardening
- [ ] Include PostgreSQL:
  - [ ] Install PostgreSQL in container
  - [ ] Configure for single-container operation
  - [ ] Set up initialization scripts
  - [ ] Configure data persistence
- [ ] Add tree-sitter grammars:
  - [ ] Download and compile all language grammars
  - [ ] Include in container image
  - [ ] Verify all languages work
- [ ] Configure application:
  - [ ] Environment variable support
  - [ ] Default configuration
  - [ ] Volume mount points for config
- [ ] Create entrypoint script:
  - [ ] Start PostgreSQL
  - [ ] Run database migrations
  - [ ] Start FastAPI server
  - [ ] Serve React frontend
  - [ ] Handle graceful shutdown
- [ ] Optimize image size:
  - [ ] Multi-stage builds
  - [ ] Remove build dependencies
  - [ ] Use .dockerignore
- [ ] Tests:
  - [ ] Build container successfully
  - [ ] Verify all services start
  - [ ] Test from fresh container

**Deliverables:**
- Working Dockerfile
- Single-container deployment
- All dependencies included
- Container tested

**Estimated Complexity:** Medium-High

---

### 7.2 Docker Compose (Production Finalization)

**Objectives:**
- Finalize production docker-compose configuration
- Add production-specific optimizations
- Document deployment scenarios

**Note:** docker-compose.dev.yml was created in Phase 1.1 for development. This phase focuses on production docker-compose.yml.

**Tasks:**
- [ ] Optimize production docker-compose.yml (basic version from Phase 1.1):
  - [ ] Add resource limits (memory, CPU)
  - [ ] Configure restart policies
  - [ ] Add logging configuration
  - [ ] Optimize volume mounts for production
- [ ] Add production volume configuration:
  - [ ] Config file mount with read-only option
  - [ ] Database data with backup considerations
  - [ ] Repository cache optimization
  - [ ] Log rotation configuration
- [ ] Enhance health checks:
  - [ ] Add dependency ordering with health checks
  - [ ] Configure startup timeout limits
  - [ ] Add readiness probes
- [ ] Create deployment variants:
  - [ ] docker-compose.prod.yml - single-server deployment
  - [ ] docker-compose.cloud.yml - cloud deployment template
- [ ] Production documentation:
  - [ ] Deployment guide for different environments
  - [ ] Backup and restore procedures
  - [ ] Scaling considerations
  - [ ] Security best practices

**Deliverables:**
- Optimized production docker-compose configurations
- Deployment variant templates
- Production deployment documentation
- Backup/restore procedures documented

**Estimated Complexity:** Low-Medium

---

### 7.3 Deployment Documentation

**Objectives:**
- Document deployment process
- Provide configuration examples
- Create troubleshooting guide

**Tasks:**
- [ ] Write deployment guide:
  - [ ] Prerequisites
  - [ ] Installation steps
  - [ ] Configuration instructions
  - [ ] Initial indexing
  - [ ] Accessing the UI
- [ ] Document local development:
  - [ ] Development environment setup
  - [ ] Running without Docker
  - [ ] Database setup
  - [ ] Frontend dev server
- [ ] Create configuration reference:
  - [ ] All config.yaml options
  - [ ] Environment variables
  - [ ] Example configurations
  - [ ] Best practices
- [ ] Add cloud deployment guides:
  - [ ] AWS deployment
  - [ ] Google Cloud deployment
  - [ ] Azure deployment
  - [ ] Generic cloud VM setup
- [ ] Create troubleshooting guide:
  - [ ] Common errors
  - [ ] Log locations
  - [ ] Debugging tips
  - [ ] Performance tuning
- [ ] Add operational guides:
  - [ ] Backup and restore
  - [ ] Upgrading
  - [ ] Monitoring
  - [ ] Security considerations

**Deliverables:**
- Comprehensive deployment guide
- Configuration reference
- Troubleshooting documentation
- Cloud deployment examples

**Estimated Complexity:** Medium

---

## Phase 8: Documentation & Examples

### 8.1 User Documentation

**Objectives:**
- Enable users to use INXR2 effectively
- Provide clear examples
- Document all features

**Tasks:**
- [ ] Write user guide:
  - [ ] Getting started tutorial
  - [ ] Navigating repositories
  - [ ] Searching for symbols
  - [ ] Using temporal navigation
  - [ ] Sharing permalinks
  - [ ] Advanced features
- [ ] Create configuration guide:
  - [ ] Setting up repositories
  - [ ] Configuring branches
  - [ ] Indexing options
  - [ ] Performance tuning
- [ ] Document CLI usage:
  - [ ] All commands and options
  - [ ] Examples for common tasks
  - [ ] Scheduling re-indexing
- [ ] Add screenshots/videos:
  - [ ] Annotated screenshots
  - [ ] GIF demos of key features
  - [ ] Video walkthrough (optional)
- [ ] Create FAQ:
  - [ ] Common questions
  - [ ] Troubleshooting tips
  - [ ] Best practices
- [ ] Write changelog:
  - [ ] Version history
  - [ ] Migration guides

**Deliverables:**
- Complete user guide
- CLI reference
- Visual documentation
- FAQ

**Estimated Complexity:** Medium

---

### 8.2 Developer Documentation

**Objectives:**
- Enable contributions
- Document architecture
- Provide extension guides

**Tasks:**
- [ ] Update architecture documentation:
  - [ ] Component diagrams
  - [ ] Data flow diagrams
  - [ ] Database schema diagram
  - [ ] API architecture
- [ ] Create API documentation:
  - [ ] OpenAPI/Swagger spec
  - [ ] Endpoint descriptions
  - [ ] Request/response examples
  - [ ] Authentication (if added)
- [ ] Write extension guides:
  - [ ] Adding new languages
  - [ ] Custom symbol extractors
  - [ ] Plugin system (if implemented)
- [ ] Document code structure:
  - [ ] Module organization
  - [ ] Key classes and functions
  - [ ] Design patterns used
  - [ ] Coding conventions
- [ ] Update CONTRIBUTING.md:
  - [ ] Development workflow
  - [ ] Testing requirements
  - [ ] Code review process
  - [ ] Release process
- [ ] Add code examples:
  - [ ] Parser examples
  - [ ] API usage examples
  - [ ] Custom extractor example

**Deliverables:**
- API documentation (OpenAPI)
- Architecture documentation
- Extension guides
- Updated contributing guide

**Estimated Complexity:** Medium

---

### 8.3 Testing & Validation

**Objectives:**
- Validate with real repositories
- Create demo environment
- Gather feedback

**Tasks:**
- [ ] Create test repository collection:
  - [ ] Sample repositories for each language
  - [ ] Real-world open-source projects
  - [ ] Edge case repositories
- [ ] Build comprehensive fixtures:
  - [ ] Unit test fixtures
  - [ ] Integration test data
  - [ ] Performance test data
- [ ] Set up demo environment:
  - [ ] Publicly accessible instance (optional)
  - [ ] Pre-indexed popular repositories
  - [ ] Demo configuration
- [ ] Perform validation testing:
  - [ ] Index real repositories
  - [ ] Verify accuracy of cross-references
  - [ ] Test all features end-to-end
  - [ ] Performance validation
- [ ] Create performance benchmarks:
  - [ ] Indexing speed
  - [ ] Query performance
  - [ ] UI responsiveness
  - [ ] Compare to targets
- [ ] Gather feedback:
  - [ ] Internal testing
  - [ ] Beta users (if applicable)
  - [ ] Iterate based on feedback
- [ ] Document findings:
  - [ ] Known limitations
  - [ ] Performance characteristics
  - [ ] Best practices learned

**Deliverables:**
- Test repository collection
- Demo environment
- Performance benchmarks
- Validation report

**Estimated Complexity:** Medium

---

## Key Decision Points

Before starting implementation, decide on the following:

### 1. Syntax Highlighting Library
**Options:**
- **Prism.js**: Lightweight, extensible, good language support
- **highlight.js**: Automatic language detection, large bundle
- **Monaco Editor**: Full editor experience, heavy
- **Server-side (Pygments)**: No JS bundle, requires server round-trip

**Recommendation:** Prism.js for balance of features and size

### 2. Git Library for Python
**Options:**
- **GitPython**: Pythonic API, easier to use, slower
- **pygit2**: Libgit2 bindings, faster, more complex
- **subprocess**: Direct git CLI calls, simple, requires git installed

**Recommendation:** GitPython for development, consider pygit2 if performance issues

### 3. Frontend Build Tool
**Options:**
- **Vite**: Modern, fast, great DX, ESM-native
- **Create React App**: Established, batteries-included, slower
- **Next.js**: SSR support, more complex, overkill for SPA

**Recommendation:** Vite for modern development experience

### 4. Database Migrations
**Options:**
- **Alembic**: Standard for SQLAlchemy, battle-tested
- **Custom scripts**: Simple, more control
- **Django migrations**: Not applicable (using FastAPI)

**Recommendation:** Alembic for reliability and community support

### 5. State Management (Frontend)
**Options:**
- **Context API**: Built-in, simple, good for moderate complexity
- **Redux Toolkit**: Powerful, established, more boilerplate
- **Zustand**: Lightweight, modern, minimal boilerplate
- **Jotai/Recoil**: Atomic state, modern patterns

**Recommendation:** Context API initially, migrate to Zustand if complexity grows

---

## Success Metrics

### MVP Success Criteria
- [ ] Successfully index 10 repositories with mixed languages
- [ ] Symbol search responds in < 1 second
- [ ] Navigate between files and definitions seamlessly
- [ ] Browse git history and compare file versions
- [ ] Runs reliably in Docker container on Mac and cloud
- [ ] >80% test coverage (backend and frontend)
- [ ] All 7 core languages supported

### User Experience Goals
- [ ] Faster than grep/ripgrep for finding symbol definitions
- [ ] More accurate than ctags for cross-references
- [ ] Easier than IDE for cross-repository navigation
- [ ] More performant than GitHub web UI for large codebases
- [ ] Intuitive UI requiring minimal documentation

### Performance Targets
- [ ] Simple symbol lookup: < 1 second
- [ ] Complex queries or file rendering: < 5 seconds
- [ ] Incremental indexing: < 30 seconds for typical changes
- [ ] Support 10-100 repositories
- [ ] Handle 10k - 1M lines of code
- [ ] Support ~5 concurrent users

---

## Implementation Sequence Recommendation

### Phase 1: Foundation (Weeks 1-2)
Start here to establish the core infrastructure:
1. Docker development environment (1.1) - **DO THIS FIRST**
2. Project setup (1.2)
3. Database foundation (1.3)
4. Configuration system (1.4)

### Phase 2: Parsing (Weeks 3-4)
Build the parsing capabilities:
1. Tree-sitter setup (2.1)
2. Python extraction (2.2)
3. Start multi-language support (2.3 - can be done incrementally)

### Phase 3: Indexing (Weeks 5-7)
Make it functional:
1. Git integration (3.1)
2. Initial indexing pipeline (3.2)
3. Validate with Python-only support
4. Incremental indexing (3.3)

### Phase 4: API (Weeks 8-9)
Build the backend API:
1. Core endpoints (4.1)
2. Temporal navigation (4.2)
3. Search APIs (4.3)

### Phase 5: Frontend (Weeks 10-13)
Build the UI:
1. Core UI components (5.1)
2. Search interface (5.2)
3. Temporal navigation UI (5.3)
4. Permalinks (5.4)

### Phase 6: Polish (Weeks 14-15)
Make it production-ready:
1. Integration (6.1)
2. Performance optimization (6.2)
3. Testing (6.3)

### Phase 7: Deployment (Week 16)
Package and document:
1. Docker container (7.1)
2. Docker Compose (7.2)
3. Deployment docs (7.3)

### Phase 8: Documentation (Week 17)
Finish it off:
1. User documentation (8.1)
2. Developer documentation (8.2)
3. Testing & validation (8.3)

---

## Notes

- **Clean Architecture**: Follow the dependency rule strictly - dependencies point inward only
- **Incremental Development**: Complete each phase before moving to the next
- **Test-Driven**: Write tests first, then implementation (easier with Clean Architecture)
- **Domain First**: Start by implementing domain entities and use cases, then add adapters
- **Validation Points**: After Phases 3, 5, and 6, validate with real use cases
- **Language Support**: Start with Python only, add other languages after core functionality works
- **Performance**: Monitor performance early and often
- **Documentation**: Update documentation as you build, not at the end

**Document Version**: 1.3
**Created**: 2025-12-29
**Last Updated**: 2026-01-12 (Phase 1.6 Plan - Cross-Reference Code Browser UI)
**Status**: Active Development
