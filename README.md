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

### Using Docker

```bash
# Clone the repository
git clone <repository-url>
cd inxr2

# Create configuration file
cat > config.yaml <<EOF
repositories:
  team_repos:
    - name: "my-repo"
      url: "https://github.com/myorg/my-repo"
      branches:
        - main
EOF

# Run with Docker Compose
docker-compose up -d

# Index repositories
docker exec inxr2 inxr2 index --config /app/config.yaml

# Access the web UI
open http://localhost:8000
```

### Local Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed setup instructions.

## Documentation

- **[DESIGN.md](DESIGN.md)** - Complete design document including architecture, requirements, data model, and deployment strategy
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Coding standards, testing requirements, and contribution guidelines
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Quick reference for common development tasks and workflows

## Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Docker (for containerized deployment)

### Setup

```bash
# Backend setup
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Frontend setup
cd frontend
npm install

# Install pre-commit hooks
pre-commit install

# Run tests
pytest --cov=src
npm test
```

For more details, see [DEVELOPMENT.md](DEVELOPMENT.md).

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
