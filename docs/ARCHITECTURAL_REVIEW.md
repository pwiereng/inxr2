# INXR2 Architectural Review

**Date**: 2026-01-24
**Branch**: architectural-review
**Overall Grade**: **A-** (Excellent foundation with specific improvements needed)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Database Schema Assessment](#database-schema-assessment)
3. [Clean Architecture Adherence](#clean-architecture-adherence)
4. [Test Coverage & Testability](#test-coverage--testability)
5. [Extensibility for Future Features](#extensibility-for-future-features)
6. [Code Quality & AI-Friendliness](#code-quality--ai-friendliness)
7. [Priority Improvement List](#priority-improvement-list)
8. [Appendix: Detailed Metrics](#appendix-detailed-metrics)

---

## Executive Summary

### Grade Summary

| Area | Grade | Key Finding |
|------|-------|-------------|
| Database Schema | B+ | Over-denormalized, storing git-queryable data |
| Clean Architecture | B+ | Good structure, Pydantic in domain is main violation |
| Test Coverage | B+ | Strong patterns (fakes not mocks), gaps in CLI/infrastructure |
| Extensibility | A- | Excellent for languages, moderate for non-git files |
| Code Quality | A | Strong types, good documentation, minor print() issue |
| AI-Friendliness | A+ | Exceptional documentation and patterns |
| **Overall** | **A-** | **Production-ready with specific fixes needed** |

### Key Strengths

1. **Clean Architecture** - Proper layer separation with dependency injection
2. **Test Doubles** - Uses fakes instead of mocks (maintainable, refactor-safe)
3. **Documentation** - CLAUDE.md, DESIGN.md, comprehensive docstrings
4. **Type Safety** - Strict mypy + TypeScript, only 8 type:ignore comments
5. **Extensibility** - Plugin architecture for languages, clear extension points

### Key Weaknesses

1. **Over-denormalized schema** - Storing data queryable from git
2. **Pydantic in domain layer** - Framework dependency violates Clean Architecture
3. **CLI test coverage** - 1,191-line file at 3% coverage
4. **Infrastructure untested** - 0% coverage on app startup code

---

## Database Schema Assessment

**Grade: B+**

### Data That Should Be Removed (Query from Git Instead)

| Field | Table | Reason | Savings |
|-------|-------|--------|---------|
| `author_name` | commits | Available from git commit object | ~255 bytes/commit |
| `author_email` | commits | Available from git commit object | ~255 bytes/commit |
| `committer_name` | commits | Available from git commit object | ~255 bytes/commit |
| `committer_email` | commits | Available from git commit object | ~255 bytes/commit |
| `message` | commits | Available from git commit object | ~500 bytes/commit |
| `parent_hashes` | commits | Available from git commit parents | ~80 bytes/commit |
| `short_hash` | commits | Derived from commit_hash[:7] | ~7 bytes/commit |
| `total_*` counts | index_status | Compute via COUNT(*) queries | ~16 bytes/repo |

**Estimated storage savings**: ~30% reduction in database size

### Data That's Correctly Stored

| Field | Table | Why Keep |
|-------|-------|----------|
| `content_hash` | files | Essential for deduplication, requires reading blob |
| `commit_date` | commits | Needed for temporal ordering, incremental indexing |
| `symbols.*` | symbols | Core indexed data - not in git |
| `references.*` | references | Core indexed data - not in git |

### Design Issue: Branch Duplication

Same commit is stored multiple times (once per branch). Current workaround:

```python
# commit_adapter.py line 66-81
# "Same commit hash may exist for multiple branches. We just need any matching commit."
```

**Recommendation**: Create `branch_commits` junction table:

```sql
CREATE TABLE branch_commits (
    repository_id INTEGER NOT NULL,
    branch VARCHAR(255) NOT NULL,
    commit_id BIGINT NOT NULL,
    PRIMARY KEY (repository_id, branch, commit_id)
);
```

### Missing Indexes

| Index | Purpose | Priority |
|-------|---------|----------|
| `(repository_id, language)` on files | "Get all Python files in repo" | Medium |
| `(repository_id, kind)` on symbols | "Get all classes in repo" | Medium |
| `(repository_id, branch, commit_date DESC)` on commits | Incremental indexing | Low |

### Full-Text Search Gap

Schema documents FTS trigger on `name_tsvector`, but ORM model excludes it:

```python
# symbol.py lines 56-62
# Note: For now, we simply exclude this from the ORM by not mapping it
```

**Impact**: FTS documented but not implemented in ORM.

---

## Clean Architecture Adherence

**Grade: B+**

### Layer Structure

```
┌─────────────────────────────────────────┐
│  Infrastructure (FastAPI, SQLAlchemy)  │
│  ┌─────────────────────────────────┐   │
│  │  Adapters (API, CLI, Repos)     │   │
│  │  ┌─────────────────────────┐    │   │
│  │  │  Application (Use Cases) │   │   │
│  │  │  ┌─────────────────┐    │    │   │
│  │  │  │  Domain         │    │    │   │
│  │  │  │  (Entities)     │    │    │   │
│  │  │  └─────────────────┘    │    │   │
│  │  └─────────────────────────┘    │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### Layer Violations Found

| Violation | Severity | Location | Fix |
|-----------|----------|----------|-----|
| Pydantic in domain | 🔴 Critical | `domain/value_objects/config.py` | Move to infrastructure |
| File I/O in use case | 🟠 High | `use_cases/indexing/index_local_directory.py` | Create FileSystemPort |
| Business logic in controllers | 🟡 Medium | `api/routes/symbols.py`, `repositories.py` | Extract to use cases |
| Direct adapter access | 🟡 Medium | Multiple routes orchestrate adapters | Create orchestration use cases |
| Git service in controller | 🟡 Medium | `api/routes/repositories.py` | Route through use case |

### What's Working Well

- ✅ Domain entities are frozen dataclasses (immutable)
- ✅ Clear port interfaces (6 repository ports defined)
- ✅ Proper mapper pattern (entity ↔ ORM model separation)
- ✅ No circular dependencies detected
- ✅ Test doubles use dependency injection, not mocking

### Critical Fix: Pydantic in Domain

**Current** (`domain/value_objects/config.py`):
```python
from pydantic import BaseModel, Field  # ❌ Framework in domain

class RepositoryConfig(BaseModel):
    name: str
    path: str | None = None
    ...
```

**Should be** (`infrastructure/config/models.py`):
```python
from pydantic import BaseModel

class RepositoryConfigModel(BaseModel):  # Pydantic for validation
    ...

# Domain uses pure dataclass
@dataclass(frozen=True)
class RepositoryConfig:  # No framework dependencies
    name: str
    path: str | None = None
```

### Missing Abstractions

| Abstraction | Purpose | Where to Add |
|-------------|---------|--------------|
| `FileSystemPort` | Abstract file I/O operations | `application/ports/services.py` |
| `GetRepositoryStatsUseCase` | Stats calculation orchestration | `application/use_cases/` |
| `GetRepositoryBranchesUseCase` | Branch listing orchestration | `application/use_cases/` |
| `SearchSymbolsWithFilesUseCase` | Symbol search with file enrichment | `application/use_cases/` |

---

## Test Coverage & Testability

**Grade: B+**

### Coverage Summary

| Layer | Source LOC | Test LOC | Ratio | Coverage Est. |
|-------|------------|----------|-------|---------------|
| Domain | 896 | 450 | 0.50x | 85-90% |
| Application | 1,386 | 1,300 | 0.94x | 85-95% ✅ |
| Adapters | 6,971 | 5,400 | 0.77x | 70-80% |
| Infrastructure | 868 | 0 | 0x | 0% 🔴 |
| CLI | 753 | 148 | 0.20x | 20-30% 🔴 |
| Frontend | 5,401 | 2,941 | 0.54x | 45-55% 🟡 |
| **Total** | **16,275** | **12,010** | **0.74x** | **62-70%** |

### Test Pattern: Dependency Injection (Excellent)

The codebase uses **fakes instead of mocks**, which is the recommended pattern:

```python
# tests/fixtures/test_doubles.py - 999 lines of fake implementations

class InMemorySymbolRepository(SymbolRepositoryPort):
    def __init__(self):
        self._symbols: dict[int, Symbol] = {}
        self._next_id = 1

    async def save(self, symbol: Symbol) -> Symbol:
        symbol_id = self._next_id
        self._next_id += 1
        saved = Symbol(id=symbol_id, ...)
        self._symbols[symbol_id] = saved
        return saved
```

**Benefits**:
- Tests survive refactoring (test behavior, not implementation)
- Explicit test data setup
- No framework overhead
- Fakes follow real interface contracts

### Available Test Doubles

| Fake | Lines | Purpose |
|------|-------|---------|
| `InMemorySymbolRepository` | ~80 | Symbol CRUD operations |
| `InMemoryFileRepository` | ~70 | File CRUD operations |
| `InMemoryCommitRepository` | ~90 | Commit operations with branch support |
| `InMemoryReferenceRepository` | ~60 | Reference operations |
| `InMemoryRepositoryRepository` | ~50 | Repository metadata |
| `InMemoryIndexStatusRepository` | ~50 | Indexing status |
| `StubParserService` | ~30 | Symbol/reference extraction |
| `StubGitService` | ~40 | Git operations |

### Critical Test Gaps

| File | Lines | Test Coverage | Risk |
|------|-------|---------------|------|
| `index_command.py` | 1,191 | ~3% | 🔴 HIGH - Core indexing logic |
| `cli.py` | 691 | ~3% | 🔴 HIGH - Entry point |
| `infrastructure/*` | 868 | 0% | 🟠 MEDIUM - App startup |
| `files.py` (routes) | 655 | ~60% | 🟡 MEDIUM - Complex handlers |

### Well-Tested Areas

| Area | Test LOC | Coverage | Notes |
|------|----------|----------|-------|
| Application use cases | 1,300 | 94% | Thoroughly tested |
| Repository adapters | 990 | 80-90% | Comprehensive DB tests |
| Tree-sitter parsing | 649 | 75-85% | Good AST extraction tests |
| API endpoints | 1,841 | 60-75% | Integration tests |
| useBrowseState hook | 1,192 | 95% | Heavily tested |

### Architecture Testability: 9/10

Clean Architecture makes testing easy:
- Ports define clear contracts → easy to create fakes
- Use cases isolated from infrastructure → unit testable
- Domain entities are pure → simple to construct
- Mappers separate concerns → testable in isolation

### Recommendations

1. **Enable coverage enforcement**:
   ```bash
   pytest --cov=src --cov-fail-under=80
   ```

2. **Add CLI tests** - Currently 3% on 1,191-line file

3. **Add infrastructure tests** - 0% on app startup

4. **Improve frontend tests** - Replace vi.mock() with MSW for realistic API mocking

---

## Extensibility for Future Features

### Git Blame Integration

**Difficulty: EASY** ⭐ | **Effort: 1-2 days**

Infrastructure already exists:
- Commit metadata indexed
- GitService has all needed methods
- Just add `get_file_blame()` + API route

```python
# Add to git_service.py
def get_file_blame(self, repo_path: Path, file_path: str, commit_hash: str = None):
    repo = Repo(repo_path)
    blame_data = repo.blame(commit_hash or "HEAD", file_path)
    return {line_num: {"commit": entry[0].hexsha, "author": entry[0].author.name}
            for line_num, entry in enumerate(blame_data, 1)}
```

### New Language Support (Java, Go, etc.)

**Difficulty: EASY** ⭐ | **Effort: 3-5 days per language**

Excellent plugin architecture already exists:

```python
# 1. Create parser (adapters/external/treesitter/go_parser.py)
class GoParser(BaseLanguageParser):
    @property
    def language_name(self) -> str:
        return "go"

    def extract(self, root: Node, content: str):
        # Go-specific AST traversal
        ...

# 2. Register in service.py
SUPPORTED_LANGUAGES = {
    "python": [".py", ".pyi"],
    "typescript": [".ts", ".tsx"],
    "go": [".go"],  # Add this
}

# 3. Update language_detector.py
EXTENSION_MAP = {
    ".go": "go",
}
```

### Non-Git File Indexing (node_modules, site-packages)

**Difficulty: MODERATE** ⭐⭐⭐ | **Effort: 2-3 weeks**

Current gaps:
- No `FileSourcePort` abstraction (hardcoded to GitService)
- `File` entity has no `source_type` field
- CLI assumes git workflow throughout

**Required changes**:

1. Create `FileSourcePort` interface:
```python
class FileSourcePort(ABC):
    @abstractmethod
    async def list_files(self, path: str) -> list[str]: ...

    @abstractmethod
    async def get_file_content(self, path: str, file_path: str) -> str: ...
```

2. Add `source_type` to File entity:
```python
@dataclass(frozen=True)
class File:
    source_type: Literal["git", "local", "package"] = "git"
    source_metadata: dict = field(default_factory=dict)
```

3. Implement adapters:
   - `GitFileSource` (wraps current logic)
   - `LocalFileSource` (for non-git directories)
   - `PackageFileSource` (for node_modules, site-packages)

### Extensibility Summary

| Feature | Difficulty | Effort | Current Readiness |
|---------|------------|--------|-------------------|
| Git Blame | Easy | 1-2 days | Infrastructure exists |
| New Languages | Easy | 3-5 days each | Plugin architecture ready |
| Non-Git Files | Moderate | 2-3 weeks | Needs abstraction layer |

---

## Code Quality & AI-Friendliness

**Grade: A / A+**

### Documentation Quality

| Document | Size | Purpose |
|----------|------|---------|
| CLAUDE.md | 24 KB | AI agent guidelines, architecture, commands |
| DESIGN.md | 18 KB | System architecture, tech stack rationale |
| CONTRIBUTING.md | 21 KB | Development standards, testing philosophy |
| IMPLEMENTATION_PLAN.md | 90 KB | Phase-by-phase roadmap |

### Type Safety

**Python (mypy strict)**:
```toml
[tool.mypy]
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
strict_equality = true
```

**TypeScript**:
```json
"strict": true,
"noUnusedLocals": true,
"noUncheckedIndexedAccess": true
```

- Only 8 `type: ignore` comments in entire codebase
- All functions have return type annotations
- Generic types used correctly

### Code Quality Metrics

| Metric | Value | Status |
|--------|-------|--------|
| Type ignores | 8 | ✅ Excellent |
| print() statements | 128 | 🟡 Should be logging |
| TODOs | 62 | ✅ All future enhancements |
| Largest file | 1,191 lines | 🟡 Could split |
| Test-to-code ratio | 0.74x | ✅ Good |

### AI-Friendliness Assessment

**What Makes This AI-Friendly**:

1. **Test doubles module** (999 lines) is a "pattern cookbook"
2. **CLAUDE.md** explicitly addresses AI development
3. **Layer separation** makes it obvious where to add code
4. **Port interfaces** define contracts clearly
5. **No magic** - straightforward dependency injection
6. **Explicit intent** - exceptions, value objects, mappers documented

**Most AI-Friendly Areas**:
- Domain entities (pure data, simple logic)
- Use case tests (concrete fixtures, explicit assertions)
- API route definitions (straightforward controller pattern)

**Least AI-Friendly Areas**:
- Tree-sitter parsers (complex AST traversal)
- Git service (20+ methods)
- index_command.py (1,191 lines, multiple responsibilities)

### Issues to Fix

| Issue | Count | Fix |
|-------|-------|-----|
| `print()` statements | 128 | Replace with `logger.info()` |
| Large files | 2 | Split index_command.py, files.py |
| Missing use cases | 4+ | Extract from controllers |

---

## Priority Improvement List

### 🔴 Priority 1: Critical (Do First)

| Task | Effort | Impact |
|------|--------|--------|
| Move Pydantic config to infrastructure | 1 day | Fixes architecture violation |
| Remove redundant git data from commits | 2-3 days | 30% storage reduction |
| Add CLI test coverage | 3-4 days | De-risks core indexing |

### 🟠 Priority 2: High (Next Sprint)

| Task | Effort | Impact |
|------|--------|--------|
| Abstract file I/O (create FileSystemPort) | 2-3 days | Enables non-git indexing |
| Extract business logic from controllers | 3-4 days | Cleaner architecture |
| Replace print() with logging | 1 day | Better debugging |
| Add infrastructure layer tests | 2 days | Verify app startup |

### 🟡 Priority 3: Medium (When Convenient)

| Task | Effort | Impact |
|------|--------|--------|
| Normalize branch handling (junction table) | 1 week | Eliminates duplicate commits |
| Split large files | 2-3 days | Better maintainability |
| Remove redundant index_status statistics | 1 day | Simpler schema |
| Enable coverage enforcement | 1 hour | Prevent regression |
| Improve frontend component tests | 1 week | Better UI reliability |

### 🟢 Priority 4: Nice to Have

| Task | Effort | Impact |
|------|--------|--------|
| Add FTS implementation to ORM | 2 days | Better search |
| Add stress/performance tests | 1 week | Scale confidence |
| Document layer boundaries | 1 day | Onboarding |

---

## Appendix: Detailed Metrics

### File Size Distribution

| Range | Python Files | TypeScript Files |
|-------|--------------|------------------|
| < 100 lines | 45 | 12 |
| 100-300 lines | 32 | 8 |
| 300-500 lines | 10 | 4 |
| 500-1000 lines | 5 | 2 |
| > 1000 lines | 1 | 1 |

### Largest Files

| File | Lines | Notes |
|------|-------|-------|
| index_command.py | 1,191 | Should split into multiple commands |
| test_api_endpoints.py | 1,841 | Integration tests (acceptable) |
| useBrowseState.test.ts | 1,192 | Hook tests (acceptable) |
| test_doubles.py | 999 | Fake implementations (acceptable) |
| files.py (routes) | 655 | Could extract controller logic |

### Test File Counts

```
Backend:
  tests/unit/domain/           5 files
  tests/unit/application/      6 files
  tests/adapters/persistence/  5 files
  tests/adapters/external/     2 files
  tests/adapters/cli/          1 file
  tests/adapters/config/       1 file
  tests/integration/           2 files
  tests/fixtures/              2 files
  ─────────────────────────────────────
  Total:                      24 files

Frontend:
  src/**/*.test.ts(x)         12 files
```

### Coverage Configuration Status

```toml
# pyproject.toml - Configured but not enforced
[tool.coverage.run]
source = ["src"]

[tool.coverage.report]
# No fail_under threshold set
```

**Recommendation**: Add `fail_under = 80` to enforce coverage.

---

## Future Work: Indexer Performance Optimization

**Current Status**: The indexer is primarily **I/O bound (database)**, not CPU bound.

### Bottleneck Analysis

| Operation | Type | Current Behavior | Impact |
|-----------|------|------------------|--------|
| `file_repository.save()` | DB I/O | Individual INSERT + flush per file | High |
| `file_repository.find_by_path()` | DB I/O | Individual SELECT per file to check existence | High |
| `symbol_repository.save_many()` | DB I/O | Batched per file, but flush after each batch | Medium |
| `reference_repository.save_many()` | DB I/O | Batched per file, but flush after each batch | Medium |
| `git_service.get_file_content()` | Disk I/O | Individual git read per file | Medium |
| Tree-sitter parsing | CPU | Fast, processes sequentially | Low |

**Root cause**: Every `save()` and `save_many()` calls `session.flush()`, forcing a database round-trip. For 100 files with symbols, that's 300+ round-trips to PostgreSQL.

### Recommended Optimizations

1. **Batch file inserts** - Accumulate file records and use `save_many()` instead of individual `save()` calls
2. **Remove per-file existence checks** - Skip `find_by_path()` or batch existence checks with `WHERE path IN (...)`
3. **Defer flushes** - Only flush at commit/batch boundaries (e.g., every 50 files), not per-operation
4. **Parallel git reads** - Use `asyncio.gather()` to read multiple file contents concurrently
5. **Use COPY for bulk inserts** - For large imports, PostgreSQL COPY is 10x faster than INSERT

### Expected Impact

| Optimization | Estimated Speedup | Effort |
|--------------|-------------------|--------|
| Batch file inserts | 2-3x | Low |
| Remove existence checks | 1.5x | Low |
| Defer flushes | 2x | Medium |
| Parallel git reads | 1.5x | Medium |
| COPY for bulk inserts | 3-5x | High |

**Combined potential**: 5-10x faster indexing for large repositories.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-24 | Claude + User | Initial architectural review |
| 1.1 | 2026-01-25 | Claude + User | Added indexer performance analysis |
