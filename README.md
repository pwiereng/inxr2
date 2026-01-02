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

See [Deployment](#deployment) section below for production setup instructions.

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

INXR2 is designed to run in a self-contained Docker container:

```bash
# Build the image
docker build -t inxr2 .

# Run the container
docker run -d \
  -p 8000:8000 \
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

Example `config.yaml`:

```yaml
repositories:
  team_repos:
    - name: "backend-api"
      url: "https://github.com/myorg/backend-api"
      branches:
        - main

    - name: "frontend-app"
      url: "https://github.com/myorg/frontend-app"
      branches:
        - main
        - develop

  third_party:
    - name: "react"
      url: "https://github.com/facebook/react"
      branches:
        - main

indexing:
  incremental: true
  max_commit_history: 1000

search:
  max_results: 100
```

## Project Status

**Current Phase**: Design and Early Development

INXR2 is currently in the design phase with comprehensive documentation complete. Implementation is underway following clean code principles with high test coverage.

### Roadmap

- [x] Design document
- [x] Coding standards and guidelines
- [ ] Core indexing engine
- [ ] Database schema and migrations
- [ ] Tree-sitter integration
- [ ] FastAPI backend
- [ ] React frontend
- [ ] Docker packaging
- [ ] Documentation and examples

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
