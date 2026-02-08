# Refactoring Backlog

**Created:** 2026-02-07
**Branch:** main (create feature branches per item)
**Source:** Consolidated from `2026-02-07-code-review.md` and `2026-02-07-architecture-review.md`

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

## Priority 3: Architecture (STRUCTURAL IMPROVEMENTS)

### 3.1 Create GitServicePort ⚠️ DEFERRED
**Severity:** MEDIUM | **Effort:** 1-2 days (revised up from 4 hours)

**Location:** `src/inxr2/application/ports/services.py`

**Issue:** `git_service` typed as `Any` in orchestrator, breaking type safety.

**Status:** Attempted 2026-02-07, reverted due to complexity. The refactor touches many files and requires:
- Changing dict return types to typed dataclasses (`CommitInfo`, `ChangedFiles`)
- Updating all call sites from dict access (`data["hash"]`) to attribute access (`data.hash`)
- Updating `FakeGitService` test double to match new interface
- Cascading changes through orchestrator and tests

**Recommendation:** Defer until after 3.5 (indexing unification) simplifies the orchestrator. Less code to update.

**Tasks:**
- [ ] Create `GitServicePort` abstract class in `application/ports/services.py`
- [ ] Define typed dataclasses for return values (`CommitInfo`, `ChangedFiles`, etc.)
- [ ] Define abstract methods for all git operations used by orchestrator
- [ ] Update `DefaultIndexingOrchestrator` to use typed port
- [ ] Update `FakeGitService` test double to implement port
- [ ] Remove `Any` type hint

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

### 3.4 Decompose Orchestrator (God Class)
**Severity:** HIGH | **Effort:** 3-4 days

**Location:** `src/inxr2/application/use_cases/indexing/default_orchestrator.py` (1,211 lines)

**Issue:** Single class handles 10+ responsibilities, violating SRP.

**Tasks:**
- [ ] Extract `PrepareRepositoryUseCase`
- [ ] Extract `SelectCommitsUseCase` (single strategy after 3.5 unification)
- [ ] Extract `ProcessCommitUseCase`
- [ ] Extract `ProcessFileUseCase`
- [ ] Extract `IndexTextContentUseCase`
- [ ] Orchestrator becomes thin coordinator (~200 lines)
- [ ] Add unit tests for each extracted use case
- [ ] Update existing integration tests

**Note:** Effort reduced from 1 week to 3-4 days after 3.5 unification eliminates dual-path complexity.

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

### 4.1 Extract Base Tree-Sitter Parser
**Severity:** MEDIUM | **Effort:** 3-4 days

**Location:** `src/inxr2/adapters/external/treesitter/`

**Issue:** 40-60% code overlap across Python, TypeScript, Java, C parsers.

**Tasks:**
- [ ] Create `AbstractTreeSitterParser` base class
- [ ] Extract shared traversal logic to base
- [ ] Extract shared scope tracking to base
- [ ] Extract shared comment extraction to base
- [ ] Refactor `PythonParser` to extend base
- [ ] Refactor `TypeScriptParser` to extend base
- [ ] Refactor `JavaParser` to extend base
- [ ] Refactor `CParser` to extend base
- [ ] Verify all existing tests pass

---

### 4.2 Extract Comment Marker Stripping Utility
**Severity:** LOW | **Effort:** 2 hours

**Location:** TypeScript parser (550-575), C parser (909-931)

**Issue:** Nearly identical `strip_comment_markers()` functions.

**Tasks:**
- [ ] Create `comment_utils.py` with shared functions
- [ ] Update TypeScript and C parsers to use shared utility
- [ ] Add comprehensive tests for utility

---

### 4.3 Standardize content_type Naming
**Severity:** LOW | **Effort:** 1 hour

**Issue:** Python uses `inline_comment`, others use `single_line_comment`.

**Tasks:**
- [ ] Decide on standard names
- [ ] Update Python parser to use `single_line_comment`
- [ ] Add migration for existing data (if any)
- [ ] Update search filters

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

### 5.2 Add Error Handling to Comment Parsers
**Severity:** MEDIUM | **Effort:** 2 hours

**Location:** All `extract_comments` methods

**Issue:** No try-except around node traversal. Malformed nodes crash extraction.

**Tasks:**
- [ ] Add defensive error handling in each parser
- [ ] Log warnings for skipped nodes
- [ ] Return partial results on error (don't fail entire file)
- [ ] Add tests for malformed input

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

### 6.2 Fix Test Double Behavioral Mismatches
**Severity:** HIGH | **Effort:** 1 day

**Location:** `tests/fixtures/test_doubles.py`

**Issue:** Test doubles don't match production behavior for temporal deduplication.

**Tasks:**
- [ ] Add latest file version filtering to `InMemorySymbolRepository.search_by_name`
- [ ] Add latest file version filtering to `InMemoryReferenceRepository.find_references_to_symbol`
- [ ] Simplify `InMemoryFileRepository.list_changed_at_commit` (90 lines → simpler)
- [ ] Add contract tests verifying fake matches real behavior

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

## Summary Table

| ID | Priority | Effort | Description |
|----|----------|--------|-------------|
| 1.1 | P1 | 4h | SQL injection in regex ✅ DONE |
| 1.2 | P1 | 2h | Invalid tsquery construction ✅ DONE |
| 1.3 | P1 | 2h | Python docstring bug ✅ DONE |
| 1.4 | P1 | 2h | Input validation ✅ DONE |
| 2.1 | P2 | 1d | N+1 in file search ✅ DONE |
| 2.2 | P2 | 1d | N+1 in text search ✅ DONE |
| 3.1 | P3 | 1-2d | GitServicePort ⚠️ DEFERRED |
| 3.2 | P3 | 4h | SearchFilesUseCase ✅ DONE |
| 3.3 | P3 | 2h | Fix adapter dependency ✅ DONE |
| 3.4 | P3 | 3-4d | Decompose orchestrator (reduced after 3.5) |
| 3.5 | P3 | 4h | Unify full/incremental indexing ✅ DONE |
| 4.1 | P4 | 3-4d | Base parser extraction |
| 4.2 | P4 | 2h | Comment stripping utility |
| 4.3 | P4 | 1h | Standardize content_type |
| 5.1 | P5 | 4h | Database error handling |
| 5.2 | P5 | 2h | Parser error handling |
| 6.1 | P6 | 2h | C comment tests |
| 6.2 | P6 | 1d | Fix test doubles |
| 6.3 | P6 | 4h | Missing integration tests |
| ~~7.1~~ | ~~P7~~ | - | ~~ResetDatabaseUseCase~~ (not needed) |
| 7.2 | P7 | 4h | IndexingProgressRenderer |
| 8.1 | P8 | 1d | Split useBrowseState |
| 8.2 | P8 | 2h | ApiError class |

---

## Recommended Execution Order

### Week 1: Security & Critical Fixes ✅ DONE
- ~~1.1, 1.2, 1.3, 1.4 (10 hours)~~ Completed
- 6.2 partial: Fix critical test double mismatches (4 hours)

### Week 2: Performance ✅ DONE
- ~~2.1, 2.2 (2 days)~~ Completed

### Week 3: Architecture - Indexing Unification ✅ DONE
- ~~3.5 Unify full/incremental indexing (4 hours)~~ ✅ DONE
- ~~3.2 SearchFilesUseCase (4 hours)~~ ✅ DONE
- ~~3.3 Fix adapter dependency (2 hours)~~ ✅ DONE
- 3.1 GitServicePort (1-2 days) - deferred, easier after 3.5 simplified orchestrator

### Week 4: Architecture - Orchestrator Decomposition
- 3.4 orchestrator decomposition (3-4 days, reduced complexity after 3.5)

### Week 5: Code Quality
- 4.1 base parser extraction (3-4 days)
- 5.1 database error handling (4 hours)

### Week 6+: Polish
- Remaining items as time permits

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
| 3.3 | 2026-02-07 | (pending) | Fix adapter layer dependency (PlaintextParserPort) |

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

Both fixes are in the working tree (pending commit).

### StrEnum Migration (2026-02-07)
Fixed 4 pre-existing ruff UP042 warnings: `QueryMode`, `ReferenceType`, `SymbolKind`, and `TextSearchSourceType` changed from `(str, Enum)` to `StrEnum`. Done alongside item 3.3.

### GitServicePort Deferred (2026-02-07)
Attempted to create typed `GitServicePort` to replace `Any` type hint. Reverted after discovering the refactor was larger than estimated—requires changing dict returns to typed dataclasses throughout orchestrator and test doubles. Recommend completing 3.5 first to reduce the surface area of this change.
