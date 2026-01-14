# INXR2 - Cross-Reference Code Browser

A modern cross-reference code browser designed for teams working with git repositories. INXR2 enables developers to browse, search, and understand code across multiple repositories with powerful temporal navigation capabilities.

## Overview

INXR2 is similar to LXR (Linux Cross Reference) but built specifically for git-based development workflows. It provides deep code intelligence with the ability to browse code at any point in history, making it easy to understand how your codebase evolved over time.

### Key Differentiators

- **Temporal Navigation**: Browse code at different points in time based on git history
- **Cross-Repository Browsing**: Navigate seamlessly across multiple team repositories
- **Shareable Permalinks**: Every line and symbol has a permanent, shareable URL
- **Self-Contained**: Runs in a single Docker container for easy local and cloud deployment
- **Multi-Language**: Support for Python, TypeScript/JavaScript, Java, C#, Go, C, and C++

## Features

### Core Capabilities

- **Jump to Definition & Find References**: Navigate code with semantic understanding
- **Symbol Search**: Fast search across all indexed repositories
- **Full-Text Search**: Find anything across all files, including non-indexed languages
- **Git History Integration**: Browse code at any commit on configured branches
- **Side-by-Side Diff View**: Compare file versions across time
- **Incremental Indexing**: Fast updates without full re-indexing
- **Shareable Links**: Permanent URLs for lines, ranges, symbols, and diffs

### Supported Languages

**With Semantic Indexing:**
- Python
- TypeScript/JavaScript
- Java
- C#
- Go
- C
- C++

**All Other Languages:**
- Displayed with syntax highlighting
- Included in text search
- Available in git history and diffs
- No semantic cross-references (yet)

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React (TypeScript)
- **Database**: PostgreSQL
- **Code Parser**: Tree-sitter
- **Deployment**: Docker

For detailed architecture and design decisions, see [DESIGN.md](DESIGN.md).

## Quick Start

### Development Setup (Recommended)

The fastest way to get started is using the Docker development environment:

```bash
# Clone the repository
git clone <repository-url>
cd inxr2

# The project includes a .env.dev file with development defaults
# No additional configuration needed for development!
# For production, see "Production Deployment" section below
```

**Option 1: Using VS Code/Cursor (Recommended)**
1. Open the project in VS Code or Cursor
2. Install the "Dev Containers" extension
3. Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
4. Select "Dev Containers: Reopen in Container"
5. Wait for the container to build (~5 minutes first time)

**Option 2: Using Docker Compose Directly**
```bash
# Start the development environment
docker-compose -f docker-compose.dev.yml up -d

# Open a shell in the container
docker exec -it inxr2-dev bash

# Or use the helper scripts
./scripts/dev-start.sh   # Start containers
./scripts/dev-shell.sh   # Open shell
./scripts/dev-stop.sh    # Stop containers
```

The dev container automatically installs all dependencies and includes:
- Python 3.11 with virtual environment
- Node.js 18 for the frontend
- PostgreSQL database
- All development tools (pytest, black, mypy, etc.)

**Services Available:**
- Backend API: `http://localhost:8000` (once started)
- Frontend: `http://localhost:5173` (once started)
- PostgreSQL: `localhost:5432`

For more details, see [DEVELOPMENT.md](DEVELOPMENT.md).

## ⚠️ CRITICAL: Development Guidelines

**BEFORE making any changes, READ and FOLLOW these mandatory guidelines:**

### 1. Docker-Only Development
- ❌ **NEVER** run `npm install`, `pip install`, or `uv pip install` on your host machine
- ✅ **ALWAYS** run package management and development commands in Docker containers
- All work must be done inside the Docker development container

### 2. Testing Requirements
- ✅ **MANDATORY**: Run `./scripts/run-all-tests.sh` before EVERY commit
- All code changes MUST include tests (no exceptions)
- Use dependency injection, NOT mocking (see CONTRIBUTING.md)
- Minimum 80% test coverage (enforced)

### 3. Code Quality
- All code must pass linting (Black, isort, Ruff, ESLint)
- All code must pass type checking (mypy, tsc)
- Run formatters BEFORE committing
- Zero tolerance for linting errors

### 4. Package Management
- Only use well-supported, actively maintained packages
- No deprecated or vulnerable packages allowed
- Run `npm audit` regularly (zero vulnerabilities required)
- Python: Use `uv` with virtual environment
- Node: Check for deprecation warnings

### 5. Before Every Commit
```bash
# This MUST pass before you commit
./scripts/run-all-tests.sh
```

**👉 See [CONTRIBUTING.md](CONTRIBUTING.md) for complete guidelines - READ IT!**

### Production Deployment

**IMPORTANT: Configure environment variables before deployment!**

```bash
# 1. Create production environment file
cp .env.prod.example .env.prod

# 2. Edit .env.prod and set secure values
# CRITICAL: Change POSTGRES_PASSWORD to a strong password!
# CRITICAL: Generate a random SECRET_KEY!
# Update ALLOWED_HOSTS and CORS_ORIGINS for your domain
nano .env.prod

# 3. Build and start
docker-compose build
docker-compose up -d
```

See [Deployment](#deployment) section below for complete production setup instructions.

## Documentation

- **[DESIGN.md](DESIGN.md)** - Complete design document including architecture, requirements, data model, and deployment strategy
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Coding standards, testing requirements, and contribution guidelines
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Quick reference for common development tasks and workflows

## Development

### Prerequisites

- **Docker Desktop** - Required for dev containers
- **VS Code or Cursor** - Recommended (with Dev Containers extension)
- **Git** - For version control

No need to install Python, Node.js, or PostgreSQL locally - the dev container includes everything!

### Quick Commands

Once inside the dev container:

```bash
# Run Python tests
pytest --cov=src

# Run frontend tests
cd frontend && npm test

# Format code
black .                    # Python
cd frontend && npm run format  # TypeScript

# Lint code
ruff check .               # Python
cd frontend && npm run lint    # TypeScript

# Type check
mypy .                     # Python
cd frontend && npm run type-check  # TypeScript

# Install pre-commit hooks
pre-commit install
```

### Helper Scripts

```bash
./scripts/dev-start.sh      # Start dev environment
./scripts/dev-stop.sh       # Stop dev environment
./scripts/dev-shell.sh      # Open shell in container
./scripts/dev-logs.sh       # View container logs
./scripts/dev-reset-db.sh   # Reset database (WARNING: deletes data)
```

For detailed development workflows and troubleshooting, see [DEVELOPMENT.md](DEVELOPMENT.md).

### Database Reset and Re-indexing

If you need to rebuild the database from scratch or re-index a repository:

**Reset Database (clears all data):**
```bash
# Inside dev container
./scripts/dev-reset-db.sh

# Or manually:
docker exec inxr2-dev bash -c "PGPASSWORD=inxr2_dev_password psql -h postgres -U inxr2_user -d inxr2_dev -c 'TRUNCATE repositories CASCADE;'"
```

**Full Index (from scratch):**
```bash
# Index a single repository
docker exec inxr2-dev inxr2 index full --path /workspace

# Index multiple repositories using config file
docker exec inxr2-dev inxr2 index full --config /workspace/config.yaml

# Index a specific repository from config
docker exec inxr2-dev inxr2 index full --config /workspace/config.yaml --repo myrepo

# With verbose output
docker exec inxr2-dev inxr2 index full --path /workspace --verbose

# Index specific languages only (default: python,typescript)
docker exec inxr2-dev inxr2 index full --path /workspace --languages python,typescript,javascript
```

**Incremental Index (only changed files):**
```bash
# Faster - only indexes files changed since last index
docker exec inxr2-dev inxr2 index incremental --path /workspace

# Specify a branch
docker exec inxr2-dev inxr2 index incremental --path /workspace --branch main
```

**Check Index Status:**
```bash
docker exec inxr2-dev inxr2 index status --path /workspace
```

### Indexing External Repositories

You can index repositories stored outside the INXR2 project directory by mounting them into the container:

**1. Update docker-compose.dev.yml to mount your repos:**
```yaml
volumes:
  - .:/workspace
  - /path/to/your/repos:/repos:ro  # Mount repos read-only
```

**2. Create a config.yaml:**
```yaml
# config.yaml
repositories:
  - name: "project-a"
    path: "/repos/project-a"
    branches:
      - main
    languages:
      - python
      - typescript

  - name: "project-b"
    path: "/repos/project-b"
    branches:
      - main
      - develop
```

**3. Restart containers and index:**
```bash
# Restart to pick up new mount
docker-compose -f docker-compose.dev.yml up -d

# Validate config
docker exec inxr2-dev inxr2 config validate /workspace/config.yaml

# Index all repositories
docker exec inxr2-dev inxr2 index full --config /workspace/config.yaml

# Start the servers
docker exec -d inxr2-dev bash -c "cd /workspace && inxr2 serve --reload"
docker exec -d inxr2-dev bash -c "cd /workspace/frontend && npm run dev"

# Browse at http://localhost:5173
```

**Config Commands:**
```bash
# Validate config file
docker exec inxr2-dev inxr2 config validate /workspace/config.yaml

# Show parsed config (with env vars expanded)
docker exec inxr2-dev inxr2 config show /workspace/config.yaml
```

**Complete Reset and Re-index:**
```bash
# 1. Clear all indexed data
docker exec inxr2-dev bash -c "PGPASSWORD=inxr2_dev_password psql -h postgres -U inxr2_user -d inxr2_dev -c 'TRUNCATE repositories CASCADE;'"

# 2. Run full index
docker exec inxr2-dev inxr2 index full --path /workspace

# 3. Start the server (if not running)
docker exec -d inxr2-dev bash -c "cd /workspace && inxr2 serve --reload"

# 4. Access at http://localhost:5173
```

### Troubleshooting

**Container won't start?**
```bash
docker ps  # Check if Docker is running
docker-compose -f docker-compose.dev.yml build --no-cache  # Rebuild
```

**Packages not installed?**
The dev container automatically installs packages on startup. If you see import errors, restart the container:
```bash
docker-compose -f docker-compose.dev.yml restart dev
```

**Database connection issues?**
```bash
docker-compose -f docker-compose.dev.yml ps  # Check postgres is healthy
./scripts/dev-reset-db.sh  # Reset database if needed
```

## Deployment

### Environment Configuration

**CRITICAL: Set up environment variables before deploying to production!**

1. **Create production environment file:**
   ```bash
   cp .env.prod.example .env.prod
   ```

2. **Edit `.env.prod` and set secure values:**
   - `POSTGRES_PASSWORD`: Strong password (generate with `openssl rand -base64 32`)
   - `SECRET_KEY`: Random secret key (generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
   - `ALLOWED_HOSTS`: Your domain(s)
   - `CORS_ORIGINS`: Your frontend URL(s)

3. **Never commit `.env.prod` to version control!** (already in `.gitignore`)

### Docker Compose Deployment (Recommended)

```bash
# 1. Configure environment (see above)
cp .env.prod.example .env.prod
nano .env.prod  # Edit with secure values

# 2. Build and start
docker-compose build
docker-compose up -d

# 3. View logs
docker-compose logs -f

# 4. Stop
docker-compose down
```

### Standalone Docker Deployment

INXR2 can also run as a single Docker container:

```bash
# Build the image
docker build -t inxr2 .

# Run with environment file
docker run -d \
  -p 8000:8000 \
  --env-file .env.prod \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v inxr2-data:/var/lib/postgresql/data \
  --name inxr2 \
  inxr2:latest
```

The container includes:
- FastAPI application server
- React frontend (built static assets)
- PostgreSQL database
- Tree-sitter parsers for all supported languages

See [DESIGN.md - Section 9](DESIGN.md#9-deployment) for detailed deployment options.

## Configuration

### Environment Variables

Environment variables are managed through `.env` files:

- **`.env.dev`**: Development environment (committed to repo)
- **`.env.prod`**: Production environment (NOT committed - create from `.env.prod.example`)
- **`.env.example`**: Template showing all available variables

**Key Variables:**
- `POSTGRES_PASSWORD`: Database password (CHANGE in production!)
- `DATABASE_URL`: Full database connection string
- `ENVIRONMENT`: development, staging, or production
- `DEBUG`: Enable debug mode (false in production)
- `LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `SECRET_KEY`: Secret key for security features (production only)
- `ALLOWED_HOSTS`: Comma-separated list of allowed domains
- `CORS_ORIGINS`: Comma-separated list of allowed CORS origins

See `.env.example` for complete list of variables.

### Application Configuration

Example `config.yaml`:

```yaml
repositories:
  # Local repository (path must be accessible inside container)
  - name: "backend-api"
    path: "/repos/backend-api"
    branches:
      - main
    languages:
      - python
      - typescript
      - javascript
    exclude_patterns:
      - "**/node_modules/**"
      - "**/__pycache__/**"

  # Environment variables supported
  - name: "frontend-app"
    path: "${HOME}/projects/frontend"
    branches:
      - main
      - develop

  # Remote URLs (Phase 1.9 - not yet implemented)
  # - name: "react"
  #   url: "https://github.com/facebook/react"
  #   branches:
  #     - main

indexing:
  incremental: true           # Use incremental indexing when possible
  max_commit_history: 1000    # Max commits to index per branch
  batch_size: 100             # Files per database batch

server:
  host: "0.0.0.0"
  port: 8000
```

See `config.example.yaml` for a complete example.

## Project Status

**Current Phase**: Phase 1.7 Complete (Configuration System)

INXR2 has completed Phase 1.7 with multi-repository configuration support. You can now define multiple repositories in a YAML config file and index them all with a single command. The implementation includes 195 tests passing.

### Roadmap

**Completed Phases:**
- [x] Phase 1.1: Project Setup
- [x] Phase 1.2: React Frontend and Development Infrastructure
- [x] Phase 1.3: Database Foundation and Environment Configuration (2026-01-04)
- [x] Phase 1.4: Vertical Slice - Basic File Indexing (2026-01-05)
- [x] Phase 1.5: CLI Indexing Engine - Python & TypeScript (2026-01-10)
- [x] Phase 1.6: Cross-Reference Code Browser UI (2026-01-11)
  - Symbol search with autocomplete and filters
  - Go to Definition (click symbol to navigate)
  - Find References panel with type annotations
  - Syntax highlighting with Prism.js (20+ languages)
  - File tree navigation with language icons
  - Symbol disambiguation for multiple definitions
- [x] Phase 1.7: Configuration System (2026-01-13)
  - YAML configuration with Pydantic validation
  - Multi-repository indexing via `--config` flag
  - Environment variable expansion (`${VAR}` and `${VAR:-default}`)
  - Config validation and show commands
  - Repository selector in UI
  - 195 tests passing (178 backend + 17 frontend)

**Next Phases:**
- [ ] Phase 1.8: Tree-sitter Integration (replace regex extraction)
- [ ] Phase 1.9: Remote Repository Support (clone from URLs)
- [ ] Phase 1.10: Improved Reference Resolution (scope-aware, import-aware)
- [ ] Phase 2: Additional Language Support (Java, C#, Go, C/C++)

## Contributing

We welcome contributions! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development philosophy and clean code principles
- Code style requirements (Black for Python, Prettier for TypeScript)
- Testing requirements (80%+ coverage, prefer dependency injection over mocking)
- Git commit guidelines

**Key Requirements:**
- All code must have tests (run before AND after changes)
- Follow type hints in Python and strict TypeScript
- Use dependency injection instead of mocking
- Run formatters and linters before committing

## License

TBD

## Support

For questions or issues:
- Open an issue on GitHub
- See [DESIGN.md](DESIGN.md) for architectural questions
- See [DEVELOPMENT.md](DEVELOPMENT.md) for development help

---

Built with focus on clean code, high test coverage, and developer experience.
