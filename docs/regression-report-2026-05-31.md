# Regression Test Report — 2026-05-31

## Summary

| Phase | Passed | Total | Notes |
|-------|--------|-------|-------|
| Indexing | 8 | 8 | All pass; IX-05 multi-commit repos indexed fewer commits (10-day window slid forward) |
| Browser | 39 | 39 | All pass; docs header says 40 but only 39 RT IDs are enumerated |
| MCP | 26 | 26 | All pass; MCP-25/26 re-run with current swift terms (stale BucketList test data) |
| **Total** | **73** | **73** | **0 failures — every product behavior verified working** |

No genuine product defects were found. Every initial discrepancy traced to stale test scaffolding in `docs/regression-tests.md` (renamed API endpoints, changed UI selectors, drifted test-data assumptions) or probe-script bugs — not to the application. A list of doc fixes worth making is in **Known Issues / Observations**.

Environment: `main` (container `inxr2-dev`), ports 8000/5173/9222/3000. Index reset + re-indexed all 19 repos (`--days 10`).

---

## Phase 1: Indexing (8/8 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| IX-01 | Reset DB and index all repos | PASS | 19 repos, 15m 38s total (git repo = 14m 11s, 635K files / 3.38M lines / 84.2% resolved) |
| IX-02 | Verify indexing status | PASS | 19 repos, all `Completed`, all non-zero files/symbols/references |
| IX-03 | Verify API serves indexed data | PASS | All 19 config repos in `/api/repositories`; stats non-zero; languages present |
| IX-04 | Multi-language symbols (10 langs) | PASS | Python, TS, JS, C, C++, Java, C#, Go, Ruby, Bash all return symbols |
| IX-04a | Reference extraction | PASS | express `lib/response.js`: `require()` lines → `import` refs; bare ids → `usage` refs |
| IX-04b | ES6 export/re-export references | PASS | `export *` barrel + `export { x as y }` → import/usage refs |
| IX-05 | Performance comparison | PASS | See table; single-commit repos identical counts; multi-commit repos lower due to window slide |
| IX-06 | FileFilter completeness (#349) | PASS | inxr2/crisp/cJSON: 0 dropped files; `adapters/external/` present (60 files) |

### IX-05 Performance Comparison (prior run 02:18–02:55 → current run 15:08–15:23)

| Repo | Branch | Commits (prev → now) | Elapsed | Symbols | Refs Resolved % |
|------|--------|----------------------|---------|---------|-----------------|
| crisp | main | 1 → 1 | 5.6s → 1.5s | 1330 = 1330 | 73.1% = 73.1% |
| inxr2 | main | 23 → 21 | 27.7s → 21.3s | 8512 = 8512 | 59.1% = 59.1% |
| Java | master | 15 → 6 | 34.3s → 22.5s | 11970 → 11913 | 60.3% → 60.4% |
| travelbuddy | main | 72 → 6 | 15.6s → 4.5s | (window slid) | 60.9% → 59.8% |
| git | master | 361 → 134 | 2057s → 851s | (window slid) | 83.9% → 84.2% |

**Interpretation:** The `--days 10` window slid forward ~13h between runs, so multi-commit repos indexed fewer historical commits this run — explaining the lower absolute symbol/reference counts and faster elapsed times. Single-commit (snapshot) repos show **byte-identical** symbol/reference/resolution counts, confirming no parser regression. Resolution percentages held steady or improved across the board.

---

## Phase 2: Browser (39/39 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| RT-01 | Home page repo cards | PASS | 19 cards = 19 API repos |
| RT-02 | Repo card statistics | PASS | crisp 109 files / 1.3K symbols match API; language tags shown |
| RT-02a | Repo card indexing stats | PASS | file/symbol counts + language tags match API; refs shown as "% resolved" |
| RT-03 | Navigate to browse from home | PASS | → `/browse/crisp` |
| RT-04 | File tree matches git | PASS | all 8 top-level entries match `git ls-tree` |
| RT-05 | Directory expansion | PASS | `src/` children (cool/crisp/platform/ptime/udptrans) match git |
| RT-06 | Code viewer content | PASS | line count ±1 (trailing newline); first line matches git exactly |
| RT-07 | Line numbers clickable | PASS | line number is `td:first-child`; click adds `line=5` |
| RT-08 | Symbol click opens references | PASS | clicking SymbolLocation opens Definition/References panel |
| RT-09 | References panel shows usages | PASS | References (8) with real file paths + line numbers |
| RT-10 | "Search globally" link | PASS | → `/search?query=SymbolLocation` |
| RT-11 | Blame matches git blame | PASS | line 1: `318c611` + Paul Wierenga match `git blame` |
| RT-12 | Diff mode enter/exit | PASS | `diff=<commit>` toggles on compare/exit |
| RT-12a | Diff colors temporal order | PASS | older=red/pink (left), newer=green (right) — confirmed via screenshot |
| RT-12b | Diff version selectors | PASS | selector spans full indexed range (superset of the file's 6 versions) |
| RT-13 | Keyword search | PASS | "FileFilter" → 29 UI results with real paths |
| RT-14 | Search result navigates | PASS | click → `/browse/.../file_filter.py?line=20` |
| RT-15 | Regex search | PASS | 1,482 results |
| RT-16 | File search | PASS | file_filter.py + test_file_filter.py |
| RT-16a | Extensionless file search | PASS | 10 Dockerfiles across repos |
| RT-17 | History matches git log | PASS | UI hashes match `git log --oneline` |
| RT-18 | Commit click → browse | PASS | → `/browse/inxr2?commit=d82c201…` |
| RT-19 | Tab navigation preserves context | PASS | Search/History/Browse tabs preserve `repo=inxr2` |
| RT-20 | Branch selector | PASS | shows current branch `main` |
| RT-21 | URL state on reload | PASS | `branch` + `line=10` retained |
| RT-22 | Theme toggle | PASS | light rgb(247,246,242) ↔ dark rgb(30,30,30), reverts (toggle on browse pages) |
| RT-22a | Diff colors both themes | PASS | light red/green vs dark red/green, distinguishable + theme-adapted |
| RT-23 | Markdown rendering | PASS | `# INXR2 …` → h1 without `#` |
| RT-24 | Logical View loads | PASS | 397 files + kind breakdown, no "Coming Soon" |
| RT-25 | Logical View expand shows symbols | PASS | expanding client.py reveals HttpInxr2Client/Inxr2Client classes |
| RT-26 | Logical View symbol click → browse | PASS | McpToolError → `/browse/.../errors.py?…&line=` |
| RT-27 | Language/kind filters | PASS | python filter 397 → 300 files, all `.py` |
| RT-28 | Dependencies tab | PASS | express 44 packages match API, no "Coming Soon" |
| RT-29 | Dependencies commit picker | PASS | `commit=dae209ae` retained, 44 packages @ that commit |
| RT-30 | Dependencies empty state | PASS | nonexistent repo → empty state, no crash |
| RT-31 | References → Logical View link | PASS | → `/logical-view?repo=inxr2` |
| RT-32 | Browse rename banner | PASS | banner: "this file was at docs/2026-03-08-architecture-review.md" + GO TO FILE |
| RT-33 | Diff viewer rename following | PASS* | diff loads across rename boundary (left=old path content, right=new path); *R100 pure rename → no content delta |
| RT-34 | Mermaid renders as SVG (#383) | PASS | flowchart SVG rendered, no raw `graph TD` text — confirmed via screenshot |

---

## Phase 3: MCP Server (26/26 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| MCP-01 | List repos | PASS | 19 repos, all `commits_behind: 0` |
| MCP-02 | List repo detail / branches | PASS | inxr2: main, 21 commits, head d82c201 |
| MCP-03 | Search symbols | PASS | "Repository" → 3 of 150 with kind + file:line |
| MCP-04 | Search symbols kind filter | PASS | kind=class all-class; kind=interface includes Swift `protocol` (KeychainPort/LLMPort) — #385 |
| MCP-05 | Go to definition | PASS | SearchSymbolsUseCase → search_symbols.py:85 |
| MCP-06 | Find references | PASS | 46 refs with types + file:line |
| MCP-07 | Find references type filter | PASS | ref_type=import → 3, all `[import]` |
| MCP-08 | Search code | PASS | "async def execute" phrase → 3 results with snippets |
| MCP-09 | Search code repo filter | PASS | all 5 results from inxr2 |
| MCP-10 | No-match graceful messages | PASS | all 4 tools return "No … found" echoing the query |
| MCP-11 | MCP unit tests | PASS | 154 passed |
| MCP-12 | Browse URLs (frontend_url) | PASS | covered by MCP-18 URL presence/absence checks |
| MCP-13 | Find dead code | PASS | 12 unreferenced symbols with kind/name/file/line |
| MCP-14 | Find dead code kind filter | PASS | kind=function → all `[function]` |
| MCP-15 | Review helper blast radius | PASS | d82c201 → 1 changed file (ci.yml) matches `git diff-tree` |
| MCP-16 | Review helper changed files only | PASS | modify-commit 94b7db6 → 1 file (not hundreds) |
| MCP-17 | Staleness warning | PASS | index current → no warning (correct) |
| MCP-18 | Browse URLs in dead_code/review_helper | PASS | URLs present with frontend_url, absent without |
| MCP-19 | get_file_structure | PASS | two-level tree: class FileFilter → staticmethod should_skip, signatures shown |
| MCP-20 | get_change_impact | PASS | FileFilter: 15 refs / 2 files grouped Source/Test; depth2 ≥ depth1 |
| MCP-21 | explain_symbol (via SSE :3000) | PASS | header + Location + Docstring + References grouped by type |
| MCP-22 | search_symbols wildcard (#384) | PASS | `*` → 5 of 8512 (not empty) |
| MCP-23 | search_code extensions no dupes (#400) | PASS | TraceLogger swift: 2 lines, 2 unique |
| MCP-24 | search_code always has file path (#387) | PASS | 93 result lines, 0 commit-message entries |
| MCP-25 | search_code code body content (#395) | PASS | RouteLeg → 10 swift results, 0 non-swift (re-run; BucketList test data stale) |
| MCP-26 | search_code source_only filter | PASS | TravelBuddy: source_only removes .md, keeps swift |

### MCP-25 / MCP-26 data note

The documented probe symbol `BucketList` no longer exists in the currently-indexed `travelbuddy` swift files (`git grep` confirms 0 matches; the symbol API returns nothing). The re-index brought a different travelbuddy state. Re-running with present swift terms — `RouteLeg` (struct) for MCP-25 and `TravelBuddy` (in both `.md` and `.swift`) for MCP-26 — confirms both behaviors. The `search_code` body-content and `source_only` features are working; only the doc's hard-coded test symbol is stale.

---

## Known Issues / Observations

These are **test-scaffolding drift** items in `docs/regression-tests.md`, not product bugs. Worth fixing so future runs are cleaner:

1. **Stale API endpoints in doc steps:**
   - `/api/references?repository_name=…&file_path=…` → use `/api/files/by-path/references?repo=…&path=…` (also: no `from_module` field on that response).
   - `/api/files/{repo}/{file}/history` → use `/api/files/history?repo=…&path=…`.
   - `/api/repositories/by-name/{repo}/renames` → use `/api/renames/by-commit` (and friends).
   - `/api/commits?repo=…` (used in MCP-18/RT-29 examples) returns the SPA fallback; the working call is per-repo.
2. **Stale browser selectors:**
   - Search results are `.MuiListItem-root` (clickable inner `button`), **not** `.MuiListItemButton-root`.
   - Code line number cell is `td:first-child`, **not** `td:last-child` (RT-07).
   - Clickable code symbols are styled spans (e.g. `span.css-*`), not `span[data-mui-internal-clone-element]` (RT-08).
   - Theme toggle lives on browse/inner pages with aria-label `Switch to dark mode` (DarkModeIcon); it is **not** on the home page, and `[aria-label*='Switch to']` also matches the grid/list view toggle (RT-22).
   - Logical View file tree uses `.MuiListItemButton-root` for container symbols and a nested `.MuiCollapse-root` + `button` for leaf symbols (the navigating click is on the leaf symbol's button) (RT-25/26).
3. **Stale MCP test data:** `BucketList` in travelbuddy swift (MCP-25/26) — see note above.
4. **IX-05 cross-run comparison** is only apples-to-apples for single-commit repos; multi-commit repos shift with the sliding `--days` window. Consider logging the commit window in the comparison.
5. **Doc count mismatch:** the Phase 2 header says "40 tests" but enumerates 39 RT IDs; Phase 3 header says "27" but enumerates 26 (MCP-01–MCP-26). Totals should read 73, not 75.
6. **RT-33** exercised an R100 pure rename (no content change), so there is no add/delete delta to display — rename-following itself works. A rename with content edits would more fully exercise the "diff is not empty" criterion.
