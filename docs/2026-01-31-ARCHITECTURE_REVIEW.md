# INXR2 Architectural Review

**Date:** 2026-01-31
**Scope:** Post-C/Java language support, pre-optimization phase
**Context:** Preparing for faster indexing, free text search, and potential SQLite migration

---

## TL;DR

**Overall Grade: B+ (Good with room for focused improvements)**

### Key Strengths
- **Excellent Clean Architecture**: Zero framework leakage in domain layer, proper port/adapter pattern
- **Strong Testing Philosophy**: Only 6 mock usages across entire test suite (95% fakes)
- **Good Multi-Language Support**: Tree-sitter parsers well-structured with 600-1000 LOC test coverage each
- **SQLite Migration Ready**: Architecture is 9/10 ready due to port/adapter pattern

### Critical Issues to Address

| ID | Issue | Impact | Effort |
|----|-------|--------|--------|
| **C1** | Monolithic `index_command.py` (1,489 lines) | Blocks parallel indexing | 2 days |
| **C2** | No abstraction for indexing orchestration | Limits testability, can't swap strategies | 1 day |

### Recommended Refactoring Before New Features

**Phase 1 - Quick Wins (1 day)**:
- Remove legacy search use case with TODOs
- Fix datetime.utcnow() deprecations
- Add pagination support
- Centralize language list

**Phase 2 - Architectural (4 days)**:
- Extract `IndexingOrchestrator` to application layer
- Deduplicate full/incremental indexing logic
- Extract content-hash optimization to reusable use case

**Total: ~5 days of prep work before new features**

### Impact on Planned Features

| Feature | Readiness | Blockers |
|---------|-----------|----------|
| **Faster Indexing** | 6/10 | C1 blocks parallelization |
| **Free Text Search** | 8/10 | Just needs new port + migration |
| **SQLite Migration** | 9/10 | Already well-architected |

### Key Recommendation

The **monolithic index_command.py** is the highest-leverage fix. Refactoring it will:
1. Unblock parallel file processing (3-4x speedup potential)
2. Enable testing indexing logic without CLI infrastructure
3. Allow webhook/API-triggered indexing in the future
4. Reduce duplication between full and incremental indexing

---

## Executive Summary

The INXR2 codebase demonstrates **strong adherence to Clean Architecture principles** with well-defined layer boundaries and excellent separation of concerns. The project has grown to 32,060 LOC of production Python code with 56 test files achieving good coverage. The architecture is fundamentally sound and well-positioned for the planned features (faster indexing, free text search, SQLite migration). However, there are several areas where **complexity has accumulated** in critical paths, particularly the 1,489-line indexing command module, creating maintenance and extensibility challenges.

**Overall Grade: B+ (Good with room for focused improvements)**

---

## Part 1: Current Architectural State Assessment

### Strengths

**1. Excellent Clean Architecture Implementation**
- **Zero framework leakage in domain layer**: No FastAPI or SQLAlchemy imports detected in `src/inxr2/domain/`
- **Proper port/adapter pattern**: 21 use cases properly depend on abstract ports, not concrete implementations
- **Well-structured mappers**: Bidirectional conversion between domain entities and ORM models is clean and consistent
- **Domain validation**: Entities validate themselves (e.g., `Symbol.__post_init__` validates line/column ranges)

**2. Testing Philosophy Alignment**
- **Minimal mock usage**: Only 6 instances of `unittest.mock` across entire test suite
- **Rich fake implementations**: 2 major fake repository classes (plus inline fakes in test files)
- **1,418-line test doubles module**: Comprehensive, reusable test infrastructure
- **Integration test coverage**: 961-line repository adapter test suite verifies real database behavior

**3. Strong Multi-Language Support**
- **Tree-sitter parsers**: Python, TypeScript, JavaScript, C, Java all with dedicated parsers
- **Extensible design**: `BaseLanguageParser` abstraction makes adding languages straightforward
- **Comprehensive tests**: Each parser has 600-1,000 lines of test coverage

**4. Temporal Data Model**
- All entities (files, symbols, references) tied to specific commits
- Enables time-travel features
- Content-hash optimization for unchanged files between commits

### Architectural Concerns

**1. Domain Layer Purity**

The domain layer is framework-agnostic with one minor inconsistency:

**Finding: `re` module imported in domain entity**
- **Location**: `src/inxr2/domain/entities/repository.py:42-48`
- **Issue**: Uses regex for name validation inside `Repository.__post_init__`
- **Severity**: Low (stdlib is acceptable, but consider value object)
- **Recommendation**: Extract validation to a value object or domain service for better testability

**2. Adapter Layer Complexity**

**Finding: Monolithic indexing command (1,489 lines)**
- **Location**: `src/inxr2/adapters/cli/commands/index_command.py`
- **Severity**: High
- **Issue**: Single file handles:
  - Full indexing workflow
  - Incremental indexing workflow
  - Database reset
  - Progress reporting
  - Signal handling
  - Configuration parsing
  - Content-hash reuse optimization
  - Commit traversal
  - File parsing
  - Symbol/reference extraction
  - Reference resolution

**Symptoms**:
- Difficult to test individual indexing steps in isolation
- Hard to add new indexing strategies (e.g., parallel processing)
- Mixing infrastructure concerns (signal handling, progress bars) with business logic
- Duplicated logic between full and incremental indexing

**Finding: Large language parsers**
- Java parser: 1,066 lines
- C parser: 879 lines
- Python parser: 601 lines

**Analysis**: Parser size is justifiable given:
- Comprehensive symbol extraction (classes, methods, fields, enums, etc.)
- Reference detection (imports, calls, type annotations)
- Builtin filtering (JAVA_BUILTINS, PYTHON_BUILTINS have 100+ entries each)
- Scope tracking for nested symbols

These are **not architectural violations** but indicate opportunity for shared utilities.

**3. Port Abstraction Completeness**

**Finding: Missing port for indexing orchestration**
- **Current state**: CLI command directly orchestrates indexing workflow
- **Issue**: Cannot swap indexing strategies without modifying CLI adapter
- **Impact**: Limits testability and prevents alternative indexing implementations

**Finding: Repository port interface well-sized (538 lines)**
- **Location**: `src/inxr2/application/ports/repositories.py`
- **Analysis**: Contains 6 port interfaces (Repository, Commit, File, Symbol, Reference, IndexStatus)
- **Verdict**: Acceptable - well-organized with clear responsibilities

**4. Use Case Organization**

**Finding: 21 use case files with good organization**
```
application/use_cases/
├── commits/ (1 use case)
├── files/ (3 use cases)
├── indexing/ (3 use cases)
├── repositories/ (5 use cases)
└── symbols/ (2 use cases)
```

**Strengths**:
- Clear feature-based organization
- Single responsibility per use case
- Proper dependency injection

**Weakness**:
- Some use cases are thin wrappers around repository calls
- Example: `ListRepositoriesUseCase` is essentially `repository_repo.list_all()`

**5. Database Schema Observations**

Recent migrations indicate active evolution:
- `remove_redundant_commit_columns.py` - Good: cleaning up technical debt
- `add_time_travel_fields.py` - Good: supporting planned features
- `normalize_branch_commits.py` - Good: proper many-to-many relationship

**Positive signals**: Schema is being actively refined based on lessons learned.

---

## Part 2: Findings Matrix

### Critical Issues (Red)

| ID | Issue | Location | Impact | Effort |
|----|-------|----------|--------|--------|
| **C1** | Monolithic indexing command violates SRP | `index_command.py` (1,489 LOC) | Blocks parallelization, hard to test, maintenance burden | L |
| **C2** | No abstraction for indexing orchestration | CLI directly runs indexing | Cannot swap strategies, limits testability | M |

### High Priority (Orange)

| ID | Issue | Location | Impact | Effort |
|----|-------|----------|--------|--------|
| **H1** | Content-hash reuse logic embedded in CLI | `index_command.py:800-900` | Optimization not available to other indexing paths | M |
| **H2** | Duplicate code between full/incremental indexing | `index_command.py` | Maintenance burden, risk of divergence | M |
| **H3** | No pagination strategy for large result sets | Symbol/reference queries | Performance issues at scale | S |
| **H4** | Missing database connection pooling config | `database/connection.py` | Suboptimal performance under load | S |

### Medium Priority (Yellow)

| ID | Issue | Location | Impact | Effort |
|----|-------|----------|--------|--------|
| **M1** | Thin use case wrappers | Various use cases | Questionable value, boilerplate | S |
| **M2** | Parser code duplication | Language parsers | Harder to maintain, inconsistencies | M |
| **M3** | TODOs in legacy search use case | `application/use_cases/search_symbols.py` | Confusing - appears to be superseded | XS |
| **M4** | Hard-coded language list duplication | Multiple files | Single source of truth missing | XS |
| **M5** | No centralized error handling strategy | Scattered try/except blocks | Inconsistent error messages | M |

### Low Priority (Green)

| ID | Issue | Location | Impact | Effort |
|----|-------|----------|--------|--------|
| **L1** | Regex import in domain entity | `repository.py:42` | Minor purity violation | XS |
| **L2** | datetime.utcnow() usage | Mappers | Deprecated (use datetime.now(UTC)) | XS |
| **L3** | Some ORM relationships not typed correctly | Model files | Type safety | XS |

---

## Part 3: Detailed Recommendations

### C1: Monolithic Indexing Command

**Current Architecture**:
```
index_command.py (1,489 lines)
├── Full indexing workflow
├── Incremental indexing workflow
├── Database operations
├── Git operations
├── Progress UI
└── Signal handling
```

**Recommended Refactoring**:

```python
# New structure in application/use_cases/indexing/

class IndexingOrchestrator:
    """Orchestrates indexing workflow (Application Layer)."""
    def __init__(
        self,
        commit_walker: CommitWalkerPort,
        file_indexer: FileIndexerPort,
        symbol_extractor: SymbolExtractionPort,
        reference_resolver: ReferenceResolutionPort,
        progress_reporter: ProgressReporterPort,
    ):
        ...

    async def index_repository(
        self,
        request: IndexRepositoryRequest
    ) -> IndexRepositoryResponse:
        """Main indexing workflow."""
        # Clean orchestration logic without infrastructure concerns
        ...

# Separate strategies
class FullIndexingStrategy(IndexingStrategyPort):
    """Full repository indexing strategy."""
    ...

class IncrementalIndexingStrategy(IndexingStrategyPort):
    """Delta-based incremental indexing."""
    ...

class ParallelFileIndexingStrategy(IndexingStrategyPort):
    """Parallel file processing (future optimization)."""
    ...

# CLI becomes thin adapter
@click.command()
def index(...):
    """Index command - thin adapter layer."""
    orchestrator = build_indexing_orchestrator(strategy=strategy_type)
    progress = RichProgressReporter(console)  # Adapter
    result = await orchestrator.index_repository(request)
    progress.display_results(result)
```

**Benefits**:
1. **Testability**: Test orchestrator without CLI infrastructure
2. **Extensibility**: Swap strategies (parallel, distributed, etc.)
3. **Maintainability**: Each component has single responsibility
4. **Reusability**: Orchestrator can be used by webhook triggers, admin UI, etc.

**Migration Path**:
1. Extract `IndexingOrchestrator` to application layer (keep existing CLI working)
2. Move business logic from CLI to orchestrator (one step at a time)
3. Create strategy abstractions
4. Refactor CLI to delegate to orchestrator
5. Delete old implementation

**Estimated Effort**: 2-3 days (Large)

---

### C2: Missing Indexing Orchestration Port

**Problem**: No port interface for indexing orchestration means:
- CLI is tightly coupled to implementation
- Cannot test indexing workflow in isolation from CLI framework
- Cannot provide alternative indexing implementations (API endpoint, webhook, scheduled job)

**Recommendation**:

```python
# application/ports/services.py

class IndexingOrchestratorPort(ABC):
    """Port for indexing orchestration."""

    @abstractmethod
    async def index_repository(
        self,
        request: IndexRepositoryRequest
    ) -> IndexRepositoryResponse:
        """Index a repository with specified strategy."""
        pass

    @abstractmethod
    async def index_incremental(
        self,
        request: IncrementalIndexRequest
    ) -> IndexRepositoryResponse:
        """Incrementally index changes since last index."""
        pass

# Implementation in application layer
class DefaultIndexingOrchestrator(IndexingOrchestratorPort):
    """Default implementation of indexing orchestration."""
    ...

# CLI becomes adapter
class IndexCommand:
    def __init__(self, orchestrator: IndexingOrchestratorPort):
        self.orchestrator = orchestrator

    async def run(self, ...):
        result = await self.orchestrator.index_repository(...)
        # Display results
```

**Estimated Effort**: 1 day (Medium)

---

### H1: Content-Hash Reuse Optimization Buried in CLI

**Current State**:
```python
# In index_command.py around line 850
if content_hash in hash_to_file_id:
    donor_file_id = hash_to_file_id[content_hash]
    symbols_copied = await symbol_repo.copy_symbols_to_file(...)
    refs_copied = await ref_repo.copy_references_to_file(...)
```

**Issue**: This performance optimization is:
- Embedded in CLI code
- Not available to other indexing paths
- Hard to test independently
- Not documented as a feature

**Recommendation**: Extract to dedicated use case

```python
# application/use_cases/indexing/optimize_file_indexing.py

class OptimizeFileIndexingUseCase:
    """
    Reuse symbols/references from files with identical content.

    When indexing a file, check if another file with the same
    content_hash has already been indexed. If so, copy its
    symbols and references instead of re-parsing.

    This is a significant performance optimization for repos with:
    - Many unchanged files across commits
    - Generated/vendored code
    - Large binary commits
    """

    async def execute(
        self,
        file: File,
        content_hash_cache: dict[str, int],
    ) -> OptimizationResult:
        """
        Try to reuse existing symbols/references.

        Returns:
            OptimizationResult with reused_symbols/reused_references
            counts, or None if optimization not applicable.
        """
        ...
```

**Benefits**:
1. Reusable across all indexing strategies
2. Testable in isolation
3. Documented as a feature
4. Can be toggled on/off

**Estimated Effort**: 0.5 day (Medium)

---

### H2: Duplication Between Full and Incremental Indexing

**Current State**:
- `_run_full_index_async` (lines 200-500)
- `_run_incremental_index_async` (lines 600-900)
- Share ~60% of logic but implemented separately

**Recommendation**: Extract shared workflow

```python
class IndexingWorkflow:
    """Shared indexing workflow steps."""

    async def prepare_repository(self, ...):
        """Common: validate repo, create/load from DB."""
        ...

    async def process_commits(self, commits: list[Commit]):
        """Common: iterate commits, process files."""
        ...

    async def process_file(self, file: File):
        """Common: parse, extract symbols, store."""
        ...

    async def finalize(self, stats: IndexingStats):
        """Common: resolve references, update status."""
        ...

# Full strategy uses all commits
class FullIndexing:
    def get_commits(self, repo) -> list[Commit]:
        return repo.get_all_commits(max=limit)

# Incremental uses delta
class IncrementalIndexing:
    def get_commits(self, repo) -> list[Commit]:
        last_indexed = get_last_indexed_commit()
        return repo.get_commits_since(last_indexed)
```

**Estimated Effort**: 1 day (Medium)

---

### H3: No Pagination Strategy

**Issue**: Symbol search queries have `limit` parameter but no offset/cursor mechanism.

```python
# Current
async def search_by_name(
    self,
    name: str,
    limit: int = 50,  # Can't get next page!
) -> list[Symbol]:
    ...
```

**Recommendation**:

```python
@dataclass
class PaginatedRequest:
    """Pagination parameters."""
    limit: int = 50
    offset: int = 0
    # Or cursor-based:
    # cursor: str | None = None

@dataclass
class PaginatedResponse[T]:
    """Paginated response wrapper."""
    items: list[T]
    total_count: int
    has_more: bool
    next_cursor: str | None = None

async def search_by_name(
    self,
    name: str,
    pagination: PaginatedRequest,
) -> PaginatedResponse[Symbol]:
    ...
```

**Estimated Effort**: 0.5 day (Small)

---

### M2: Parser Code Duplication

**Pattern Observed**: Each language parser (Python, Java, C, TypeScript) has:
- `BUILTIN_LIST` (60-120 items)
- `_get_text(node, content)` helper
- `_node_location(node)` helper
- Similar traversal patterns

**Recommendation**: Extract shared utilities

```python
# adapters/external/treesitter/utils.py

class ParserUtils:
    """Shared utilities for tree-sitter parsers."""

    @staticmethod
    def get_text(node: Node, content: str) -> str:
        """Extract text from node."""
        return content[node.start_byte:node.end_byte]

    @staticmethod
    def get_location(node: Node) -> dict[str, int]:
        """Get location dict from node."""
        return {
            "start_line": node.start_point[0] + 1,
            "start_column": node.start_point[1],
            "end_line": node.end_point[0] + 1,
            "end_column": node.end_point[1],
        }

    @staticmethod
    def filter_builtins(
        references: list[dict],
        builtins: set[str]
    ) -> list[dict]:
        """Remove builtin references."""
        return [ref for ref in references if ref["text"] not in builtins]

# Move builtins to data files
# adapters/external/treesitter/builtins/python.txt
# adapters/external/treesitter/builtins/java.txt
```

**Benefits**:
- DRYer codebase
- Consistent behavior across parsers
- Easier to add new languages (less boilerplate)

**Estimated Effort**: 1 day (Medium)

---

## Part 4: Refactoring Roadmap

### Phase 1: Quick Wins (1-2 days)
*Improve maintainability with minimal risk*

1. **M3: Remove legacy search use case** (5 min)
   - Delete or clearly deprecate old file
   - Update imports if needed

2. **L2: Fix datetime.utcnow() deprecations** (30 min)
   - Replace with `datetime.now(UTC).replace(tzinfo=None)`
   - Already partially done, complete the migration

3. **H3: Add pagination support** (0.5 day)
   - Add `PaginatedRequest`/`PaginatedResponse` DTOs
   - Update repository ports
   - Implement in PostgreSQL adapters

4. **M4: Centralize language list** (1 hour)
   - Single source of truth for supported languages
   - Update all references to use constant

### Phase 2: Architectural Improvements (3-4 days)
*Address core architectural concerns before adding features*

5. **C2: Extract IndexingOrchestrator port** (1 day)
   - Define port interface
   - Create initial implementation
   - Update CLI to use port

6. **H1: Extract content-hash optimization** (0.5 day)
   - Create `OptimizeFileIndexingUseCase`
   - Test independently
   - Integrate into workflow

7. **H2: Deduplicate full/incremental logic** (1 day)
   - Extract shared `IndexingWorkflow`
   - Refactor both strategies to use it
   - Comprehensive testing

8. **C1: Refactor monolithic index command** (2 days)
   - Extract `IndexingOrchestrator` to application layer
   - Create strategy abstractions
   - Migrate CLI to thin adapter
   - **CRITICAL**: This unblocks parallelization work

### Phase 3: Code Quality (2-3 days)
*Polish and maintainability improvements*

9. **M2: Extract parser utilities** (1 day)
   - Create `ParserUtils` class
   - Refactor all parsers to use it
   - Extract builtins to data files

10. **M5: Centralize error handling** (1 day)
    - Define exception hierarchy
    - Create adapter-specific handlers
    - Update all error handling sites

11. **M1: Evaluate thin use cases** (1 day)
    - Identify truly thin wrappers
    - Either enrich with business logic or remove
    - Document decision rationale

### Phase 4: Performance Foundations (1-2 days)
*Prepare for scaling*

12. **H4: Database connection pooling** (0.5 day)
    - Configure pool size based on concurrency needs
    - Add connection monitoring
    - Test under load

13. **Add caching layer** (1 day)
    - In-memory cache for frequently accessed symbols
    - Cache invalidation strategy
    - Metrics for cache hit rate

---

## Part 5: Impact Analysis for Planned Features

### Feature 1: Faster Indexing

**Current Bottlenecks** (from code analysis):

1. **Sequential file processing** (MAJOR)
   - Location: `index_command.py:~400` loops over files serially
   - Impact: 100 files take ~100x the time of 1 file
   - **Blocked by**: C1 (monolithic command structure)

2. **Database flush per file** (MODERATE)
   - Location: `symbol_adapter.py:38` flushes after each save
   - Impact: ~50ms latency per file
   - **Solution**: Batch commits (already supported via `save_many`)

3. **N+1 queries for reference resolution** (MODERATE)
   - Location: `reference_adapter.py:~420` resolve_unlinked_references
   - Impact: One query per unresolved reference
   - **Solution**: Batch resolution query

**Architectural Readiness**: 6/10
- **Strengths**:
  - Clean separation allows parallel processing
  - `save_many` already exists for bulk operations
  - Content-hash optimization reduces parsing load

- **Blockers**:
  - C1: Monolithic CLI prevents parallel strategy
  - No worker pool abstraction
  - Progress reporting assumes sequential execution

**Recommended Approach**:

```python
# After Phase 2 refactoring:

class ParallelFileIndexingStrategy(IndexingStrategyPort):
    """Process files in parallel using worker pool."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers)

    async def process_files(self, files: list[File]):
        # Parse files in parallel
        tasks = [
            self.executor.submit(parse_file, f)
            for f in files
        ]
        results = [task.result() for task in tasks]

        # Batch DB operations
        all_symbols = [s for r in results for s in r.symbols]
        await symbol_repo.save_many(all_symbols)  # Single transaction
```

**Expected Improvement**: 3-4x faster for repos with many files

---

### Feature 2: Free Text Search

**Current State**:
- Symbol search: Implemented (`search_by_name`)
- File path search: Implicit via file listing
- Content search: Not implemented

**Database Schema Analysis**:
```sql
-- From symbol model:
-- extra_metadata JSONB  -- Could store full-text search vector

-- Missing: file_content table or tsvector column
```

**Architectural Fit**: 8/10
- **Strengths**:
  - Clean layer separation allows adding search without disrupting indexing
  - PostgreSQL full-text search ready to use
  - Port/adapter pattern allows swapping search backends

- **Gaps**:
  - No file content storage (currently read from git)
  - No tsvector column on files table
  - No search result ranking/highlighting port

**Recommended Architecture**:

```python
# Migration: Add content storage and search index
ALTER TABLE files ADD COLUMN content_text TEXT;
ALTER TABLE files ADD COLUMN content_search tsvector;
CREATE INDEX files_content_search_idx ON files
    USING GIN (content_search);

# Domain layer
@dataclass
class SearchResult:
    """Search result with ranking and highlights."""
    file: File
    snippet: str
    rank: float
    highlights: list[tuple[int, int]]  # (start_line, end_line)

# Application port
class TextSearchPort(ABC):
    @abstractmethod
    async def search_content(
        self,
        query: str,
        repository_id: int | None = None,
        language: str | None = None,
    ) -> list[SearchResult]:
        """Full-text search across file content."""
        pass

# PostgreSQL adapter
class PostgresTextSearch(TextSearchPort):
    async def search_content(self, query: str, ...):
        # Use ts_query, ts_rank for PostgreSQL full-text search
        ...

# SQLite adapter (future)
class SQLiteFTSSearch(TextSearchPort):
    async def search_content(self, query: str, ...):
        # Use FTS5 virtual table
        ...
```

**Migration Complexity**: Medium
- Add content storage to indexing pipeline
- Populate tsvector on insert/update
- Implement search use case
- Add API endpoint
- Frontend integration

**No architectural changes required** - fits cleanly into existing structure.

---

### Feature 3: PostgreSQL → SQLite Migration

**Current Database Dependencies** (analyzed):

1. **PostgreSQL-specific SQL**:
   - `pg_terminate_backend` in `index_command.py:130`
   - `TRUNCATE CASCADE` in `index_command.py:141`
   - Used only in CLI `--reset` command (development tool)

2. **Type mappings**:
   - JSONB → JSON (compatible)
   - TSVECTOR → FTS5 virtual table (migration needed)
   - ARRAY → JSON array (compatible)

3. **Database drivers**:
   - `asyncpg` for async operations
   - `psycopg2` for Alembic migrations

**Architectural Readiness**: 9/10
- **Strengths**:
  - All DB access through repository ports
  - Mappers abstract ORM details
  - Test suite already uses SQLite (aiosqlite)

- **Minimal changes needed**:
  - Swap connection string
  - Replace pg_specific SQL in reset command
  - Update driver dependencies
  - Migration for full-text search (TSVECTOR → FTS5)

**Migration Path**:

```python
# 1. Make database dialect pluggable
class DatabaseConnection:
    def __init__(self, url: str):
        self.dialect = self._detect_dialect(url)
        # sqlite:// vs postgresql://

    def _detect_dialect(self, url: str) -> str:
        return url.split("://")[0]

    async def reset_database(self):
        if self.dialect == "postgresql":
            await self._reset_postgres()
        elif self.dialect == "sqlite":
            await self._reset_sqlite()

# 2. Update full-text search
class SQLiteFileRepository(FileRepositoryPort):
    async def search_content(self, query: str):
        # Use FTS5 instead of tsvector
        stmt = select(FileModel).join(
            FileContentFTS, FileContentFTS.rowid == FileModel.id
        ).where(FileContentFTS.match(query))
        ...
```

**Benefits of SQLite**:
- **Simpler deployment**: Single file database
- **Faster full scans**: For small-medium repos (< 1M LOC)
- **Better for development**: No separate Postgres container
- **Portable**: Copy .db file to move entire index

**When PostgreSQL is still better**:
- Very large repos (> 10M LOC)
- High concurrent users (> 20)
- Advanced full-text search needs
- Database replication requirements

**Recommendation**: Support both via adapter pattern
```python
# User chooses via DATABASE_URL
DATABASE_URL=sqlite:///inxr2.db  # SQLite
DATABASE_URL=postgresql://...    # PostgreSQL
```

**No major refactoring required** - this is exactly what the port/adapter pattern was designed for.

---

## Part 6: Priority Order Summary

### Before Starting New Features

**Critical Path (Must Do First)**:

1. **C1: Refactor monolithic index command** (2 days)
   - Reason: Blocks parallel indexing work
   - Blocks: Faster indexing feature

2. **C2: Extract indexing orchestrator port** (1 day)
   - Reason: Architectural completeness
   - Enables: Alternative indexing implementations

**High Value (Should Do)**:

3. **H1: Extract content-hash optimization** (0.5 day)
4. **H2: Deduplicate full/incremental logic** (1 day)
5. **H3: Add pagination** (0.5 day)

**Nice to Have (Time Permitting)**:

6. **M2: Extract parser utilities** (1 day)
7. **M5: Centralize error handling** (1 day)

### Estimated Timeline

- **Phase 1 (Quick Wins)**: 1 day
- **Phase 2 (Architectural)**: 4 days
- **Total before new features**: 5 days

---

## Part 7: Architectural Principles Validation

### Clean Architecture Adherence: A-

| Principle | Grade | Evidence |
|-----------|-------|----------|
| **Dependency Rule** | A+ | Zero framework imports in domain layer |
| **Stable Abstractions** | A | 21 use cases depend on ports, not implementations |
| **Single Responsibility** | B+ | Most classes focused, but indexing command violates |
| **Open/Closed** | A | Easy to add languages, parsers, repositories |
| **Interface Segregation** | A- | Port interfaces well-sized, some could be split |
| **Dependency Inversion** | A+ | Excellent use of dependency injection |

### Testing Philosophy: A

| Metric | Score | Notes |
|--------|-------|-------|
| **Fakes over Mocks** | 95% | Only 6 mock usages in entire test suite |
| **Test Independence** | A | Tests use tmp_path, don't depend on external repos |
| **Coverage** | B+ | Good coverage, some edge cases missing |
| **Integration Tests** | A | Real database tests verify actual behavior |

### Code Organization: B+

| Area | Grade | Notes |
|------|-------|-------|
| **Layer Separation** | A | Clear boundaries, proper dependency flow |
| **Module Cohesion** | A | Features well-grouped |
| **File Size** | C | 1,489-line index_command.py is too large |
| **Duplication** | B | Some parser logic duplicated |

---

## Conclusion

The INXR2 codebase demonstrates **excellent architectural discipline** with Clean Architecture principles properly applied. The foundation is solid for all three planned features. The primary issue is **accumulated complexity in the indexing command module** (C1, C2), which should be addressed before implementing parallel indexing.

**Key Recommendations**:

1. **Refactor indexing command** (C1) - This is the highest-leverage improvement
2. **Extract orchestration port** (C2) - Completes the architectural vision
3. **Address duplication** (H2) - Reduces future maintenance burden

**Timeline**:
- 5 days of refactoring before new features
- Unlocks 3-4x faster development of planned features
- Prevents architectural debt from accumulating further

**Next Steps**:
1. Review and approve refactoring roadmap
2. Start with Phase 1 (quick wins) for early momentum
3. Tackle Phase 2 (architectural improvements) before new feature work
4. Implement features in order: faster indexing → free text search → SQLite support

The architecture is fundamentally sound. With focused refactoring on the identified issues, INXR2 will be well-positioned for rapid feature development while maintaining high code quality.
