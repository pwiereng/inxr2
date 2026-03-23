# INXR2 - Cross-Reference Code Browser

This is a modern cross-reference code browser designed for teams working with git repositories. INXR2 enables developers to browse, search, and understand code across multiple repositories with powerful temporal navigation capabilities.

## Overview

INXR2 is similar to LXR (Linux Cross Reference) but built specifically for git-based development workflows. It provides deep code intelligence with the ability to browse code at any point in history, making it easy to understand how your codebase evolved over time.

### Key Differentiators

- **Temporal Navigation**: Browse code at different points in time based on git history
- **Cross-Repository Browsing**: Navigate seamlessly across multiple team repositories
- **Shareable Permalinks**: Every line and symbol has a permanent, shareable URL
- **Self-Contained**: Runs in a single Docker container for easy local and cloud deployment
- **Multi-Language**: Support for Python, TypeScript/JavaScript, C, C++, Java, C#, Go, Ruby, and Swift

## Features

### Core Capabilities

- **Jump to Definition & Find References**: Navigate code with semantic understanding
- **Symbol Search**: Fast search across all indexed repositories
- **Full-Text Search**: Find anything across all files, including non-indexed languages
- **Git History Integration**: Browse code at any commit on configured branches
- **Side-by-Side Diff View**: Compare file versions across time
- **Incremental Indexing**: Fast updates without full re-indexing
- **Shareable Links**: Permanent URLs for lines, ranges, symbols, and diffs
- **Logical View**: Hierarchical symbol browser with language and kind filters
- **Dependency Inventory**: Manifest/lock file parsing across 6 language ecosystems
- **MCP Server**: AI assistant integration via Model Context Protocol (Claude, Cursor)

### Supported Languages

**With Semantic Indexing:**
- Python
- TypeScript/JavaScript
- C / C++
- Java
- C#
- Go
- Ruby
- Swift

**With Dependency Parsing:**
- Python (pyproject.toml, requirements.txt, setup.py)
- JavaScript/TypeScript (package.json, package-lock.json)
- Java (pom.xml, build.gradle)
- C# (*.csproj)
- Go (go.mod, go.sum)
- Ruby (Gemfile, Gemfile.lock)

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

For detailed architecture decisions, see [CLAUDE.md](CLAUDE.md).

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

**Build from scratch:**
```bash
# Build and start (first time takes ~2-3 minutes)
docker compose -f docker-compose.dev.yml up -d --build

# Monitor the build/setup progress (wait for "🎉 Container ready!")
docker compose -f docker-compose.dev.yml logs -f dev

# Open a shell in the container
docker exec -it inxr2-dev bash
```

The entrypoint automatically handles everything:
- Starts embedded PostgreSQL
- Creates databases (`inxr2_dev`, `inxr2_test`) and user role
- Applies database migrations
- Installs Node packages (via npm)

Python packages are pre-installed into system Python at image build time.
Rebuild the image (`docker compose -f docker-compose.dev.yml up -d --build`) when `pyproject.toml` changes.

**Index repositories:**
```bash
# Inside the container
inxr2 index --config config.yaml

# Or from the host
docker exec inxr2-dev inxr2 index --config config.yaml
```

**Start the servers:**
```bash
# Inside the container — starts both backend and frontend
./scripts/dev-serve.sh
```

**Tear down to nothing (removes containers + all data):**
```bash
docker compose -f docker-compose.dev.yml down -v
```

**Helper scripts (run from host):**
```bash
./scripts/dev-start.sh   # Build and start
./scripts/dev-shell.sh   # Open shell
./scripts/dev-stop.sh    # Stop (preserves data)
./scripts/dev-logs.sh    # View logs
```

**Services Available:**
- Backend API: `http://localhost:8000` (once started)
- Frontend: `http://localhost:5173` (once started)
- PostgreSQL: embedded inside container (no external port)

For more details, see [DEVELOPMENT.md](DEVELOPMENT.md).

## ⚠️ CRITICAL: Development Guidelines

**BEFORE making any changes, READ and FOLLOW these mandatory guidelines:**

### 1. Docker-Only Development
- ❌ **NEVER** run `npm install` or `pip install` on your host machine
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
- Python: Packages installed at image build time; rebuild image when `pyproject.toml` changes
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

## MCP Server (AI Assistant Integration)

INXR2 includes an MCP (Model Context Protocol) server that exposes code intelligence as tools for AI assistants like Claude Desktop, Cursor, and Claude Code.

**Available tools:**
- `list_repositories` — List indexed repos with branches and stats
- `search_symbols` — Find symbol definitions by name (semantic search)
- `find_references` — Find all usages of a symbol across repos
- `go_to_definition` — Jump to where a symbol is defined
- `search_code` — Full-text or regex search across all files
- `find_dead_code` — Find unreferenced symbols (potential dead code)
- `review_helper` — Analyze blast radius of a commit (changed files, affected symbols, downstream references)

The MCP server runs inside the dev container on port 3000 (SSE transport) and starts automatically with `./scripts/dev-serve.sh`.

See [mcp-server/README.md](mcp-server/README.md) for tool parameters, configuration, and setup instructions.

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Architecture, project structure, development guidelines, and AI assistant instructions
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Coding standards, testing requirements, and contribution guidelines
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Quick reference for common development tasks and workflows
- **[mcp-server/README.md](mcp-server/README.md)** - MCP server tools, configuration, and AI assistant setup

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
mypy src/ tests/           # Python
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

### Indexing

INXR2 uses **full snapshot indexing** — every indexed commit stores the complete file tree. This makes indexing idempotent and ensures correct time-travel at any indexed commit.

**How it works:**

| Command | Behavior |
|---------|----------|
| `inxr2 index` | **First run**: indexes HEAD only. **Subsequent**: indexes all new commits since last run (forward fill). |
| `inxr2 index --days 30` | Indexes all commits from the last 30 days. Already-indexed commits are skipped. |
| `inxr2 db reset --yes` | Wipes all data. Follow with `inxr2 index` to start fresh. |

**Key properties:**

- **Idempotent**: Running the same command twice produces the same result. No `--force` needed.
- **No gaps**: Forward fill always runs, ensuring contiguous coverage from the oldest indexed commit to HEAD.
- **Backfill with `--days`**: Extend history backward at any time. `--days 10` today, `--days 100` tomorrow — equivalent to `--days 100` from scratch.
- **Content-hash reuse**: Files unchanged between commits skip parsing. Watch for "File Versions (new)" and "File Versions (cached)" in output.

**Examples:**
```bash
# Index HEAD of all configured repos
docker exec inxr2-dev inxr2 index --config config.yaml

# Index last 30 days of history
docker exec inxr2-dev inxr2 index --config config.yaml --days 30

# Index a specific repo
docker exec inxr2-dev inxr2 index --config config.yaml --repo myrepo

# Full reset + re-index
docker exec inxr2-dev bash -c "inxr2 db reset --yes && inxr2 index --config config.yaml --days 30"

# Check what's indexed
docker exec inxr2-dev inxr2 index status --config config.yaml
```

**Branch behavior with `--days`:**
- **Primary branch** (first in config): Always indexed — at minimum HEAD, or N days if specified.
- **Other branches**: Only indexed if they have commits within the `--days` window.

```yaml
repositories:
  - name: myrepo
    branches:
      - main        # Primary - always indexed (at least HEAD)
      - feature-a   # Only indexed if has commits within --days
      - feature-b   # Only indexed if has commits within --days
```

**Interactive Shell (alternative):**
```bash
# Open a shell inside the container, then run commands directly:
docker exec -it inxr2-dev bash

# Now you can run without docker exec prefix:
inxr2 db reset --yes
inxr2 index --config config.yaml
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
docker compose -f docker-compose.dev.yml up -d

# Validate config
docker exec inxr2-dev inxr2 config validate /workspace/config.yaml

# Index all repositories
docker exec inxr2-dev inxr2 index --config /workspace/config.yaml

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

### Starting the Servers

**Recommended: Use the helper script to start both servers at once:**
```bash
# Inside the dev container
./scripts/dev-serve.sh

# Or from the host
docker exec -it inxr2-dev ./scripts/dev-serve.sh
```

This starts both backend (port 8000) and frontend (port 5173) with hot reload. Press Ctrl+C to stop both.

**Alternative: Start servers separately:**
```bash
# Start the backend server (runs in background)
docker exec -d inxr2-dev bash -c "cd /workspace && inxr2 serve --reload"

# Start the frontend dev server (runs in background)
docker exec -d inxr2-dev bash -c "cd /workspace/frontend && npm run dev"

# Or open an interactive shell and run them:
docker exec -it inxr2-dev bash
inxr2 serve --reload  # In one terminal
cd frontend && npm run dev  # In another terminal
```

### Troubleshooting

**Container won't start?**
```bash
docker ps                                                            # Check if Docker is running
docker compose -f docker-compose.dev.yml logs dev                    # Check entrypoint logs
docker compose -f docker-compose.dev.yml build --no-cache            # Full rebuild
```

**Start completely fresh (nuclear option):**
```bash
docker compose -f docker-compose.dev.yml down -v      # Remove containers + volumes
docker compose -f docker-compose.dev.yml up -d --build # Rebuild everything
```

**Packages not installed?**
The dev container automatically installs packages on startup. If you see import errors, restart the container:
```bash
docker compose -f docker-compose.dev.yml restart dev
```

**Database connection issues?**
PostgreSQL is embedded inside the dev container. Check it's running:
```bash
docker exec inxr2-dev pg_isready -h localhost          # Should say "accepting connections"
./scripts/dev-reset-db.sh                              # Reset database if needed
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

See [CLAUDE.md](CLAUDE.md) for detailed architecture and deployment information.

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
    exclude_paths:            # Directory segments to skip (opt-in)
      - node_modules
      - vendor

  # Environment variables supported
  - name: "frontend-app"
    path: "${HOME}/projects/frontend"
    branches:
      - main
      - develop

  # Remote URLs (Phase 1.12 - not yet implemented)
  # - name: "react"
  #   url: "https://github.com/facebook/react"
  #   branches:
  #     - main

server:
  host: "0.0.0.0"
  port: 8000
```

See `config.example.yaml` for a complete example.

## Project Status

**Current Phase**: Active development — all core features implemented

INXR2 has completed all core phases (1.1–1.11) plus Logical View, Dependency Inventory, and MCP server integration. 771 commits across 53 active days, with 1,727 backend tests passing and a 62-test regression suite.

### Completed Features
- Project setup, React frontend, and development infrastructure
- Database foundation with PostgreSQL and environment configuration
- File indexing with Tree-sitter AST parsing (Python, TypeScript, JavaScript, C, C++, Java, C#, Go, Ruby, Swift)
- Cross-reference code browser UI with symbol search
- Configuration system (YAML-based multi-repository support)
- Time travel and temporal navigation (browse code at any indexed commit)
- Side-by-side diff viewer with syntax highlighting
- Full URL state management for bookmarkable views and permalinks
- Multi-branch support with branch selector and cross-branch diffs
- Full-text search (keyword, phrase, regex) across all files
- Git blame integration
- Light and dark theme support
- Logical View (hierarchical symbol browser with language/kind filters)
- Dependency inventory (manifest/lock file parsing for Python, JS/TS, Java, C#, Go, Ruby)
- MCP server with 7 tools for AI assistant integration

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
- See [CLAUDE.md](CLAUDE.md) for architectural questions
- See [DEVELOPMENT.md](DEVELOPMENT.md) for development help

---

Built with focus on clean code, high test coverage, and developer experience.
