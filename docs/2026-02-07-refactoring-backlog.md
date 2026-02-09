# Refactoring Backlog

**Created:** 2026-02-07
**Branch:** main (create feature branches per item)
**Source:** Consolidated from `archived/2026-02-07-code-review.md` and `archived/2026-02-07-architecture-review.md`

---

## Priority 1: Security & Correctness (MUST FIX)

### 1.1 Fix SQL Injection in Regex Search Mode ✅ DONE
**Severity:** CRITICAL | **Effort:** 4 hours

**Location:** `src/inxr2/adapters/persistence/repositories/postgres_text_search.py:183`

**Issue:** User-supplied regex passed directly to PostgreSQL without validation. Can cause ReDoS or database exhaustion.

**Completed Tasks:**
- [x] Add regex pattern validation (complexity limits, max length)
- [x] Add query timeout for regex operations
- [x] Add tests for malicious regex patterns
- [ ] Document regex limitations in API docs

---

### 1.2 Fix Invalid tsquery Syntax Construction ✅ DONE
**Severity:** CRITICAL | **Effort:** 2 hours

**Location:** `src/inxr2/adapters/persistence/repositories/postgres_text_search.py:204-206`

**Issue:** Special characters (`:`, `!`, `&`, `|`, `(`, `)`) in user input cause PostgreSQL syntax errors.

**Completed Tasks:**
- [x] Replace `to_tsquery()` with `plainto_tsquery()` for keyword mode
- [x] Add error handling for query parsing failures
- [x] Add tests for queries with special characters

---

### 1.3 Fix Python Docstring Detection Bug ✅ DONE
**Severity:** HIGH | **Effort:** 2 hours

**Location:** `src/inxr2/adapters/external/treesitter/python_parser.py:668-684`

**Issue:** Extracts ANY string in function/class, not just first statement (actual docstring).

**Completed Tasks:**
- [x] Track whether non-docstring statement already seen in parent scope
- [x] Add test case for string that's not a docstring
- [x] Verify existing tests still pass

---

### 1.4 Add Input Validation for Search Queries ✅ DONE
**Severity:** HIGH | **Effort:** 2 hours

**Location:** Multiple search endpoints

**Issue:** No max_length on query parameters (DoS vector).

**Completed Tasks:**
- [x] Add `max_length=500` to text search query
- [x] Add `max_length=200` to file search query
- [x] Validate mode parameter against enum values
- [x] Validate source_types and languages against known values

---

## Priority 2: Performance (HIGH IMPACT)

### 2.1 Fix N+1 Queries in File Search ✅ DONE
**Severity:** HIGH | **Effort:** 1 day

**Location:** `src/inxr2/adapters/api/routes/search.py:247-260`

**Issue:** 41 queries for 20 results (1 search + 20 repo + 20 commit lookups).

**Completed Tasks:**
- [x] Add `find_by_ids(ids: list[int])` to `RepositoryPort`
- [x] Add `find_by_ids(ids: list[int])` to `CommitRepositoryPort`
- [x] Implement bulk methods in PostgreSQL adapters
- [x] Update file search endpoint to use bulk fetch
- [x] Add test for bulk methods
- [x] Update test doubles to support bulk methods

---

### 2.2 Fix N+1 Queries in Text Search ✅ DONE
**Severity:** HIGH | **Effort:** 1 day

**Location:** `src/inxr2/application/use_cases/search/search_text_use_case.py:176-224`

**Issue:** 81 queries for 20 results (1 search + 20 repo + 20 file + 20 commit + 20 branch).

**Completed Tasks:**
- [x] Collect all unique IDs before lookup loop
- [x] Use bulk fetch methods (after 2.1 is complete)
- [x] Consider joining data in search query itself (better performance)
- [ ] Add performance test to prevent regression

---

### 2.3 Optimize resolve_references_batch Query ✅ DONE
**Severity:** HIGH | **Effort:** 1 day

**Location:** `src/inxr2/adapters/persistence/repositories/reference_adapter.py:296-380`

**Issue:** The `resolve_references_batch` SQL uses a correlated subquery that runs per-reference in the batch. Scales poorly as symbols/files tables grow across multiple branches.

**Observed:** Indexing `inxr2/automated-testing-agent` branch (187 commits, 663K unresolved refs) took **22 minutes** total. A similar branch (`add-java-support`, 127 commits, 541K unresolved refs) took **3 minutes** — 7x slower despite only 22% more data. The resolving phase dominates total time.

**Root Cause:**
- Correlated subquery in `UPDATE SET target_symbol_id = (SELECT ... WHERE s.name = r.reference_text ...)` executes per row
- Two `JOIN files` per reference (for language matching) multiplies cost
- Performance degrades as more branches add rows to symbols/files tables

**Solution:** Replaced correlated subquery with two-pass `UPDATE ... FROM` using a pre-computed lookup table. Pass 1 resolves same-file references (preferred), pass 2 resolves cross-file with lowest symbol ID as tiebreaker. The lookup (`GROUP BY name` on symbols) is small and joined inside the FROM subquery so LIMIT naturally filters to matchable refs only — unresolvable refs (builtins like `str`, `int`) are excluded without extra computation.

Also carried forward already-resolved `target_symbol_id` during content-hash reference copy (via `CopySymbolsResult.id_mapping`), reducing the number of references that need resolution after cross-branch indexing.

Dropped same-language priority from resolution (was causing expensive file JOINs with negligible benefit).

**Results:** Main branch resolving dropped from **47s → 25s** (~2x faster). Full 14-repo/branch indexing improved significantly.

**Completed Tasks:**
- [x] Rewrite correlated subquery as two-pass `UPDATE ... FROM` with pre-computed lookup
- [x] Carry forward resolved `target_symbol_id` during reference copy (`CopySymbolsResult`)
- [x] Drop same-language priority (removes expensive file JOINs)
- [x] Benchmark before/after on large branch (25s vs 47s baseline on main)
- [x] Add 7 integration tests for `resolve_references_batch` (SQLite-compatible)
- [x] Add regression test for unresolvable refs not blocking resolvable ones
- [ ] Add compound index `symbols(repository_id, name)` (deferred to migration)
- [ ] Add compound index `references(repository_id, target_symbol_id)` (deferred to migration)

---

### 2.4 Auto-detect base_branch for Feature Branch Indexing
**Severity:** MEDIUM | **Effort:** 4 hours

**Location:** `src/inxr2/application/use_cases/indexing/default_orchestrator.py`, `config.yaml`

**Issue:** When indexing feature branches, the indexer walks ALL reachable commits (including shared history with main), even though shared commits are already indexed. Content-hash optimization prevents re-parsing, but the commit-walking, file-change detection, and DB lookups still cost significant time. Example: `automated-testing-agent` (187 total commits, ~10-20 unique) spends 1m 49s on indexing with 100% cache reuse — most of that time is wasted on shared commits.

**Investigation:**
- `IndexRepositoryRequest.base_branch` already exists but requires manual config
- Could auto-detect: if branch != default_branch, use default_branch as base_branch
- Use `git merge-base` to find fork point, only index commits after that
- Would reduce feature branch indexing from minutes to seconds
- Need to handle edge cases: branches with no common ancestor, rebased branches

**Tasks:**
- [ ] Investigate auto-detecting base_branch when not explicitly configured
- [ ] Benchmark time saved on feature branches with base_branch set
- [ ] Consider adding `auto_base_branch: true` config option
- [ ] Update "Oldest/Newest" display to show branch-specific range

---

## Priority 3: Architecture (STRUCTURAL IMPROVEMENTS)

### 3.1 Create GitServicePort ✅ DONE
**Severity:** MEDIUM | **Effort:** 1-2 days

**Location:** `src/inxr2/application/ports/services.py`

**Issue:** `git_service` typed as `Any` in orchestrator, breaking type safety.

**Completed Tasks:**
- [x] Create `GitServicePort` abstract class with 9 sync methods
- [x] Define frozen dataclasses: `CommitInfo`, `ChangedFiles`, `RepositoryInfo`
- [x] Update `GitService` adapter to implement port, return dataclasses
- [x] Update `DefaultIndexingOrchestrator` — `git_service: Any` → `GitServicePort`, all dict→attribute access
- [x] Replace `StubGitService` with full `FakeGitService` in shared test doubles
- [x] Update orchestrator tests, CLI, API, dependencies, protocol return types
- [x] Update test stubs in `test_get_file_history_use_case.py` and `test_list_commits_use_case.py`
- [x] 811 tests pass, mypy clean (0 errors), ruff/black/isort clean

---

### 3.2 Create SearchFilesUseCase ✅ DONE
**Severity:** MEDIUM | **Effort:** 4 hours

**Location:** `src/inxr2/application/use_cases/search/`

**Issue:** 130 lines of business logic in API controller violates Clean Architecture.

**Completed Tasks:**
- [x] Create `SearchFilesUseCase` with `SearchFilesRequest` and `SearchFilesResponse`
- [x] Move repository/commit resolution logic from controller
- [x] Move deduplication semantics to use case
- [x] Update controller to be thin wrapper
- [x] Add unit tests for use case
- [x] Update dependency injection

---

### 3.3 Fix Adapter Layer Dependency in Orchestrator ✅ DONE
**Severity:** MEDIUM | **Effort:** 2 hours

**Location:** `src/inxr2/application/use_cases/indexing/default_orchestrator.py:145`

**Issue:** Application layer imports `PlaintextParser` from adapter layer.

**Completed Tasks:**
- [x] Create `PlaintextParserPort` in `application/ports/services.py`
- [x] Inject `PlaintextParser` as constructor parameter
- [x] Remove import from `__init__`
- [x] Update dependency injection configuration
- [x] Add `FakePlaintextParser` test double
- [x] Update all orchestrator test construction sites

---

### 3.4 Decompose Orchestrator (God Class) ✅ DONE
**Severity:** HIGH | **Effort:** 3-4 days

**Location:** `src/inxr2/application/use_cases/indexing/default_orchestrator.py` (was 1,022 lines → now 443 lines)

**Issue:** Single class handles 10+ responsibilities, violating SRP.

**Completed Tasks:**
- [x] Remove `enable_text_search` flag (text search always on)
- [x] Extract `ProcessFileUseCase` (~370 lines) — file processing, language detection, comment extraction, non-code indexing
- [x] Extract `ProcessCommitUseCase` (~170 lines) — commit save/reuse, branch linking, commit message indexing, file delegation
- [x] Replace mutable `stats: dict` with typed `ProcessCommitResult` dataclass aggregation
- [x] Orchestrator becomes thin coordinator (443 lines, down from 1,022)
- [x] Add 7 unit tests for `ProcessFileUseCase`
- [x] Add 7 unit tests for `ProcessCommitUseCase`
- [x] All 833 tests pass, mypy clean, ruff/black/isort clean
- [x] Fix timestamp display (dropped " UTC" — GitPython returns committer's local timezone)

**Note:** Orchestrator is 443 lines rather than ~200 because `_select_commits()` and progress callback plumbing remain as necessary coordinator logic. `PrepareRepositoryUseCase`, `SelectCommitsUseCase`, and `IndexTextContentUseCase` were not extracted as separate use cases — their logic is either trivial or better kept inline in the coordinator.

---

### 3.5 Unify Full/Incremental Indexing ✅ DONE
**Severity:** HIGH | **Effort:** 4 hours

**Location:** `src/inxr2/application/use_cases/indexing/default_orchestrator.py`

**Issue:** Two separate methods (`index_repository` and `index_incremental`) with ~200 lines of duplicated logic. The distinction is unnecessary—indexing should always be incremental (index what's not yet indexed).

**Architectural Decision:** Remove "full" vs "incremental" distinction. One `index` command that:
- Indexes commits not yet in the database
- Skips already-indexed commits (always incremental)
- For "full reindex", user runs `inxr2 reset` then `inxr2 index`

**Benefits:**
- Eliminates ~200 lines of duplicated code
- Simplifies CLI (one command instead of two)
- Cleaner mental model for users
- Reduces orchestrator complexity for 3.4 decomposition

**Completed Tasks:**
- [x] Merge `index_repository` and `index_incremental` into single `index` method
- [x] Update `IndexingOrchestratorPort` interface (remove `index_incremental`)
- [x] Removed CLI `index incremental` and `index full` subcommands - unified to just `index`
- [x] Remove `IncrementalIndexRequest` (use `IndexRepositoryRequest` only)
- [x] Update all tests
- [x] Update CLAUDE.md command reference

**Full reindex workflow:** `inxr2 db reset --yes && inxr2 index --config config.yaml`

**Supersedes:** The original 3.5 "Extract Shared Logic" item is now obsolete—unification eliminates the duplication entirely.

---

## Priority 4: Code Duplication (DRY VIOLATIONS)

### 4.1 Extract Base Tree-Sitter Parser ✅ DONE
**Severity:** MEDIUM | **Effort:** 3-4 days

**Location:** `src/inxr2/adapters/external/treesitter/`

**Issue:** 40-60% code overlap across Python, TypeScript, Java, C parsers.

**Completed Tasks:**
- [x] Create `BaseLanguageParser` base class with shared helpers
- [x] Extract `_make_symbol`, `_make_reference`, `_add_reference` dict builders
- [x] Extract `_strip_block_comment` (also covers 4.2)
- [x] Extract `extract_comments` template with visitor pattern
- [x] Refactor all 4 parsers (Python, TypeScript, Java, C) to extend base
- [x] Add 31 unit tests for base helpers
- [x] ~460 lines reduced across parsers

---

### 4.2 Extract Comment Marker Stripping Utility ✅ DONE (subsumed by 4.1)
**Severity:** LOW | **Effort:** 2 hours

**Location:** TypeScript parser (550-575), C parser (909-931)

**Issue:** Nearly identical `strip_comment_markers()` functions.

**Resolution:** Subsumed by 4.1 — `_strip_block_comment()` extracted into `BaseLanguageParser`. All parsers now call `self._strip_block_comment(text)` instead of duplicated local functions.

---

### 4.3 Standardize content_type Naming ✅ DONE
**Severity:** LOW | **Effort:** 1 hour

**Issue:** Python uses `inline_comment`, others use `single_line_comment`.

**Tasks:**
- [x] Decide on standard names
- [x] Update Python parser to use `single_line_comment`
- [x] Add migration for existing data (if any) — not needed, informational column only
- [x] Update search filters — no filters use content_type; updated default fallback

---

## Priority 5: Error Handling

### 5.1 Add Database Error Handling to Orchestrator
**Severity:** HIGH | **Effort:** 4 hours

**Location:** `src/inxr2/application/use_cases/indexing/default_orchestrator.py` (throughout)

**Issue:** No error handling for database operations. Entire indexing run fails with no recovery.

**Tasks:**
- [ ] Add retry logic with exponential backoff for transient failures
- [ ] Implement transaction batching (commit every N operations)
- [ ] Add checkpoint/resume capability (save progress)
- [ ] Wrap critical sections in try/except
- [ ] Add tests for error recovery scenarios

---

### 5.2 Add Error Handling to Comment/Symbol Parsers ✅ DONE
**Severity:** MEDIUM | **Effort:** 2 hours

**Location:** All `extract_comments` methods + `TreeSitterService`

**Issue:** No try-except around node traversal. Malformed nodes crash extraction.

**Completed Tasks:**
- [x] Add per-node try/except in `BaseLanguageParser.extract_comments` (covers C, Java, TypeScript)
- [x] Add per-node try/except in `PythonParser.extract_comments` (overrides base)
- [x] Wrap `language_parser.extract()` and `extract_comments()` in `TreeSitterService` with try/except
- [x] Log warnings (per-node) and errors (service-level) with file/line context
- [x] Return partial results on per-node error; return empty on total extraction failure
- [x] Add 7 tests for error resilience (partial results, logging, service fallback)

---

## Priority 6: Test Coverage

### 6.1 Add C Comment Extraction Tests
**Severity:** MEDIUM | **Effort:** 2 hours

**Location:** `tests/adapters/external/`

**Issue:** Only 1 basic test with 3 assertions for C comments.

**Tasks:**
- [ ] Create `test_c_comment_extraction.py`
- [ ] Add tests for single-line comments
- [ ] Add tests for block comments
- [ ] Add tests for comments in preprocessor directives
- [ ] Add tests for edge cases

---

### 6.2 Fix Test Double Behavioral Mismatches ✅ DONE
**Severity:** HIGH | **Effort:** 1 day

**Location:** `tests/fixtures/test_doubles.py`

**Issue:** Test doubles don't match production behavior for temporal deduplication.

**Completed Tasks:**
- [x] Add `_compute_latest_file_ids` helper to `InMemoryFileRepository`
- [x] Add `file_repo` injection to `InMemorySymbolRepository` (optional, backward-compatible)
- [x] Add latest file version filtering to `InMemorySymbolRepository.search_by_name`, `find_by_exact_name`, `find_by_qualified_name`
- [x] Add latest file version filtering to `InMemoryReferenceRepository.find_references_to_symbol`, `find_references_by_text`
- [x] Simplify `InMemoryFileRepository.list_changed_at_commit` (O(N^3) → O(N))
- [x] Add 24 contract tests (`tests/contract/`) verifying fake-vs-Postgres parity
- [x] 901 tests pass, mypy clean, ruff/black/isort clean

---

### 6.3 Add Missing Integration Tests
**Severity:** LOW | **Effort:** 4 hours

**Issue:** Missing tests for branch/commit parameters in file search.

**Tasks:**
- [ ] Add `test_search_files_with_branch_filter`
- [ ] Add `test_search_files_with_commit_hash`
- [ ] Add `test_search_files_branch_without_repository` (expect 400)

---

## Priority 7: CLI Refactoring

### ~~7.1 Extract ResetDatabaseUseCase~~ REMOVED
**Status:** Not needed

**Rationale:** `inxr2 db reset --yes` already exists and works. For "full reindex", users run:
```bash
inxr2 db reset --yes && inxr2 index --config config.yaml
```

No need to extract this to a use case—the CLI command is sufficient.

---

### 7.2 Create IndexingProgressRenderer
**Severity:** LOW | **Effort:** 4 hours

**Location:** `src/inxr2/adapters/cli/commands/index_command.py`

**Issue:** Presentation concerns mixed with orchestration (1,267 lines).

**Tasks:**
- [ ] Create `IndexingProgressRenderer` class
- [ ] Move Rich console progress rendering to renderer
- [ ] Move statistics formatting to renderer
- [ ] CLI becomes: parse args → call use case → render results

---

## Priority 8: Frontend

### 8.1 Split useBrowseState Hook
**Severity:** LOW | **Effort:** 1 day

**Location:** `frontend/src/hooks/useBrowseState.ts` (681 lines)

**Issue:** Complex hook doing too much.

**Tasks:**
- [ ] Extract `useUrlState()` for URL synchronization
- [ ] Extract `useDataFetching()` for API calls
- [ ] Extract `useDiffMode()` for diff state
- [ ] Compose in `useBrowseState()`
- [ ] Verify existing tests pass

---

### 8.2 Create ApiError Class
**Severity:** LOW | **Effort:** 2 hours

**Location:** `frontend/src/lib/api-client.ts`

**Issue:** Basic error handling with generic Error class.

**Tasks:**
- [ ] Create `ApiError` class with `status`, `message`, `details`
- [ ] Update `request()` to throw `ApiError`
- [ ] Update components to handle `ApiError` appropriately

---

### 8.3 Fix Frontend Test Warnings
**Severity:** LOW | **Effort:** 2 hours

**Location:** Frontend test suite

**Issue:** 12 warnings in frontend tests:
- React Router v7 future flag warnings (`v7_startTransition`, `v7_relativeSplatPath`) — 6 instances
- React `act(...)` warnings in `Home` and `CodeHeader` test components — 6 instances

**Tasks:**
- [ ] Add React Router v7 future flags to test router configuration
- [ ] Wrap async state updates in `act()` in Home and CodeHeader tests

---

## Summary Table

| ID | Priority | Effort | Description |
|----|----------|--------|-------------|
| 1.1 | P1 | 4h | SQL injection in regex ✅ DONE |
| 1.2 | P1 | 2h | Invalid tsquery construction ✅ DONE |
| 1.3 | P1 | 2h | Python docstring bug ✅ DONE |
| 1.4 | P1 | 2h | Input validation ✅ DONE |
| 2.1 | P2 | 1d | N+1 in file search ✅ DONE |
| 2.2 | P2 | 1d | N+1 in text search ✅ DONE |
| 2.3 | P2 | 1d | Optimize resolve_references_batch query ✅ DONE |
| 2.4 | P2 | 4h | Auto-detect base_branch for feature branch indexing |
| 3.1 | P3 | 1-2d | GitServicePort ✅ DONE |
| 3.2 | P3 | 4h | SearchFilesUseCase ✅ DONE |
| 3.3 | P3 | 2h | Fix adapter dependency ✅ DONE |
| 3.4 | P3 | 3-4d | Decompose orchestrator ✅ DONE |
| 3.5 | P3 | 4h | Unify full/incremental indexing ✅ DONE |
| 4.1 | P4 | 3-4d | Base parser extraction ✅ DONE |
| 4.2 | P4 | 2h | Comment stripping utility ✅ DONE (subsumed by 4.1) |
| 4.3 | P4 | 1h | Standardize content_type ✅ DONE |
| 5.1 | P5 | 4h | Database error handling |
| 5.2 | P5 | 2h | Parser error handling ✅ DONE |
| 6.1 | P6 | 2h | C comment tests |
| 6.2 | P6 | 1d | Fix test doubles ✅ DONE |
| 6.3 | P6 | 4h | Missing integration tests |
| ~~7.1~~ | ~~P7~~ | - | ~~ResetDatabaseUseCase~~ (not needed) |
| 7.2 | P7 | 4h | IndexingProgressRenderer |
| 8.1 | P8 | 1d | Split useBrowseState |
| 8.2 | P8 | 2h | ApiError class |
| 8.3 | P8 | 2h | Fix frontend test warnings |

---

## Recommended Execution Order

### Week 1: Security & Critical Fixes ✅ DONE
- ~~1.1, 1.2, 1.3, 1.4 (10 hours)~~ Completed
- ~~6.2 partial: Fix critical test double mismatches (4 hours)~~ ✅ DONE (full)

### Week 2: Performance ✅ DONE
- ~~2.1, 2.2 (2 days)~~ Completed
- ~~2.3 Optimize resolve_references_batch (1 day)~~ ✅ DONE

### Week 3: Architecture - Indexing Unification ✅ DONE
- ~~3.5 Unify full/incremental indexing (4 hours)~~ ✅ DONE
- ~~3.2 SearchFilesUseCase (4 hours)~~ ✅ DONE
- ~~3.3 Fix adapter dependency (2 hours)~~ ✅ DONE
- ~~3.1 GitServicePort (1-2 days)~~ ✅ DONE

### Week 4: Architecture - Orchestrator Decomposition ✅ DONE
- ~~3.4 orchestrator decomposition (3-4 days)~~ ✅ DONE

### Week 5: Code Quality ✅ DONE (partial)
- ~~4.1 base parser extraction (3-4 days)~~ ✅ DONE
- ~~4.2 comment stripping utility (2 hours)~~ ✅ DONE (subsumed by 4.1)
- ~~4.3 standardize content_type (1 hour)~~ ✅ DONE
- 5.1 database error handling (4 hours)

### Week 6+: Polish
- ~~5.2 Parser error handling~~ ✅ DONE
- Remaining items as time permits (2.4, 5.1, 6.x, 7.2, 8.x)

---

## Notes

- Create feature branch per item (e.g., `refactor/fix-sql-injection`)
- Run full test suite before merging
- Update CLAUDE.md if patterns change
- Link PR to this document item number

## Completed Items

| ID | Date | Commit | Description |
|----|------|--------|-------------|
| 1.1 | 2026-02-07 | 8c5ebfe | SQL injection in regex + tsquery fix |
| 1.2 | 2026-02-07 | 8c5ebfe | Invalid tsquery construction (combined with 1.1) |
| 1.3 | 2026-02-07 | be60a4c | Python docstring detection bug |
| 1.4 | 2026-02-07 | e0fcde9 | Input validation for search endpoints |
| 2.1 | 2026-02-07 | e0a5bf5 | N+1 in file search |
| 2.2 | 2026-02-07 | c1e630c | N+1 in text search |
| 3.5 | 2026-02-07 | f388b6c | Unify full/incremental indexing |
| 3.2 | 2026-02-07 | 17561ae | Extract SearchFilesUseCase from controller |
| 3.3 | 2026-02-07 | 985556a | Fix adapter layer dependency (PlaintextParserPort) |
| 2.3 | 2026-02-08 | 8ada668, 3b64639, 23a9922 | Optimize resolve_references_batch (two-pass UPDATE...FROM) |
| 3.1 | 2026-02-08 | d74197c | GitServicePort with typed return values |
| 3.4 | 2026-02-08 | 4fbfde5 | Decompose orchestrator (ProcessFileUseCase + ProcessCommitUseCase) |
| 4.1 | 2026-02-08 | 609f429 | Extract shared helpers into BaseLanguageParser |
| 4.2 | 2026-02-08 | 609f429 | Comment stripping utility (subsumed by 4.1) |
| 4.3 | 2026-02-08 | fb091e3 | Standardize content_type naming |
| 5.2 | 2026-02-08 | — | Parser error handling (per-node + service-level) |
| — | 2026-02-08 | 69e9fd4 | Remove SQLite, use PostgreSQL test database (aiosqlite removed, savepoint isolation, 877 tests pass) |

## Architectural Decisions

### Indexing is Always Incremental (2026-02-07)
Decided to remove the "full" vs "incremental" distinction. The command is now just `inxr2 index`, which always indexes commits not yet in the database. For a complete reindex:
```bash
inxr2 db reset --yes && inxr2 index --config config.yaml
```
This simplifies the codebase and mental model. See item 3.5.

### Bugs Found During Exploratory Testing (2026-02-07)
Two data-quality bugs discovered during UI testing of the `2026-02-07-refactor` branch:

1. **Duplicate commit messages**: `_process_commit` always called `_index_commit_message` even for already-existing commits, inflating text search result counts. Fixed by guarding with `existing_commit is None`.
2. **Pagination non-determinism**: Text search `ORDER BY rank DESC` had no tiebreaker, so rows with identical ranks shuffled across pages. Fixed by adding `TextContentModel.id` as secondary sort key.

Both fixes committed in f388b6c.

### StrEnum Migration (2026-02-07)
Fixed 4 pre-existing ruff UP042 warnings: `QueryMode`, `ReferenceType`, `SymbolKind`, and `TextSearchSourceType` changed from `(str, Enum)` to `StrEnum`. Done alongside item 3.3.

### Reference Resolution Optimization (2026-02-08)
Replaced correlated subquery in `resolve_references_batch` with two-pass `UPDATE ... FROM` using pre-computed lookup table. Key design decisions:

1. **Dropped same-language priority** — the expensive `JOIN files` for language matching provided negligible benefit. Resolution now uses: same-file first, then lowest symbol ID as deterministic tiebreaker.
2. **Pre-computed lookup** — `GROUP BY name` on symbols produces a small result set, joined inside the FROM subquery so `LIMIT` naturally filters to matchable refs only. Unresolvable refs (builtins like `str`, `int`) are excluded without extra computation.
3. **Carry-forward during copy** — `copy_references_to_file()` now remaps `target_symbol_id` via `CopySymbolsResult.id_mapping`, avoiding re-resolution of already-resolved references after cross-branch content-hash reuse.

Performance: Total 14-repo/branch indexing dropped from ~32m to ~22m. Main branch resolving: 47s → 25s.

### Orchestrator Decomposition (2026-02-08)
Extracted `ProcessFileUseCase` and `ProcessCommitUseCase` from the 1,022-line `DefaultIndexingOrchestrator`. Key decisions:

1. **Two use cases, not five** — the plan originally considered `PrepareRepositoryUseCase`, `SelectCommitsUseCase`, and `IndexTextContentUseCase`, but these are either trivial (repo prep is 10 lines) or better kept inline (commit selection logic is tightly coupled to the coordinator). Extracting per-file and per-commit processing captured the bulk of the complexity.
2. **Typed result aggregation** — replaced mutable `stats: dict[str, Any]` with frozen `ProcessFileResult` and `ProcessCommitResult` dataclasses. The orchestrator aggregates `ProcessCommitResult` instances via `_merge_commit_result()`.
3. **`enable_text_search` removed** — text search (comments, docstrings, commit messages, non-code files) is now always on. Removed the flag from `IndexRepositoryRequest`, CLI, and 3 conditional blocks.
4. **443 lines, not 200** — the orchestrator retains `_select_commits()` (~55 lines) and progress callback plumbing, which are coordinator concerns. The 57% reduction (1,022 → 443) is the practical sweet spot.

### GitServicePort Completed (2026-02-08)
Initially attempted 2026-02-07, reverted due to cascading changes. Re-attempted 2026-02-08 after 3.5 unification simplified the orchestrator. Successfully replaced `git_service: Any` with `GitServicePort`, dict returns with frozen dataclasses (`CommitInfo`, `ChangedFiles`, `RepositoryInfo`), and all `data["hash"]` → `data.hash` across codebase. 811 tests pass, mypy clean.

---

## Post-Refactoring Review (2026-02-08)

After completing 16 of 21 backlog items (priorities 1-4 fully done, plus 5.2), a full architectural review was performed to assess codebase health before resuming feature work.

### Overall Assessment

The refactoring cycle was well-executed. Clean Architecture boundaries hold, the orchestrator decomposition is clean, and the Tree-sitter parser hierarchy is solid. No critical issues found — the codebase is in good shape to resume feature work (Phase 1.12: Remote Repository Support).

### What Went Well

- **Orchestrator decomposition** (3.4) — Clean separation between `DefaultIndexingOrchestrator` (443 lines), `ProcessCommitUseCase`, and `ProcessFileUseCase`. The coordinator retains appropriate responsibilities (commit selection, progress plumbing).
- **GitServicePort** (3.1) — Frozen dataclasses replacing dict returns eliminated an entire class of runtime errors. No remaining `data["key"]` patterns.
- **Base parser hierarchy** (4.1) — `BaseLanguageParser` with template methods and shared helpers (`_make_symbol`, `_make_reference`, `_strip_block_comment`) eliminated ~460 lines of duplication cleanly.
- **Error handling** (5.2) — Per-node try/except in comment extraction + service-level fallback is the right granularity.
- **Layer boundaries** — No domain imports of framework code. Adapters properly implement ports. Infrastructure wires things via DI.
- **Test isolation** — CLI tests use isolated PostgreSQL test database, repository tests use savepoint isolation, no tests touch the live database.

### Issues Identified

#### Fix Before Adding Features

| Priority | Issue | Location | Effort |
|----------|-------|----------|--------|
| ~~1~~ | ~~Test double behavioral drift (backlog 6.2)~~ | ~~`tests/fixtures/test_doubles.py`~~ | ~~1 day~~ ✅ DONE |
| 1 | Extract CLI rendering (backlog 7.2) | `index_command.py` (976 lines) | 4 hours |

~~**Test double drift** is the highest-risk item.~~ ✅ FIXED — All 6 fake methods now match Postgres latest-file-version filtering. 24 contract tests verify parity.

**`index_command.py`** at 976 lines mixes CLI orchestration, Rich progress rendering (~200 lines), CSV log writing, summary formatting (~150 lines), and database reset logic. This is already tracked as backlog 7.2.

#### Worth Improving (Not Blocking)

| Priority | Issue | Location | Effort |
|----------|-------|----------|--------|
| 3 | Move branch-filtering logic out of `cli.py` | `cli.py:125-342` (~220 lines) | 4 hours |
| 4 | Type the parser dict returns | `TreeSitterService`, parsers, `ProcessFileUseCase` | 1 day |

**Branch-filtering in cli.py**: `_run_config_based_index` contains ~220 lines of branch-activity filtering, strategy selection, and progress display — application-layer logic living in the adapter layer. Could be folded into the 7.2 extraction.

**Untyped parser returns**: `parse_file` and `extract_comments` return `list[dict[str, Any]]`. These could use `TypedDict` or dataclasses (following the GitServicePort pattern from 3.1), catching bugs at the boundary between parsers and repositories.

### Items Confirmed As Fine

- `ProcessFileUseCase` (453 lines) — well-structured, worth watching but not urgent
- Mixed sync/async in GitService — GitPython is sync by nature, works fine in current indexing model
- Port organization (some ISP Protocols, some full ports) — both approaches valid, minor inconsistency
- `DefaultIndexingOrchestrator` at 443 lines — appropriate coordinator size

### Recommended Path Forward

1. ~~Fix test double drift (6.2) — prevents false confidence in tests~~ ✅ DONE
2. Extract CLI rendering (7.2) — unblocks clean CLI additions
3. Resume Phase 1.12 (Remote Repository Support) — the architecture is ready

### PostgreSQL Test Database Migration (2026-02-08)

Removed all SQLite support and switched tests to a dedicated `inxr2_test` PostgreSQL database. Key decisions:

1. **Savepoint isolation** — `join_transaction_mode="create_savepoint"` (SQLAlchemy 2.0+) wraps each test in a transaction. `session.commit()` releases a SAVEPOINT; the outer transaction rolls back after the test. Zero data persists between tests.
2. **CLI truncation** — CLI commands manage their own sessions/commits, so savepoint isolation doesn't apply. CLI tests use TRUNCATE after each test instead.
3. **Session-scoped event loop** — `asyncio_default_test_loop_scope = "session"` and `asyncio_default_fixture_loop_scope = "session"` in pyproject.toml ensure all tests share one event loop with the session-scoped engine.
4. **`content_tsvector` via raw SQL** — The tsvector column isn't in the ORM model (managed by triggers in production). Test conftest adds it via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` after `create_all`.
5. **`references` quoting** — PostgreSQL reserved word; must quote as `"references"` in raw SQL (e.g., TRUNCATE).
6. **CHAR(40) padding** — PostgreSQL CHAR(40) pads short values with spaces. All test content_hash values updated to exactly 40 characters.

Removed: `aiosqlite` dependency, `types.py` (StringArray), all SQLite URL conversion code, 7 SQLite-specific tests, all dual-dialect comments. Result: 877 tests pass (up from 721+skipped), all running against real PostgreSQL.

### Indexing Performance Baseline (2026-02-09)

Full re-index of all configured repos after completing the refactoring cycle. Run inside `inxr2-dev` container against PostgreSQL.

#### Small Repos (1 commit each)

| Repo | Language | Files | Symbols | References | Resolved % | Total Time |
|------|----------|-------|---------|------------|------------|------------|
| crisp | py/ts/js/c | 55 | 1,324 | 5,780 | 82% | 5.5s |
| inxr | py/ts/js | 10 | 248 | 1,062 | 25% | 1.1s |
| multidockerdevcontainer | py/ts/js | 133 | 738 | 4,966 | 16% | 6.3s |
| soccer-stats | java | 53 | 210 | 1,364 | 65% | 1.6s |
| cJSON | c | 154 | 2,632 | 8,972 | 84% | 11.3s |

#### inxr2 Multi-Branch (content-hash reuse)

| Branch | Commits | Files Processed | Reused | Reuse % | Index Time | Resolve Time | Total |
|--------|---------|-----------------|--------|---------|------------|--------------|-------|
| main | 196 | 2,106 | 864 | 41% | 161.7s | 24.1s | 185.8s |
| architecture-review | 150 | 1,766 | 1,766 | 100% | 63.0s | 5.0s | 68.0s |
| 2026-02-07-refactor | 210 | 2,278 | 2,190 | 96% | 110.4s | 9.7s | 120.1s |
| add-file-search | 194 | 2,165 | 2,165 | 100% | 101.9s | 11.5s | 113.4s |
| add-java-support | 127 | 1,628 | 1,628 | 100% | 79.7s | 12.4s | 92.1s |
| automated-testing-agent | 187 | 2,123 | 2,123 | 100% | 113.8s | 19.8s | 133.7s |
| exploring-freetext-search | 180 | 2,017 | 2,017 | 100% | 117.6s | 22.3s | 139.9s |
| fix-more-bugs-with-c | 111 | 1,525 | 1,525 | 100% | 89.8s | 17.9s | 107.7s |

#### Large Repo

| Repo | Commits | Files | Symbols | References | Resolved % | Index Time | Resolve Time | Total |
|------|---------|-------|---------|------------|------------|------------|--------------|-------|
| Java | 1,000 | 3,863 | 26,231 | 185,620 | 56% | 240.7s | 135.7s | 376.5s |

#### Key Observations

1. **Content-hash reuse is excellent** — feature branches hit 96-100% reuse since they share most files with main. No re-parsing happens, just DB copies.
2. **Commit-walking is still the bottleneck** — even with 100% reuse, feature branches still take 68-140s because the indexer walks every reachable commit. Backlog item **2.4 (auto-detect base_branch)** would fix this by using `git merge-base` to skip shared commits, dropping feature branch time from minutes to seconds.
3. **Java repo is the outlier** — 1,000 commits, 376s total. The 135.7s resolve time (36% of total) is the largest resolve cost in the suite; 185K references is the biggest batch.
4. **Resolution rates vary by ecosystem** — C (84%), Python (82%), Java (65%) resolve well. Repos referencing many external libraries (inxr at 25%, multidockerdevcontainer at 16%) resolve less since those symbols aren't indexed.
5. **Total re-index time** — all 14 repo/branch combinations: ~23 minutes. Dominated by inxr2 multi-branch (~15 min) and Java (~6 min).
