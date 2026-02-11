# INXR2 Database Schema Design

**Version:** 3.0
**Date:** 2026-02-09
**Status:** Implemented

## Overview

This document defines the PostgreSQL database schema for INXR2, a cross-reference code browser. The schema is designed to support:
- Multi-repository indexing
- Temporal code navigation (browse code at any commit)
- Symbol cross-referencing within and across repositories
- Incremental indexing
- Efficient search queries
- Multi-branch support (commits can exist on multiple branches)

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
    config              JSONB,                      -- Repository-specific config
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_repositories_name ON repositories(name);
```

**Fields:**
- `id`: Auto-incrementing primary key
- `name`: Unique identifier for the repository (e.g., "linux-kernel", "django")
- `url`: Local filesystem path to the repository (plain path, not file:// URL)
- `description`: Optional description
- `default_branch`: Default branch to index (usually "main" or "master")
- `config`: JSONB for repository-specific settings
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

Stores minimal git commit metadata. Author info, message, and parent hashes are queried from git on-demand.

```sql
CREATE TABLE commits (
    id                  BIGSERIAL PRIMARY KEY,
    repository_id       INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_hash         CHAR(40) NOT NULL,          -- Full SHA-1 hash
    author_date         TIMESTAMP NOT NULL,         -- When authored
    commit_date         TIMESTAMP NOT NULL,         -- When committed
    indexed_at          TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_repo_commit_hash UNIQUE(repository_id, commit_hash)
);

CREATE INDEX idx_commits_hash ON commits(commit_hash);
CREATE INDEX idx_commits_repo_date ON commits(repository_id, commit_date DESC);
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
    id                  BIGSERIAL PRIMARY KEY,
    repository_id       INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    branch              VARCHAR(255) NOT NULL,
    commit_id           BIGINT NOT NULL REFERENCES commits(id) ON DELETE CASCADE,

    CONSTRAINT uq_branch_commit UNIQUE(repository_id, branch, commit_id)
);

CREATE INDEX idx_branch_commits_branch ON branch_commits(branch);
CREATE INDEX idx_branch_commits_commit ON branch_commits(commit_id);
CREATE INDEX idx_branch_commits_repo_branch ON branch_commits(repository_id, branch);
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

### 5. symbols

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

-- Full-text search index (PostgreSQL only)
CREATE INDEX idx_symbols_name_fts ON symbols USING GIN(name_tsvector);
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
- `metadata`: JSONB for language-specific attributes

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

---

### 6. references

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

---

### 7. index_status

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

    -- Error tracking
    error_message           TEXT,
    error_count             INTEGER DEFAULT 0,

    -- Metadata
    indexer_version         VARCHAR(50),            -- Version of indexer that ran
    extra_metadata          JSONB,

    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT index_status_unique_repo_branch UNIQUE(repository_id, branch)
);

CREATE INDEX idx_index_status_repo ON index_status(repository_id);
CREATE INDEX idx_index_status_status ON index_status(indexing_status);
```

**Fields:**
- `last_indexed_commit`: SHA-1 of most recent fully indexed commit
- `oldest_indexed_commit`: SHA-1 of oldest indexed commit (defines time-travel range)
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

### 8. text_contents

Stores searchable text extracted from code comments, docstrings, commit messages, and non-code files (markdown, YAML, etc.) for full-text search.

```sql
CREATE TABLE text_contents (
    id                  BIGSERIAL PRIMARY KEY,
    repository_id       INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_id           BIGINT NOT NULL REFERENCES commits(id) ON DELETE CASCADE,

    -- Source information
    source_type         VARCHAR(50) NOT NULL,       -- comment, docstring, commit_message, non_code_file
    source_file_id      BIGINT REFERENCES files(id) ON DELETE CASCADE,  -- NULL for commit messages
    source_line         INTEGER,                    -- Start line in source file
    source_end_line     INTEGER,                    -- End line in source file

    -- Searchable content
    content             TEXT NOT NULL,               -- Extracted text (stripped of comment markers)

    -- Full-text search vector (PostgreSQL only, managed by triggers)
    -- content_tsvector tsvector,

    -- Metadata
    language            VARCHAR(50),                -- Language of source file (NULL for commit messages)
    content_type        VARCHAR(50),                -- single_line_comment, block_comment, docstring, etc.

    indexed_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_text_contents_source_type ON text_contents(source_type);
CREATE INDEX idx_text_contents_source_file ON text_contents(source_file_id);
CREATE INDEX idx_text_contents_language ON text_contents(language);
-- CREATE INDEX idx_text_contents_fts ON text_contents USING GIN(content_tsvector);  -- PostgreSQL only
```

**Fields:**
- `source_type`: What kind of text this is — `comment`, `docstring`, `commit_message`, or `non_code_file`
- `source_file_id`: FK to files table (NULL for commit messages which have no source file)
- `source_line/source_end_line`: Location in source file (for comments/docstrings)
- `content`: The extracted text, stripped of comment markers (e.g., `#`, `//`, `/* */`)
- `language`: Programming language of the source file
- `content_type`: Finer classification — `single_line_comment`, `block_comment`, `docstring`, `jsdoc`, etc.

**Source Types:**
- `comment`: Code comments (single-line or block)
- `docstring`: Python docstrings, JSDoc, Javadoc
- `commit_message`: Git commit messages
- `non_code_file`: Content from markdown, YAML, text files, etc.

**Design Notes:**
- Full-text search vector (`content_tsvector`) is managed by PostgreSQL triggers, not the ORM
- The tsvector column is excluded from SQLAlchemy mappings (managed by triggers)
- Comments are deduplicated per-file per-commit (same file at same commit won't have duplicate entries)

---

## Relationships Diagram

```
repositories (1) ──────< (N) commits
    │                        │
    │                        ├──< branch_commits (junction)
    │                        │
    │                        ├──< text_contents
    │                        │
    └────────────────< files ┘
                        │
                        ├──< text_contents (source_file)
                        │
                    symbols
                      │  │
                      │  └───< references (self-ref for parent)
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

### 5. List commits for a branch
```sql
SELECT c.* FROM commits c
JOIN branch_commits bc ON bc.commit_id = c.id
WHERE bc.repository_id = ? AND bc.branch = ?
ORDER BY c.commit_date DESC;
```
**Indexes:** `idx_branch_commits_repo_branch`, `idx_commits_repo_date`

### 6. Find latest commit for a branch
```sql
SELECT c.* FROM commits c
JOIN branch_commits bc ON bc.commit_id = c.id
WHERE c.repository_id = ?
  AND bc.repository_id = ?
  AND bc.branch = ?
ORDER BY c.commit_date DESC
LIMIT 1;
```
**Indexes:** `idx_branch_commits_repo_branch`

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

**Observed data (2026-02-09):**
Indexing 7 repos across 14 branches produced:
- inxr2 main (196 commits, 322 files): 36K symbols, 177K references, 64K resolved (36%)
- Java master (1,000 commits, 1,559 files): 26K symbols, 186K references, 104K resolved (56%)
- Content-hash reuse across branches: 96-100% for feature branches sharing history with main

---

## Migration History

| Migration | Description |
|-----------|-------------|
| `edc605da5d0a` | Initial schema: repositories, commits, files, symbols, references, index_status |
| `add_time_travel_001` | Add oldest_indexed_commit to index_status for time-travel range |
| `normalize_branch_001` | Add branch_commits junction table, remove branch column from commits |
| `remove_redundant_commit_001` | Remove redundant columns from commits (author, message, etc.) |
| `bc889896e6d7` | Add unique constraint and cleanup orphaned schema artifacts |
| `add_text_contents_001` | Add text_contents table for full-text search |

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

### Why `extra_metadata` in ORM but `metadata` in SQL?

SQLAlchemy reserves `metadata` as an attribute on its `Base` class. The ORM models use `extra_metadata` as the Python attribute name, mapped to the `metadata` column in the database. Domain entities use `metadata` (no conflict). The mapper layer handles the translation. See `adapters/persistence/mappers.py`.

### Why PostgreSQL-only?

The schema uses PostgreSQL-native features for optimal performance:
- Full-text search with tsvector and GIN indexes
- Native ARRAY and JSONB types
- Tests run against a real PostgreSQL database (`inxr2_test`) for production-accurate behavior

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-04 | Claude + User | Initial schema design |
| 2.0 | 2026-01-26 | Claude + User | Normalized branches, removed redundant commit columns, added time-travel support |
| 3.0 | 2026-02-09 | Claude + User | Added text_contents table, expanded symbol kinds (C/Java), updated migration history, added observed data volumes |
