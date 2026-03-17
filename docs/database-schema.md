# INXR2 Database Schema Design

**Version:** 7.0
**Date:** 2026-03-16
**Status:** Implemented

## Overview

This document defines the PostgreSQL database schema for INXR2, a cross-reference code browser. The schema is designed to support:
- Multi-repository indexing
- Temporal code navigation (browse code at any commit)
- Symbol cross-referencing within and across repositories
- Incremental indexing
- Efficient search queries
- Multi-branch support (commits can exist on multiple branches)
- Dependency tracking (manifest/lock file parsing)
- File rename tracking (follow files across renames for browse and diff)
- Activity logging (HTTP request and MCP tool call audit trail)

## Design Principles

1. **Temporal Support**: All entities are tied to specific commits to enable time-travel
2. **Minimal Storage**: Only store data that can't be queried from git on-demand
3. **Normalized Branch Handling**: Branches stored in junction table (commits can be on multiple branches)
4. **JSONB for Flexibility**: Use JSONB for language-specific metadata
5. **Indexing Strategy**: Indexes optimized for common query patterns
6. **Clean Architecture**: ORM models (SQLAlchemy) separate from domain entities
7. **PostgreSQL Native**: Schema uses PostgreSQL-specific features (tsvector, GIN indexes, ARRAY)

---

## Core Tables

### 1. repositories

Stores metadata about indexed git repositories.

```sql
CREATE TABLE repositories (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(255) NOT NULL UNIQUE,
    url                 TEXT NOT NULL,              -- Local path (e.g., /repos/myproject)
    description         TEXT,
    default_branch      VARCHAR(100) DEFAULT 'main',
    config              JSON,                       -- Repository-specific config
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX ix_repositories_name ON repositories(name);
```

**Fields:**
- `id`: Auto-incrementing primary key
- `name`: Unique identifier for the repository (e.g., "linux-kernel", "django")
- `url`: Local filesystem path to the repository (plain path, not file:// URL)
- `description`: Optional description
- `default_branch`: Default branch to index (usually "main" or "master")
- `config`: JSON for repository-specific settings
- `created_at`, `updated_at`: Audit timestamps

**JSON config example:**
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

Stores minimal git commit metadata. Author info, message, and parent hashes are queried from git on-demand.

```sql
CREATE TABLE commits (
    id                  SERIAL PRIMARY KEY,
    repository_id       INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_hash         CHAR(40) NOT NULL,          -- Full SHA-1 hash
    author_date         TIMESTAMP NOT NULL,         -- When authored
    commit_date         TIMESTAMP NOT NULL,         -- When committed
    indexed_at          TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_repo_commit_hash UNIQUE(repository_id, commit_hash)
);

CREATE INDEX ix_commits_commit_hash ON commits(commit_hash);
```

**Fields:**
- `commit_hash`: Full 40-character SHA-1 hash
- `author_date` vs `commit_date`: Support for rebasing/cherry-picking
- `indexed_at`: When this commit was indexed

**Design Note:**
The following fields are intentionally NOT stored (queried from git on-demand):
- `author_name`, `author_email`: Available from git commit object
- `committer_name`, `committer_email`: Available from git commit object
- `message`: Available from git commit object
- `parent_hashes`: Available from git commit parents
- `short_hash`: Computed property (commit_hash[:7])
- `branch`: Stored in branch_commits junction table

This design reduces storage by ~30% and avoids data duplication with git.

**Computed Property:**
```python
@property
def short_hash(self) -> str:
    return self.commit_hash[:7]
```

---

### 3. branch_commits (Junction Table)

Links commits to branches. A commit can exist on multiple branches (reflecting git's model).

```sql
CREATE TABLE branch_commits (
    id                  SERIAL PRIMARY KEY,
    repository_id       INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    branch              VARCHAR(255) NOT NULL,
    commit_id           INTEGER NOT NULL REFERENCES commits(id) ON DELETE CASCADE,

    CONSTRAINT uq_branch_commit UNIQUE(repository_id, branch, commit_id)
);

CREATE INDEX ix_branch_commits_branch ON branch_commits(branch);
CREATE INDEX ix_branch_commits_commit_id ON branch_commits(commit_id);
```

**Fields:**
- `repository_id`: Repository this branch-commit link belongs to
- `branch`: Branch name (e.g., "main", "feature/login")
- `commit_id`: Reference to the commit

**Design Note:**
This junction table replaces the previous `branch` column on commits. Benefits:
- A commit can be on multiple branches (e.g., after merge)
- No duplicate commit storage per branch
- Proper representation of git's branch model

---

### 4. files

Stores file versions using content-addressable storage. A file row represents a unique (repo, path, content) combination. Commit association is via the `commit_files` junction table.

```sql
CREATE TABLE files (
    id                  SERIAL PRIMARY KEY,
    repository_id       INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    path                TEXT NOT NULL,              -- Relative path from repo root
    content_hash        CHAR(40) NOT NULL,          -- SHA-1 of file content (git blob hash)
    size_bytes          INTEGER NOT NULL,
    language            VARCHAR(50),                -- Detected language (python, typescript, etc.)
    extension           VARCHAR(20),                -- File extension (e.g., ".py", ".ts")
    encoding            VARCHAR(50) DEFAULT 'utf-8',
    is_binary           BOOLEAN DEFAULT FALSE,
    line_count          INTEGER,
    indexed_at          TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_file_version UNIQUE(repository_id, path, content_hash)
);

CREATE INDEX ix_files_repo_content_hash ON files(repository_id, content_hash);
CREATE INDEX ix_files_language ON files(language);
CREATE INDEX ix_files_extension ON files(extension);
CREATE INDEX ix_files_content_hash ON files(content_hash);
```

**Fields:**
- `path`: File path relative to repository root (e.g., "src/main.py")
- `content_hash`: Git blob SHA-1 (enables deduplication - same content = same hash)
- `extension`: File extension for quick filtering
- `language`: Detected programming language (python, java, typescript, etc.)
- `is_binary`: Skip binary files for parsing
- `line_count`: For UI display and statistics

**Design Notes:**
- Content-addressable: unique on (repository_id, path, content_hash)
- If a file's content doesn't change between commits, it reuses the same row (no duplicate)
- Commit context provided via `commit_files` junction table
- Symbols and references are linked to file versions (not directly to commits)

---

### 5. commit_files (Junction Table)

Maps commits to the files they contain. A file can appear in multiple commits (reused via content hash), and a commit contains many files.

```sql
CREATE TABLE commit_files (
    commit_id           INTEGER NOT NULL REFERENCES commits(id) ON DELETE CASCADE,
    file_id             INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,

    PRIMARY KEY (commit_id, file_id)
);

CREATE INDEX ix_commit_files_file_id ON commit_files(file_id);
```

**Design Notes:**
- Decouples the commit-file relationship from the files table's `commit_id` column
- Enables efficient queries like "which files are in this commit?" and "which commits include this file?"
- Used by the latest-file-version dedup logic for branch-aware queries

---

### 6. symbols

Stores extracted code symbols (functions, classes, variables, constants, etc.) linked to file versions.

```sql
CREATE TABLE symbols (
    id                  SERIAL PRIMARY KEY,
    file_id             INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    repository_id       INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,

    -- Symbol identification
    name                VARCHAR(500) NOT NULL,      -- Symbol name
    qualified_name      TEXT,                       -- Fully qualified name (e.g., "module.Class.method")
    kind                VARCHAR(50) NOT NULL,       -- function, class, method, variable, constant, etc.

    -- Location
    start_line          INTEGER NOT NULL,
    start_column        INTEGER NOT NULL,
    end_line            INTEGER NOT NULL,
    end_column          INTEGER NOT NULL,

    -- Scope and context
    parent_symbol_id    INTEGER REFERENCES symbols(id) ON DELETE SET NULL,
    scope               TEXT,                       -- Scope path (e.g., "Class.method")

    -- Language-specific metadata
    signature           TEXT,                       -- Function signature, type annotations
    docstring           TEXT,                       -- Documentation string
    extra_metadata      JSON,                       -- Language-specific attributes

    indexed_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_symbols_repo_name_file ON symbols(repository_id, name, file_id);
CREATE INDEX ix_symbols_file_id ON symbols(file_id);
CREATE INDEX ix_symbols_name ON symbols(name);
CREATE INDEX ix_symbols_qualified_name ON symbols(qualified_name);
CREATE INDEX ix_symbols_kind ON symbols(kind);
CREATE INDEX ix_symbols_parent_symbol_id ON symbols(parent_symbol_id);
CREATE INDEX ix_symbols_repository_id ON symbols(repository_id);
```

**Fields:**
- `name`: Simple symbol name (e.g., "calculate_total")
- `qualified_name`: Fully qualified name including module/class
- `kind`: Symbol type - function, class, method, variable, constant, interface, enum, property, staticmethod, classmethod, etc.
- `start_line/column`, `end_line/column`: Precise location in file (1-indexed)
- `parent_symbol_id`: Self-referencing FK for nested symbols (methods within classes)
- `scope`: Scope path for resolution (e.g., "MyClass.my_method")
- `signature`: Function/method signature with types
- `docstring`: Extracted documentation
- `extra_metadata`: JSON for language-specific attributes

**Symbol Kinds:**
- `function`: Top-level function
- `class`: Class definition
- `method`: Instance method
- `staticmethod`: Static method (Python `@staticmethod`)
- `classmethod`: Class method (Python `@classmethod`)
- `property`: Property (getter/setter)
- `variable`: Module-level variable
- `constant`: Module-level constant (UPPER_CASE)
- `class_variable`: Class-level variable
- `class_constant`: Class-level constant (UPPER_CASE)
- `instance_variable`: Instance variable (`self.x` in `__init__`)
- `interface`: TypeScript interface
- `enum`: Enumeration
- `enum_member`: Enum member/variant
- `type_alias`: Type alias
- `struct`: C struct
- `union`: C union
- `macro`: C preprocessor macro
- `typedef`: C typedef

**JSON metadata examples:**

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

---

### 7. references

Stores symbol references (usages) - links from one location to a symbol definition.

```sql
CREATE TABLE "references" (
    id                      SERIAL PRIMARY KEY,
    repository_id           INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,

    -- Source location (where the reference occurs)
    source_file_id          INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    source_line             INTEGER NOT NULL,
    source_column           INTEGER NOT NULL,
    source_end_column       INTEGER NOT NULL,
    reference_text          VARCHAR(500) NOT NULL,  -- The actual text being referenced

    -- Target symbol (what is being referenced)
    target_symbol_id        INTEGER REFERENCES symbols(id) ON DELETE SET NULL,
    target_repository_id    INTEGER REFERENCES repositories(id) ON DELETE SET NULL,  -- For cross-repo refs

    -- Reference metadata
    reference_type          VARCHAR(50) NOT NULL,   -- call, import, inheritance, type_annotation, usage, etc.
    is_definition           BOOLEAN NOT NULL,       -- True if this is the definition site
    is_write                BOOLEAN NOT NULL,       -- True if reference modifies the symbol

    -- Resolution metadata
    resolution_confidence   FLOAT NOT NULL,         -- Confidence in symbol resolution (0.0-1.0)
    extra_metadata          JSON,                   -- Language-specific reference info

    indexed_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_references_source_file_id ON "references"(source_file_id);
CREATE INDEX ix_references_target_symbol_id ON "references"(target_symbol_id);
CREATE INDEX idx_references_repo_unresolved ON "references"(repository_id) WHERE target_symbol_id IS NULL;
CREATE INDEX ix_references_reference_type ON "references"(reference_type);
CREATE INDEX ix_references_reference_text ON "references"(reference_text);
CREATE INDEX ix_references_repository_id ON "references"(repository_id);
CREATE INDEX ix_references_target_repository_id ON "references"(target_repository_id);
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

---

### 8. index_status

Tracks indexing progress and status for each repository/branch combination.

```sql
CREATE TABLE index_status (
    id                      SERIAL PRIMARY KEY,
    repository_id           INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    branch                  VARCHAR(255) NOT NULL,

    -- Indexing state
    last_indexed_commit     CHAR(40),               -- Most recent indexed commit hash
    oldest_indexed_commit   CHAR(40),               -- Oldest indexed commit hash (for time-travel range)
    last_indexed_at         TIMESTAMP,              -- When indexing completed
    indexing_started_at     TIMESTAMP,              -- When current/last indexing started
    indexing_status         VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, in_progress, completed, failed

    -- Statistics
    total_commits_indexed   INTEGER DEFAULT 0,
    total_files_indexed     INTEGER DEFAULT 0,
    total_symbols_indexed   INTEGER DEFAULT 0,
    total_references_indexed INTEGER DEFAULT 0,

    -- Duration tracking
    last_indexing_duration_seconds   FLOAT,         -- Time spent parsing/extracting in last run
    last_resolving_duration_seconds  FLOAT,         -- Time spent resolving references in last run

    -- Error tracking
    error_message           TEXT,
    error_count             INTEGER DEFAULT 0,

    -- Metadata
    indexer_version         VARCHAR(50),            -- Version of indexer that ran
    extra_metadata          JSON,

    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_index_status_repo_branch UNIQUE(repository_id, branch)
);

CREATE INDEX ix_index_status_indexing_status ON index_status(indexing_status);
```

**Fields:**
- `last_indexed_commit`: SHA-1 of most recent fully indexed commit
- `oldest_indexed_commit`: SHA-1 of oldest indexed commit (defines time-travel range)
- `indexing_status`: Current state (pending, in_progress, completed, failed)
- Statistics: Count of indexed entities (for progress tracking)
- `last_indexing_duration_seconds`: Wall-clock seconds spent in the file parsing/extraction phase of the last run
- `last_resolving_duration_seconds`: Wall-clock seconds spent in the reference resolution phase of the last run
- `error_message`: Last error encountered
- `indexer_version`: Track which version of INXR2 performed indexing

**Status Values:**
- `pending`: Not yet indexed
- `in_progress`: Currently indexing
- `completed`: Successfully indexed
- `failed`: Indexing failed (see error_message)

---

### 9. text_contents

Stores searchable text extracted from code comments, docstrings, commit messages, and non-code files (markdown, YAML, etc.) for full-text search.

```sql
CREATE TABLE text_contents (
    id                  SERIAL PRIMARY KEY,
    repository_id       INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_id           BIGINT REFERENCES commits(id) ON DELETE CASCADE,  -- nullable for content-addressable model

    -- Source information
    source_type         VARCHAR(50) NOT NULL,       -- comment, docstring, commit_message, non_code_file
    source_file_id      BIGINT REFERENCES files(id) ON DELETE CASCADE,  -- NULL for commit messages
    source_line         INTEGER,                    -- Start line in source file
    source_end_line     INTEGER,                    -- End line in source file

    -- Searchable content
    content             TEXT NOT NULL,              -- Extracted text (stripped of comment markers)
    content_tsvector    TSVECTOR,                   -- Full-text search vector (managed by trigger)

    -- Metadata
    language            VARCHAR(50),                -- Language of source file (NULL for commit messages)
    content_type        VARCHAR(50),                -- single_line_comment, block_comment, docstring, etc.

    indexed_at          TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT text_contents_valid_source CHECK (
        (source_type = 'commit_message' AND source_file_id IS NULL)
        OR (source_type != 'commit_message' AND source_file_id IS NOT NULL)
    )
);

CREATE INDEX idx_text_contents_source_type ON text_contents(source_type);
CREATE INDEX idx_text_contents_source_file ON text_contents(source_file_id);
CREATE INDEX idx_text_contents_language ON text_contents(language);
CREATE INDEX idx_text_contents_repo_commit ON text_contents(repository_id, commit_id);
CREATE INDEX idx_text_contents_fts ON text_contents USING GIN(content_tsvector);

-- Trigger to keep content_tsvector in sync
CREATE TRIGGER text_contents_tsvector_update
    BEFORE INSERT OR UPDATE ON text_contents
    FOR EACH ROW EXECUTE FUNCTION
    tsvector_update_trigger('content_tsvector', 'pg_catalog.english', 'content');
```

**Fields:**
- `source_type`: What kind of text this is — `comment`, `docstring`, `commit_message`, or `non_code_file`
- `source_file_id`: FK to files table (NULL for commit messages which have no source file)
- `source_line/source_end_line`: Location in source file (for comments/docstrings)
- `content`: The extracted text, stripped of comment markers (e.g., `#`, `//`, `/* */`)
- `content_tsvector`: PostgreSQL full-text search vector, kept in sync by trigger
- `language`: Programming language of the source file
- `content_type`: Finer classification — `single_line_comment`, `block_comment`, `docstring`, `jsdoc`, etc.

**Source Types:**
- `comment`: Code comments (single-line or block)
- `docstring`: Python docstrings, JSDoc, Javadoc
- `commit_message`: Git commit messages
- `non_code_file`: Content from markdown, YAML, text files, etc.

**Design Notes:**
- Full-text search vector (`content_tsvector`) is managed by a PostgreSQL `BEFORE INSERT OR UPDATE` trigger — not written by the ORM
- The tsvector column is excluded from SQLAlchemy mappings (managed purely by the trigger)
- The check constraint enforces that `commit_message` rows have no `source_file_id`, and all other types must have one
- Comments are deduplicated per-file per-commit (same file at same commit won't have duplicate entries)

---

### 10. dependencies

Stores parsed package dependencies from manifest files (package.json, pyproject.toml, pom.xml, etc.) and lock files (package-lock.json, Gemfile.lock, etc.). Linked to file versions for commit-aware dependency tracking.

```sql
CREATE TABLE dependencies (
    id                      SERIAL PRIMARY KEY,
    file_id                 INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    repository_id           INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,

    -- Package identification
    package_name            TEXT NOT NULL,               -- Package/library name
    version_spec            TEXT,                        -- Version constraint from manifest (e.g., "^2.5.0")
    resolved_version        TEXT,                        -- Exact version from lock file (e.g., "2.5.3")

    -- Classification
    language                VARCHAR(50) NOT NULL,        -- Language ecosystem (python, javascript, java, etc.)
    dependency_type         VARCHAR(50) NOT NULL DEFAULT 'runtime',  -- runtime, dev, optional, build, peer
    is_direct               BOOLEAN NOT NULL DEFAULT TRUE,           -- Direct vs transitive dependency

    -- Dependency tree
    parent_dependency_id    INTEGER REFERENCES dependencies(id) ON DELETE CASCADE,  -- For transitive deps

    -- Source location
    source_line             INTEGER,                     -- Line number in manifest file where dep is declared

    -- Metadata
    extras                  JSONB,                       -- Language-specific metadata
    indexed_at              TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_dependencies_source_line_positive CHECK (source_line IS NULL OR source_line >= 1)
);

CREATE INDEX idx_dependencies_package ON dependencies(package_name, language);
CREATE INDEX idx_dependencies_file ON dependencies(file_id);
CREATE INDEX idx_dependencies_repo ON dependencies(repository_id);
CREATE INDEX idx_dependencies_repo_file_package ON dependencies(repository_id, file_id, package_name);
CREATE INDEX ix_dependencies_parent_dependency_id ON dependencies(parent_dependency_id);
```

**Fields:**
- `file_id`: FK to the manifest/lock file version in `files` table
- `package_name`: Package name (e.g., "react", "fastapi", "spring-boot-starter")
- `version_spec`: Version constraint from manifest (e.g., `^2.5.0`, `>=3.0,<4.0`)
- `resolved_version`: Exact resolved version from lock file (e.g., `2.5.3`)
- `language`: Language ecosystem — `python`, `javascript`, `java`, `csharp`, `go`, `ruby`
- `dependency_type`: Classification — `runtime`, `dev`, `optional`, `build`, `peer`
- `is_direct`: `true` for direct dependencies, `false` for transitive
- `parent_dependency_id`: Self-referencing FK for modeling transitive dependency trees
- `source_line`: Line number in the manifest/lock file where this dependency is declared (for UI navigation)
- `extras`: JSONB for language-specific metadata (e.g., npm peer dependency ranges)

**Supported Manifest/Lock Files:**

| Language | Manifest | Lock File |
|----------|----------|-----------|
| Python | `pyproject.toml`, `setup.py`, `requirements.txt` | — |
| JavaScript/TypeScript | `package.json` | `package-lock.json` |
| Java | `pom.xml`, `build.gradle` | — |
| C# | `*.csproj` | — |
| Go | `go.mod` | `go.sum` |
| Ruby | `Gemfile` | `Gemfile.lock` |

**Design Notes:**
- Content-addressable: dependencies belong to a file version (manifest/lock file), not directly to commits. Commit context provided via `commit_files` junction table.
- Self-referencing FK (`parent_dependency_id`) enables transitive dependency tree modeling.
- Lock files provide `resolved_version`; manifests provide `version_spec`.
- Parsing is handled by language-specific parsers in `adapters/external/dependency_parsers/`.

---

### 11. file_renames

Tracks file renames detected during indexing via `git diff --find-renames`. Each row represents a single rename event in a specific commit — the path changed from `old_path` to `new_path` at that commit.

Used by the browse page (rename banner) and diff viewer to follow files across renames.

```sql
CREATE TABLE file_renames (
    id                  SERIAL PRIMARY KEY,
    repository_id       INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_id           INTEGER NOT NULL REFERENCES commits(id) ON DELETE CASCADE,

    old_path            TEXT NOT NULL,              -- Path before rename
    new_path            TEXT NOT NULL,              -- Path after rename
    similarity          SMALLINT NOT NULL,          -- Git rename similarity score (0-100)

    indexed_at          TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_file_renames_commit_paths UNIQUE(commit_id, old_path, new_path),
    CONSTRAINT ck_file_renames_similarity_range CHECK (similarity >= 0 AND similarity <= 100)
);

CREATE INDEX idx_file_renames_repo      ON file_renames(repository_id);
CREATE INDEX idx_file_renames_commit    ON file_renames(commit_id);
CREATE INDEX idx_file_renames_old_path  ON file_renames(repository_id, old_path);
CREATE INDEX idx_file_renames_new_path  ON file_renames(repository_id, new_path);
```

**Fields:**
- `old_path`: Repository-relative path before the rename (e.g., `src/old_name.py`)
- `new_path`: Repository-relative path after the rename (e.g., `src/new_name.py`)
- `similarity`: Git's rename similarity score (0–100). Git reports a rename when similarity ≥ 50 by default. 100 = identical content, just moved.
- `commit_id`: The commit in which the rename occurred

**Design Notes:**
- Populated by `git diff --find-renames` between consecutive commits during indexing
- The unique constraint is on `(commit_id, old_path, new_path)` — a file can only be renamed once per commit
- Indexed on both `old_path` and `new_path` to support bidirectional lookup (forward and backward time travel)
- Used by the browse page: when a file is not found at a commit, the rename table is queried to show a "this file was at `old_path` in this commit" banner with a clickable link
- Used by the diff viewer: auto-resolves the correct path for each side of the diff when a rename occurred between the two compared commits

**Example:**
```
commit_id=42  old_path="src/utils.py"  new_path="src/helpers.py"  similarity=95
```
Means: in commit 42, `src/utils.py` was renamed to `src/helpers.py` with 95% content similarity.

---

### 12. query_log

Ring-buffer table storing structured HTTP request and MCP tool call logs. Provides an audit trail for both human (browser) and AI assistant (MCP) usage. Capped at `MAX_QUERY_LOG_ENTRIES` (default 10,000) via application-level cleanup on insert.

```sql
CREATE TABLE query_log (
    id              BIGSERIAL PRIMARY KEY,
    logged_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    source          VARCHAR(10) NOT NULL,   -- 'http' | 'mcp'
    tool_or_path    TEXT NOT NULL,          -- MCP tool name or HTTP path
    params          JSONB,                  -- query params / tool args
    repository      TEXT,                  -- extracted repo name if present
    status_code     SMALLINT,              -- HTTP status code (NULL for MCP)
    duration_ms     INTEGER,               -- request duration in milliseconds
    result_count    INTEGER,               -- number of results returned
    session_id      TEXT                   -- future use: correlate a user/AI session
);

CREATE INDEX ix_query_log_logged_at   ON query_log(logged_at);
CREATE INDEX ix_query_log_source      ON query_log(source);
CREATE INDEX ix_query_log_repository  ON query_log(repository);
```

**Fields:**
- `source`: Origin of the request — `http` (browser/API client) or `mcp` (AI assistant tool call)
- `tool_or_path`: For MCP: tool name (e.g., `search_symbols`). For HTTP: request path (e.g., `/api/symbols`)
- `params`: JSONB of query parameters or tool arguments
- `repository`: Repository name extracted from path/params (NULL if not determinable)
- `status_code`: HTTP response status (NULL for MCP calls)
- `duration_ms`: End-to-end request duration
- `result_count`: Number of items returned by the query
- `session_id`: Reserved for future session correlation

**Design Notes:**
- No foreign keys — query_log is a standalone audit table, intentionally decoupled from the rest of the schema
- Ring buffer: application middleware deletes the oldest rows when the count exceeds `MAX_QUERY_LOG_ENTRIES`
- Only `/api/*` paths are logged for HTTP (static assets, health checks excluded)
- MCP tool calls are logged by middleware wrapping the tool handlers in `mcp-server/`
- Controlled by env vars: `LOG_HTTP_REQUESTS` and `LOG_MCP_CALLS` (both default `true`)

**Browsing logs:**
```
GET /api/activity?source=mcp&repository=inxr2&limit=100
```
Returns entries newest-first. Available via the hidden `/activity` page in the UI.

---

## Relationships Diagram

```
repositories (1) ──────< (N) commits
    │                        │
    │                        ├──< branch_commits (junction)
    │                        │
    │                        ├──< file_renames (old_path/new_path per commit)
    │                        │
    │                        └──< commit_files (junction) ──> files
    │                                                           │
    └───────────────────────────────────────────────────< files ┘
                                                           │
                                                           ├──< symbols
                                                           │       │
                                                           │       └──< references (parent_symbol)
                                                           │
                                                           ├──< references (source_file)
                                                           │       │
                                                           │       └──> symbols (target)
                                                           │       └──> repositories (cross-repo)
                                                           │
                                                           ├──< text_contents (source_file)
                                                           │
                                                           └──< dependencies (file)
                                                                    │
                                                                    └──> dependencies (parent, self-ref)

index_status (N) ────> (1) repositories

query_log  (standalone — no foreign keys)
```

---

## Query Patterns & Index Justification

### 1. Find symbol by name in repository
```sql
SELECT * FROM symbols
WHERE repository_id = ? AND name = ?
ORDER BY file_id;
```
**Index:** `idx_symbols_repo_name_file`

### 2. Get all symbols in a file
```sql
SELECT * FROM symbols
WHERE file_id = ?
ORDER BY start_line, start_column;
```
**Index:** `ix_symbols_file_id`

### 3. Find all references to a symbol
```sql
SELECT r.*, f.path
FROM "references" r
JOIN files f ON r.source_file_id = f.id
WHERE r.target_symbol_id = ?;
```
**Index:** `ix_references_target_symbol_id`

### 4. Get file at specific commit
```sql
SELECT f.* FROM files f
JOIN commit_files cf ON cf.file_id = f.id
JOIN commits c ON cf.commit_id = c.id
WHERE f.repository_id = ? AND c.commit_hash = ? AND f.path = ?;
```
**Index:** `uq_file_version`, `ix_commit_files_file_id`

### 5. List commits for a branch
```sql
SELECT c.* FROM commits c
JOIN branch_commits bc ON bc.commit_id = c.id
WHERE bc.repository_id = ? AND bc.branch = ?
ORDER BY c.commit_date DESC;
```
**Indexes:** `ix_branch_commits_branch`, `ix_branch_commits_commit_id`

### 6. Look up rename for a file at a commit (bidirectional)
```sql
-- Forward: file existed at old_path before this commit, find new name
SELECT new_path, similarity FROM file_renames
WHERE repository_id = ? AND commit_id = ? AND old_path = ?;

-- Backward: file exists at new_path after this commit, find old name
SELECT old_path, similarity FROM file_renames
WHERE repository_id = ? AND commit_id = ? AND new_path = ?;
```
**Indexes:** `idx_file_renames_old_path`, `idx_file_renames_new_path`

### 7. Find latest commit for a branch
```sql
SELECT c.* FROM commits c
JOIN branch_commits bc ON bc.commit_id = c.id
WHERE c.repository_id = ?
  AND bc.repository_id = ?
  AND bc.branch = ?
ORDER BY c.commit_date DESC
LIMIT 1;
```
**Index:** `ix_branch_commits_branch`

### 8. Query recent activity log
```sql
SELECT * FROM query_log
WHERE source = 'mcp'
  AND repository = 'inxr2'
ORDER BY logged_at DESC
LIMIT 100;
```
**Indexes:** `ix_query_log_source`, `ix_query_log_repository`, `ix_query_log_logged_at`

---

## Data Volume Estimates

For a medium-sized repository (100k LOC):
- **Files**: ~1,000 files × 100 commits = 100,000 rows
- **Symbols**: ~10,000 symbols per commit × 100 commits = 1,000,000 rows
- **References**: ~50,000 references per commit × 100 commits = 5,000,000 rows
- **Branch Commits**: ~100 commits × 3 branches = 300 rows

**Estimated storage per repository:**
- Files: ~10 MB
- Symbols: ~200 MB
- References: ~800 MB
- Commits: ~1 MB (minimal - no message/author stored)
- **Total per repo: ~1 GB**

For 10 repositories: ~10 GB database size

**query_log storage:** ~180 bytes/row × 10,000 rows (ring buffer cap) = ~2–3 MB total (negligible)

**Observed data (2026-03-08):**
Indexing 12 repos across 17 branches (10 days) produced:
- 123,834 files, 698,121 lines, 55.4% reference resolution
- inxr2 main: 24,159 symbols, 58.0% resolution
- Java master: 11,540 symbols, 60.5% resolution
- Content-hash reuse across branches: 96-100% for feature branches sharing history with main
- Dependencies: 665 packages across 5 manifest files (for inxr2 repo)

---

## Migration History

| Migration | Description |
|-----------|-------------|
| `edc605da5d0a` | Initial schema: repositories, commits, files, symbols, references, index_status |
| `add_time_travel_fields` | Add oldest_indexed_commit to index_status for time-travel range |
| `normalize_branch_commits` | Add branch_commits junction table, remove branch column from commits |
| `remove_redundant_commit_columns` | Remove redundant columns from commits (author, message, etc.) |
| `bc889896e6d7` | Add unique constraint on index_status, drop name_tsvector from symbols |
| `add_text_contents_table` | Add text_contents table for full-text search |
| `content_addressable_file_versions` | Content-addressable file versions: add commit_files junction, remove commit_id from files/symbols/references, make text_contents.commit_id nullable |
| `add_extension_column` | Add extension column to files table |
| `add_file_repo_content_hash_index` | Add (repository_id, content_hash) index on files |
| `add_resolution_performance_indexes` | Add indexes for reference resolution performance |
| `8c8caa7883cc` | Add indexes to foreign key columns |
| `add_dependencies_001` | Add dependencies table for manifest/lock file parsing |
| `add_dep_source_line_001` | Add `source_line` column to dependencies table |
| `9e60343223f9` | Add `last_indexing_duration_seconds` and `last_resolving_duration_seconds` to index_status |
| `add_file_renames_001` | Add file_renames table for tracking renames via `git diff --find-renames` |
| `add_query_log_001` | Add query_log table for HTTP request and MCP tool call activity logging |

---

## Design Decisions

### Why no author/message in commits table?

Author info and commit messages are stored in git and can be queried on-demand. Storing them in the database:
- Duplicates data that git already has
- Increases storage by ~30%
- Requires keeping data in sync with git

Instead, the API hydrates this data from git when needed.

### Why branch_commits junction table?

Git's model allows a commit to exist on multiple branches (e.g., after merging). The junction table:
- Properly represents this relationship
- Avoids storing duplicate commits per branch
- Makes branch filtering queries explicit

### Why `extra_metadata` (JSON not JSONB) in most tables?

Most tables use plain `JSON` (not `JSONB`) for `extra_metadata`. This preserves insertion order and is sufficient for metadata that is read back as-is. The `dependencies.extras` column uses `JSONB` because it needs to support operator queries (e.g., key existence checks). `query_log.params` uses `JSONB` for the same reason — it's actively filtered.

### Why `extra_metadata` in ORM but `metadata` in domain entities?

SQLAlchemy reserves `metadata` as an attribute on its `Base` class. The ORM models use `extra_metadata` as both the Python attribute name and the database column name to avoid this conflict. Domain entities use `metadata` (no conflict there). The mapper layer handles the translation. See `adapters/persistence/mappers.py`.

### Why PostgreSQL-only?

The schema uses PostgreSQL-native features for optimal performance:
- Full-text search with tsvector and GIN indexes
- Native ARRAY and JSONB types
- Tests run against a real PostgreSQL database (`inxr2_test`) for production-accurate behavior

### Why is query_log standalone (no foreign keys)?

Activity logging must never block or fail a real request. Foreign keys would create hard dependencies on repositories existing before a log entry can be written — causing failures on startup or during re-indexing. Using a plain `TEXT` repository name keeps logging decoupled and resilient.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-04 | Claude + User | Initial schema design |
| 2.0 | 2026-01-26 | Claude + User | Normalized branches, removed redundant commit columns, added time-travel support |
| 3.0 | 2026-02-09 | Claude + User | Added text_contents table, expanded symbol kinds (C/Java), updated migration history, added observed data volumes |
| 4.0 | 2026-03-01 | Claude + User | Content-addressable file versions: removed commit_id from files/symbols/references, added commit_files junction table, added extension column, updated indexes, added 5 new migrations |
| 5.0 | 2026-03-08 | Claude + User | Added dependencies table for manifest/lock file parsing (Python, JS/TS, Java, C#, Go, Ruby), updated relationships diagram, added dependency migration |
| 6.0 | 2026-03-15 | Claude + User | Added file_renames table (PR #342), source_line to dependencies, duration columns to index_status, updated relationships diagram, query patterns, and migration history |
| 7.0 | 2026-03-16 | Claude + User | Added query_log table (PR #362); corrected SERIAL/BIGSERIAL types; corrected JSON/JSONB types; fixed index names throughout; documented content_tsvector column and trigger; added check constraint on text_contents; updated design decisions |
