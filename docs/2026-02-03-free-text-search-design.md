# Free Text Search - Design Document

**Version:** 1.0
**Date:** 2026-02-03
**Status:** Planned

## Overview

This document describes the design for adding free text search to INXR2, enabling users to search across code comments, docstrings, commit messages, and non-code files (markdown, YAML, etc.).

## Goals

1. **Searchable content**: Comments, docstrings, commit messages, non-code files
2. **Efficient storage**: Store only extracted text, not raw file lines (content retrieved from git on demand)
3. **Line-level navigation**: Click a result → jump to exact line in code browser
4. **Integrated indexing**: Runs alongside existing symbol/reference indexing (not separate)
5. **Configurable**: Global enable/disable via config
6. **Database agnostic**: PostgreSQL tsvector now, with path to SQLite FTS5 later
7. **Branch/version aware**: Search scoped to specific branch and/or commit (like symbol search)

## Migration Note

No data migration is required. After schema changes, a full re-index from scratch will populate the new table.

## Non-Goals (v1)

- Full fuzzy matching / typo tolerance (basic prefix matching OK)
- Semantic search / synonyms
- Cross-repository search (future enhancement)
- Search analytics

---

## Search Capabilities

### Query Modes

| Mode | Syntax | Example | Implementation |
|------|--------|---------|----------------|
| **Keyword** | Plain text | `TODO refactor` | PostgreSQL `to_tsquery` |
| **Phrase** | Quoted string | `"fix bug"` | PostgreSQL phrase search |
| **Regex** | `/pattern/` | `/TODO:?\s+\w+/` | PostgreSQL `~` operator (bypasses tsvector) |

### Scope Filters

| Filter | Description | Example |
|--------|-------------|---------|
| **Repository** | Limit to specific repo | `repo:inxr2` |
| **Branch** | Limit to specific branch | `branch:main` |
| **Commit** | Search at specific version | `commit:abc1234` |
| **File type** | Filter by extension | `type:py,ts` |
| **Source type** | Filter by content source | `source:comment,docstring` |

### Example Queries

```
# Simple keyword search on main branch
TODO                          branch:main

# Phrase search in Python files
"database connection"         type:py

# Regex search for TODO patterns
/TODO:?\s+\w+/                type:py,ts

# Search docstrings only
authentication                source:docstring
```

---

## Architecture

### High-Level Data Flow

```
INDEXING:
  Git Commit → Files → Parse (Tree-sitter or Plaintext)
                     → Extract comments/docstrings/content
                     → Save to text_contents table (searchable text only)

SEARCHING:
  User Query → SearchTextUseCase → Port Interface → PostgreSQL/SQLite
            → Return matches with file/line info
            → Frontend fetches actual line content from git for display
            → Click result → Navigate to code browser
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Store extracted text only, not file lines | 10-100x smaller DB, git has authoritative content |
| PostgreSQL tsvector (with FTS5 path) | No new infrastructure, good enough for millions of docs |
| Abstract behind port interface | Future SQLite FTS5 support without rewrite |
| Integrated with existing indexing | Single process, transactional consistency |
| Config kill switch | Users can disable if storage/performance is concern |

---

## Database Schema

### New Table: `text_contents`

```sql
CREATE TABLE text_contents (
    id                  BIGSERIAL PRIMARY KEY,
    repository_id       INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_id           BIGINT NOT NULL REFERENCES commits(id) ON DELETE CASCADE,

    -- Source information
    source_type         VARCHAR(50) NOT NULL,   -- 'comment', 'docstring', 'commit_message', 'file_content'
    source_file_id      BIGINT REFERENCES files(id) ON DELETE CASCADE,  -- NULL for commit messages
    source_line         INTEGER,                -- Start line for navigation
    source_end_line     INTEGER,                -- End line (for multi-line content)

    -- Searchable content (extracted text, NOT raw file content)
    content             TEXT NOT NULL,
    content_tsvector    TSVECTOR,               -- PostgreSQL full-text search vector

    -- Metadata
    language            VARCHAR(50),            -- python, typescript, markdown, yaml, etc.
    content_type        VARCHAR(50),            -- inline_comment, block_comment, docstring, etc.

    indexed_at          TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Constraint: commit messages don't have file/line info
    CONSTRAINT text_contents_valid_source CHECK (
        (source_type = 'commit_message' AND source_file_id IS NULL) OR
        (source_type != 'commit_message' AND source_file_id IS NOT NULL)
    )
);

-- Performance indexes
CREATE INDEX idx_text_contents_repo_commit ON text_contents(repository_id, commit_id);
CREATE INDEX idx_text_contents_source_file ON text_contents(source_file_id);
CREATE INDEX idx_text_contents_source_type ON text_contents(source_type);
CREATE INDEX idx_text_contents_language ON text_contents(language);

-- Full-text search index (PostgreSQL GIN)
CREATE INDEX idx_text_contents_fts ON text_contents USING GIN(content_tsvector);

-- Auto-update tsvector on insert/update
CREATE TRIGGER text_contents_tsvector_update
BEFORE INSERT OR UPDATE ON text_contents
FOR EACH ROW EXECUTE FUNCTION
  tsvector_update_trigger(content_tsvector, 'pg_catalog.english', content);
```

### SQLite FTS5 Alternative (Future)

```sql
-- Main table (same structure, minus tsvector)
CREATE TABLE text_contents (...);

-- FTS5 virtual table
CREATE VIRTUAL TABLE text_contents_fts USING fts5(
    content,
    content='text_contents',
    content_rowid='id'
);

-- Sync triggers for insert/update/delete
```

---

## What Gets Indexed

| Source Type | Content Stored | Example |
|-------------|----------------|---------|
| `comment` | Inline/block comments | `# TODO: refactor this` |
| `docstring` | Function/class docstrings | `"""Calculate the total..."""` |
| `commit_message` | Git commit messages | `fix: resolve null pointer in parser` |
| `file_content` | Non-code file paragraphs | Markdown sections, YAML values |

### What Does NOT Get Indexed

- Raw source code lines (retrieved from git on demand)
- Language keywords like `if`, `for`, `int`, `bool`
- Binary files
- Files matching exclude patterns (e.g., `*.min.js`, `*.lock`)

---

## Backend Components

### Domain Layer

**New Entity**: `src/inxr2/domain/entities/text_content.py`

```python
@dataclass
class TextContent:
    id: int | None
    repository_id: int
    commit_id: int
    source_type: str          # 'comment', 'docstring', 'commit_message', 'file_content'
    source_file_id: int | None
    source_line: int | None
    source_end_line: int | None
    content: str
    language: str | None
    content_type: str | None  # 'inline_comment', 'block_comment', 'markdown', etc.
    indexed_at: datetime | None = None
```

**New Value Object**: `src/inxr2/domain/value_objects/text_search_source_type.py`

```python
class TextSearchSourceType(str, Enum):
    COMMENT = "comment"
    DOCSTRING = "docstring"
    COMMIT_MESSAGE = "commit_message"
    FILE_CONTENT = "file_content"
```

### Application Layer

**New Port**: `src/inxr2/application/ports/repositories/text_content_repository.py`

```python
class TextContentRepositoryPort(ABC):
    @abstractmethod
    async def save(self, text_content: TextContent) -> TextContent: ...

    @abstractmethod
    async def save_batch(self, text_contents: list[TextContent]) -> list[TextContent]: ...

    @abstractmethod
    async def delete_by_commit(self, commit_id: int) -> int: ...

    @abstractmethod
    async def delete_by_file(self, file_id: int) -> int: ...
```

**New Port**: `src/inxr2/application/ports/services/text_search_port.py`

This is the key abstraction for database-agnostic search:

```python
@dataclass
class TextSearchResult:
    text_content: TextContent
    rank: float               # Relevance score
    headline: str | None      # Highlighted snippet (optional)

class QueryMode(str, Enum):
    KEYWORD = "keyword"    # Default: uses tsvector full-text search
    PHRASE = "phrase"      # Exact phrase match
    REGEX = "regex"        # PostgreSQL regex (~), bypasses tsvector

@dataclass
class TextSearchQuery:
    query: str
    mode: QueryMode = QueryMode.KEYWORD
    repository_id: int | None = None
    branch: str | None = None           # Filter by branch (uses branch_commits table)
    commit_id: int | None = None        # Filter by specific commit
    source_types: list[str] | None = None
    languages: list[str] | None = None  # File types mapped to languages
    limit: int = 20
    offset: int = 0

class TextSearchPort(ABC):
    """
    Abstract interface for full-text search.
    Implementations: PostgreSQL tsvector, SQLite FTS5
    """

    @abstractmethod
    async def search(self, query: TextSearchQuery) -> tuple[list[TextSearchResult], int]:
        """
        Execute full-text search.
        Returns: (results, total_count)
        """
        pass
```

**New Use Case**: `src/inxr2/application/use_cases/search/search_text_use_case.py`

```python
class SearchTextUseCase:
    def __init__(
        self,
        text_search: TextSearchPort,
        file_repository: FileRepositoryPort,
        repository_repository: RepositoryPort,
        commit_repository: CommitRepositoryPort,
        git_service: GitServicePort,
    ):
        ...

    async def execute(self, request: SearchTextRequest) -> SearchTextResponse:
        # 1. Search via port
        results, total = await self._text_search.search(...)

        # 2. Hydrate with file/repo/commit info
        # 3. Fetch actual line content from git for display
        # 4. Return enriched results
```

### Adapters Layer

**PostgreSQL Implementation**: `src/inxr2/adapters/persistence/repositories/postgres_text_search.py`

```python
class PostgresTextSearch(TextSearchPort):
    async def search(self, query: TextSearchQuery) -> tuple[list[TextSearchResult], int]:
        # Build tsquery from user input
        # Execute: WHERE content_tsvector @@ to_tsquery(...)
        # Order by ts_rank()
        # Use ts_headline() for snippets
```

**SQLite Implementation (Future)**: `src/inxr2/adapters/persistence/repositories/sqlite_text_search.py`

```python
class SqliteTextSearch(TextSearchPort):
    async def search(self, query: TextSearchQuery) -> tuple[list[TextSearchResult], int]:
        # Execute: WHERE text_contents_fts MATCH ...
        # Order by bm25()
        # Use snippet() for highlights
```

**Comment Extraction**: Modify existing Tree-sitter parsers

Each parser (`python_parser.py`, `typescript_parser.py`, etc.) gains a method:

```python
def extract_comments(self, root: Node, content: str) -> list[dict]:
    """Extract comments and docstrings from AST."""
    # Walk AST, find comment nodes
    # Return list of {content, content_type, source_line, source_end_line}
```

**Non-Code File Parser**: `src/inxr2/adapters/external/plaintext_parser.py`

```python
class PlaintextParser:
    SUPPORTED_EXTENSIONS = {'.md', '.markdown', '.txt', '.yaml', '.yml', '.toml', 'Dockerfile'}

    def parse(self, content: str, file_path: str) -> list[dict]:
        # Split into searchable chunks (paragraphs for markdown, etc.)
        # Return list of {content, content_type, source_line, source_end_line}
```

### API Layer

**New Endpoint**: `GET /api/search/text`

```
Query Parameters:
  q           (required)  Search query string
  mode        (optional)  Query mode: keyword (default), phrase, regex
  repo        (optional)  Repository ID filter
  branch      (optional)  Branch name filter (e.g., "main")
  commit      (optional)  Specific commit hash filter
  file_types  (optional)  File extensions: py, ts, md
  source_types(optional)  comment, docstring, commit_message, file_content
  limit       (optional)  Results per page (default 20, max 100)
  offset      (optional)  Pagination offset

Response:
{
  "results": [
    {
      "id": 123,
      "repository_name": "inxr2",
      "branch": "main",
      "file_path": "src/main.py",
      "source_line": 42,
      "source_type": "comment",
      "content": "TODO: refactor this function",
      "snippet": "...the <b>TODO</b>: refactor this...",
      "commit_hash": "abc1234",
      "line_content": "    # TODO: refactor this function"  // Fetched from git
    }
  ],
  "total": 156,
  "query": "TODO",
  "mode": "keyword",
  "limit": 20,
  "offset": 0
}
```

---

## Frontend Components

### Navigation Structure

The frontend will have **3 main tabs**:

| Tab | Purpose | Status |
|-----|---------|--------|
| **Browse** | Code browser with symbol navigation, file tree, syntax highlighting | Existing |
| **Search** | Free text search across comments, docstrings, commit messages, non-code files | To be added |
| **History** | Git commit history browser (TBD) | Future |

### Search Tab (New)

Location: `frontend/src/pages/TextSearch.tsx`

- Search input with debounce
- Query mode selector (keyword, phrase, regex)
- Filter dropdowns: file type, source type, branch
- Results list showing:
  - Source type badge (comment, docstring, etc.)
  - File path and line number
  - Snippet with highlighted matches
  - Actual line content (fetched from git)
- Pagination (20 results per page)
- Click result → navigate to `/browse/{repo}/{path}?line={n}&commit={hash}`

### History Tab (Future)

Location: `frontend/src/pages/History.tsx`

- Git commit history timeline
- Commit details (message, author, date, files changed)
- Navigate to code at any commit
- Diff viewer between commits
- Branch filtering
- Search within commit messages (integrates with text search)

*Note: History tab design to be defined in a separate document.*

### API Client

Add `searchText()` function to `frontend/src/lib/api.ts`.

---

## Configuration

Add to `config.yaml`:

```yaml
indexing:
  # ... existing fields ...

  text_search:
    enabled: true                    # Global enable/disable

    # What to index
    index_comments: true
    index_docstrings: true
    index_commit_messages: true
    index_non_code_files: true

    # Non-code file extensions to index
    non_code_extensions:
      - .md
      - .markdown
      - .rst
      - .txt
      - .yaml
      - .yml
      - .toml
      - Dockerfile

    # Exclude patterns (in addition to global excludes)
    exclude_patterns:
      - "*.min.js"
      - "*.min.css"
      - "*.lock"
      - "package-lock.json"

    # Limits
    max_content_length: 10000        # Skip content longer than this (chars)
```

Add Pydantic model for validation in `src/inxr2/infrastructure/config/`.

---

## Implementation Plan

### Phase 1: Foundation
**Goal**: Database schema and core abstractions

- [ ] Create Alembic migration for `text_contents` table
- [ ] Create `TextContent` domain entity
- [ ] Create `TextSearchSourceType` value object
- [ ] Create `TextContentRepositoryPort` interface
- [ ] Create `TextSearchPort` interface (the key abstraction)
- [ ] Create `PostgresTextContentRepository` implementation
- [ ] Create `PostgresTextSearch` implementation
- [ ] Create ORM model and mapper
- [ ] Add configuration schema for `text_search` section
- [ ] Unit tests for all new components

**Deliverables**: Can save and search text contents via ports

### Phase 2: Comment Extraction
**Goal**: Extract comments during indexing

- [ ] Add `extract_comments()` to Python parser
- [ ] Add `extract_comments()` to TypeScript/JavaScript parser
- [ ] Add `extract_comments()` to Java parser (if exists)
- [ ] Add `extract_comments()` to C parser (if exists)
- [ ] Update parser service to return comments alongside symbols
- [ ] Integrate with indexing orchestrator
- [ ] Tests for comment extraction

**Deliverables**: Comments extracted and saved during indexing

### Phase 3: Non-Code Files & Commit Messages
**Goal**: Index markdown, YAML, and commit messages

- [ ] Create `PlaintextParser` for non-code files
- [ ] Integrate plaintext parsing into indexing orchestrator
- [ ] Add commit message indexing to orchestrator
- [ ] Tests for non-code file parsing

**Deliverables**: All content types indexed

### Phase 4: Search Use Case & API
**Goal**: Backend search functionality complete

- [ ] Create `SearchTextUseCase`
- [ ] Add git content fetching for result display
- [ ] Create API endpoint `GET /api/search/text`
- [ ] Integration tests for search

**Deliverables**: Search API working end-to-end

### Phase 5: Frontend
**Goal**: User-facing search UI

- [ ] Create `TextSearch.tsx` page component
- [ ] Add API client function `searchText()`
- [ ] Add navigation tab
- [ ] Implement result click → code browser navigation
- [ ] Add filters (file type, source type)
- [ ] Add pagination
- [ ] Frontend tests

**Deliverables**: Complete user-facing feature

### Phase 6: Polish
**Goal**: Production-ready quality

- [ ] Performance testing with large repositories
- [ ] Add `ts_headline()` for highlighted snippets
- [ ] Query optimization
- [ ] Documentation updates
- [ ] End-to-end testing

**Deliverables**: Feature ready for release

---

## Future Enhancements

1. **SQLite FTS5 support**: Implement `SqliteTextSearch` adapter
2. **Cross-repository search**: Search across all repos, not just one
3. **Advanced query syntax**: Phrase search (`"exact phrase"`), OR queries
4. **Fuzzy matching**: Typo tolerance (would likely need Elasticsearch)
5. **Search suggestions**: "Did you mean..." based on popular queries

---

## Testing Strategy

### Unit Tests
- `TextContent` entity validation
- `PostgresTextSearch.search()` query building
- Comment extraction for each language
- `PlaintextParser` for various file types
- Configuration validation

### Integration Tests
- End-to-end indexing with text search enabled
- API endpoint with various query/filter combinations
- Search result hydration (git content fetching)

### Test Data
- Create test fixtures with:
  - Python files with inline comments, block comments, docstrings
  - TypeScript files with JSDoc comments
  - Markdown documentation
  - YAML config files
  - Sample commit messages

---

## Performance Considerations

### Database
- GIN index on `content_tsvector` is essential (10-100x faster than sequential scan)
- Batch inserts during indexing (100-500 records per batch)
- Consider partial indexes if searching mostly HEAD commits

### Query Optimization
```sql
-- Use ts_rank for relevance, ts_headline for snippets
SELECT
    tc.*,
    ts_rank(tc.content_tsvector, query) AS rank,
    ts_headline('english', tc.content, query, 'MaxWords=35, MinWords=15') AS headline
FROM text_contents tc,
     to_tsquery('english', 'refactor & TODO') query
WHERE tc.content_tsvector @@ query
  AND tc.repository_id = $1
ORDER BY rank DESC
LIMIT 20;
```

### Indexing Performance
- Comment extraction adds ~10-20% overhead to file parsing
- Batch database inserts mitigate this
- Incremental indexing only processes changed files

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-03 | Claude + User | Initial design |
