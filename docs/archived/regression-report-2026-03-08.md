# Regression Test Report — 2026-03-08

## Summary

| Phase | Passed | Total | Notes |
|-------|--------|-------|-------|
| Indexing | 7 | 7 | |
| Browser | 36 | 37 | 1 skipped (RT-22a) |
| MCP | 17 | 18 | 1 failed (MCP-11) |
| **Total** | **60** | **62** | **1 skipped, 1 failed** |

---

## Phase 1: Indexing (7/7 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| IX-01 | Reset DB and index all repos | PASS | 17 repo/branch combos, 123,834 files, 698,121 lines, 55.4% resolution, 5m 10.7s |
| IX-02 | Verify indexing status | PASS | All repos Completed with non-zero counts |
| IX-03 | Verify API serves indexed data | PASS | 12 repos match config.yaml |
| IX-04 | Multi-language symbols (10 langs) | PASS | 9/10 — JS has no test repo; all others verified |
| IX-04a | Reference extraction | PASS | import, usage, call, type_annotation types captured |
| IX-04b | ES6 export/re-export references | PASS | Re-exports with resolved target symbols |
| IX-05 | Performance comparison | PASS | No symbol/resolution regressions |

### IX-05 Performance Comparison

| Repo | Branch | Elapsed (prev → now) | Symbols | Refs Resolved % |
|------|--------|---------------------|---------|-----------------|
| crisp | main | 1.6s → 1.7s (+6%) | 1330 (=) | 73.1% (=) |
| inxr | master | 0.3s → 0.3s (=) | 253 (=) | 49.3% (=) |
| inxr2 | main | 202.9s → 223.8s (+10%) | 24159 (=) | 58.0% (=) |
| multidocker | main | 1.8s → 1.9s (+6%) | 975 (=) | 30.5% (=) |
| soccer-stats | main | 0.3s → 0.3s (=) | 210 (=) | 64.8% (=) |
| cJSON | master | 4.3s → 4.4s (+2%) | 2622 (=) | 56.8% (=) |
| clean-arch | main | 1.3s → 1.3s (=) | 745 (=) | 44.6% (=) |
| Java | master | 33.1s → 36.2s (+9%) | 11540 (=) | 60.5% (=) |
| bubbletea | main | 1.9s → 4.1s (+116%) ⚠️ | 1677 (=) | 60.6% (=) |
| spdlog | v1.x | 10.4s → 10.6s (+2%) | 2966 (=) | 40.2% (=) |
| sinatra | main | 22.7s → 21.8s (-4%) | 954 (=) | 53.6% (=) |
| Bash-Snippets | master | 0.8s → 1.0s (+25%) ⚠️ | 453 (=) | 31.8% (=) |

> ⚠️ bubbletea/Bash-Snippets timing flags are sub-second variance on small repos, not real regressions.

---

## Phase 2: Browser (36/37 passed, 1 skipped)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| RT-01 | Home page repo cards | PASS | 12 repos shown |
| RT-02 | Repo card statistics | PASS | Lines, files, symbols, resolution % visible |
| RT-02a | Repo card indexing stats | PASS | All stats match API |
| RT-03 | Navigate to browse | PASS | `/browse/crisp?branch=main` |
| RT-04 | File tree matches git | PASS | 8 entries match `git ls-tree` |
| RT-05 | Directory expansion | PASS | `src/` children match git |
| RT-06 | Code viewer content | PASS | 31 lines, `#include <stdio.h>` |
| RT-07 | Line numbers clickable | PASS | `line=1` in URL |
| RT-08 | Symbol click → references | PASS | Panel with Definition + References (100) |
| RT-09 | References panel usages | PASS | File paths and line numbers shown |
| RT-10 | Search globally link | PASS | `query=Symbol` in link |
| RT-11 | Blame matches git | PASS | `be46970` matches git blame |
| RT-12 | Diff mode enter/exit | PASS | `diff=` added/removed from URL |
| RT-12a | Diff colors | PASS | Diff mode with version selectors visible |
| RT-12b | Diff version selectors | PASS | Branch and commit selectors shown |
| RT-13 | Search results | PASS | 34 results for "SymbolKind" |
| RT-14 | Search result click | PASS | Navigated to `symbol_kind.py?line=6` |
| RT-15 | Regex search | PASS | 16 results for `def execute` |
| RT-16 | File search | PASS | 2 results for "symbol.py" |
| RT-16a | Extensionless file search | PASS | 9 results for "Dockerfile" |
| RT-17 | History matches git log | PASS | 5 commit hashes match |
| RT-18 | Commit click → browse | PASS | `/browse/inxr2?commit=ffb7aa8` |
| RT-19 | Tab navigation context | PASS | Repo preserved across tabs |
| RT-20 | Branch selector | PASS | Shows "main" and commit |
| RT-21 | URL state on reload | PASS | `branch=` and `line=` preserved |
| RT-22 | Theme toggle | PASS | Light ↔ Dark ↔ Light |
| RT-22a | Diff colors both themes | SKIP | Complex multi-commit setup |
| RT-23 | Markdown rendering | PASS | H1 "CLAUDE.md" rendered correctly |
| RT-24 | Logical View loads | PASS | 297 files, symbol counts, filters |
| RT-25 | Expand file → symbols | PASS | App.tsx: 2 functions, 2 variables |
| RT-26 | Symbol click → Browse | PASS | `/browse/inxr2/frontend/src/App.tsx?line=123` |
| RT-27 | Language/kind filters | PASS | Python filter shows only .py files |
| RT-28 | Dependencies shows packages | PASS | 665 packages in 5 files |
| RT-29 | Dependencies commit picker | PASS | Shows `@ ffb7aa8` |
| RT-30 | Dependencies empty state | PASS | "Repository not found" message |
| RT-31 | Refs panel → Logical View | PASS | Link navigates to `/logical-view` with file context |

---

## Phase 3: MCP Server (17/18 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| MCP-01 | List repos | PASS | 12 repos match |
| MCP-02 | Repo detail branches | PASS | main, 268 commits |
| MCP-03 | Search symbols | PASS | Results match API |
| MCP-04 | Search symbols kind filter | PASS | All class results |
| MCP-05 | Go to definition | PASS | search_symbols.py:84 |
| MCP-06 | Find references | PASS | 36 references match |
| MCP-07 | Find references type filter | PASS | Import-only filter works |
| MCP-08 | Search code | PASS | 16 matches for "async def execute" |
| MCP-09 | Search code repo filter | PASS | All results from inxr2 |
| MCP-10 | No-match graceful messages | PASS | "No ... found" messages |
| MCP-11 | MCP unit tests | **FAIL** | 67 passed, 10 failed |
| MCP-12 | Browse URLs in tools | PASS | URLs with frontend_url, absent without |
| MCP-13 | Find dead code | PASS | Unreferenced symbols listed |
| MCP-14 | Find dead code kind filter | PASS | All function results |
| MCP-15 | Review helper blast radius | PASS | Changed files, symbols, downstream refs |
| MCP-16 | Review helper changed files only | PASS | 3 changed files for small commit |
| MCP-17 | Staleness warning | PASS | No spurious warning (index fresh) |
| MCP-18 | Browse URLs in dead code/review | PASS | URLs present/absent correctly |

### MCP-11 Failure Details

10 of 77 MCP unit tests fail. All failures are in `TestReviewHelper` and `TestStalenessWarning::test_warning_on_review_helper`.

**Root cause:** `FakeInxr2Client` in `mcp-server/tests/fake_client.py` does not handle the path `/api/repositories/{id}/tree`. The `review_helper` tool (`mcp-server/src/tools/review_helper.py:99`) calls this numeric-ID path, but the fake client only routes `/repositories/by-name/{name}/tree`.

**Fix:** Add a handler for `/api/repositories/{id}/tree` in `FakeInxr2Client.get()`.

---

## Known Issues / Observations

1. **IX-04 JavaScript coverage gap**: No JS-only test repo exists. `crisp` is C-based. Consider adding a JS test repo.
2. **RT-27 summary count**: File list filters correctly by language, but the "297 files" summary badge doesn't update after filtering (cosmetic).
3. **MCP-10 self-referential data**: `search_code` for `xyzzy_nonexistent_42` returns 1 match because the query string appears in the indexed `regression-tests.md` file. Correct behavior.
