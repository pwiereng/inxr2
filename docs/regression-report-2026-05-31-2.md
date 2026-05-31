# Regression Test Report — 2026-05-31 (Run 2)

> Second full regression run of the day (the earlier run is `regression-report-2026-05-31.md`).

## Summary

| Phase | Passed | Total | Notes |
|-------|--------|-------|-------|
| Indexing | 8 | 8 | |
| Browser | 39 | 39 | |
| MCP | 26 | 26 | |
| **Total** | **73** | **73** | **0 skipped, 0 failed** |

**Regression suite: 73/73 passed (8 indexing + 39 browser + 26 MCP).**

## Component Versions

| Component | Version |
|-----------|---------|
| inxr2 | 0.1.0 |
| Python | 3.11.15 |
| FastAPI | 0.136.3 |
| PostgreSQL | 17.10 (Debian) |
| Tree-sitter | 0.25.2 |
| Node | 20.20.2 |
| React | 19.2.6 |
| Vite | 6.4.2 |
| TypeScript | 6.0.3 |
| MUI | 5.15.0 |
| MCP lib | 1.27.2 |
| Docker engine | 29.2.1 |
| Codebase HEAD | df316ff |

Other notable: SQLAlchemy 2.0.50, Alembic 1.18.4, Pydantic 2.13.4, Uvicorn 0.48.0, GitPython 3.1.50, npm 10.8.2, Vitest 4.1.7.

---

## Phase 1: Indexing (8/8 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| IX-01 | Reset DB and index all repos (10 days) | PASS | 19/19 repos OK, 0 failures. 862,250 file versions, 4,603,912 lines, resolution 2,102,241/2,620,990 (80.2%), 20m 27s total. |
| IX-02 | Verify indexing status | PASS | `inxr2 status` lists 19 repos, all "Completed", all non-zero files/symbols/references. |
| IX-03 | Verify API serves indexed data | PASS | `/api/repositories/stats` returns all 19 repos, non-zero counts, language maps present. |
| IX-04 | Multi-language symbols (10 langs) | PASS | All 10 languages produce symbols, cross-checked against git source (see note on filter param below). |
| IX-04a | Reference extraction | PASS | express `lib/response.js`: 772 refs — 13 import, 599 usage, 154 call, 6 instantiation. require targets → import, bare identifiers → usage. |
| IX-04b | ES6 export/re-export references | PASS | inxr2 `frontend/src/test/utils.tsx`: `export *` (barrel) + `export { customRender as render }` → 12 import, 21 usage, 7 type_annotation, 2 call. |
| IX-05 | Performance comparison | PASS | No genuine regressions (table below). |
| IX-06 | FileFilter completeness (#349) | PASS | All 19 repos: git-vs-API file sets match. inxr2 `adapters/external/` = 60 files present. |

### IX-05 Performance Comparison (prev 15:08 run → this 19:30 run)

| Repo | Branch | Commits (prev → now) | Elapsed (prev → now) | Symbols (prev → now) | Refs Resolved % |
|------|--------|---------------------|---------------------|---------------------|-----------------|
| crisp | main | 1 → 1 | 1.5s → 1.5s | 1330 → 1330 | 73.1% → 73.1% |
| inxr | master | 1 → 1 | 0.5s → 0.4s | 253 → 253 | 39.6% → 39.6% |
| inxr2 | main | 21 → 29 | 21.3s → 22.6s | 8512 → 8526 | 59.1% → 58.1% |
| multidockerdevcontainer | main | 1 → 1 | 2.3s → 2.3s | 975 → 975 | 35.8% → 35.8% |
| soccer-stats | main | 1 → 1 | 0.5s → 0.4s | 210 → 210 | 64.8% → 64.8% |
| cJSON | master | 1 → 1 | 3.7s → 3.6s | 2622 → 2622 | 56.6% → 56.6% |
| clean-architecture | main | 1 → 1 | 1.6s → 1.6s | 745 → 745 | 44.9% → 44.9% |
| Java | master | 6 → 5 | 22.5s → 21.6s | 11913 → 11913 | 60.4% → 60.4% |
| bubbletea | main | 1 → 1 | 4.0s → 3.9s | 1705 → 1705 | 49.9% → 49.9% |
| spdlog | v1.x | 1 → 1 | 7.0s → 7.0s | 3001 → 3001 | 40.3% → 40.3% |
| sinatra | main | 1 → 1 | 5.1s → 5.0s | 954 → 954 | 53.6% → 53.6% |
| Bash-Snippets | master | 1 → 1 | 1.0s → 1.0s | 453 → 453 | 31.8% → 31.8% |
| express | master | 1 → 1 | 4.7s → 4.7s | 592 → 592 | 58.9% → 58.9% |
| travelbuddy | main | 6 → 6 | 4.5s → 4.6s | 2546 → 2546 | 59.8% → 59.8% |
| appbase | main | 1 → 1 | 0.2s → 0.2s | 49 → 49 | 48.5% → 48.5% |
| carbingo | main | 1 → 1 | 0.2s → 0.2s | 46 → 46 | 48.9% → 48.9% |
| sentimeter | main | 1 → 1 | 2.3s → 2.2s | 980 → 980 | 47.1% → 47.1% |
| geobuddy | main | 68 → 73 | 4.3s → 4.9s | 1853 → 2036 | 54.8% → 54.2% |
| git | master | 134 → 175 | 850.8s → 1139.0s | 112474 → 127924 | 84.2% → 84.2% |

Snapshot (single-commit) repos are bit-identical run-over-run. The only deltas are on multi-commit
repos whose rolling `--days 10` window slid forward:
- **git** elapsed +34% (850.8s → 1139.0s) is fully explained by indexing **+41 more commits** (134 → 175);
  resolution held at 84.2% and symbols rose. Not flagged (higher commit count explains higher elapsed).
- **inxr2** (21 → 29 commits) and **geobuddy** (68 → 73 commits) show sub-1pp resolution wobble
  (59.1→58.1, 54.8→54.2) with symbol counts flat/up — attributable to the larger commit window, not a parser regression.

---

## Phase 2: Browser (39/39 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| RT-01 | Home page repo cards | PASS | 19 card links = 19 API repos. |
| RT-02 | Repo card statistics | PASS | crisp: 109 files / 1.3K symbols / 73% resolved / c,cpp,makefile — matches API. |
| RT-02a | Repo card indexing stats | PASS | Each card shows files, symbols, resolution %, langs, commit range, last-indexed, duration. |
| RT-03 | Navigate to browse from home | PASS | → `/browse/crisp?branch=main`. |
| RT-04 | File tree matches git | PASS | inxr2 top-level dirs/files match `git ls-tree`. |
| RT-05 | Directory expansion | PASS | `.claude` → `skills`, `settings.json` (matches git). |
| RT-06 | Code viewer content | PASS | Line 1 = `"""` matches git; row count matches (trailing-newline off-by-one). |
| RT-07 | Line numbers clickable | PASS | line-5 cell click → URL `line=5`. |
| RT-08 | Symbol click opens references | PASS | FileFilter → panel with Definition `file_filter.py:20`. |
| RT-09 | References panel shows usages | PASS | 15 refs (process_commit.py, test_file_filter.py); both files exist in git. |
| RT-10 | "Search globally" link | PASS | → `/search?query=FileFilter`. |
| RT-11 | Blame matches git blame | PASS | line-1 commit `5e0a9319`, author Paul Wierenga — matches `git blame`. |
| RT-12 | Diff mode enter/exit | PASS | enter → `diff=<commit>`; exit → removed. |
| RT-12a | Diff colors temporal order | PASS | additions green `rgba(80,161,79,.14)`, deletions red `rgba(228,86,73,.14)`; older=left, newer=right. |
| RT-12b | Diff version selectors | PASS | left selector resolves to oldest indexed version `d5971141` (API oldest); right = HEAD. |
| RT-13 | Keyword search | PASS | "FileFilter" → 20 results; first = file_filter.py:20 (exists in git). |
| RT-14 | Search result click | PASS | → `/browse/inxr2/...file_filter.py?line=20`. |
| RT-15 | Regex search | PASS | `def should_skip` → 2 real matches. |
| RT-16 | File search | PASS | "file_filter" → file_filter.py, test_file_filter.py, .rb. |
| RT-16a | Extensionless file search | PASS | "Dockerfile" → 5 repos (lang=dockerfile); click → Java/.devcontainer/Dockerfile. |
| RT-17 | History matches git log | PASS | top commits 411387d, b8295e1, be3f427... match `git log --oneline`. |
| RT-18 | Commit click → browse | PASS | commit button → `/browse/inxr2?commit=411387d...`. |
| RT-19 | Tab navigation context | PASS | Search/History/Browse tabs preserve `repo=inxr2`, `branch=main`. |
| RT-20 | Branch selector | PASS | inxr2 test-repo has only `main`; selector shows it. |
| RT-21 | URL state on reload | PASS | `branch=main` and `line=10` preserved. |
| RT-22 | Theme toggle | PASS | light `rgb(247,246,242)` → dark `rgb(30,30,30)` → reverts. |
| RT-22a | Diff colors both themes | PASS | light add/del `(80,161,79)/(228,86,73)`; dark `(46,160,67)/(248,81,73)` — theme-adapted, distinguishable. |
| RT-23 | Markdown rendering | PASS | `# Close Skill` → H1 "Close Skill". |
| RT-24 | Logical View loads tree | PASS | 397 container nodes (~398 API files), no "Coming Soon". |
| RT-25 | Logical View expand file | PASS | App.test.tsx → `renderApp()` function, `mockRepositories` variable (matches API). |
| RT-26 | Logical View symbol → browse | PASS | "Go to line 25" button → `/browse/.../App.test.tsx?line=25`. |
| RT-27 | Logical View filters | PASS | `language=python` → 300 `.py` files (from 397; inxr2 has 301 py). |
| RT-28 | Dependencies tab | PASS | "695 packages in 5 files @ 411387d" (matches API total=695); Language/Type/Scope filters. |
| RT-29 | Dependencies commit picker | PASS | `?commit=b8295e1` → URL has commit, 695 packages shown. |
| RT-30 | Dependencies empty state | PASS | nonexistent repo → "not found", no crash. |
| RT-31 | References → Logical View link | PASS | "View in Logical View" → `/logical-view?repo=inxr2&file=...file_filter.py`. |
| RT-32 | Browse rename banner | PASS | new path at parent commit shows "this file was at docs/2026-03-08-architecture-review.md [Go to file]"; button → old path. |
| RT-33 | Diff rename following | PASS | R100 pure rename: both panes 431 rows, left resolved via rename-following, no error. (No delta — R100, per doc note.) |
| RT-34 | Mermaid renders as SVG | PASS | docs/archived/2026-03-23-mermaid-test.md → 60 SVG els, flowchart rendered, no raw `graph TD` text. |

---

## Phase 3: MCP Server (26/26 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| MCP-01 | List repos | PASS | 19 repos, each with indexed branch + head, all `commits_behind: 0`. |
| MCP-02 | List repo detail / branches | PASS | inxr2: main 29 commits, head 411387d, behind 0. |
| MCP-03 | Search symbols | PASS | "Repository" → 3 of 150, classes with file:line. |
| MCP-04 | Search symbols by kind | PASS | kind=class all-class; kind=interface → 7 Swift protocols in travelbuddy (#385 KIND_ALIASES). |
| MCP-05 | Go to definition | PASS | SearchSymbolsUseCase → search_symbols.py:85, class, docstring. |
| MCP-06 | Find references | PASS | 46 refs, typed (import/type_annotation/call). |
| MCP-07 | Find references by type | PASS | ref_type=import → 3, all import. |
| MCP-08 | Search code (phrase) | PASS | "async def execute" → 3 results incl. list_repositories.py:29. |
| MCP-09 | Search code repo filter | PASS | all results from inxr2. |
| MCP-10 | No-match graceful | PASS | all 4 tools return readable no-results messages w/ query term. |
| MCP-11 | MCP unit tests | PASS | 154 passed in 0.54s. |
| MCP-12 | Browse URLs correct | PASS | all 4 tools emit `…/browse/…?line=N` with frontend_url, none without. |
| MCP-13 | Find dead code | PASS | 12 unreferenced symbols (kind/name/path/line), scan-cap noted. |
| MCP-14 | Find dead code by kind | PASS | kind=function → all function. |
| MCP-15 | Review helper blast radius | PASS | commit 411387d → "Blast radius", 3 changed files (resolved even for merge commit). |
| MCP-16 | Review helper changed-only | PASS | small commit b8295e1 → 3 files (not whole repo). |
| MCP-17 | Staleness warning | PASS | index current → no warning (correct). |
| MCP-18 | Browse URLs in dead_code/review | PASS | URLs present with frontend_url, absent without. |
| MCP-19 | get_file_structure | PASS | class FileFilter [L20-53] → should_skip; matches API, signatures shown. |
| MCP-20 | get_change_impact grouped | PASS | Source/Test files groups, 15 refs/2 files, depth2≥depth1. |
| MCP-21 | explain_symbol context | PASS | Location/Docstring/References(46); unknown → "not found". |
| MCP-22 | search_symbols wildcard | PASS | `*` → 5 of 8512 (#384 fixed). |
| MCP-23 | search_code extensions dedup | PASS | TraceLogger swift → 2 lines, no duplicates (#400 fixed). |
| MCP-24 | search_code has file path | PASS | 0 commit-message-like lines (#387 fixed). |
| MCP-25 | search_code code bodies | PASS | RouteLeg swift → 10 results, all .swift (#395 fixed). |
| MCP-26 | search_code source_only | PASS | .md 16 → 0, .swift retained with source_only=true. |

---

## Known Issues / Observations

1. **Regression-test doc uses a non-functional `repository_name` param on `/api/symbols`.**
   The `/api/symbols` (search_symbols) route declares only `repository_id` — FastAPI silently drops the
   unknown `repository_name` query param, so the documented IX-04 / MCP-04 / MCP-20 example curls
   (`...?q=X&repository_name=<repo>`) run **unfiltered** and return cross-repo results. This is a
   **test-doc inaccuracy, not a product bug** — filtering works correctly via `repository_id`, and the
   MCP layer resolves repo name → id internally (verified: MCP-04 `repository=travelbuddy` correctly
   returned only travelbuddy protocols). IX-04 was re-run with `repository_id` and passed for all 10
   languages. *Suggestion: update the doc's `/api/symbols` examples to use `repository_id`.*

2. **`geobuddy` is a Swift repo, not TypeScript; `crisp` is C/C++.** The IX-04 language→repo mapping in
   the plan is loose. TypeScript was verified via `multidockerdevcontainer` (99 ts/tsx symbols) and
   `inxr2` (118 ts/tsx files). Worth pinning representative repos per language in the doc.

3. **IX-06 git path-quoting artifact.** `git ls-tree` octal-quotes non-ASCII paths (`core.quotePath`),
   so two express files with CJK / `snow ☃` names appeared "missing" until re-run with
   `core.quotePath=false` (then 0 missing). The `git` repo's lone "missing" entry `sha1collisiondetection`
   is a submodule (mode 160000), correctly not indexed as a file. Comparisons should set
   `core.quotePath=false`.

4. **MCP-13 output header wording differs from the doc's assertion string.** The tool prints
   `Dead code in '<repo>': N symbols with no references` rather than the doc's expected
   `Unreferenced symbols` / `No unreferenced symbols`. Behavior is correct; the doc's hardcoded
   assertion string is stale.

5. **Stale `index.log` CSV header.** The on-disk header lists 15 columns but rows carry 18
   (`file_versions_new/cached`, `db_size_mb`, `db_size_added_mb` were added later). Cosmetic — the
   writer (`index_command.py`) emits the correct 18-column rows; only the long-lived header row predates
   the schema change.

6. **Logical View symbol navigation is via the "Go to line N" arrow button**, not the symbol-name text
   (clicking the name only sets the `file=` context). RT-26's documented `.MuiCollapse-root button`
   selector no longer matches the leaf DOM (leaves are `MuiListItemText` spans). Test still passes via
   the correct target; doc selector could be refreshed.
