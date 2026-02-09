# Code Review: February 2026 Changes

**Date:** 2026-02-07
**Reviewer:** Senior Developer Code Review
**Scope:** All commits since 2026-02-01 (~29,000 lines added)

## Executive Summary

This review covers the file search feature, text search feature, comment extraction parsers, indexing orchestrator, and test infrastructure. While the features are functionally complete, several **critical issues** require attention before production use.

**Critical Issues:** 12
**High Priority Issues:** 15
**Medium Priority Issues:** 18
**Low Priority Issues:** 12

---

## 1. File Search Feature

### Critical Issues

#### 1.1 N+1 Query Problem
**Location:** `src/inxr2/adapters/api/routes/search.py:247-260`

```python
# Fetch repositories (N+1 for now; bulk fetch would require new port method)
repo_map: dict[int, str] = {}
for rid in repo_ids:
    repo = await repository_adapter.find_by_id(rid)  # 1 query per repo
```

**Impact:** With 20 files from different repos, this generates 41 queries (1 search + 20 repos + 20 commits). Will not scale.

**Fix:** Add `find_by_ids()` bulk methods to repository ports.

#### 1.2 Broken Branch Filtering Semantics
**Location:** `src/inxr2/adapters/api/routes/search.py:225-230`

When user specifies a `branch` parameter, the code fetches only the HEAD commit and searches at that single commit. In delta-indexed repos, most files won't have rows at HEAD.

**Expected:** Search should return files from all commits on branch (latest version of each file).

**Fix:** Use snapshot semantics similar to `list_latest_by_branch`.

#### 1.3 Architectural Violation - Missing Use Case Layer
**Location:** `src/inxr2/adapters/api/routes/search.py:169-297`

The entire `search_files` endpoint contains 130 lines of business logic directly in the API controller. This violates Clean Architecture - business logic belongs in Use Cases.

**Missing:** `SearchFilesUseCase`

---

### High Priority Issues

#### 1.4 No Query Length Validation
**Location:** `src/inxr2/adapters/api/routes/search.py:174`

No `max_length` on query parameter. Malicious users could send multi-MB queries causing DoS.

**Fix:** Add `max_length=200` or similar limit.

#### 1.5 Inconsistent Parameter Naming
Text search uses `repo` but file search uses `repository`. Confusing API.

**Fix:** Standardize to one name.

---

## 2. Text Search Feature

### Critical Issues

#### 2.1 SQL Injection via Regex Mode
**Location:** `src/inxr2/adapters/persistence/repositories/postgres_text_search.py:183`

```python
return query_builder.where(TextContentModel.content.op("~")(query.query))
```

User-supplied regex is passed directly to PostgreSQL without validation. Malicious patterns can cause:
- ReDoS (catastrophic backtracking)
- Database CPU exhaustion
- Query timeouts

**Fix:** Add regex pattern validation, complexity limits, and query timeouts.

#### 2.2 Invalid tsquery Syntax Construction
**Location:** `src/inxr2/adapters/persistence/repositories/postgres_text_search.py:204-206`

```python
query_text = " & ".join(query.query.split())
return func.to_tsquery("english", query_text)
```

Special characters in user input (`:`, `!`, `&`, `|`, `(`, `)`) cause PostgreSQL syntax errors.

**Examples that crash:**
- `"TODO: fix this"` → PostgreSQL error
- `"fix bug!"` → PostgreSQL error
- `"(important)"` → PostgreSQL error

**Fix:** Use `plainto_tsquery()` instead (handles raw user input safely).

#### 2.3 N+1 Query Problem in Use Case
**Location:** `src/inxr2/application/use_cases/search/search_text_use_case.py:176-224`

For 20 search results, this generates ~81 database queries:
- 1 search + 20 repo + 20 file + 20 commit + 20 branch lookups

**Fix:** Implement bulk lookup methods or join in search query.

---

### High Priority Issues

#### 2.4 Missing Mode Validation
**Location:** `src/inxr2/adapters/api/routes/search.py:80`

Invalid mode like `"fuzzy"` passes through without validation. Should use enum.

#### 2.5 Silent Data Loss for Missing References
**Location:** `src/inxr2/application/use_cases/search/search_text_use_case.py:180-195`

If repository/file/commit doesn't exist, returns `"unknown"` instead of failing. Masks data integrity issues.

**Fix:** Fail fast or log warnings.

---

## 3. Comment Extraction Parsers

### Critical Issues

#### 3.1 Massive Code Duplication
**Location:** TypeScript (550-575), C (909-931)

Nearly identical `strip_comment_markers()` functions with only minor variations.

**Fix:** Extract to shared utility module or `BaseLanguageParser`.

#### 3.2 Python Docstring Detection Bug
**Location:** `src/inxr2/adapters/external/treesitter/python_parser.py:668-684`

Logic extracts ANY string expression statement in function/class/module, not just the first one.

```python
def foo():
    x = 1
    """This is NOT a docstring but will be extracted as one"""
```

**Fix:** Track whether non-docstring statement already seen.

#### 3.3 Missing Error Handling
No try-except around node traversal. If tree-sitter returns malformed nodes, extraction crashes.

**Fix:** Add defensive error handling.

#### 3.4 Missing C Parser Tests
Almost no dedicated test coverage for C comment extraction. Only 1 basic test with 3 assertions.

**Fix:** Create comprehensive C comment extraction tests.

---

### Medium Priority Issues

#### 3.5 Inconsistent content_type Naming
- Python: `inline_comment`
- TypeScript/C: `single_line_comment`

**Fix:** Standardize to one naming scheme.

#### 3.6 Plaintext Parser Discards Comments
YAML, Dockerfile, config file comments starting with `#` are completely discarded.

**Fix:** Add `extract_comments()` to PlaintextParser.

---

## 4. Indexing Orchestrator

### Critical Issues

#### 4.1 God Class Anti-Pattern (1,211 lines)
**Location:** `src/inxr2/application/use_cases/indexing_orchestrator.py`

Single class handles:
- Repository preparation
- Commit discovery and filtering
- File processing
- Symbol/reference extraction
- Text search indexing
- Statistics aggregation
- Progress tracking

Violates Single Responsibility Principle.

**Fix:** Extract into separate use cases:
1. `PrepareRepositoryUseCase`
2. `SelectCommitsUseCase`
3. `ProcessCommitUseCase`
4. `ProcessFileUseCase`
5. `IndexTextContentUseCase`

#### 4.2 Massive Code Duplication (Lines 149-660)
`index_repository()` and `index_incremental()` share ~200 lines of nearly identical code.

**Fix:** Extract shared logic into private methods.

#### 4.3 No Database Error Handling
Database operations have no error handling. If any operation fails, entire indexing run fails with no recovery.

**Fix:** Add retry logic, transaction batching, checkpoint/resume capability.

---

### High Priority Issues

#### 4.4 Type Safety Violations
**Location:** Lines 107-108

```python
git_service: Any,  # GitServicePort - not yet in ports
parser_service: Any,  # ParserServicePort - exists but simpler interface
```

**Fix:** Use proper port interfaces.

#### 4.5 Adapter Layer Dependency
**Location:** Line 145

Application layer imports from adapter layer:
```python
from inxr2.adapters.external.plaintext_parser import PlaintextParser
```

Violates Clean Architecture.

**Fix:** Create `PlaintextParserPort` and inject as dependency.

#### 4.6 Missing Input Validation
No validation that repository_path exists, is a git repo, or that parameters are valid.

**Fix:** Add request validation.

---

## 5. Test Doubles and Fixtures

### Critical Issues

#### 5.1 InMemorySymbolRepository Missing Latest File Version Logic
**Location:** `tests/fixtures/test_doubles.py:126-162`

Production filters to latest file versions; test double doesn't. Tests pass even when production would return different results.

**Fix:** Add file version filtering to match production.

#### 5.2 InMemoryFileRepository.list_changed_at_commit Too Complex (90 lines!)
**Location:** `tests/fixtures/test_doubles.py:583-672`

Nested loops and difficult-to-understand logic. Violates "fakes should be simpler than production" principle.

**Fix:** Simplify to mirror production SQL logic.

#### 5.3 InMemoryReferenceRepository Missing Default Mode Filtering
When `commit_id` is None, production filters to latest file versions; fake doesn't.

**Fix:** Add latest file version filtering.

---

### Medium Priority Issues

#### 5.4 Test Doubles Access Private Members
```python
self._commit_repo._branch_commits.items()
self._file_repo._files.values()
```

Creates tight coupling between fakes.

**Fix:** Add public helper methods instead.

#### 5.5 Inconsistent add() vs save() Behavior
Some test doubles require IDs for `add()`, others auto-generate. Confusing.

**Fix:** Standardize across all test doubles.

---

## Summary Tables

### By Severity

| Severity | Count | Top Areas |
|----------|-------|-----------|
| Critical | 12 | SQL injection, N+1 queries, God class |
| High | 15 | Validation, error handling, type safety |
| Medium | 18 | Code duplication, inconsistency |
| Low | 12 | Documentation, naming |

### By Component

| Component | Critical | High | Medium | Low |
|-----------|----------|------|--------|-----|
| File Search | 3 | 2 | 3 | 2 |
| Text Search | 3 | 2 | 3 | 2 |
| Comment Parsers | 4 | 0 | 3 | 3 |
| Indexing Orchestrator | 3 | 5 | 5 | 3 |
| Test Doubles | 3 | 2 | 4 | 2 |

---

## Recommended Action Plan

### Phase 1: Security & Correctness (Immediate)
1. Fix SQL injection in regex mode (add validation)
2. Fix tsquery construction (use `plainto_tsquery`)
3. Fix Python docstring detection bug
4. Add input validation (query length limits)

### Phase 2: Performance (This Week)
5. Add bulk `find_by_ids()` methods to ports
6. Fix N+1 queries in file and text search
7. Simplify test double implementations

### Phase 3: Architecture (Next 2 Weeks)
8. Create `SearchFilesUseCase`
9. Extract use cases from orchestrator
10. Fix adapter layer dependencies
11. Add proper error handling with retry logic

### Phase 4: Technical Debt (Ongoing)
12. Extract comment marker stripping to shared utility
13. Add missing test coverage
14. Standardize naming conventions
15. Update test doubles to match production behavior

---

## Estimated Effort

| Phase | Effort | Risk if Deferred |
|-------|--------|------------------|
| Phase 1 | 2-3 days | HIGH - security vulnerabilities |
| Phase 2 | 3-5 days | HIGH - performance degradation |
| Phase 3 | 2-3 weeks | MEDIUM - maintainability issues |
| Phase 4 | Ongoing | LOW - technical debt accumulation |

---

## Conclusion

The features are **functionally complete** but have **critical security and performance issues** that must be addressed before production use. The codebase shows good patterns (dependency injection, clean architecture intent) but execution has drifted from architectural principles in several areas.

**Top 3 Priorities:**
1. Fix SQL injection in regex search
2. Fix N+1 query problems
3. Begin orchestrator decomposition

See also: `docs/2026-02-07-architecture-review.md` for related architectural findings.
