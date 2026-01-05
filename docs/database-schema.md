# INXR2 Database Schema Design

**Version:** 1.0
**Date:** 2026-01-04
**Status:** Proposed

## Overview

This document defines the PostgreSQL database schema for INXR2, a cross-reference code browser. The schema is designed to support:
- Multi-repository indexing
- Temporal code navigation (browse code at any commit)
- Symbol cross-referencing within and across repositories
- Incremental indexing
- Efficient search queries

## Design Principles

1. **Temporal Support**: All entities are tied to specific commits to enable time-travel
2. **Denormalization for Performance**: Some data duplicated to avoid expensive JOINs
3. **JSONB for Flexibility**: Use JSONB for language-specific metadata
4. **Indexing Strategy**: Indexes optimized for common query patterns
5. **Clean Architecture**: ORM models (SQLAlchemy) separate from domain entities

---

## Core Tables

### 1. repositories

Stores metadata about indexed git repositories.

```sql
CREATE TABLE repositories (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(255) NOT NULL UNIQUE,
    url                 TEXT NOT NULL,
    description         TEXT,
    default_branch      VARCHAR(100) DEFAULT 'main',
    config              JSONB,                      -- Repository-specific config
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT repositories_name_check CHECK (name ~ '^[a-zA-Z0-9_-]+$')
);

CREATE INDEX idx_repositories_name ON repositories(name);
```

**Fields:**
- `id`: Auto-incrementing primary key
- `name`: Unique identifier for the repository (e.g., "linux-kernel", "django")
- `url`: Git repository URL (https or ssh)
- `description`: Optional description
- `default_branch`: Default branch to index (usually "main" or "master")
- `config`: JSONB for repository-specific settings (branches to index, file patterns, etc.)
- `created_at`, `updated_at`: Audit timestamps

**JSONB config example:**
```json
{
    "branches": ["main", "develop"],
    "file_patterns": ["*.py", "*.java"],
    "exclude_patterns": ["**/test/**", "**/vendor/**"],
    "max_file_size_kb": 1024
}
```

---

### 2. commits

Stores git commit metadata for all indexed commits.

```sql
CREATE TABLE commits (
    id                  BIGSERIAL PRIMARY KEY,
    repository_id       INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_hash         CHAR(40) NOT NULL,          -- Full SHA-1 hash
    short_hash          CHAR(7) NOT NULL,           -- Short hash for display
    parent_hashes       TEXT[],                     -- Array of parent commit hashes
    branch              VARCHAR(255),               -- Branch name (nullable for detached)
    author_name         VARCHAR(255) NOT NULL,
    author_email        VARCHAR(255) NOT NULL,
    committer_name      VARCHAR(255) NOT NULL,
    committer_email     VARCHAR(255) NOT NULL,
    author_date         TIMESTAMP NOT NULL,         -- When authored
    commit_date         TIMESTAMP NOT NULL,         -- When committed
    message             TEXT NOT NULL,
    indexed_at          TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT commits_unique_repo_hash UNIQUE(repository_id, commit_hash)
);

CREATE INDEX idx_commits_repo_hash ON commits(repository_id, commit_hash);
CREATE INDEX idx_commits_repo_branch ON commits(repository_id, branch);
CREATE INDEX idx_commits_repo_date ON commits(repository_id, commit_date DESC);
CREATE INDEX idx_commits_hash ON commits(commit_hash);
```

**Fields:**
- `commit_hash`: Full 40-character SHA-1 hash
- `short_hash`: 7-character short hash for UI display
- `parent_hashes`: Array of parent commit hashes (for merge commits)
- `branch`: Branch this commit belongs to (can be NULL for detached commits)
- Author vs Committer: Git distinguishes between who wrote the code and who committed it
- `author_date` vs `commit_date`: Support for rebasing/cherry-picking

**Indexes:**
- Fast lookup by repository + hash (most common query)
- Fast filtering by branch
- Temporal queries sorted by date
- Global hash lookup (for cross-repo scenarios)

---

### 3. files

Stores metadata about files at specific commits (temporal snapshot).

```sql
CREATE TABLE files (
    id                  BIGSERIAL PRIMARY KEY,
    repository_id       INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_id           BIGINT NOT NULL REFERENCES commits(id) ON DELETE CASCADE,
    path                TEXT NOT NULL,              -- Relative path from repo root
    content_hash        CHAR(40) NOT NULL,          -- SHA-1 of file content (git blob hash)
    size_bytes          INTEGER NOT NULL,
    language            VARCHAR(50),                -- Detected language (python, typescript, etc.)
    encoding            VARCHAR(50) DEFAULT 'utf-8',
    is_binary           BOOLEAN DEFAULT FALSE,
    line_count          INTEGER,
    indexed_at          TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT files_unique_repo_commit_path UNIQUE(repository_id, commit_id, path)
);

CREATE INDEX idx_files_repo_commit ON files(repository_id, commit_id);
CREATE INDEX idx_files_repo_path ON files(repository_id, path);
CREATE INDEX idx_files_language ON files(language);
CREATE INDEX idx_files_content_hash ON files(content_hash);
```

**Fields:**
- `path`: File path relative to repository root (e.g., "src/main.py")
- `content_hash`: Git blob SHA-1 (enables deduplication - same content = same hash)
- `language`: Detected programming language (python, java, typescript, etc.)
- `is_binary`: Skip binary files for parsing
- `line_count`: For UI display and statistics

**Design Notes:**
- Each file entry represents a snapshot at a specific commit
- Same file at different commits = different rows
- `content_hash` allows detecting when files haven't changed between commits
- Unique constraint on (repository_id, commit_id, path) ensures one entry per file per commit

---

### 4. symbols

Stores extracted code symbols (functions, classes, variables, etc.) at specific file versions.

```sql
CREATE TABLE symbols (
    id                  BIGSERIAL PRIMARY KEY,
    file_id             BIGINT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    repository_id       INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_id           BIGINT NOT NULL REFERENCES commits(id) ON DELETE CASCADE,

    -- Symbol identification
    name                VARCHAR(500) NOT NULL,      -- Symbol name
    qualified_name      TEXT,                       -- Fully qualified name (e.g., "module.Class.method")
    kind                VARCHAR(50) NOT NULL,       -- function, class, method, variable, etc.

    -- Location
    start_line          INTEGER NOT NULL,
    start_column        INTEGER NOT NULL,
    end_line            INTEGER NOT NULL,
    end_column          INTEGER NOT NULL,

    -- Scope and context
    parent_symbol_id    BIGINT REFERENCES symbols(id) ON DELETE SET NULL,  -- Parent (e.g., class for method)
    scope               TEXT,                       -- Scope path (e.g., "Class.method")

    -- Language-specific metadata
    signature           TEXT,                       -- Function signature, type annotations
    docstring           TEXT,                       -- Documentation string
    metadata            JSONB,                      -- Language-specific attributes

    -- Search optimization
    name_tsvector       tsvector,                   -- Full-text search vector

    indexed_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_symbols_file ON symbols(file_id);
CREATE INDEX idx_symbols_repo_commit ON symbols(repository_id, commit_id);
CREATE INDEX idx_symbols_name ON symbols(name);
CREATE INDEX idx_symbols_qualified_name ON symbols(qualified_name);
CREATE INDEX idx_symbols_kind ON symbols(kind);
CREATE INDEX idx_symbols_repo_name_kind ON symbols(repository_id, name, kind);
CREATE INDEX idx_symbols_parent ON symbols(parent_symbol_id);

-- Full-text search index
CREATE INDEX idx_symbols_name_fts ON symbols USING GIN(name_tsvector);

-- Trigger to automatically update name_tsvector
CREATE TRIGGER symbols_name_tsvector_update
    BEFORE INSERT OR UPDATE ON symbols
    FOR EACH ROW EXECUTE FUNCTION
    tsvector_update_trigger(name_tsvector, 'pg_catalog.english', name, qualified_name);
```

**Fields:**
- `name`: Simple symbol name (e.g., "calculate_total")
- `qualified_name`: Fully qualified name including module/class (e.g., "myapp.utils.Math.calculate_total")
- `kind`: Symbol type - function, class, method, variable, constant, interface, enum, etc.
- `start_line/column`, `end_line/column`: Precise location in file (1-indexed)
- `parent_symbol_id`: Self-referencing FK for nested symbols (methods within classes)
- `scope`: Scope path for resolution (e.g., "MyClass.my_method")
- `signature`: Function/method signature with types
- `docstring`: Extracted documentation
- `metadata`: JSONB for language-specific attributes

**JSONB metadata examples:**

Python:
```json
{
    "decorators": ["@staticmethod", "@property"],
    "is_async": true,
    "return_type": "List[str]",
    "parameters": [
        {"name": "self", "type": null},
        {"name": "count", "type": "int", "default": "10"}
    ]
}
```

TypeScript:
```json
{
    "modifiers": ["private", "readonly"],
    "is_arrow_function": false,
    "generic_params": ["T", "K"],
    "return_type": "Promise<User>"
}
```

**Indexes:**
- Fast lookup by file (for rendering file with symbols)
- Fast filtering by repository + commit (temporal queries)
- Symbol search by name (autocomplete)
- Qualified name lookup (precise resolution)
- Full-text search with GIN index

---

### 5. references

Stores symbol references (usages) - links from one location to a symbol definition.

```sql
CREATE TABLE references (
    id                      BIGSERIAL PRIMARY KEY,
    repository_id           INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_id               BIGINT NOT NULL REFERENCES commits(id) ON DELETE CASCADE,

    -- Source location (where the reference occurs)
    source_file_id          BIGINT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    source_line             INTEGER NOT NULL,
    source_column           INTEGER NOT NULL,
    source_end_column       INTEGER NOT NULL,
    reference_text          VARCHAR(500) NOT NULL,  -- The actual text being referenced

    -- Target symbol (what is being referenced)
    target_symbol_id        BIGINT REFERENCES symbols(id) ON DELETE SET NULL,
    target_repository_id    INTEGER REFERENCES repositories(id) ON DELETE SET NULL,  -- For cross-repo refs

    -- Reference metadata
    reference_type          VARCHAR(50) NOT NULL,   -- call, import, inheritance, assignment, etc.
    is_definition           BOOLEAN DEFAULT FALSE,  -- True if this is the definition site
    is_write                BOOLEAN DEFAULT FALSE,  -- True if reference modifies the symbol

    -- Resolution metadata
    resolution_confidence   FLOAT DEFAULT 1.0,      -- Confidence in symbol resolution (0.0-1.0)
    metadata                JSONB,                  -- Language-specific reference info

    indexed_at              TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT references_confidence_check CHECK (resolution_confidence >= 0.0 AND resolution_confidence <= 1.0)
);

CREATE INDEX idx_references_source_file ON references(source_file_id);
CREATE INDEX idx_references_target_symbol ON references(target_symbol_id);
CREATE INDEX idx_references_repo_commit ON references(repository_id, commit_id);
CREATE INDEX idx_references_type ON references(reference_type);
CREATE INDEX idx_references_text ON references(reference_text);
CREATE INDEX idx_references_source_line ON references(source_file_id, source_line);
```

**Fields:**
- `source_*`: Where the reference appears (file, line, column)
- `reference_text`: The actual text (e.g., "calculate_total" or "MyClass")
- `target_symbol_id`: The symbol being referenced (FK to symbols)
- `target_repository_id`: For cross-repository references
- `reference_type`: Nature of reference (call, import, inheritance, type_annotation, etc.)
- `is_definition`: True if this is the definition location (not just a usage)
- `is_write`: True for assignments/modifications
- `resolution_confidence`: Quality score for symbol resolution (useful for ambiguous cases)

**Reference Types:**
- `call`: Function/method call
- `import`: Import statement
- `inheritance`: Class inheritance
- `type_annotation`: Type hint/annotation
- `assignment`: Variable assignment
- `attribute_access`: Object attribute access
- `instantiation`: Class instantiation

**JSONB metadata examples:**
```json
{
    "is_qualified": true,
    "qualifier": "math",
    "context": "function_argument"
}
```

---

### 6. index_status

Tracks indexing progress and status for each repository/branch combination.

```sql
CREATE TABLE index_status (
    id                      SERIAL PRIMARY KEY,
    repository_id           INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    branch                  VARCHAR(255) NOT NULL,

    -- Indexing state
    last_indexed_commit     CHAR(40),               -- Last successfully indexed commit hash
    last_indexed_at         TIMESTAMP,              -- When indexing completed
    indexing_started_at     TIMESTAMP,              -- When current/last indexing started
    indexing_status         VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, in_progress, completed, failed

    -- Statistics
    total_commits_indexed   INTEGER DEFAULT 0,
    total_files_indexed     INTEGER DEFAULT 0,
    total_symbols_indexed   INTEGER DEFAULT 0,
    total_references_indexed INTEGER DEFAULT 0,

    -- Error tracking
    error_message           TEXT,
    error_count             INTEGER DEFAULT 0,

    -- Metadata
    indexer_version         VARCHAR(50),            -- Version of indexer that ran
    metadata                JSONB,

    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT index_status_unique_repo_branch UNIQUE(repository_id, branch)
);

CREATE INDEX idx_index_status_repo ON index_status(repository_id);
CREATE INDEX idx_index_status_status ON index_status(indexing_status);
```

**Fields:**
- `last_indexed_commit`: SHA-1 of last fully indexed commit
- `indexing_status`: Current state (pending, in_progress, completed, failed)
- Statistics: Count of indexed entities (for progress tracking)
- `error_message`: Last error encountered
- `indexer_version`: Track which version of INXR2 performed indexing

**Status Values:**
- `pending`: Not yet indexed
- `in_progress`: Currently indexing
- `completed`: Successfully indexed
- `failed`: Indexing failed (see error_message)

---

## Supporting Tables

### 7. file_contents (Optional - for full-text search)

Optionally store file contents for full-text search without hitting git.

```sql
CREATE TABLE file_contents (
    file_id             BIGINT PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    content             TEXT NOT NULL,
    content_tsvector    tsvector,

    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Full-text search index
CREATE INDEX idx_file_contents_fts ON file_contents USING GIN(content_tsvector);

-- Trigger to update tsvector
CREATE TRIGGER file_contents_tsvector_update
    BEFORE INSERT OR UPDATE ON file_contents
    FOR EACH ROW EXECUTE FUNCTION
    tsvector_update_trigger(content_tsvector, 'pg_catalog.english', content);
```

**Design Decision:**
- **Trade-off**: Storage space vs query performance
- Storing contents enables fast full-text search without git operations
- Alternative: Always fetch from git (slower but saves space)
- **Recommendation**: Start without this table, add if needed

---

## Relationships Diagram

```
repositories (1) ──────< (N) commits
    │                        │
    │                        │
    └────────────────< files │
                        │    │
                        │    │
                    symbols  │
                      │  │   │
                      │  └───┘
                      │
                  references
                      │
                      └──> symbols (target)
                      └──> repositories (cross-repo)

index_status (N) ────> (1) repositories
```

---

## Query Patterns & Index Justification

### 1. Find symbol by name in repository
```sql
SELECT * FROM symbols
WHERE repository_id = ? AND name = ?
ORDER BY commit_date DESC
LIMIT 10;
```
**Index:** `idx_symbols_repo_name_kind`

### 2. Get all symbols in a file
```sql
SELECT * FROM symbols
WHERE file_id = ?
ORDER BY start_line, start_column;
```
**Index:** `idx_symbols_file`

### 3. Find all references to a symbol
```sql
SELECT r.*, f.path, c.commit_hash
FROM references r
JOIN files f ON r.source_file_id = f.id
JOIN commits c ON r.commit_id = c.id
WHERE r.target_symbol_id = ?;
```
**Index:** `idx_references_target_symbol`

### 4. Get file at specific commit
```sql
SELECT * FROM files
WHERE repository_id = ? AND commit_id = ? AND path = ?;
```
**Index:** `files_unique_repo_commit_path` (unique constraint serves as index)

### 5. Search symbols (autocomplete)
```sql
SELECT name, qualified_name, kind, COUNT(*) as usage_count
FROM symbols
WHERE name_tsvector @@ to_tsquery('calculate:*')
AND repository_id = ?
GROUP BY name, qualified_name, kind
ORDER BY usage_count DESC
LIMIT 20;
```
**Index:** `idx_symbols_name_fts` (GIN full-text)

### 6. Incremental indexing - detect changed files
```sql
SELECT DISTINCT f.path
FROM files f
JOIN commits c ON f.commit_id = c.id
WHERE f.repository_id = ?
AND c.commit_date > (
    SELECT last_indexed_at FROM index_status
    WHERE repository_id = ? AND branch = ?
);
```
**Index:** `idx_commits_repo_date`

---

## Performance Considerations

### 1. Partitioning Strategy (Future)
For very large deployments, consider partitioning:
- `files` by `repository_id`
- `symbols` by `repository_id`
- `references` by `repository_id`

### 2. Archival Strategy
Older commits can be archived:
- Keep last N commits fully indexed
- Archive older commits to separate tables or cold storage
- Implement on-demand indexing for archived commits

### 3. Connection Pooling
- Use connection pooling (pgBouncer or SQLAlchemy pool)
- Recommended pool size: 10-20 connections for 5 concurrent users

### 4. Materialized Views (Optional)
For expensive aggregations:
```sql
CREATE MATERIALIZED VIEW symbol_statistics AS
SELECT
    repository_id,
    kind,
    COUNT(*) as count,
    AVG(end_line - start_line) as avg_lines
FROM symbols
GROUP BY repository_id, kind;

CREATE INDEX idx_symbol_stats_repo ON symbol_statistics(repository_id);
```

---

## Data Volume Estimates

For a medium-sized repository (100k LOC):
- **Files**: ~1,000 files × 100 commits = 100,000 rows
- **Symbols**: ~10,000 symbols per commit × 100 commits = 1,000,000 rows
- **References**: ~50,000 references per commit × 100 commits = 5,000,000 rows

**Estimated storage per repository:**
- Files: ~10 MB
- Symbols: ~200 MB
- References: ~800 MB
- **Total per repo: ~1 GB**

For 10 repositories: ~10 GB database size

---

## Migration Strategy

1. **Initial schema**: All tables created via Alembic migration
2. **Indexes**: Created in same migration (or separate for large tables)
3. **Data migrations**: Separate migrations for data transformations
4. **Version tracking**: Alembic versions stored in `alembic_version` table

### Alembic Migration Naming Convention
- `001_create_core_tables.py` - repositories, commits, files
- `002_create_symbol_tables.py` - symbols, references
- `003_create_index_status.py` - index_status table
- `004_add_indexes.py` - Performance indexes
- `005_add_fts_indexes.py` - Full-text search indexes

---

## Open Questions

1. **File contents storage**: Store in DB or always fetch from git?
   - **Recommendation**: Start without storage, add if performance requires

2. **Cross-repository references**: How to handle unresolved external symbols?
   - **Recommendation**: Store as unresolved (target_symbol_id = NULL) with metadata

3. **Symbol versioning**: Track symbol renames across commits?
   - **Recommendation**: Phase 2 feature, not MVP

4. **Deleted files/symbols**: Hard delete or soft delete?
   - **Recommendation**: Cascade delete (temporal nature means old commits preserved)

5. **Multi-branch indexing**: Index all branches or just default?
   - **Recommendation**: Configurable per repository, start with default branch only

---

## Next Steps

1. Review and approve this schema design
2. Create Alembic migrations
3. Define domain entities (Python dataclasses)
4. Define repository ports (interfaces)
5. Implement SQLAlchemy ORM models
6. Implement repository adapters
7. Write tests with test database

---

**Review Checklist:**
- [ ] Schema supports all INXR2 features
- [ ] Indexes cover common query patterns
- [ ] Foreign keys ensure referential integrity
- [ ] Constraints prevent invalid data
- [ ] Temporal queries supported
- [ ] Incremental indexing feasible
- [ ] Cross-repository references handled
- [ ] Performance considerations addressed
