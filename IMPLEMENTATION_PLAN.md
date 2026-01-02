# INXR2 Implementation Plan

This document outlines the step-by-step implementation plan for building INXR2, a cross-reference code browser for git repositories.

## Overview

INXR2 is a modern code browser similar to LXR but designed specifically for git-based workflows. It provides semantic code navigation, temporal browsing, and cross-repository search capabilities.

**Tech Stack**: FastAPI (Python) + React (TypeScript) + PostgreSQL + Tree-sitter + Docker

**Architecture**: Clean Architecture (Hexagonal/Ports & Adapters)

**Current Status**: Phase 1 (Infrastructure) in progress
- ✅ Docker development environment complete
- ✅ Dev containers configured and working
- ✅ Hello world apps deployed (FastAPI + React)
- ✅ Production Docker build and deployment verified
- 🔄 Database schema design in progress

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

**Clean Architecture Note:**
- Domain entities (in `domain/entities/`) are pure Python dataclasses/Pydantic models
- SQLAlchemy ORM models (in `adapters/persistence/models/`) are separate from domain entities
- Repository implementations map between domain entities and ORM models

**Tasks:**
- [ ] Define domain entities (in `domain/entities/`):
  - [ ] `Repository` entity - domain model for git repository
  - [ ] `Commit` entity - domain model for commit
  - [ ] `File` entity - domain model for source file
  - [ ] `Symbol` entity - domain model for code symbol
  - [ ] `Reference` entity - domain model for symbol reference
- [ ] Design PostgreSQL schema:
  - [ ] `repositories` table (id, name, url, config)
  - [ ] `commits` table (hash, repo_id, branch, timestamp, author, message)
  - [ ] `files` table (id, repo_id, commit_hash, path, content_hash, language)
  - [ ] `symbols` table (id, name, kind, file_id, line, column, scope, metadata JSONB)
  - [ ] `references` table (id, source_file_id, source_line, source_column, target_symbol_id, ref_type)
  - [ ] `index_status` table (repo_id, branch, last_indexed_commit, last_update_time)
- [ ] Create indexes:
  - [ ] B-tree on symbol names, file paths
  - [ ] GIN for full-text search on file contents
  - [ ] Composite indexes for common queries
  - [ ] Partial indexes for latest commits
- [ ] Set up Alembic (in `infrastructure/database/migrations/`):
  - [ ] Initialize alembic configuration
  - [ ] Create initial migration
  - [ ] Add migration scripts for schema creation
- [ ] Implement database infrastructure (in `infrastructure/database/`):
  - [ ] Database connection management
  - [ ] Session factory with connection pooling
  - [ ] Base configuration
- [ ] Create SQLAlchemy ORM models (in `adapters/persistence/models/`):
  - [ ] `RepositoryModel`, `CommitModel`, `FileModel`, `SymbolModel`, `ReferenceModel`
  - [ ] Define relationships between models
  - [ ] **Note**: These are separate from domain entities
- [ ] Define repository ports/interfaces (in `application/ports/repositories/`):
  - [ ] `SymbolRepositoryPort` (ABC interface)
  - [ ] `FileRepositoryPort` (ABC interface)
  - [ ] `CommitRepositoryPort` (ABC interface)
  - [ ] Define methods: CRUD operations, temporal queries
- [ ] Implement repository adapters (in `adapters/persistence/repositories/`):
  - [ ] `PostgresSymbolRepository` implements `SymbolRepositoryPort`
  - [ ] `PostgresFileRepository` implements `FileRepositoryPort`
  - [ ] `PostgresCommitRepository` implements `CommitRepositoryPort`
  - [ ] Map between ORM models and domain entities
  - [ ] Implement all interface methods

**Deliverables:**
- Complete database schema with migrations
- Domain entities defined (framework-agnostic)
- Repository ports (interfaces) defined
- SQLAlchemy models in adapters layer
- Repository implementations with entity mapping
- Data access layer fully tested

**Estimated Complexity:** High

---

### 1.4 Configuration System

**Objectives:**
- Parse YAML configuration files
- Validate repository configurations
- Support CLI arguments

**Tasks:**
- [ ] Define configuration schema:
  - [ ] Pydantic models for config validation
  - [ ] Repository configuration (name, url, branches, languages)
  - [ ] Indexing options (incremental, max_commit_history)
  - [ ] Search settings (max_results)
- [ ] Implement YAML parser:
  - [ ] Load and validate config.yaml
  - [ ] Handle errors gracefully with clear messages
  - [ ] Support environment variable substitution
- [ ] Create CLI framework:
  - [ ] Use Click or argparse
  - [ ] Commands: `index`, `reindex`, `serve`, `status`
  - [ ] Global options: `--config`, `--verbose`, `--log-level`
- [ ] Add configuration tests:
  - [ ] Valid configuration parsing
  - [ ] Invalid configuration rejection
  - [ ] Default value handling

**Deliverables:**
- Configuration schema defined
- YAML parser working
- CLI framework in place
- Configuration validation with tests

**Estimated Complexity:** Low-Medium

---

## Phase 2: Tree-sitter Integration & Parsing

### 2.1 Tree-sitter Setup

**Objectives:**
- Integrate tree-sitter with Python
- Support multiple language grammars
- Build language detection

**Tasks:**
- [ ] Install tree-sitter:
  - [ ] Add tree-sitter Python bindings
  - [ ] Download and compile language grammars
  - [ ] Create grammar management system
- [ ] Implement language detection:
  - [ ] File extension mapping
  - [ ] Shebang detection
  - [ ] Fallback to text/unknown
- [ ] Create parser abstraction:
  - [ ] `LanguageParser` base class
  - [ ] Parser factory for language selection
  - [ ] Error handling for parse failures
- [ ] Add supported languages:
  - [ ] Python (priority 1)
  - [ ] TypeScript/JavaScript
  - [ ] Java
  - [ ] C#
  - [ ] Go
  - [ ] C/C++

**Deliverables:**
- Tree-sitter integrated
- All language grammars available
- Language detection working
- Parser abstraction layer

**Estimated Complexity:** Medium

---

### 2.2 Symbol Extraction (Start with Python)

**Objectives:**
- Extract symbols from Python code
- Identify definitions and references
- Build foundation for other languages

**Tasks:**
- [ ] Write tree-sitter queries for Python:
  - [ ] Function definitions: `(function_definition name: (identifier) @name)`
  - [ ] Class definitions: `(class_definition name: (identifier) @name)`
  - [ ] Method definitions (inside classes)
  - [ ] Variable assignments
  - [ ] Import statements (from/import)
- [ ] Implement Python symbol extractor:
  - [ ] Parse AST with tree-sitter
  - [ ] Extract symbol metadata (name, kind, location, scope)
  - [ ] Handle nested scopes (classes, functions)
  - [ ] Store scope information for resolution
- [ ] Implement reference finder:
  - [ ] Identify identifier usages
  - [ ] Distinguish definitions from references
  - [ ] Track import relationships
  - [ ] Handle qualified names (module.function)
- [ ] Create symbol resolver:
  - [ ] Link references to definitions
  - [ ] Handle same-file references
  - [ ] Support cross-file references (via imports)
- [ ] Add comprehensive tests:
  - [ ] Test fixtures with various Python patterns
  - [ ] Edge cases: decorators, lambdas, comprehensions
  - [ ] Verify correct line/column positions

**Deliverables:**
- Python symbol extraction working
- Accurate definition/reference identification
- Symbol resolver functional
- Comprehensive test coverage

**Estimated Complexity:** High

---

### 2.3 Multi-Language Support

**Objectives:**
- Extend symbol extraction to all target languages
- Create language-specific strategies
- Ensure consistent symbol model

**Tasks:**
- [ ] TypeScript/JavaScript extraction:
  - [ ] Function/arrow function definitions
  - [ ] Class/interface definitions
  - [ ] Variable declarations (const/let/var)
  - [ ] Import/export statements
  - [ ] JSX/TSX support
- [ ] Java extraction:
  - [ ] Method definitions
  - [ ] Class/interface/enum definitions
  - [ ] Field declarations
  - [ ] Package/import statements
- [ ] C# extraction:
  - [ ] Method/property definitions
  - [ ] Class/struct/interface definitions
  - [ ] Using statements
  - [ ] Namespace handling
- [ ] Go extraction:
  - [ ] Function definitions
  - [ ] Type/struct/interface definitions
  - [ ] Import statements
  - [ ] Package declarations
- [ ] C/C++ extraction:
  - [ ] Function declarations/definitions
  - [ ] Struct/class/enum definitions
  - [ ] Include directives
  - [ ] Namespace handling (C++)
- [ ] Create language-specific extractors:
  - [ ] Inherit from base `SymbolExtractor` class
  - [ ] Override language-specific logic
  - [ ] Share common functionality
- [ ] Build comprehensive test suite:
  - [ ] Test fixtures for each language
  - [ ] Real-world code samples
  - [ ] Cross-language integration tests

**Deliverables:**
- All 7 languages supported
- Language-specific extractors implemented
- Consistent symbol model across languages
- Full test coverage per language

**Estimated Complexity:** High

---

## Phase 3: Indexing Engine

### 3.1 Git Integration

**Objectives:**
- Implement git operations
- Handle repository cloning and updates
- Track commit history

**Tasks:**
- [ ] Choose git library (GitPython vs pygit2 vs subprocess):
  - [ ] Evaluate performance and ease of use
  - [ ] Make decision and document rationale
- [ ] Implement `GitClient` class:
  - [ ] Clone repository (with auth support)
  - [ ] Fetch updates from remote
  - [ ] Checkout specific commits/branches
  - [ ] List commits in range
  - [ ] Get file content at specific commit
  - [ ] Compute diffs between commits
- [ ] Create repository manager:
  - [ ] Manage local repository cache
  - [ ] Handle concurrent access safely
  - [ ] Clean up old/unused repos
- [ ] Implement commit traversal:
  - [ ] Walk commit history from HEAD
  - [ ] Filter by branch
  - [ ] Limit to max_commit_history
- [ ] Add file change detection:
  - [ ] Get added/modified/deleted files between commits
  - [ ] Compute file diffs
  - [ ] Handle renames and moves
- [ ] Tests:
  - [ ] Mock git repositories for testing
  - [ ] Test all git operations
  - [ ] Verify error handling

**Deliverables:**
- Git operations abstraction
- Repository management working
- Commit traversal functional
- Tests with mock repositories

**Estimated Complexity:** Medium-High

---

### 3.2 Initial Indexing Pipeline

**Objectives:**
- Build end-to-end indexing pipeline
- Index entire repositories
- Store all extracted data

**Tasks:**
- [ ] Create indexing orchestrator:
  - [ ] `IndexingEngine` class
  - [ ] Coordinate git, parsing, and database operations
  - [ ] Handle errors and rollbacks
- [ ] Implement file scanner:
  - [ ] Walk repository file tree
  - [ ] Filter by language support
  - [ ] Skip binary/large files
  - [ ] Respect .gitignore patterns
- [ ] Build indexing pipeline:
  - [ ] For each file:
    - [ ] Detect language
    - [ ] Parse with tree-sitter
    - [ ] Extract symbols
    - [ ] Extract references
    - [ ] Store in database
  - [ ] Batch database inserts for performance
  - [ ] Track progress
- [ ] Implement cross-reference building:
  - [ ] After all files indexed, resolve references
  - [ ] Link references to symbol definitions
  - [ ] Handle cross-file references
  - [ ] Store in `references` table
- [ ] Add progress tracking:
  - [ ] Log files processed
  - [ ] Show progress bar
  - [ ] Estimate time remaining
  - [ ] Report errors without stopping
- [ ] Create CLI commands:
  - [ ] `inxr2 index --config config.yaml` (index all repos)
  - [ ] `inxr2 index --repo <name>` (index specific repo)
  - [ ] `inxr2 status` (show indexing status)
- [ ] Tests:
  - [ ] End-to-end indexing with test repositories
  - [ ] Verify all symbols extracted
  - [ ] Verify cross-references correct
  - [ ] Test error scenarios

**Deliverables:**
- Complete indexing pipeline
- CLI commands functional
- Progress tracking implemented
- End-to-end tests passing

**Estimated Complexity:** High

---

### 3.3 Incremental Indexing

**Objectives:**
- Update indexes efficiently
- Only re-index changed files
- Maintain data consistency

**Tasks:**
- [ ] Implement commit tracking:
  - [ ] Store last indexed commit per repository/branch
  - [ ] Query `index_status` table
- [ ] Build change detection:
  - [ ] Fetch latest commits
  - [ ] Compare with last indexed commit
  - [ ] Get list of changed files (git diff)
- [ ] Create incremental update logic:
  - [ ] For modified files:
    - [ ] Delete old symbols/references
    - [ ] Re-parse and re-index
  - [ ] For deleted files:
    - [ ] Mark as deleted (preserve for history)
    - [ ] Remove from latest view
  - [ ] For added files:
    - [ ] Index normally
- [ ] Update cross-references:
  - [ ] Find references affected by changed symbols
  - [ ] Re-resolve references
  - [ ] Update reference table
- [ ] Optimize performance:
  - [ ] Parallel processing of files
  - [ ] Batch database operations
  - [ ] Minimize full table scans
- [ ] Add rollback capability:
  - [ ] Use database transactions
  - [ ] Rollback on errors
  - [ ] Preserve previous state
- [ ] Create `reindex` command:
  - [ ] `inxr2 reindex --config config.yaml` (update all repos)
  - [ ] `inxr2 reindex --repo <name>` (update specific repo)
  - [ ] `inxr2 reindex --force` (full re-index)
- [ ] Tests:
  - [ ] Simulate repository changes
  - [ ] Verify incremental updates correct
  - [ ] Test rollback on failure
  - [ ] Performance benchmarks (vs full re-index)

**Deliverables:**
- Incremental indexing working
- Significantly faster than full re-index
- Rollback on errors
- Performance benchmarks

**Estimated Complexity:** High

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

**Document Version**: 1.1
**Created**: 2025-12-29
**Last Updated**: 2025-12-29 (Added Clean Architecture)
**Status**: Planning
