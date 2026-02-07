# Refactoring Backlog

**Created:** 2026-02-07
**Branch:** main (create feature branches per item)
**Source:** Consolidated from `2026-02-07-code-review.md` and `2026-02-07-architecture-review.md`

---

## Priority 1: Security & Correctness (MUST FIX)

### 1.1 Fix SQL Injection in Regex Search Mode
**Severity:** CRITICAL | **Effort:** 4 hours

**Location:** `src/inxr2/adapters/persistence/repositories/postgres_text_search.py:183`

**Issue:** User-supplied regex passed directly to PostgreSQL without validation. Can cause ReDoS or database exhaustion.

**Tasks:**
- [ ] Add regex pattern validation (complexity limits, max length)
- [ ] Add query timeout for regex operations
- [ ] Add tests for malicious regex patterns
- [ ] Document regex limitations in API docs

---

### 1.2 Fix Invalid tsquery Syntax Construction
**Severity:** CRITICAL | **Effort:** 2 hours

**Location:** `src/inxr2/adapters/persistence/repositories/postgres_text_search.py:204-206`

**Issue:** Special characters (`:`, `!`, `&`, `|`, `(`, `)`) in user input cause PostgreSQL syntax errors.

**Tasks:**
- [ ] Replace `to_tsquery()` with `plainto_tsquery()` for keyword mode
- [ ] Add error handling for query parsing failures
- [ ] Add tests for queries with special characters

---

### 1.3 Fix Python Docstring Detection Bug
**Severity:** HIGH | **Effort:** 2 hours

**Location:** `src/inxr2/adapters/external/treesitter/python_parser.py:668-684`

**Issue:** Extracts ANY string in function/class, not just first statement (actual docstring).

**Tasks:**
- [ ] Track whether non-docstring statement already seen in parent scope
- [ ] Add test case for string that's not a docstring
- [ ] Verify existing tests still pass

---

### 1.4 Add Input Validation for Search Queries
**Severity:** HIGH | **Effort:** 2 hours

**Location:** Multiple search endpoints

**Issue:** No max_length on query parameters (DoS vector).

**Tasks:**
- [ ] Add `max_length=500` to text search query
- [ ] Add `max_length=200` to file search query
- [ ] Validate mode parameter against enum values
- [ ] Validate source_types and languages against known values

---

## Priority 2: Performance (HIGH IMPACT)

### 2.1 Fix N+1 Queries in File Search
**Severity:** HIGH | **Effort:** 1 day

**Location:** `src/inxr2/adapters/api/routes/search.py:247-260`

**Issue:** 41 queries for 20 results (1 search + 20 repo + 20 commit lookups).

**Tasks:**
- [ ] Add `find_by_ids(ids: list[int])` to `RepositoryPort`
- [ ] Add `find_by_ids(ids: list[int])` to `CommitRepositoryPort`
- [ ] Implement bulk methods in PostgreSQL adapters
- [ ] Update file search endpoint to use bulk fetch
- [ ] Add test for bulk methods
- [ ] Update test doubles to support bulk methods

---

### 2.2 Fix N+1 Queries in Text Search
**Severity:** HIGH | **Effort:** 1 day

**Location:** `src/inxr2/application/use_cases/search/search_text_use_case.py:176-224`

**Issue:** 81 queries for 20 results (1 search + 20 repo + 20 file + 20 commit + 20 branch).

**Tasks:**
- [ ] Collect all unique IDs before lookup loop
- [ ] Use bulk fetch methods (after 2.1 is complete)
- [ ] Consider joining data in search query itself (better performance)
- [ ] Add performance test to prevent regression

---

## Priority 3: Architecture (STRUCTURAL IMPROVEMENTS)

### 3.1 Create GitServicePort
**Severity:** MEDIUM | **Effort:** 4 hours

**Location:** `src/inxr2/application/ports/services.py`

**Issue:** `git_service` typed as `Any` in orchestrator, breaking type safety.

**Tasks:**
- [ ] Create `GitServicePort` abstract class in `application/ports/services.py`
- [ ] Define abstract methods for all git operations used by orchestrator
- [ ] Update `DefaultIndexingOrchestrator` to use typed port
- [ ] Create `InMemoryGitService` test double
- [ ] Remove `Any` type hint

---

### 3.2 Create SearchFilesUseCase
**Severity:** MEDIUM | **Effort:** 4 hours

**Location:** `src/inxr2/application/use_cases/search/`

**Issue:** 130 lines of business logic in API controller violates Clean Architecture.

**Tasks:**
- [ ] Create `SearchFilesUseCase` with `SearchFilesRequest` and `SearchFilesResponse`
- [ ] Move repository/commit resolution logic from controller
- [ ] Move deduplication semantics to use case
- [ ] Update controller to be thin wrapper
- [ ] Add unit tests for use case
- [ ] Update dependency injection

---

### 3.3 Fix Adapter Layer Dependency in Orchestrator
**Severity:** MEDIUM | **Effort:** 2 hours

**Location:** `src/inxr2/application/use_cases/indexing/default_orchestrator.py:145`

**Issue:** Application layer imports `PlaintextParser` from adapter layer.

**Tasks:**
- [ ] Create `PlaintextParserPort` in `application/ports/services.py`
- [ ] Inject `PlaintextParser` as constructor parameter
- [ ] Remove import from `__init__`
- [ ] Update dependency injection configuration

---

### 3.4 Decompose Orchestrator (God Class)
**Severity:** HIGH | **Effort:** 1 week

**Location:** `src/inxr2/application/use_cases/indexing/default_orchestrator.py` (1,211 lines)

**Issue:** Single class handles 10+ responsibilities, violating SRP.

**Tasks:**
- [ ] Extract `PrepareRepositoryUseCase`
- [ ] Extract `SelectCommitsUseCase` (with Full/Incremental strategies)
- [ ] Extract `ProcessCommitUseCase`
- [ ] Extract `ProcessFileUseCase`
- [ ] Extract `IndexTextContentUseCase`
- [ ] Orchestrator becomes thin coordinator (~200 lines)
- [ ] Add unit tests for each extracted use case
- [ ] Update existing integration tests

---

### 3.5 Extract Shared Logic from index_repository/index_incremental
**Severity:** MEDIUM | **Effort:** 4 hours

**Location:** `src/inxr2/application/use_cases/indexing/default_orchestrator.py:149-660`

**Issue:** ~200 lines duplicated between methods.

**Tasks:**
- [ ] Extract `_prepare_indexing_context()` helper
- [ ] Extract `_execute_indexing_workflow()` helper
- [ ] Apply Template Method pattern for strategy variation
- [ ] Ensure both methods still work correctly

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

### 7.1 Extract ResetDatabaseUseCase
**Severity:** MEDIUM | **Effort:** 4 hours

**Location:** `src/inxr2/adapters/cli/commands/index_command.py:88-147`

**Issue:** Database reset logic embedded in CLI adapter, not reusable.

**Tasks:**
- [ ] Create `ResetDatabaseUseCase` in application layer
- [ ] Move truncate operations to use case
- [ ] CLI only handles confirmation and progress display
- [ ] Add unit test for use case

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
| 1.1 | P1 | 4h | SQL injection in regex |
| 1.2 | P1 | 2h | Invalid tsquery construction |
| 1.3 | P1 | 2h | Python docstring bug |
| 1.4 | P1 | 2h | Input validation |
| 2.1 | P2 | 1d | N+1 in file search |
| 2.2 | P2 | 1d | N+1 in text search |
| 3.1 | P3 | 4h | GitServicePort |
| 3.2 | P3 | 4h | SearchFilesUseCase |
| 3.3 | P3 | 2h | Fix adapter dependency |
| 3.4 | P3 | 1w | Decompose orchestrator |
| 3.5 | P3 | 4h | Extract shared logic |
| 4.1 | P4 | 3-4d | Base parser extraction |
| 4.2 | P4 | 2h | Comment stripping utility |
| 4.3 | P4 | 1h | Standardize content_type |
| 5.1 | P5 | 4h | Database error handling |
| 5.2 | P5 | 2h | Parser error handling |
| 6.1 | P6 | 2h | C comment tests |
| 6.2 | P6 | 1d | Fix test doubles |
| 6.3 | P6 | 4h | Missing integration tests |
| 7.1 | P7 | 4h | ResetDatabaseUseCase |
| 7.2 | P7 | 4h | IndexingProgressRenderer |
| 8.1 | P8 | 1d | Split useBrowseState |
| 8.2 | P8 | 2h | ApiError class |

---

## Recommended Execution Order

### Week 1: Security & Critical Fixes
- 1.1, 1.2, 1.3, 1.4 (10 hours)
- 6.2 partial: Fix critical test double mismatches (4 hours)

### Week 2: Performance
- 2.1, 2.2 (2 days)

### Week 3-4: Architecture
- 3.1, 3.2, 3.3, 3.5 (2 days)
- 3.4 orchestrator decomposition (3-5 days)

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
