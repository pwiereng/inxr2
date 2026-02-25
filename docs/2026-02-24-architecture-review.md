# Architecture Review — 2026-02-24

## Executive Summary

Comprehensive review of the INXR2 codebase covering clean architecture adherence, DRY violations, test quality, coupling/inefficiencies, and frontend architecture. The codebase is well-structured overall with strong clean architecture foundations, but has specific areas that warrant refactoring before adding more language support.

**Overall Score: B+** — Solid architecture with targeted improvements needed.

---

## 1. Clean Architecture Adherence

**Score: 93/100**

### Violations Found

#### HIGH: Application layer imports GitPython exceptions (3 files)

The application layer should not depend on external framework types. Three use cases import `git.exc` directly:

| File | Line | Import |
|------|------|--------|
| `application/use_cases/commits/list_commits.py` | 11 | `from git.exc import BadName, GitCommandError` |
| `application/use_cases/files/get_file_history.py` | 11 | `from git.exc import BadName, GitCommandError` |
| `application/use_cases/repositories/get_repository_tree.py` | 6 | `from git.exc import BadName, GitCommandError` |

**Impact:** If GitPython is replaced, these exception handlers break.

**Fix:** Define domain-agnostic exception types (e.g., `GitOperationError`) in `domain/exceptions/` and have `GitServicePort` implementations translate GitPython exceptions into domain exceptions.

#### MEDIUM: CLI adapter imports directly from infrastructure

| File | Line | Import |
|------|------|--------|
| `adapters/cli/commands/index_command.py` | 25 | `from inxr2.infrastructure.database.connection import DatabaseConnection` |

**Impact:** Couples CLI directly to infrastructure; harder to test in isolation.

**Fix:** Receive `DatabaseConnection` via dependency injection instead of direct instantiation.

### Clean Patterns Verified

- Domain layer: 100% clean — no framework imports, proper validation in `__post_init__`
- Application ports: Properly abstract external dependencies with frozen dataclasses
- No cross-adapter imports (API doesn't import CLI, persistence doesn't import external)
- Proper use of `TYPE_CHECKING` blocks to avoid circular dependencies
- Mappers properly separate domain entities from ORM models

---

## 2. DRY Violations

### HIGH Severity

#### 1. Duplicated resolution SQL in `reference_adapter.py` (~55 LOC)

`resolve_references_batch()` (lines 411-500) and `resolve_unlinked_references()` (lines 502-579) execute the exact same 3-pass resolution SQL. The only difference is `LIMIT :batch_size` in the batched version.

**Fix:** Extract `_execute_resolution_pass(pass_table, join_clause, repo_id, limit=None)` — both methods call it 3 times with appropriate parameters.

### MEDIUM Severity

#### 2. `save_many` with timestamp pattern (3 adapters, ~25 LOC)

`symbol_adapter.py`, `reference_adapter.py`, `text_content_adapter.py` all have identical `save_many` implementations with `indexed_at` timestamp setting.

**Fix:** Add `save_many` to `BaseSQLAlchemyRepository` with optional `set_indexed_at` flag.

#### 3. `delete_by_repository` / `count_by_repository` (5 adapters, ~35 LOC)

Five nearly identical implementations across adapters.

**Fix:** Add to `BaseSQLAlchemyRepository` using `self._model_class`.

#### 4. Regex/like search query building (3 files, ~20 LOC)

`symbol_adapter.search_by_name`, `reference_adapter.search_by_text`, and `postgres_text_search.py` all have identical regex vs like/ilike query building logic.

**Fix:** Extract `build_text_match_filter(column, text, mode, case_sensitive)` into `regex_utils.py` or `query_builders.py`.

#### 5. Named type declaration extraction in parsers (~90 LOC)

Java parser has 5 instances, C# parser has 6 instances of nearly identical type declaration processing (find identifier child, build qualified name, append symbol).

**Fix:** Extract `_extract_named_type_declaration(node, kind, scope, ...)` into `BaseLanguageParser`.

#### 6. File resolution boilerplate in `files.py` API routes (~30 LOC)

Four endpoints repeat the same validate + resolve block.

**Fix:** Extract helper `_resolve_file(use_case, repo, path, commit, branch)`.

#### 7. `SymbolResponse` construction in `symbols.py` (~20 LOC)

Two endpoints have identical 16-line list comprehensions for symbol-to-response conversion.

**Fix:** Add `symbol_search_result_to_response()` converter in `converters.py`.

### LOW Severity

- Comment node dict construction duplicated across 4 parsers (~30 LOC)
- `find_by_ids` pattern across 3 adapters (~15 LOC)
- Dual API clients in frontend (`api-client.ts` vs `api.ts`) — `api-client.ts` appears legacy
- `delete_by_file` pattern across 3 adapters (~12 LOC)
- `extract_function_name` duplication in C parser (~20 LOC)

**Total estimated LOC reduction: ~457 lines**

---

## 3. Coupling & Inefficiencies

### God Files / High LOC

#### Backend
| File | LOC | Issue |
|------|-----|-------|
| `treesitter/csharp_parser.py` | 1,306 | Massive builtin lists + grammar parsing |
| `treesitter/java_parser.py` | 996 | Same pattern |
| `application/ports/repositories.py` | 932 | 9 port interfaces in single file |
| `adapters/external/git_service.py` | 883 | 15+ methods, poor cohesion |
| `treesitter/c_parser.py` | 791 | Same builtin lists pattern |
| `adapters/cli/commands/index_command.py` | 747 | Mixed signal handling, DB reset, indexing |
| `cli.py` | 733 | 30+ Click commands in one file |
| `treesitter/python_parser.py` | 738 | Same pattern |
| `adapters/api/routes/files.py` | 623 | Multiple endpoint types bundled |
| `persistence/repositories/reference_adapter.py` | 579 | Complex multi-pass resolution |

#### Frontend
| File | LOC | Issue |
|------|-----|-------|
| `hooks/useBrowseState.ts` | 1,346 | God hook — URL, data, diff, refs all in one |
| `pages/Search.tsx` | 1,049 | Search logic, filtering, pagination, rendering |
| `pages/Browse.tsx` | 865 | File viewing, blame, diffs, references |
| `components/DiffCodeViewer.tsx` | 755 | Complex but at acceptable limit |

### Specific Coupling Issues

1. **`ports/repositories.py` (932 LOC)** — 9 port interfaces in one file. Should split into `ports/repositories/` directory with one file per port.

2. **`infrastructure/dependencies.py` (480 LOC)** — 40+ DI functions creating tight coupling. Any use case constructor change requires updating this file.

3. **Language parser builtin lists** — ~2,000 LOC of builtin type/constant dicts across 4 parsers. Should extract to data files or a `builtins/` directory.

### Type Safety Issues

- **13 `# type: ignore` comments** across 7 files — mostly `asyncio.gather` result unpacking and SQLAlchemy `rowcount`
- **23 files with `Any` annotations** — mostly legitimate (git tree traversal, kwargs), but `postgres_text_search.py` tsvector column and `cli.py` kwargs could be better typed

### N+1 Query Patterns: None Found

Bulk fetching is used correctly throughout — `find_by_ids`, `find_by_repository`, subqueries for latest-file filtering. No database queries inside loops detected.

---

## 4. Test Quality

**Score: B+** — 1,088 tests, 100% use case coverage, but some issues.

### Mock Usage (Against Project Guidelines)

| File | Severity | Issue |
|------|----------|-------|
| `tests/infrastructure/test_dependencies.py` | HIGH | Heavy `MagicMock` usage for DI wiring tests |
| `tests/infrastructure/test_settings.py` | MEDIUM | `@patch.dict(os.environ)` for env vars |
| `tests/infrastructure/test_database_connection.py` | MEDIUM | Same `@patch.dict` pattern |

### Low-Value Tests

| File | Lines | Issue |
|------|-------|-------|
| `tests/unit/domain/test_value_objects.py` | 68-71 | `test_symbol_kind_is_string()` — redundant with `test_symbol_kinds_exist()` |
| `tests/unit/domain/test_exceptions.py` | 6-22 | Tests basic dataclass creation, not business logic |

### Large Test Files (Splitting Candidates)

| File | LOC | Recommendation |
|------|-----|----------------|
| `tests/integration/api/test_api_endpoints.py` | 2,339 | Split by endpoint type (repos, files, symbols, search) |
| `tests/unit/application/test_default_indexing_orchestrator.py` | 1,876 | Acceptable — orchestrator is complex |
| `tests/integration/adapters/test_resolve_references.py` | 1,469 | Acceptable |
| Language parser tests (C#, C, Java) | 1,000-1,288 | Could split by construct type |

### Coverage Summary

- **Use cases:** 27/27 (100%) have tests
- **Adapters:** All covered
- **Contract tests:** Properly implemented in `tests/contract/` for fake-vs-Postgres parity
- **Test doubles:** Properly implement port interfaces via `tests/fixtures/test_doubles.py`

---

## 5. Frontend Architecture

**Score: B+** — Strong type safety, some structural improvements needed.

### Strengths

- **Zero `any` types** — excellent TypeScript strictness with `strict: true`
- **Consistent MUI `sx` prop styling** — no style inconsistency
- **Proper XSS prevention** — `sanitizeHeadline()` for `ts_headline` output, Prism HTML handled safely
- **Good API error handling** — consistent pattern with proper HTTP error detection
- **No debug `console.log` statements** — only appropriate `console.error` for API failures

### Issues

#### Missing Error Boundaries

No `<ErrorBoundary>` components found. Component crashes propagate to page level with blank screens.

**Fix:** Wrap major components (Browse, Search, CodeViewer) with error boundaries providing recovery options.

#### Prop Drilling in Browse Page

`Browse.tsx` passes 9+ props through to `CodeViewer`, `DiffCodeViewer`, and `ReferencesPanel` including nested callbacks.

**Fix:** Extract callback handlers into custom hooks; consider Context for deeply-passed props (repository, branch, commit info).

#### `useBrowseState` Hook Too Large (1,346 LOC)

Single hook managing URL state, data loading, diff mode, references panel, and symbol interactions.

**Fix:** Split into focused hooks:
- `useBrowseUrlState` — URL parameter parsing
- `useBrowseData` — Data fetching
- `useBrowseDiffState` — Diff management
- `useBrowseRefsState` — References panel

#### Missing Component Tests

| Component | LOC | Priority |
|-----------|-----|----------|
| `CommitSelect.tsx` | 184 | HIGH — complex logic, no tests |
| `Browse.tsx` (page) | 865 | MEDIUM — large page, no tests |
| `Files.tsx` (page) | 219 | LOW |
| `History.tsx` (page) | 240 | LOW |
| `Repositories.tsx` (page) | 134 | LOW |

---

## 6. Recommended Action Items

### Tier 1 — High Impact (Do Before Adding Languages)

| # | Issue | Est. LOC | Impact |
|---|-------|----------|--------|
| 1 | Abstract GitPython exceptions behind domain types | ~50 | Fixes clean architecture violation; enables git library swap |
| 2 | Extract resolution pass helper in `reference_adapter.py` | -55 | Eliminates highest-risk DRY violation |
| 3 | Move `save_many`/`delete_by_repository`/`count_by_repository` to `BaseSQLAlchemyRepository` | -60 | Completes the base repository refactoring from PR #106 |
| 4 | Extract `_extract_named_type_declaration` into `BaseLanguageParser` | -90 | Essential before adding more language parsers |
| 5 | Extract builtin constants to data files | -2,000 | Massively reduces parser file sizes |

### Tier 2 — Medium Impact (Improves Maintainability)

| # | Issue | Impact |
|---|-------|--------|
| 6 | Split `ports/repositories.py` into individual files | Better module organization |
| 7 | Extract `build_text_match_filter` for regex/like queries | DRY improvement across 3 files |
| 8 | Add frontend Error Boundaries | User experience on crashes |
| 9 | Split `useBrowseState` into focused hooks | Frontend maintainability |
| 10 | Replace MagicMock in infrastructure tests with proper fakes | Aligns with project testing philosophy |

### Tier 3 — Cleanup (Opportunistic)

| # | Issue | Impact |
|---|-------|--------|
| 11 | Extract file resolution helper in `files.py` routes | Minor DRY |
| 12 | Add `SymbolResponse` converter in `converters.py` | Minor DRY |
| 13 | Split `test_api_endpoints.py` by endpoint type | Test organization |
| 14 | Remove legacy `api-client.ts` | Code cleanup |
| 15 | Remove low-value domain tests | Test hygiene |
| 16 | Add CommitSelect.tsx tests | Frontend coverage |
