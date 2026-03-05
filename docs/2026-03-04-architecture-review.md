# Architecture Review — 2026-03-04

## Executive Summary

Follow-up review of the INXR2 codebase, building on the [2026-02-24 review](archived/2026-02-24-architecture-review.md). All 8 Tier 1 items from the previous review have been completed. The codebase continues to mature with strong clean architecture foundations and excellent test coverage. Remaining work is primarily Tier 2/3 cleanup and new parser improvements.

**Overall Score: A-** — Significant improvement from B+. All high-impact refactoring completed.

---

## Previous Review Status

### Tier 1 Items (All COMPLETED)

| # | Issue | Status | Notes |
|---|-------|--------|-------|
| 1 | Abstract GitPython exceptions behind domain types | COMPLETED | Domain exceptions in `domain/exceptions/`, `GitServicePort` translates |
| 2 | Extract resolution pass helper in `reference_adapter.py` | COMPLETED | `_execute_resolution_pass()` + class-level `_PASS1_JOIN`/`_PASS2_JOIN`/`_PASS3_JOIN` constants |
| 3 | Move `save_many`/`delete_by_repository`/`count_by_repository` to base | COMPLETED | `BaseSQLAlchemyRepository` provides shared implementations |
| 4 | Extract `_extract_named_type_declaration` into `BaseLanguageParser` | COMPLETED | Shared extraction in base parser |
| 5 | Extract builtin constants to data files | COMPLETED | ~2,000 LOC removed from parser files |

### Tier 2 Items (All COMPLETED)

| # | Issue | Status | Notes |
|---|-------|--------|-------|
| 6 | Split `ports/repositories.py` into individual files | COMPLETED | Now `ports/repositories/` directory with one file per port |
| 7 | Extract `build_text_match_filter` for regex/like queries | COMPLETED | Shared utility extracted |
| 8 | Add frontend Error Boundaries | COMPLETED | Error boundaries wrap major components |
| 9 | Split `useBrowseState` into focused hooks | COMPLETED | Split into `useBrowseUrlState`, `useBrowseData`, etc. |
| 10 | Replace MagicMock in infrastructure tests | COMPLETED | Only 1 file uses `patch` (justified — parser error simulation) |

### Tier 3 Items (Partially Complete)

| # | Issue | GH Issue | Status |
|---|-------|----------|--------|
| 11 | Extract file resolution helper in `files.py` routes | #117 | OPEN |
| 12 | Add `SymbolResponse` converter in `converters.py` | #118 | OPEN |
| 13 | Split `test_api_endpoints.py` by endpoint type | #119 | OPEN |
| 14 | Remove legacy `api-client.ts` | #120 | OPEN (still 80 LOC) |
| 15 | Remove low-value domain tests | #121 | OPEN |
| 16 | Add CommitSelect.tsx tests | #122 | OPEN |

---

## 1. Clean Architecture Adherence

**Score: 96/100** (up from 93)

### Improvements Since Last Review

- GitPython exceptions fully abstracted behind domain types
- Application layer is now 100% clean — no external framework imports
- `BaseSQLAlchemyRepository` properly encapsulates shared persistence logic

### Remaining Violations

#### MEDIUM: CLI adapter imports directly from infrastructure and persistence (5 imports)

The CLI commands bypass dependency injection, directly importing infrastructure and persistence layer classes:

| File | Line | Import |
|------|------|--------|
| `adapters/cli/commands/index_command.py` | 25 | `from inxr2.infrastructure.database.connection import DatabaseConnection` |
| `adapters/cli/commands/index_command.py` | 296 | `from inxr2.adapters.persistence.repositories import (Postgres*Repository × 7)` |
| `adapters/cli/commands/index_command.py` | 478 | `from inxr2.adapters.persistence.repositories import (Postgres*Repository × 2)` |
| `adapters/cli/commands/status_command.py` | 35 | `from inxr2.infrastructure.database.connection import DatabaseConnection` |
| `adapters/cli/commands/status_command.py` | 40 | `from inxr2.adapters.persistence.repositories import (Postgres*Repository × 2)` |

**Impact:** CLI is coupled to PostgreSQL implementation. Cannot easily swap database or test CLI commands in isolation without a real database.

**Mitigating factor:** Lines 296/478/40 are deferred imports inside function bodies, reducing import-time coupling. The `status_command.py` accepts optional injected repositories for testing.

**Fix:** Create a CLI-specific DI container or factory that provides repositories via ports. This is the same recommendation from the 2026-02-24 review (previously rated MEDIUM).

### Clean Patterns Verified

- Domain layer: 100% clean — no framework imports
- Application layer: 100% clean — GitPython exceptions fully abstracted
- No cross-adapter imports
- Proper use of `TYPE_CHECKING` blocks
- Mappers properly separate domain entities from ORM models
- Repository pattern consistently applied with ports

---

## 2. DRY Violations

### MEDIUM Severity

#### 1. Extension filter `(none)` sentinel logic (5 files, ~100 LOC) — GH #183

Five files implement identical logic for handling the `(none)` extension filter sentinel:

| File | Lines |
|------|-------|
| `persistence/repositories/symbol_adapter.py` | 94–101 |
| `persistence/repositories/reference_adapter.py` | 199–206 |
| `persistence/repositories/file_search_adapter.py` | 68–160 |
| `persistence/repositories/postgres_text_search.py` | 133–140 |
| `api/routes/search.py` | 35–42 |

Pattern: `real_exts = [e for e in extensions if e != "(none)"]` / `has_none = "(none)" in extensions`

**Fix:** Extract `split_extension_filter(extensions) -> tuple[list[str], bool]` into a shared utility. Issue #183 already tracks this.

#### 2. URLSearchParams building in frontend (14+ functions, ~140 LOC)

Multiple API functions in `frontend/src/lib/api.ts` manually build URLSearchParams with repetitive patterns. Each function individually constructs params, appends optional values, and builds the URL string.

**Fix:** Extract `buildQueryParams(params: Record<string, string | number | undefined>)` helper that skips undefined values.

#### 3. Repo name validator duplication — GH #158

Repository name validation logic exists in both domain layer and API route layer.

**Fix:** Single source of truth in domain layer, imported by API routes. Issue #158 tracks this.

### LOW Severity

| # | Issue | GH Issue | Est. LOC |
|---|-------|----------|----------|
| 4 | File resolution boilerplate in `files.py` routes | #117 | ~30 |
| 5 | `SymbolResponse` construction in `symbols.py` | #118 | ~20 |
| 6 | Parser `get_text()` helper duplicated across parsers | — | ~45 |

### Previously Fixed

- Resolution SQL passes: **FIXED** — `_execute_resolution_pass()` helper extracted
- `save_many`/`delete_by_repository`/`count_by_repository`: **FIXED** — moved to `BaseSQLAlchemyRepository`
- Named type declaration extraction: **FIXED** — moved to `BaseLanguageParser`
- Regex/like search query building: **FIXED** — `build_text_match_filter` extracted

**Total estimated remaining LOC reduction: ~335 lines**

---

## 3. Code Structure & Coupling

### Large Files

#### Backend

| File | LOC | Change | Assessment |
|------|-----|--------|------------|
| `adapters/cli/commands/index_command.py` | 748 | — | Mixed concerns (signal handling, DB reset, indexing). Consider splitting. |
| `cli.py` | 742 | — | 4 command groups + 6 commands. Acceptable — Click's decorator pattern inflates LOC. |
| `application/ports/services.py` | 641 | — | **Still monolithic.** 7 ABCs + 7 dataclasses in one file. Should split. |
| `adapters/persistence/repositories/reference_adapter.py` | ~550 | Improved | Resolution logic now cleaner after helper extraction. |

#### Frontend

| File | LOC | Change | Assessment |
|------|-----|--------|------------|
| `pages/Search.tsx` | 1,083 | +34 | Search logic, filtering, pagination, rendering. Could benefit from hook extraction. |
| `pages/Browse.tsx` | 942 | +77 | Grew since last review. File viewing, blame, diffs, references. |
| `components/DiffCodeViewer.tsx` | ~755 | — | Complex but at acceptable limit. |

### Structural Recommendations

#### 1. Split `application/ports/services.py` (641 LOC)

Currently contains 14 classes spanning 5 distinct concerns:

| Port | Methods | Related DTOs |
|------|---------|--------------|
| `ParserServicePort` | 3 | — |
| `GitServicePort` | 13 | `CommitInfo`, `ChangedFiles`, `RepositoryInfo`, `BlameLineInfo` |
| `ConfigServicePort` | 2 | — |
| `FileSystemPort` | 6 | `FileStat` |
| `IndexingOrchestratorPort` | 1 | — |
| `TextSearchPort` | 1 | `TextSearchResult`, `TextSearchQuery` |
| `PlaintextParserPort` | 2 | — |

**Fix:** Split into `ports/services/` directory: `git_service.py`, `parser_service.py`, `config_service.py`, `filesystem_service.py`, `text_search_service.py`, `indexing_orchestrator.py`.

#### 2. Legacy `api-client.ts` (80 LOC) — GH #120

Still exists alongside the active `api.ts`. Should be removed to avoid confusion.

---

## 4. Test Quality

**Score: A-** (up from B+)

### Test Coverage Summary

| Suite | Tests | Change |
|-------|-------|--------|
| Backend (pytest) | 1,432 | +344 since last review |
| Frontend (vitest) | 519 | — |
| **Total** | **1,951** | +344 |

### Mock Usage

Excellent adherence to "fakes over mocks" philosophy:

| File | Import | Justification |
|------|--------|---------------|
| `tests/adapters/external/test_parser_error_handling.py` | `unittest.mock.patch` | Forces `RuntimeError` in tree-sitter parser — hard to simulate with fakes |
| `tests/fixtures/test_doubles.py` | `unittest.mock.Mock` | **Docstring only** — shows anti-pattern example, never instantiated |

### Remaining Test Issues

#### MEDIUM: CodeHeader subcomponents lack individual tests — GH #122

`CodeHeader.test.tsx` (697 LOC) tests the composed component as an integration test, which is valuable but doesn't cover edge cases in individual subcomponents:

| Component | Individual Test File |
|-----------|---------------------|
| `CommitSelect.tsx` | None |
| `CommitDateIndicator.tsx` | None |
| `NavigationTabs.tsx` | None |
| `RepositorySelect.tsx` | None |
| `BranchSelect.tsx` | `BranchSelector.test.tsx` (494 LOC) |

#### LOW: Remaining cleanup items

| Issue | GH Issue |
|-------|----------|
| Low-value domain tests (dataclass creation) | #121 |
| Split `test_api_endpoints.py` (2,339 LOC) by endpoint type | #119 |

### Test Strengths

- 100% use case coverage (all 27+ use cases have tests)
- Contract tests in `tests/contract/` verify fake-vs-Postgres parity
- Test doubles properly implement port interfaces
- Database isolation via savepoint/truncation fixtures
- No N+1 query patterns detected

---

## 5. Open Issues Cross-Reference

### Issues That Map to Architecture Findings

| GH Issue | Title | Maps To |
|----------|-------|---------|
| #183 | Extract shared `(none)` extension sentinel helper | DRY §2.1 |
| #158 | Extract shared repo name validator | DRY §2.3 |
| #117 | Extract file resolution helper in `files.py` | DRY §2.4 |
| #118 | Add SymbolResponse converter | DRY §2.5 |
| #120 | Remove legacy `api-client.ts` | Structure §3.2 |
| #119 | Split `test_api_endpoints.py` by endpoint type | Tests §4 |
| #121 | Remove low-value domain tests | Tests §4 |
| #122 | Add CommitSelect.tsx tests | Tests §4 |
| #184 | Add frontend extension filter tests | Tests §4 |

### Bug Issues (Should Fix Before Feature Work)

| GH Issue | Title | Tier | Impact |
|----------|-------|------|--------|
| #204 | Parser doesn't extract variable declarations (let/const/var) in JS/TS | Tier 1 | Missing symbol definitions for most common JS/TS declarations |
| #205 | Indexer should skip minified/vendor JS files | Tier 2 | Noise references polluting search results |
| #206 | Go parser drops method name from chained selector calls | Tier 2 | Incorrect Go reference extraction |
| #208 | Blame commit links should navigate to History tab | Tier 2 | Broken navigation when commit isn't indexed |
| #209 | References panel should show full file path for duplicates | Tier 2 | Ambiguous references when multiple definitions exist |

### Feature Issues (For Reference)

| GH Issue | Title | Tier |
|----------|-------|------|
| #163 | Improve Java symbol/reference extraction | Tier 2 |
| #164 | Improve C# symbol/reference extraction | Tier 2 |
| #173 | Add Terraform/HCL parser support | Tier 2 |
| #177 | MCP interface for querying INXR2 | Tier 2 |
| #185 | Link unindexed blame commits to external URL | Tier 2 |
| #152 | Word-based chunking for text content | Tier 2 |
| #207 | Collapsible comment blocks | Tier 3 |
| #210 | Hyperlink issue tracker references in commits | Tier 3 |
| #186 | Hierarchy tab (browse by class/method) | Tier 3 |
| #175 | Index 3rd-party package symbols | Tier 3 |
| #176 | Retro LXR-style UI mode | Tier 3 |
| #178 | Multi-dimensional global search | Tier 3 |
| #179 | File churn heat-map | Tier 3 |

---

## 6. Recommended Action Items

### Tier 1 — High Impact (Do Before Adding Features)

| # | Issue | GH # | Est. Effort | Impact |
|---|-------|------|-------------|--------|
| 1 | Fix JS/TS variable declaration extraction | #204 | Small | Most common JS/TS symbol type is completely missing |
| 2 | Skip minified/vendor JS files | #205 | Small | Eliminates noise from reference search results |
| 3 | Fix Go chained selector method extraction | #206 | Small | Incorrect Go cross-references |

### Tier 2 — Medium Impact (Improves Maintainability)

| # | Issue | GH # | Est. Effort | Impact |
|---|-------|------|-------------|--------|
| 4 | Extract `(none)` extension filter helper | #183 | Tiny | DRY improvement across 5 files |
| 5 | Split `services.py` into individual port files | — | Small | 641 LOC → ~6 focused files |
| 6 | Fix blame commit link navigation | #208 | Small | Better user experience |
| 7 | Show full file path in references panel | #209 | Small | Disambiguates duplicate definitions |
| 8 | Extract repo name validator | #158 | Tiny | DRY improvement |
| 9 | Add extension filter frontend tests | #184 | Small | Coverage for Select All/Deselect All edge cases |
| 10 | CLI DI container (remove infrastructure imports) | — | Medium | Fixes last clean architecture violations |

### Tier 3 — Cleanup (Opportunistic)

| # | Issue | GH # | Est. Effort | Impact |
|---|-------|------|-------------|--------|
| 11 | Remove legacy `api-client.ts` | #120 | Tiny | Dead code removal |
| 12 | Remove low-value domain tests | #121 | Tiny | Test hygiene |
| 13 | Extract file resolution helper | #117 | Small | Minor DRY |
| 14 | Add SymbolResponse converter | #118 | Small | Minor DRY |
| 15 | Split `test_api_endpoints.py` | #119 | Small | Test organization |
| 16 | Add CommitSelect.tsx tests | #122 | Small | Frontend coverage |
| 17 | Extract URLSearchParams builder in frontend | — | Small | Minor DRY |

---

## 7. Summary of Progress

The codebase has improved significantly since the 2026-02-24 review:

- **Clean Architecture:** 93 → 96/100. Application layer is now fully clean. Only CLI adapter violations remain.
- **DRY:** All high-severity violations resolved. Remaining items are medium/low severity (~335 LOC reduction potential).
- **Test Quality:** B+ → A-. 1,951 tests (+344), mock usage nearly eliminated, contract tests ensure parity.
- **Code Structure:** Major improvements (ports split, useBrowseState split, error boundaries added, builtins extracted). Remaining large files are mostly acceptable or have tracked issues.

**Recommendation:** Fix the three Tier 1 parser bugs (#204, #205, #206) before adding new language parsers or features. The Tier 2 items improve code quality but are not blocking. Tier 3 items are good candidates for opportunistic cleanup during related work.
