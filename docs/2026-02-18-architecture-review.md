# INXR2 Architecture Review

**Date:** 2026-02-18
**Scope:** Clean architecture adherence, test quality, code maintainability, infrastructure

---

## Executive Summary

INXR2 demonstrates **exemplary clean architecture adherence** with zero dependency rule violations and perfect domain purity. The codebase is well-structured, with clear layer separation and proper use of ports and adapters. However, there are meaningful opportunities for improvement in test quality (low-value tests), code duplication (repository adapters), error handling, and production readiness (CORS, logging, health checks).

| Area | Rating | Summary |
|------|--------|---------|
| Clean Architecture | **A+** | Zero violations, 14 ports, proper DI |
| Test Quality | **B** | Good behavioral tests, ~25 low-value tests to prune |
| Maintainability | **B+** | Some duplication in adapters, complexity hotspots |
| Production Readiness | **C** | CORS, logging, health checks need work |

---

## 1. Clean Architecture Adherence

### 1.1 Dependency Rule: Zero Violations

The dependency rule (dependencies point inward only) is **perfectly maintained**:

- **Domain layer** (`src/inxr2/domain/`): Zero imports from application, adapters, or infrastructure. Uses only standard Python (`dataclasses`, `enum`, `pathlib`). No Pydantic, SQLAlchemy, or FastAPI.
- **Application layer** (`src/inxr2/application/`): Depends only on domain. 14 port ABCs, 20+ use cases, no adapter imports.
- **Adapters layer** (`src/inxr2/adapters/`): Properly depends on application ports and domain entities.
- **Infrastructure layer** (`src/inxr2/infrastructure/`): Correctly wires everything together. Pydantic used only in `infrastructure/config/settings.py`.

### 1.2 Port/Adapter Pattern

All 14 ports are properly defined as ABCs with complete adapter implementations:

**Repository Ports (7):**
- `RepositoryPort` -> `PostgresRepositoryAdapter`
- `CommitRepositoryPort` -> `PostgresCommitRepository`
- `FileRepositoryPort` -> `PostgresFileRepository`
- `SymbolRepositoryPort` -> `PostgresSymbolRepository`
- `ReferenceRepositoryPort` -> `PostgresReferenceRepository`
- `IndexStatusRepositoryPort` -> `PostgresIndexStatusRepository`
- `TextContentRepositoryPort` -> `PostgresTextContentRepository`

**Service Ports (7):**
- `GitServicePort` -> `GitService`
- `ParserServicePort` -> `TreeSitterService` *(see issue 1.4a)*
- `FileSystemPort` -> `LocalFileSystem`
- `ConfigServicePort` -> `YamlConfigService`
- `PlaintextParserPort` -> `PlaintextParser`
- `TextSearchPort` -> `PostgresTextSearch`
- `IndexingOrchestratorPort` -> `DefaultIndexingOrchestrator`

### 1.3 Domain Purity

All 7 entities and 6 value objects use frozen dataclasses with zero framework contamination. Business validation lives in `__post_init__()` methods. The `LanguageDetector` domain service is pure logic with no I/O.

### 1.4 Minor Architecture Issues

**a) `TreeSitterService` doesn't formally inherit from `ParserServicePort`**

`src/inxr2/adapters/external/treesitter/service.py:23` -- The class provides all required methods but uses duck typing instead of explicit inheritance. This means mypy won't catch interface mismatches.

```python
# Current:
class TreeSitterService:  # No port inheritance

# Should be:
class TreeSitterService(ParserServicePort):
```

**b) `parser_service: Any` type annotation**

`src/inxr2/application/use_cases/indexing/default_orchestrator.py:92` and `src/inxr2/application/use_cases/indexing/process_file.py:83` -- Uses `Any` instead of `ParserServicePort`, bypassing type checking.

**c) Some API routes bypass use cases**

Several routes access repository adapters directly instead of going through use cases:

- `src/inxr2/adapters/api/routes/repositories.py:131-150` -- `get_repository_by_name()` uses `repo_adapter` directly
- `src/inxr2/adapters/api/routes/symbols.py:197-229` -- `get_symbol()` injects two adapters directly
- `src/inxr2/adapters/api/routes/files.py:579-645` -- `get_file_content()` orchestrates 7 operations across 4 adapters in the route handler

This is a pragmatic tradeoff for simple fetch operations but puts business logic in the adapter layer.

---

## 2. Test Quality

### 2.1 Overall Structure

The test suite (~30K LOC Python, 25 frontend test files) mirrors the clean architecture:

```
tests/
  unit/domain/          -- Entities, value objects, exceptions
  unit/application/     -- Use cases
  adapters/             -- CLI, config, external services, persistence
  integration/          -- API endpoints
  contract/             -- Fake-vs-Postgres parity (24 tests)
  infrastructure/       -- Settings, dependencies, logging
  fixtures/             -- Shared test doubles
```

### 2.2 Low-Value Tests to Prune

The following tests verify Python language features rather than business logic:

**Enum/value tests (delete entirely):**

| File | Tests | Issue |
|------|-------|-------|
| `tests/unit/domain/value_objects/test_query_mode.py` | All 3 tests | Tests that Python enums have `.value` and work in `if` statements |
| `tests/unit/domain/value_objects/test_text_search_source_type.py` | All 3 tests | Tests `isinstance(enum.value, str)` three different ways |
| `tests/unit/domain/test_value_objects.py:60-71` | `test_symbol_kinds_exist`, `test_symbol_kind_is_string` | Verifies enum members exist |

**Trivial entity creation tests (consolidate):**

| File | Tests | Issue |
|------|-------|-------|
| `tests/unit/domain/test_entities.py:19-111` | `test_repository_creation`, `test_commit_creation`, `test_file_creation`, `test_symbol_creation` | Only assert that dataclass fields equal what was passed in |
| `tests/unit/domain/test_entities.py:33-40` | `test_repository_is_immutable` | Tests Python's `@dataclass(frozen=True)` |
| `tests/unit/domain/entities/test_text_content.py:13-63` | `test_*_creation_*` | Field assignment verification (keep the validation tests at line 81+) |

**Infrastructure framework tests (review):**

| File | Tests | Issue |
|------|-------|-------|
| `tests/infrastructure/test_settings.py:12-56` | `test_default_*` tests | Tests Pydantic's default value handling |
| `tests/infrastructure/test_logging.py:18-53` | All 3 tests | Tests that `logging.basicConfig` doesn't raise |
| `tests/infrastructure/test_dependencies.py:54-146` | Provider type checks | Tests DI container wiring, not business logic |

**Frontend:**

| File | Tests | Issue |
|------|-------|-------|
| `frontend/src/lib/prismLanguages.test.ts:6-42` | Language map assertions | Compares hardcoded data to itself |

**Estimated low-value tests: ~25-35 out of ~200+ Python tests.**

### 2.3 Strong Test Patterns (Maintain These)

- **Use case tests with fakes:** `tests/unit/application/test_search_symbols_use_case.py` -- Tests actual behavior with `InMemorySymbolRepository`, not mocks. Covers edge cases, pagination, and filtering.

- **Contract tests:** `tests/contract/test_repository_contracts.py` -- Parametrized `("fake", "postgres")` tests verify behavioral parity. Prevents fake implementations from diverging.

- **Validation error path tests:** `tests/unit/domain/entities/test_text_content.py:81+` -- Tests invalid inputs: empty content, negative line numbers, end_line < start_line.

- **Config error path tests:** `tests/adapters/config/test_yaml_config.py` -- Comprehensive error handling: file not found, invalid YAML, missing fields, invalid paths, non-git directory.

- **Parser tests:** `tests/adapters/external/test_java_parser.py` -- Tests real code patterns (abstract classes, inner classes, etc.)

### 2.4 Coverage Gaps

- **API route parameter validation:** No unit tests for `src/inxr2/adapters/api/validation.py` beyond integration tests
- **Error response consistency:** No tests verifying HTTP status codes match domain exceptions

---

## 3. Code Maintainability

### 3.1 Duplicated Subquery Builders (High Impact)

`_latest_file_ids_subquery()` is duplicated across three adapters:
- `src/inxr2/adapters/persistence/repositories/file_adapter.py:381-408`
- `src/inxr2/adapters/persistence/repositories/symbol_adapter.py:60-97`
- `src/inxr2/adapters/persistence/repositories/reference_adapter.py:167-210`

`_head_file_ids_subquery()` is duplicated across two:
- `file_adapter.py`
- `symbol_adapter.py`

**Recommendation:** Extract into a shared `SubqueryBuilders` utility class. Effort: Medium. Impact: High.

### 3.2 Repository Adapter CRUD Boilerplate

All 9 repository adapters repeat identical `save`, `save_many`, `find_by_id`, `delete_by_repository` patterns. The total adapter code is ~1,956 LOC.

**Recommendation:** Create a `BaseSQLAlchemyRepository[TEntity, TModel]` generic base class with common CRUD methods. Each adapter then only implements domain-specific methods. Effort: Medium. Impact: High (~200 LOC reduction).

### 3.3 API Response Conversion Boilerplate

Every route endpoint manually converts domain entities to Pydantic response models with identical patterns (datetime isoformat conversion, `id if id is not None else 0`, etc.).

**Recommendation:** Create `adapters/api/converters.py` with reusable converter functions. Effort: Low-Medium. Impact: High (~100 LOC reduction).

### 3.4 File Resolution Error Handling

Five endpoints in `files.py` repeat identical `try/except` blocks for `RepositoryNotFound`, `FileNotFound`, `CommitNotFound`:
- `get_file_content_by_path` (line 248)
- `get_file_raw_content_by_path` (line 157)
- `get_file_blame_by_path` (line 358)
- `get_file_symbols_by_path` (line 446)
- `get_file_references_by_path` (line 514)

**Recommendation:** Create a decorator `@handle_file_resolution_errors`. Effort: Low. Impact: Medium.

### 3.5 Complexity Hotspots

| File | LOC | Methods | Issue |
|------|-----|---------|-------|
| `file_adapter.py` | 510 | 24 | Too many responsibilities. `search_by_name()` alone is 76 LOC with 3 nested conditions. |
| `reference_adapter.py` | 379 | 11 | `resolve_references_batch()` is 100 LOC with 3-pass raw SQL resolution. |
| `CodeHeader.tsx` | 507 | -- | 6 `useState` hooks, 3 copy-paste `useEffect` hooks, 8 callback props. |
| `DiffCodeViewer.tsx` | 755 | -- | Large render function with nested ternaries and mixed diff algorithm logic. |

**Backend recommendations:**
- Split `file_adapter.py` into `FileRepository` (CRUD), `FileSearchRepository`, `FileVersionRepository`
- Extract `resolve_references_batch()` into separate `ReferenceResolutionService`

**Frontend recommendations:**
- Extract `useRepositorySelector` custom hook from CodeHeader
- Extract `computeSideBySideDiff()` into `diffUtils.ts`
- Split CodeHeader into RepositorySelect, BranchSelect, CommitSelect sub-components

### 3.6 Broad Exception Handling

20 instances of `except Exception` across the codebase, most without logging:

| File | Count | Issue |
|------|-------|-------|
| `adapters/external/git_service.py` | 5 | Silently swallows errors, falls back to defaults |
| `adapters/external/treesitter/service.py` | 4 | Import/init errors swallowed |
| `adapters/cli/commands/index_command.py` | 1 | Broad catch in CLI |
| `adapters/api/routes/commits.py:151-158` | 1 | Returns empty strings on failure, no logging |

**Recommendation:** Replace with specific exception types (e.g., `GitCommandError`). Add logging before fallback. Effort: Low. Impact: Medium.

### 3.7 Bulk Insert Performance

`save_many()` in symbol and reference adapters calls `session.refresh(model)` in a loop after `session.add_all()`, issuing N individual queries instead of 1 batch.

`src/inxr2/adapters/persistence/repositories/symbol_adapter.py:38-50`
`src/inxr2/adapters/persistence/repositories/reference_adapter.py:37-49`

**Recommendation:** Use `returning()` clause or batch the refresh. Effort: Low. Impact: Medium.

---

## 4. Production Readiness

### 4.1 CORS Configuration

`src/inxr2/infrastructure/fastapi/app.py:25-35`

```python
# TODO: Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_methods=["*"],  # Allows DELETE and other dangerous methods
    allow_headers=["*"],
)
```

Hardcoded localhost origins, `allow_methods=["*"]`, and a TODO comment. Should be environment-driven with explicit safe methods.

### 4.2 No Authentication

All API routes are publicly accessible. No auth middleware, no JWT, no API keys. Acceptable for development but must be addressed before any shared deployment.

### 4.3 Health Check Incomplete

`src/inxr2/infrastructure/fastapi/app.py:59-63`

```python
@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
```

Always returns "healthy" without checking database connectivity or external services. Not suitable for container orchestration probes.

### 4.4 No Structured Logging

No logging in any API route handler. The logging configuration (`infrastructure/logging/__init__.py`) uses `logging.basicConfig` with no JSON formatting, no log rotation, and no module-level configuration. Production debugging would be extremely difficult.

### 4.5 `os._exit()` in CLI Signal Handler

`src/inxr2/adapters/cli/commands/index_command.py:36-63` -- Uses `os._exit(1)` on Ctrl+C, which skips cleanup and can leave database connections open.

### 4.6 Unprotected Database Reset

`src/inxr2/adapters/cli/commands/index_command.py:78-80` -- `reset_database()` has no confirmation prompt and no environment check. Could accidentally delete production data.

### 4.7 Missing Foreign Key Indexes

ORM models define foreign keys without `index=True`:
- `SymbolModel.file_id`, `SymbolModel.repository_id`
- `ReferenceModel.file_id`, `ReferenceModel.repository_id`
- And similar across all child tables

This causes full table scans on FK lookups and joins.

### 4.8 Settings Configuration Incomplete

`src/inxr2/infrastructure/config/settings.py` has TODO comments for indexing configuration, search limits, grammar paths, and logging configuration. Only `database_url`, `api_host`, and `api_port` are configured.

---

## 5. Refactoring Priority Matrix

| # | Item | Effort | Impact | Priority |
|---|------|--------|--------|----------|
| 1 | Fix `parser_service: Any` type hints | Low | Low | Quick win |
| 2 | Add `ParserServicePort` inheritance to `TreeSitterService` | Low | Low | Quick win |
| 3 | Replace broad `except Exception` with specific types | Low | Medium | **High** |
| 4 | Extract shared subquery builders | Medium | High | **High** |
| 5 | Create `BaseSQLAlchemyRepository` for CRUD | Medium | High | **High** |
| 6 | Add FK indexes to ORM models | Low | High | **High** |
| 7 | Prune ~25 low-value tests | Low | Medium | Medium |
| 8 | Create API response converters | Low-Medium | High | Medium |
| 9 | Create `@handle_file_resolution_errors` decorator | Low | Medium | Medium |
| 10 | Fix `save_many()` refresh loop | Low | Medium | Medium |
| 11 | Split `file_adapter.py` into focused adapters | Medium-High | High | Medium |
| 12 | Refactor CodeHeader into hooks + sub-components | Medium | High | Medium |
| 13 | Add structured logging | Medium | High | Medium |
| 14 | Fix CORS for production | Low | High | Before deploy |
| 15 | Add health check with DB probe | Low | Medium | Before deploy |
| 16 | Protect `reset_database` with confirmation | Low | High | Before deploy |

---

## 6. Positive Findings

The codebase has many strengths worth preserving:

1. **Perfect domain isolation** -- Zero framework contamination in the domain layer
2. **Frozen dataclasses throughout** -- All entities and value objects are immutable
3. **Fakes over mocks** -- Test doubles implement actual port interfaces
4. **Contract tests** -- 24 parametrized tests verify fake-vs-Postgres parity
5. **Comprehensive use case testing** -- All 20+ use cases have behavioral tests
6. **Clear layer separation** -- 4 well-defined layers with proper dependency direction
7. **Centralized DI** -- Single `dependencies.py` file wires all adapters
8. **Bidirectional mappers** -- Clean domain-to-ORM conversion with field name mapping
9. **Strong type hints** -- mypy-compatible throughout with proper async/await
10. **Self-contained tests** -- Tests use `tmp_path` fixtures and create controlled data
