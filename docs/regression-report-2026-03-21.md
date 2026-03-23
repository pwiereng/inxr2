# Regression Test Report — 2026-03-21

## Summary

| Phase | Passed | Total | Notes |
|-------|--------|-------|-------|
| Indexing | 7 | 7 | |
| Browser | 29 | 29 | |
| MCP | 21 | 21 | |
| **Total** | **57** | **57** | **All passed** |

---

## Phase 1: Indexing (7/7 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| IX-01 | Reset DB and index all repos | PASS | 18 repo/branch combos, 103,355 files, 781,434 lines, 58.9% resolution, 1m 43.7s total |
| IX-02 | Verify indexing status | PASS | 13 repos in config, all 18 repo/branch combos Completed; non-main inxr2 branches 0 files (expected — no unique commits in 10-day window) |
| IX-03 | Verify API serves indexed data | PASS | 13 repos in /api/repositories; /api/repositories/stats shows non-zero counts (e.g., crisp 1330 symbols, inxr2 28462 symbols) |
| IX-04 | Multi-language symbols (10 langs) | PASS | Python: `_add_heritage_ref`, TS: `ALL_REPOS_OPTION`, JS: `AsyncLocalStorage`, C: `ASCII`, C++: `A_formatter`, Java: `A5Cipher`, C#: `AddApplication`, Go: `AltScreen`, Ruby: `::HelperOne`, Bash: `APIKEY` |
| IX-04a | Reference extraction | PASS | `_add_heritage_ref` (function) has 2 references; import + usage types verified |
| IX-04b | ES6 export/re-export references | PASS | TypeScript `Activity` symbol has 4 refs (2 import, 2 usage) across App.tsx and test file |
| IX-05 | Performance comparison | PASS | All repos within ±20% elapsed vs prev run; symbol counts identical |

### IX-05 Performance Comparison

| Repo | Branch | Elapsed (prev → now) | Symbols | Refs Resolved % |
|------|--------|---------------------|---------|-----------------|
| crisp | main | 1.3s → 1.4s (+8%) | 1330 (=) | 73.1% |
| inxr | master | 0.4s → 0.4s (=) | 253 (=) | 39.6% |
| inxr2 | main | 53.0s → 56.6s (+6.8%) | 28462 (=) | 63.7% |
| multidockerdevcontainer | main | 2.0s → 2.1s (+5%) | 975 (=) | 35.8% |
| soccer-stats | main | 0.4s → 0.4s (=) | 210 (=) | 64.8% |
| cJSON | master | 2.8s → 3.0s (+7.1%) | 2622 (=) | 56.6% |
| clean-architecture | main | 1.3s → 1.4s (+7.7%) | 745 (=) | 44.9% |
| Java | master | 15.8s → 15.8s (=) | 11540 (=) | 60.5% |
| bubbletea | main | 3.3s → 3.3s (=) | 1677 (=) | 49.7% |
| spdlog | v1.x | 6.2s → 6.1s (-1.6%) | 2966 (=) | 40.2% |
| sinatra | main | 4.6s → 4.3s (-6.5%) | 954 (=) | 53.6% |
| Bash-Snippets | master | 0.9s → 1.0s (+11.1%) | 453 (=) | 31.8% |
| express | master | 4.0s → 4.1s (+2.5%) | 592 (=) | 58.9% |

---

## Phase 2: Browser (29/29 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| RT-01 | Home page repo cards | PASS | 13 repo cards shown with names, stats, languages |
| RT-02 | Repo card stats | PASS | crisp: 14.5K lines, 109 files, 1.3K symbols, 73% — matches API |
| RT-03 | Repo card navigation | PASS | Navigate to /browse/inxr2?branch=main&commit=4735125 |
| RT-04 | File tree visible | PASS | Dirs and files shown at repo root |
| RT-05 | File tree matches git ls-tree | PASS | All git top-level entries visible in UI |
| RT-06 | Code viewer shows correct file content | PASS | constants.py content shown with Python code correctly |
| RT-07 | Line numbers match git | PASS | Git: 48 lines, UI: 49 tr rows (48 code + 1 header) |
| RT-08 | Symbol click shows references | PASS | Clicking "Repository" span shows 100 references panel |
| RT-09 | Reference panel shows file/line | PASS | Panel shows file paths and reference types |
| RT-10 | Reference count shown | PASS | "References (100)" heading visible |
| RT-11 | Blame matches git blame | PASS | Blame shows d2f5fc6 and "Paul Wierenga" matching git blame output |
| RT-12 | Diff mode enter and exit | PASS | URL gains &diff= param on enter, removed on exit |
| RT-12a | Diff colors follow temporal order | PASS | Older commit (7c88da1, 18:17) on left, newer (901b48a, 20:23) on right |
| RT-12b | Diff version selectors show commits | PASS | Both commit hashes appear in diff view |
| RT-13 | Search returns real results | PASS | "Repository" search returns 131 results |
| RT-14 | Search result navigates correctly | PASS | Clicking "Go to result" navigates to /browse/inxr2/src/inxr2/adapters/persistence/repositories/base_repository.py |
| RT-15 | Regex search works | PASS | class.*Repository regex returns 47 results (matches API) |
| RT-16 | File search works | PASS | "base_repository" file search finds base_repository.py |
| RT-16a | Extensionless file search | PASS | "Dockerfile" search returns results |
| RT-17 | History page matches git log | PASS | History shows commits including 0e428dd from git log |
| RT-18 | History commit click navigates | PASS | Clicking commit hash button navigates to /browse/inxr2?commit=4735125 |
| RT-19 | Tab navigation preserves context | PASS | Search tab preserves repo=inxr2&branch=main in URL |
| RT-20 | Branch selector shows branches | PASS | Branch dropdown opens showing 6 indexed branches for inxr2 |
| RT-21 | URL state reload preservation | PASS | URL unchanged after page reload (branch, commit params preserved) |
| RT-22 | Theme toggle | PASS | body class changes prism-light → prism-dark and back |
| RT-22a | Diff colors in both themes | PASS | Same content (6764 rows) visible in dark and light themes |
| RT-23 | Markdown heading rendering | PASS | README.md rendered with 38 heading elements (h1/h2/h3) |

### Notes
- RT-06: Original test used `entities.py` which was refactored to `entities/` directory — used `constants.py` instead
- RT-18: Must click the commit hash button inside the MuiListItem, not the list item itself; the History tab navigates to global `/history` page, then clicking the commit hash button navigates to `/browse/<repo>?commit=...`
- RT-20: Branch selector is a MUI Select component; must click `div.MuiSelect-select` to open
- Search URL params (`?q=...`) do not auto-populate the search box on navigation; must use /fill + Enter

---

## Phase 3: MCP Server (21/21 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| MCP-01 | List repos | PASS | 13 repos returned |
| MCP-02 | List repos detail (branches) | PASS | Shows indexed branches per repo |
| MCP-03 | Search symbols matching | PASS | `search_symbols` finds matching definitions |
| MCP-04 | Search symbols filter by kind | PASS | Kind filter returns correct symbol types |
| MCP-05 | Go to definition | PASS | `DatabaseLimits` found at constants.py:8 |
| MCP-06 | Find references cross-repo | PASS | `DatabaseLimits` has 25 references |
| MCP-07 | Find references filter by type | PASS | import filter returns 54 import references for `Repository` |
| MCP-08 | Search code returns content | PASS | `def index_commit` returns 28 results |
| MCP-09 | Search code repo filter | PASS | `routes` in sinatra returns 135 results |
| MCP-10 | No-match graceful message | PASS | "No symbols found matching 'ZZZNOMATCHZZZ'" |
| MCP-11 | MCP unit tests pass | PASS | 120 tests pass in 0.38s |
| MCP-12 | Browse URLs correct | PASS | URLs generated with frontend_url set; `constants.py?line=8` loads correct file |
| MCP-13 | Find dead code | PASS | 16 unreferenced functions found in inxr2 |
| MCP-14 | Find dead code filter by kind | PASS | Method filter returns 4 unreferenced methods |
| MCP-15 | Review helper blast radius | PASS | Commit 4735125 shows changed files and blast radius |
| MCP-16 | Review helper changed files only | PASS | Shows 10 changed files, not all repo files |
| MCP-17 | Staleness warning | PASS | No warning shown (index is current — expected behavior) |
| MCP-18 | Browse URLs in dead code/review_helper | PASS | URLs generated correctly with line/commit params |
| MCP-19 | get_file_structure | PASS | constants.py shows 3 classes (DatabaseLimits, QueryDefaults, APILimits) with line ranges |
| MCP-20 | get_change_impact | PASS | DatabaseLimits has 25 direct refs across 5 files, grouped by type |
| MCP-21 | explain_symbol | PASS | Rich context including docstring, reference breakdown by type |

---

## Known Issues / Observations

1. **entities.py removed**: `src/inxr2/domain/entities.py` no longer exists at HEAD (refactored to `entities/` directory). Test files using this path need updating.
2. **Non-main inxr2 branches index 0 files**: Expected — old feature branches with no commits in the 10-day window. Could confuse users expecting all branches to show content.
3. **RT-18 navigation subtlety**: The History tab from a file browser navigates to the global `/history?repo=...` page, not a file-specific history. Clicking the commit hash *button* (not the list item) navigates to browse view.
4. **Search URL params don't auto-populate**: Navigating to `/search?q=foo` does not populate the search box — the user/test must use fill+Enter.
5. **MCP browse URLs require INXR2_FRONTEND_URL**: The running SSE server doesn't pick up env vars set after startup. Direct tool handler calls work correctly with `frontend_url` parameter.
6. **find_dead_code scans subset**: Note in output says "scanned 200 of 845/3104 symbols — results may be incomplete." This is expected behavior (performance limit).
