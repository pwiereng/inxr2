# Cross-Reference Code Browser - Design Document

> **⚠️ CRITICAL:** Before making any code changes, read [CLAUDE.md](CLAUDE.md) and [CONTRIBUTING.md](CONTRIBUTING.md).
> All development MUST follow Docker-only workflow, testing requirements, and code quality standards.

## 1. Goals & Vision

Build a cross-reference code browser similar to LXR, but designed for teams working with git repositories. The tool enables developers to browse, search, and understand code across multiple repositories with temporal navigation capabilities.

### Key Differentiators
- **Temporal Navigation**: Browse code at different points in time based on git history
- **Cross-Repository Browsing**: Navigate seamlessly across multiple team repositories
- **Self-Contained**: Runs in a single Docker container for easy local and cloud deployment
- **Multi-Language**: Support major programming languages with extensible architecture

## 2. Requirements

### 2.1 Functional Requirements

**Must Have (v1):**
- Jump to definition and find all references (for indexed languages)
- Symbol search across all indexed repositories
- Free text search across all files (including non-indexed languages)
- Display and browse all file types, with semantic features for core languages
- **Shareable permalinks**: Every line, symbol, and code location has a permanent, shareable URL
- Git history integration with temporal navigation on configured branches (e.g., main/master)
- Side-by-side diff view for comparing file versions
- Cross-repository code browsing
- Incremental indexing (avoid full re-index on updates)
- Manual trigger for index updates

**Nice to Have (Future):**
- Call graphs (who calls this function, what does it call)
- Type hierarchy visualization
- Semantic code search
- Automated update triggers (webhooks)
- Admin web UI for configuration
- Shared third-party library indexes
- Additional language support beyond initial set

### 2.2 Non-Functional Requirements

**Performance Targets:**
- Simple symbol lookup: < 1 second
- Complex queries or file rendering: < 5 seconds
- Incremental indexing should be significantly faster than full re-index

**Scale Parameters:**
- Number of repositories: 10-100
- Repository sizes: 1,000 - 10,000 lines of code each
- Total codebase: ~10k to 1M LOC
- Concurrent users: ~5
- Indexed branches: Configured branches only (typically main/master, not all branches)

**Deployment:**
- Self-contained Docker container
- Runs locally on Mac with Docker Desktop
- Can be deployed to cloud environments
- No cloud-native dependencies required

## 3. Tech Stack

### 3.1 Core Technologies

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Backend** | FastAPI (Python) | Modern, fast, async support, excellent for APIs |
| **Frontend** | React | Rich UI capabilities, large ecosystem |
| **Database** | PostgreSQL | Self-contained, excellent full-text search, handles relational data well |
| **Code Parser** | Tree-sitter | Multi-language support, accurate AST parsing, incremental parsing |
| **Deployment** | Docker | Self-contained, portable, works locally and in cloud |

### 3.2 Language Support

**Initial Languages (with semantic indexing):**
- Python
- TypeScript/JavaScript
- Java
- C

**Non-Indexed Languages:**
Files in languages outside the core set will still be:
- Displayed in the code viewer with basic syntax highlighting
- Included in free text search
- Browsable through the UI
- Available in git history and diff views

They simply won't have semantic cross-reference features (jump-to-definition, find-references) until parsers are added.

**Extensibility:** Architecture should support adding more languages via additional tree-sitter grammars.

## 4. Architecture

### 4.1 High-Level Components

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Container                      │
│                                                          │
│  ┌──────────────┐      ┌─────────────────┐             │
│  │              │      │                 │             │
│  │  React SPA   │◄─────┤  FastAPI        │             │
│  │  (Frontend)  │ HTTP │  (Backend API)  │             │
│  │              │      │                 │             │
│  └──────────────┘      └────────┬────────┘             │
│                                 │                       │
│                        ┌────────▼────────┐              │
│                        │   PostgreSQL    │              │
│                        │   (Index Data)  │              │
│                        └─────────────────┘              │
│                                                          │
│  ┌──────────────────────────────────────┐               │
│  │  Indexing Engine (CLI)               │               │
│  │  - Git operations                    │               │
│  │  - Tree-sitter parsing               │               │
│  │  - Incremental diff processing       │               │
│  │  - Symbol extraction & storage       │               │
│  └──────────────────────────────────────┘               │
│                                                          │
│  ┌──────────────────────────────────────┐               │
│  │  Config (YAML)                       │               │
│  │  - Repository definitions            │               │
│  │  - Branch configurations             │               │
│  └──────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Component Descriptions

**React Frontend:**
- Single-page application with server-side rendering for initial load
- Code viewer with syntax highlighting
- Symbol navigation (click to jump to definition)
- Search interface (symbol search and text search)
- Timeline/history navigation UI
- Side-by-side diff viewer
- Repository/file tree browser

**FastAPI Backend:**
- REST API endpoints for:
  - Symbol search and lookup
  - Text search
  - File content retrieval
  - Git history queries
  - Cross-reference resolution
- Serves React frontend
- Queries PostgreSQL for all data

**PostgreSQL Database:**
- Stores parsed symbol information
- Stores cross-references (def-use chains)
- Stores file metadata and git history
- Full-text search indexes
- Multiple versions of code for temporal navigation

**Indexing Engine (CLI):**
- Triggered manually via command-line
- Clones/updates git repositories
- Uses tree-sitter to parse code and extract symbols
- Performs incremental updates by:
  - Tracking last indexed commit hash
  - Computing git diff between commits
  - Re-indexing only changed files
  - Updating affected cross-references
- Stores everything in PostgreSQL

**Configuration:**
- YAML file defining:
  - Repository URLs (git clone URLs or local paths)
  - Branches to index
  - Language-specific settings
- Mounted into Docker container

## 5. Data Model

### 5.1 Core Entities

**Repositories:**
- Repository ID, URL, name
- Last indexed commit hash per branch
- Configuration metadata

**Commits:**
- Commit hash, timestamp, branch
- Author, message
- Links to indexed files at this commit

**Files:**
- File path, repository, commit
- Content hash (for deduplication)
- Language type
- File content or reference to content

**Symbols:**
- Symbol name, kind (class, function, variable, etc.)
- File, line, column position
- Repository, commit (for temporal indexing)
- Scope/namespace
- Language-specific metadata (stored as JSONB)

**References:**
- Source location (file, line, column)
- Target symbol
- Reference type (definition, usage, call, etc.)
- Repository, commit

**Search Indexes:**
- Full-text search on file contents
- Symbol name search with GIN indexes
- Optimized for < 1 second lookups

### 5.2 Temporal Data Strategy

- Store snapshots of symbols and references per commit
- Query by (repository, branch, commit/timestamp) to get code at a point in time
- Enable diffing by comparing two commits

## 6. Indexing Pipeline

### 6.1 Initial Index

1. Read YAML configuration
2. For each configured repository and branch:
   - Clone repository (or use local path)
   - Checkout configured branch
   - For each file:
     - Detect language
     - Parse with tree-sitter
     - Extract symbols (definitions)
     - Extract references
     - Store in database with commit metadata
3. Build cross-reference mappings
4. Create database indexes
5. Record indexed commit hash

### 6.2 Incremental Update

1. Fetch latest changes from remote
2. Compare current HEAD with last indexed commit
3. Get list of changed files (added, modified, deleted)
4. For modified/added files:
   - Re-parse with tree-sitter
   - Update symbols and references
5. For deleted files:
   - Mark as deleted in database (preserve for history)
6. Update cross-references affected by changes
7. Update last indexed commit hash

### 6.3 Tree-sitter Integration

- Use tree-sitter Python bindings
- Load language-specific grammars for each supported language
- Write tree-sitter queries to extract:
  - Function/method definitions
  - Class/interface definitions
  - Variable declarations
  - Import/include statements
  - References to symbols
- Handle language-specific nuances with custom extraction logic

## 7. User Interface

### 7.1 Main Views

**Repository Browser:**
- List of indexed repositories
- File tree navigation
- Branch/commit selector for temporal navigation

**Code Viewer:**
- Syntax-highlighted source code
- Click-to-navigate on symbols
- Breadcrumb navigation
- Line numbers with shareable permalink support
- Copy permalink button for current location
- Git blame/history integration

**Search Interface:**
- Symbol search with autocomplete
- Full-text search across all files
- Filter by repository, language, file type
- Search results with context snippets

**History/Timeline View:**
- Select commit/date to browse code at that point
- Visualize file changes over time
- Side-by-side diff view for comparing versions

**Diff Viewer:**
- Side-by-side or unified diff
- Syntax highlighting in diffs
- Navigate between changes

### 7.2 Key Interactions

- Click on symbol → jump to definition
- Right-click menu → find references, view history, copy permalink
- Timeline slider → browse code at different points in time
- Select two commits → view diff
- Click line number → update URL to include line number for sharing

### 7.3 Shareable Permalinks

Every code location has a permanent, shareable URL that can be copied and shared with team members.

**URL Structure:**

```
# Specific line in a file
/repo/{repo-name}/blob/{commit-hash}/{file-path}#L{line-number}

# Line range
/repo/{repo-name}/blob/{commit-hash}/{file-path}#L{start}-L{end}

# Symbol reference
/repo/{repo-name}/symbol/{symbol-id}

# Diff view
/repo/{repo-name}/compare/{commit1}...{commit2}/{file-path}
```

**Examples:**
```
# Single line
/repo/backend-api/blob/abc123def/src/main.py#L42

# Line range (for sharing a function or block)
/repo/backend-api/blob/abc123def/src/main.py#L42-L58

# Symbol (auto-resolves to definition)
/repo/backend-api/symbol/calculate_total

# Diff between commits
/repo/backend-api/compare/abc123...def456/src/main.py
```

**Key Features:**
- URLs use commit hashes (not branch names) for true permanence
- Line numbers are preserved even if file changes
- Clicking line numbers updates the URL automatically
- Copy permalink button in UI
- URLs work even if you're browsing at a different commit
- Support for line ranges (e.g., L10-L20) to share code blocks

## 8. Configuration

### 8.1 Example YAML Configuration

```yaml
repositories:
  team_repos:
    - name: "backend-api"
      url: "https://github.com/myorg/backend-api"
      branches:
        - main
      languages:
        - python

    - name: "frontend-app"
      url: "https://github.com/myorg/frontend-app"
      branches:
        - main
      languages:
        - typescript
        - javascript

    - name: "shared-utils"
      url: "/local/path/to/shared-utils"
      branches:
        - main
        - develop
      languages:
        - python
        - go

  third_party:
    - name: "react"
      url: "https://github.com/facebook/react"
      branches:
        - main
      languages:
        - javascript

indexing:
  incremental: true
  max_commit_history: 1000  # Only index last N commits per branch

search:
  max_results: 100
```

### 8.2 CLI Commands

```bash
# Initial index
inxr2 index --config config.yaml

# Update/re-index
inxr2 reindex --config config.yaml

# Index specific repository
inxr2 index --repo backend-api

# Start web server
inxr2 serve --port 8000
```

## 9. Deployment

### 9.1 Docker Container

**Single container includes:**
- FastAPI application
- React frontend (built static assets)
- PostgreSQL database
- Tree-sitter libraries and grammars
- Git client

**Volumes:**
- Config file (YAML)
- Database data (PostgreSQL data directory)
- Optional: local git repositories

**Ports:**
- 8000: Web UI and API

**Example docker-compose.yml:**
```yaml
version: '3.8'

services:
  inxr2:
    image: inxr2:latest
    ports:
      - "8000:8000"
    volumes:
      - ./config.yaml:/app/config.yaml
      - ./data:/var/lib/postgresql/data
      - ./repos:/repos
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@localhost/inxr2
```

### 9.2 Local Development

- Run PostgreSQL in separate container for development
- FastAPI with hot-reload
- React with Vite/webpack dev server
- Docker Compose for full stack

## 10. Performance Considerations

### 10.1 Database Optimization

- B-tree indexes on symbol names, file paths
- GIN indexes for full-text search
- Partial indexes for common queries (e.g., latest commit on main branch)
- Query optimization for cross-reference lookups
- Connection pooling

### 10.2 Caching Strategy (Future)

- Cache parsed ASTs for unchanged files
- In-memory cache for frequently accessed symbols
- HTTP caching headers for frontend assets

### 10.3 Indexing Performance

- Parallel processing of files during indexing
- Batch inserts to database
- Incremental parsing with tree-sitter
- Skip files that haven't changed (via git hash comparison)

## 11. Future Enhancements

### 11.1 Deferred Features

- **Shared Third-Party Indexes**: Pre-built indexes for popular libraries that can be shared across instances
- **Webhook Integration**: Auto-trigger indexing on git push events
- **Admin Web UI**: Manage repositories, trigger re-indexing, view indexing status via web interface
- **Call Graphs**: Visualize function call relationships
- **Type Hierarchies**: Show class inheritance and interface implementations
- **Semantic Search**: Find similar code patterns, detect dead code
- **Additional Languages**: C#, Go, C++, Rust, Ruby, PHP, etc.
- **IDE Integration**: Plugins for VS Code, IntelliJ, etc.
- **Authentication/Authorization**: Multi-tenant support, access controls
- **API Rate Limiting**: Protect against abuse
- **Metrics/Monitoring**: Track usage, performance, indexing jobs

### 11.2 Scalability Path

If scale grows beyond initial targets:
- Separate indexing service from web service
- Add Redis for caching
- Read replicas for PostgreSQL
- Background job queue (Celery/RQ) for async indexing
- Elasticsearch for advanced search capabilities

## 12. Implementation Decisions (Resolved)

### 12.1 Implementation Details (Decided)

- **Syntax Highlighting**: Prism.js (20+ languages supported)
- **Git Operations**: GitPython for git integration
- **Frontend Build**: Vite with React + TypeScript
- **Database Migrations**: Alembic for schema versioning
- **Testing Strategy**: Unit tests with fakes (not mocks), integration tests with SQLite/PostgreSQL
- **Code Parsing**: Tree-sitter for AST-based symbol extraction

### 12.2 Future Architectural Decisions

- When to introduce separate indexing service vs keep in monolith?
- At what scale does PostgreSQL full-text search need to be replaced with Elasticsearch?
- Should we support plugins/extensions for custom language support?

## 13. Success Metrics

### 13.1 MVP Success Criteria

- Successfully index 10 repositories with mixed languages
- Symbol search responds in < 1 second
- Navigate between files and definitions seamlessly
- Browse git history and compare file versions
- Runs reliably in Docker container on Mac and cloud

### 13.2 User Experience Goals

- Faster than grep/ripgrep for finding symbol definitions
- More accurate than ctags for cross-references
- Easier than IDE for cross-repository navigation
- More performant than GitHub web UI for large codebases

## 14. Timeline & Phases

### Phase 1: Core Infrastructure
- Set up FastAPI + React + PostgreSQL
- Implement basic file browser
- Tree-sitter integration for one language (Python)
- Basic symbol extraction and storage

### Phase 2: Cross-Reference Engine
- Implement jump-to-definition
- Find all references
- Symbol search
- Extend to all 4 core languages

### Phase 3: Temporal Navigation
- Git history integration
- Browse code at different commits
- Side-by-side diff viewer

### Phase 4: Polish & Production
- Full-text search
- UI refinements
- Docker packaging
- Documentation
- Testing

---

**Document Version**: 1.1
**Last Updated**: 2026-01-31
**Status**: Implemented (Phase 1.11 Complete)
