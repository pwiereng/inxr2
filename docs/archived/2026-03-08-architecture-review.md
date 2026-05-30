# Architecture Review — 2026-03-08

## Executive Summary

Follow-up review of the INXR2 codebase, building on the [2026-03-04 review](2026-03-04-architecture-review.md). No Tier 1–3 items from the previous review have been completed (all remain open). The codebase has grown with new features (Logical View, dependency tree, MCP tools) since the last review, introducing several new bugs and a significant performance issue. This review adds new findings in adapter test coverage, security posture, and code complexity.

**Overall Score: A-** — Holding steady. New features added without addressing previous cleanup items. Test coverage gaps in critical adapters are the most concerning new finding.

---

## Previous Review Status

### Tier 1 Items (From 2026-03-04)

| # | Issue | GH # | Status | Notes |
|---|-------|------|--------|-------|
| 1 | Fix JS/TS variable declaration extraction | #204 | CLOSED | Resolved since last review |
| 2 | Skip minified/vendor JS files | #205 | CLOSED | Resolved since last review |
| 3 | Fix Go chained selector method extraction | #206 | CLOSED | Resolved since last review |

### Tier 2 Items (From 2026-03-04)

| # | Issue | GH # | Status |
|---|-------|------|--------|
| 4 | Extract `(none)` extension filter helper | #183 | CLOSED |
| 5 | Split `services.py` into individual port files | — | COMPLETED |
| 6 | Fix blame commit link navigation | #208 | CLOSED |
| 7 | Show full file path in references panel | #209 | CLOSED |
| 8 | Extract repo name validator | #158 | CLOSED |
| 9 | Add extension filter frontend tests | #184 | CLOSED |
| 10 | CLI DI container (remove infrastructure imports) | — | OPEN |

### Tier 3 Items (From 2026-03-04)

| # | Issue | GH # | Status |
|---|-------|------|--------|
| 11 | Remove legacy `api-client.ts` | #120 | OPEN |
| 12 | Remove low-value domain tests | #121 | OPEN |
| 13 | Extract file resolution helper | #117 | OPEN |
| 14 | Add SymbolResponse converter | #118 | OPEN |
| 15 | Split `test_api_endpoints.py` | #119 | OPEN |
| 16 | Add CommitSelect.tsx tests | #122 | OPEN |
| 17 | Extract URLSearchParams builder in frontend | #213 | OPEN |

---

## 1. Clean Architecture Adherence

**Score: 95/100** (down from 96 — new violation found)

### Improvements Since Last Review

- `services.py` split into `ports/services/` directory with one file per port (Tier 2 #5 completed)
- Application layer remains clean of framework imports

### Remaining Violations

#### NEW — MEDIUM: Port imports from use cases layer

**File:** `application/ports/services/indexing_orchestrator.py` (lines 8–11)

```python
if TYPE_CHECKING:
    from ...use_cases.indexing.default_orchestrator import IndexingProgress
    from ...use_cases.indexing.orchestrator import (
        IndexRepositoryRequest, IndexRepositoryResponse,
    )
```

**Problem:** The `IndexingOrchestratorPort` interface imports DTOs from the use_cases layer. Ports should only depend on domain entities and value objects, not on use cases. This creates a backward dependency.

**Mitigating factor:** Guarded by `TYPE_CHECKING` — no runtime import. Still architecturally incorrect.

**Fix:** Move `IndexingProgress`, `IndexRepositoryRequest`, `IndexRepositoryResponse`, and `DBQueryStats` from `use_cases/indexing/` to `application/dtos/indexing.py`.

#### ONGOING — MEDIUM: CLI adapter imports directly from infrastructure and persistence

Same as previous review. `index_command.py` and `status_command.py` bypass DI to import `DatabaseConnection` and `Postgres*Repository` classes directly.

**Fix:** Create CLI-specific DI container. Not yet addressed.

### Clean Patterns Verified

- Domain layer: 100% clean — no framework imports
- Application layer: 100% clean (runtime) — only TYPE_CHECKING backward reference
- No cross-adapter imports
- Proper use of `TYPE_CHECKING` blocks
- Mappers properly separate domain entities from ORM models
- Repository pattern consistently applied with ports

### Minor: Weak port return types

Some ports return `dict[str, Any]` instead of typed structures:

| Port | Method | File |
|------|--------|------|
| `ParserServicePort` | `parse_file()` | `ports/services/parser_service.py:30` |
| `ParserServicePort` | `extract_comments()` | `ports/services/parser_service.py:46` |
| `DependencyParserServicePort` | `parse()` | `ports/services/dependency_parser_service.py:29` |

**Fix:** Replace with TypedDict or dataclass definitions. Not a violation, but reduces type safety.

---

## 2. DRY Violations

### MEDIUM Severity (NEW)

#### 1. Test fixture duplication across conftest files (~50 LOC × 3)

Three test conftest files define near-identical repository fixture chains:

| File | Pattern |
|------|---------|
| `tests/unit/application/test_default_indexing_orchestrator.py` | 15+ `@pytest.fixture` for InMemory* repos (lines 101–181) |
| `tests/adapters/persistence/conftest.py` | DB session + adapter fixtures (lines 49–95) |
| `tests/adapters/cli/conftest.py` | DB session + adapter fixtures (lines 48–80) |

**Fix:** Extract shared fixture factory to `tests/conftest_shared.py` or consolidate into root `conftest.py`.

#### 2. API error handling patterns (~20 blocks across 5 route files)

Identical `except → HTTPException` mappings repeated in `files.py`, `repositories.py`, `symbols.py`, `search.py`, `commits.py`:

```python
except RepositoryPathNotFoundError:
    raise HTTPException(status_code=404, detail="Repository path not found")
except BinaryFileError as e:
    raise HTTPException(status_code=400, detail=str(e))
```

**Fix:** Create `adapters/api/exception_handlers.py` with centralized domain→HTTP exception mapping.

#### 3. URLSearchParams building in frontend — GH #213 (unchanged)

14+ API functions in `frontend/src/lib/api.ts` manually build URLSearchParams.

### LOW Severity (Unchanged from previous review)

| # | Issue | GH Issue |
|---|-------|----------|
| 4 | File resolution boilerplate in `files.py` routes | #117 |
| 5 | `SymbolResponse` construction in `symbols.py` | #118 |

### Previously Fixed

- Extension filter `(none)` sentinel: **FIXED** (GH #183)
- Repo name validator: **FIXED** (GH #158)
- `services.py` monolith: **FIXED** — split into `ports/services/` directory

---

## 3. Code Structure & Coupling

### Large / Complex Functions (NEW Findings)

#### HIGH: `ProcessFileUseCase._do_process()` — 230 lines, cyclomatic complexity ~12

**File:** `application/use_cases/indexing/process_file.py` (lines 174–407)

Handles 9 distinct responsibilities in one method: blob hash caching, content reading, hash checking, language detection, file version creation, symbol extraction, reference extraction, comment extraction, non-code file handling.

**Fix:** Extract into focused helpers:
- `_try_fast_path_blob_hash()` → `CacheResult | None`
- `_try_fast_path_content_hash()` → `CacheResult | None`
- `_parse_and_save_symbols()` → `tuple[list[Symbol], int]`
- `_parse_and_save_references()` → `tuple[list[Reference], int]`

#### MEDIUM: Inconsistent error handling status codes

Similar exceptions map to different HTTP codes across route files. Some use `from e`, others `from None`. No centralized strategy.

### Large Files

#### Backend

| File | LOC | Change | Assessment |
|------|-----|--------|------------|
| `adapters/external/git_service.py` | 923 | — | **14 public methods.** Mixes repo caching, file operations, commit queries. Consider splitting. |
| `adapters/cli/commands/index_command.py` | 732 | — | Mixed concerns (signal handling, DB reset, indexing). |
| `application/use_cases/indexing/process_file.py` | 638 | — | **_do_process() is 230 lines.** Needs decomposition. |
| `application/use_cases/indexing/default_orchestrator.py` | 524 | — | Large but well-structured with helper methods. |

#### Frontend

| File | LOC | Change | Assessment |
|------|-----|--------|------------|
| `pages/Search.tsx` | 1,083 | — | Unchanged. Could benefit from hook extraction. |
| `pages/Browse.tsx` | 942 | — | Unchanged. |
| `components/DiffCodeViewer.tsx` | ~755 | — | Complex but at acceptable limit. |

### Structural Recommendations

#### 1. Split `git_service.py` (923 LOC)

14 methods spanning 3 concerns: repo management/caching, file content operations, commit/history queries.

**Fix:** Split into `git_repository.py`, `git_file_reader.py`, `git_commit_reader.py` or extract repo caching into a separate concern.

#### 2. Centralize magic numbers

Scattered batch sizes, query limits, and thresholds across 12+ files:

| Value | Files |
|-------|-------|
| `batch_size = 1000` | reference_adapter.py, commit_repository_port.py, process_file.py |
| `limit = 100` | commit_adapter.py, reference_adapter.py, repositories.py |
| `limit = 50` | symbol_adapter.py, symbols use_case |
| `MAX_TSVECTOR_CONTENT_BYTES = 750_000` | process_file.py |
| `MAX_TEXT_QUERY_LENGTH = 500` | search.py |
| `MAX_REGEX_LENGTH = 500` | regex_utils.py |

**Fix:** Create `domain/constants.py` with `DatabaseLimits`, `QueryDefaults`, `APILimits` groupings.

#### 3. Inconsistent adapter naming

Most adapters use `PostgresXxxRepository` but two use `Adapter` suffix:

| Class | File |
|-------|------|
| `PostgresTextSearchAdapter` | `postgres_text_search.py` |
| `FileSearchAdapter` | `file_search_adapter.py` |

**Fix:** Rename to `PostgresTextSearchRepository` and `PostgresFileSearchRepository`.

---

## 4. Test Quality

**Score: B+** (down from A- — critical adapter test gaps identified)

### Test Count

| Suite | Tests | Change |
|-------|-------|--------|
| Backend (pytest) | ~1,432 | — |
| Frontend (vitest) | ~519 | — |
| **Total** | **~1,951** | — |

### CRITICAL: Missing Adapter Tests

Four major persistence adapters have **zero** dedicated test files:

| Adapter | LOC | Tests | Risk |
|---------|-----|-------|------|
| `symbol_adapter.py` | 736 | **NONE** | CRITICAL — core search functionality |
| `reference_adapter.py` | 399 | **NONE** | CRITICAL — 3-pass resolution algorithm with raw SQL |
| `dependency_adapter.py` | 100 | **NONE** | HIGH — dependency feature untested at adapter level |
| `index_status_adapter.py` | 91 | **NONE** | HIGH — upsert logic untested |

These are tested indirectly via use case tests and contract tests, but no adapter-level integration tests verify their SQL queries, filtering combinations, or error paths.

**Fix:** Create adapter integration test files:
- `tests/adapters/persistence/test_symbol_adapter.py` (~80 tests)
- `tests/adapters/persistence/test_reference_adapter.py` (~60 tests)
- `tests/adapters/persistence/test_dependency_adapter.py` (~25 tests)
- `tests/adapters/persistence/test_index_status_adapter.py` (~15 tests)

### MEDIUM: Frontend Coverage (~15%)

64 source files, only 10 test files. Major untested areas:

| Category | Untested |
|----------|----------|
| Pages | Browse, Dependencies, Files, History, LogicalView, Repositories, Search |
| Components | CodeHeader children, CodeViewer, DiffCodeViewer, FileTree, ReferencesPanel, SymbolSearch |
| Hooks | useBrowseDiffState, useBrowseRefsState, useBrowseUrlState |

### LOW: Test Quality Issues (Unchanged)

| Issue | GH Issue |
|-------|----------|
| Low-value domain tests (dataclass creation) | #121 |
| Split `test_api_endpoints.py` (2,339 LOC) | #119 |
| Add CommitSelect.tsx tests | #122 |

### Test Strengths

- 100% use case coverage (all 27+ use cases have tests)
- Contract tests in `tests/contract/` verify fake-vs-Postgres parity (1,812 LOC)
- Test doubles properly implement port interfaces
- Database isolation via savepoint/truncation fixtures
- Nearly zero mock usage (only 1 justified `patch` for parser error simulation)

---

## 5. Security Review (NEW Section)

**Overall: Safe for local development tool. Not production-ready for multi-user deployment.**

### Findings

| Category | Severity | Status | Notes |
|----------|----------|--------|-------|
| SQL Injection | LOW | ✅ Safe | All queries parameterized via SQLAlchemy ORM |
| Command Injection | LOW | ✅ Safe | GitPython library used, no shell execution |
| Path Traversal | LOW | ✅ Safe | `validation.py` rejects `..`, absolute paths |
| Input Validation | GOOD | ✅ Safe | Multi-layer Pydantic + domain validation |
| YAML Deserialization | LOW | ✅ Safe | Uses `yaml.safe_load()` |
| Secrets Management | GOOD | ✅ Safe | Dev/prod separation, `.env.prod` gitignored |
| Error Info Leakage | LOW | ✅ Safe | Generic error messages, no stack traces |

### Issues Requiring Attention

#### MEDIUM: Frontend ReDoS validation missing

**File:** `frontend/src/lib/highlightMatches.tsx` (lines 46–58)

Backend has excellent ReDoS protection via `regex_utils.py` (length limit + dangerous pattern detection). Frontend compiles user-supplied regex directly with `new RegExp()` — no validation.

**Fix:** Port backend `validate_regex_pattern()` logic to frontend before `new RegExp()` compilation.

#### MEDIUM: XSS — `dangerouslySetInnerHTML` used in 6 locations

Files: `Search.tsx`, `CodeViewer.tsx`, `DiffCodeViewer.tsx` (×4), `MarkdownViewer.tsx`

Current `sanitizeHeadline()` function escapes HTML entities then restores safe `<mark>` tags — adequate for trusted data sources. For defense-in-depth, consider adding Content Security Policy headers and/or DOMPurify.

#### MEDIUM: CORS configuration overly permissive

**File:** `infrastructure/fastapi/app.py` (lines 26–35)

- `allow_methods=["*"]` — should be `["GET", "POST"]`
- `allow_credentials=True` — enables cookie-based CSRF if auth ever added
- `allow_headers=["*"]` — no header whitelist

Acceptable for local dev; should be tightened for any shared/production deployment.

#### LOW: No authentication (by design)

All 30+ API endpoints are publicly accessible. Correct for a single-user local tool. Would need JWT/API key auth for multi-user deployment.

---

## 6. Open Issues Cross-Reference

### Issues That Map to Architecture Findings

| GH Issue | Title | Maps To |
|----------|-------|---------|
| #117 | Extract file resolution helper in `files.py` | DRY §2 |
| #118 | Add SymbolResponse converter | DRY §2 |
| #119 | Split `test_api_endpoints.py` by endpoint type | Tests §4 |
| #120 | Remove legacy `api-client.ts` | Cleanup |
| #121 | Remove low-value domain tests | Tests §4 |
| #122 | Add CommitSelect.tsx tests | Tests §4 |
| #213 | Extract URLSearchParams builder in frontend | DRY §2 |

### Bug Issues

| GH Issue | Title | Tier | Impact |
|----------|-------|------|--------|
| #275 | Reference resolution scaling bottleneck in 30-day indexing | Tier 1 | ~72% of indexing time; superlinear scaling |
| #285 | Logical View: language URL param ignored on page load | Tier 2 | Language filter not applied on initial load |
| #284 | History commits load twice when navigating from Blame tab | Tier 2 | UX flicker, double network request |
| #282 | Logical View: file count badge doesn't update after language filter | Tier 3 | Cosmetic badge issue |

### Tier 1 Feature Issues

| GH Issue | Title | Size |
|----------|-------|------|
| #239 | Track file renames across commits for seamless time-travel | Big |
| #243 | MCP tool: Call Graph — trace callers and callees N levels deep | Medium |

### Summary by Tier

| Tier | Total | Bugs | Features | MCP | Refactoring | Testing |
|------|-------|------|----------|-----|-------------|---------|
| Tier 1 | 3 | 1 | 1 | 1 | — | — |
| Tier 2 | 19 | 2 | 8 | 6 | — | — |
| Tier 3 | 16 | 1 | 6 | 3 | 6 | 3 |
| **Total** | **38** | **4** | **15** | **10** | **6** | **3** |

---

## 7. Recommended Action Items

### Tier 1 — High Impact (Do Before Adding Features)

| # | Issue | GH # | Est. Effort | Impact |
|---|-------|------|-------------|--------|
| 1 | Fix reference resolution scaling bottleneck | #275 | Medium | ~72% of indexing time; blocks 30-day window scaling |
| 2 | Move indexing DTOs from use_cases to application/dtos | — | Tiny | Fixes port→use_case backward dependency |
| 3 | Add symbol_adapter.py integration tests | — | Medium | 736 LOC of core search logic with zero tests |
| 4 | Add reference_adapter.py integration tests | — | Medium | 3-pass resolution algorithm with zero tests |

### Tier 2 — Medium Impact (Improves Maintainability)

| # | Issue | GH # | Est. Effort | Impact |
|---|-------|------|-------------|--------|
| 5 | Decompose `ProcessFileUseCase._do_process()` | — | Small | 230-line method with complexity ~12 → 4 focused methods |
| 6 | Centralize API error handling | — | Small | Eliminates ~20 duplicated exception→HTTPException blocks |
| 7 | Add frontend ReDoS validation | — | Tiny | Port backend regex validation to frontend |
| 8 | Fix Logical View language param bug | #285 | Small | Language filter broken on page load |
| 9 | Fix History double-load from Blame | #284 | Small | UX regression |
| 10 | Consolidate test fixture factories | — | Small | Eliminates 15+ duplicated fixtures across 3 conftest files |
| 11 | CLI DI container | — | Medium | Removes last clean architecture violations |
| 12 | Add dependency_adapter.py and index_status_adapter.py tests | — | Small | 191 LOC with zero adapter-level tests |
| 13 | Tighten CORS configuration | — | Tiny | Restrict methods/headers for defense-in-depth |
| 14 | Centralize magic numbers into `domain/constants.py` | — | Small | 12+ scattered values consolidated |

### Tier 3 — Cleanup (Opportunistic)

| # | Issue | GH # | Est. Effort | Impact |
|---|-------|------|-------------|--------|
| 15 | Remove legacy `api-client.ts` | #120 | Tiny | Dead code removal |
| 16 | Remove low-value domain tests | #121 | Tiny | Test hygiene |
| 17 | Extract file resolution helper | #117 | Small | Minor DRY |
| 18 | Add SymbolResponse converter | #118 | Small | Minor DRY |
| 19 | Split `test_api_endpoints.py` | #119 | Small | Test organization |
| 20 | Add CommitSelect.tsx tests | #122 | Small | Frontend coverage |
| 21 | Extract URLSearchParams builder in frontend | #213 | Small | Minor DRY |
| 22 | Standardize adapter class naming (Adapter→Repository) | — | Tiny | Naming consistency |
| 23 | Strengthen port return types (`dict[str, Any]` → typed) | — | Small | Type safety |
| 24 | Fix Logical View file count badge | #282 | Small | Cosmetic fix |
| 25 | Fix MCP-10 self-referential test match | #283 | Tiny | Test correctness |

---

## 8. Summary of Progress

Since the 2026-03-04 review:

- **Clean Architecture:** 96 → 95/100. New backward dependency found (port importing from use_cases). `services.py` split completed. CLI violations still present.
- **DRY:** Previous medium items mostly resolved (#183, #158). New findings: test fixture duplication, API error handling duplication.
- **Test Quality:** A- → B+. Critical finding: 4 major persistence adapters (1,326 LOC total) have zero dedicated tests. Frontend coverage remains very low (~15%).
- **Security:** First formal review. Safe for local dev tool. Frontend ReDoS gap and permissive CORS are the main items to address.
- **Open Issues:** 38 open (up from ~25 in March review). 4 new bugs, 10 new MCP tool proposals, file rename tracking (#239) as major new feature.

**Recommendation:** Fix the reference resolution bottleneck (#275) and add adapter integration tests before continuing feature work. The 1,326 lines of untested adapter code represent the largest quality risk — especially `reference_adapter.py` with its raw SQL 3-pass resolution algorithm. The Tier 2 code structure items (decompose `_do_process()`, centralize error handling) are good candidates for cleanup sprints.
