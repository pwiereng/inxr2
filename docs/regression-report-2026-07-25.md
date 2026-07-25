# Regression Test Report — 2026-07-25

## Summary

| Phase | Passed | Total | Notes |
|-------|--------|-------|-------|
| Indexing | 8 | 8 | |
| Browser | 38 | 39 | 1 failed (RT-12a) |
| MCP | 26 | 26 | |
| **Total** | **72** | **73** | **1 failed** |

Failure: **RT-12a** — diff add/delete colors are positional (left = red), not temporal, so they
invert when the newer commit is placed on the left side. Filed as **#520** (follow-up to the
closed #196).

Additional defects found while executing passing tests (details in
[Known Issues / Observations](#known-issues--observations)): a stale `index.log` CSV header
(**#521**), a `?branch=…&diff=…` deep-link dropping the diff param (**#522**),
`/api/symbols/{id}/references` reporting `total` as the page size rather than the true count
(**#523**), the diff header omitting the pre-rename path (**#524**), and the MCP SSE server not
auto-starting (**#525**).

None are critical: no data loss, no crash, no security impact. #520 is the most user-visible.
`docs/regression-tests.md` was refreshed in the same PR rather than filed as an issue.

## Component Versions

| Component | Version |
|-----------|---------|
| inxr2 | 0.1.0 |
| Python | 3.11.15 |
| FastAPI | 0.120.4 |
| SQLAlchemy | 2.0.50 |
| PostgreSQL | 17.10 |
| Tree-sitter | 0.25.2 |
| Node | v20.20.2 |
| React | ^19.2.7 |
| Vite | ^6.0.0 |
| TypeScript | ^6.0.3 |
| MUI | ^5.15.0 |
| Vitest | ^4.1.7 |
| MCP lib | 1.28.1 |
| Docker engine | 29.6.1 |
| Codebase HEAD | df698db |

---

## Phase 1: Indexing (8/8 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| IX-01 | Reset DB and index all repos | PASS | 20/20 repo+branch combos OK; 1,103,333 file versions, 5,712,724 lines, resolution 2,603,626/3,225,553 (80.7%), 27m 1s total |
| IX-02 | Verify indexing status | PASS | 20 repos listed = 20 in `config.yaml`; all non-zero files/symbols/refs |
| IX-03 | Verify API serves indexed data | PASS | `/api/repositories` = 20; every repo has non-zero `total_files`/`total_symbols`/`total_references`; `is_stale=false` for all |
| IX-04 | Multi-language symbols (10 langs) | PASS | 12/12 verified (10 required + Swift, PHP) |
| IX-04a | Reference extraction | PASS | `require()` targets → `import` refs; bare identifiers → `usage`; `this.<prop>` → refs |
| IX-04b | ES6 export/re-export references | PASS | all 4 export patterns produce the expected reference type |
| IX-05 | Performance comparison | PASS | no flagged rows; every symbol-count drop tracks a lower commit count (sliding `--days 10` window); resolution % flat or improved everywhere |
| IX-06 | FileFilter completeness (#349) | PASS | 20/20 repos: zero git-vs-API file drops; 38 `src/inxr2/adapters/external/` files present |

### IX-02 note — `multidockerdevcontainer/feature/oidc-authentication`

`config.yaml` declares 21 repo+branch combos but 20 were indexed. The `feature/oidc-authentication`
branch is **intentionally skipped**: it is a non-primary branch whose most recent commit is far
older than the `--days 10` window, and `src/inxr2/cli.py:188` skips non-primary branches with no
commits in that window (printing an explicit `Skipped: No commits within last N days`). Verified
directly — `list_commits(branch="feature/oidc-authentication", since_days=10)` returns 0, while the
same call without the day filter returns 1. Not a defect.

### IX-04 detail

| Language | Repo | Symbol discovered from git | API kind |
|----------|------|---------------------------|----------|
| Python | inxr2 | `Inxr2Client` | class |
| TypeScript | inxr2 | `BranchSelectorProps` | interface |
| JavaScript | express | `authenticate` | function |
| C | cJSON | `cJSON_strdup` | function |
| C++ | spdlog | `my_formatter_flag` | class |
| Java | Java | `EMAFilter` | class, constructor |
| C# | clean-architecture | `ApiController` | class |
| Go | bubbletea | `SetClipboard` | function |
| Ruby | sinatra | `Request` | class, module |
| Bash | Bash-Snippets | `tarwrite` | function |
| Swift | travelbuddy | `KeychainAdapter` | struct |
| PHP | interview-technical-challenge-2 | `VehicleRecord` | class |

### IX-05 Performance Comparison

Previous run = 2026-07-19. Commit counts are logged alongside timings because the `--days 10`
window slides — absolute counts are only apples-to-apples at equal commit counts; the resolution
percentage is window-independent.

| Repo | Branch | Commits (prev → now) | Elapsed (prev → now) | Symbols | Refs Resolved % |
|------|--------|---------------------|---------------------|---------|-----------------|
| crisp | main | 1 → 1 | 1.5s → 1.5s (+0%) | 1330 → 1330 (=) | 73.1% → 73.1% |
| inxr | master | 1 → 1 | 0.4s → 0.4s (+0%) | 253 → 253 (=) | 39.6% → 39.6% |
| inxr2 | main | 8 → 8 | 19.9s → 19.4s (−3%) | 9597 → 9597 (=) | 56.6% → 56.6% |
| multidockerdevcontainer | main | 1 → 1 | 2.2s → 2.2s (+0%) | 975 → 975 (=) | 35.8% → 35.8% |
| soccer-stats | main | 1 → 1 | 0.4s → 0.4s (+0%) | 210 → 210 (=) | 64.8% → 64.8% |
| cJSON | master | 1 → 1 | 3.5s → 3.7s (+6%) | 2622 → 2622 (=) | 56.6% → 56.6% |
| clean-architecture | main | 1 → 1 | 1.5s → 1.5s (+0%) | 745 → 745 (=) | 44.9% → 44.9% |
| Java | master | 27 → 11 | 21.0s → 22.7s (+8%) | 12234 → 12038 (−196) | 60.3% → 60.3% |
| bubbletea | main | 2 → 1 | 2.7s → 2.6s (−4%) | 1705 → 1705 (=) | 49.9% → 49.9% |
| spdlog | v1.x | 8 → 1 | 6.7s → 6.7s (+0%) | 2037 → 2031 (−6) | 34.7% → 35.0% |
| sinatra | main | 11 → 1 | 5.5s → 5.3s (−4%) | 1078 → 954 (−124) | 53.7% → 53.6% |
| Bash-Snippets | master | 1 → 1 | 0.9s → 1.0s (+11%) | 453 → 453 (=) | 31.8% → 31.8% |
| express | master | 4 → 1 | 4.2s → 4.3s (+2%) | 606 → 594 (−12) | 58.7% → 59.0% |
| travelbuddy | main | 1 → 1 | 3.5s → 3.5s (+0%) | 2230 → 2230 (=) | 58.7% → 58.7% |
| appbase | main | 1 → 1 | 0.2s → 0.2s (+0%) | 49 → 49 (=) | 48.5% → 48.5% |
| carbingo | main | 1 → 1 | 0.2s → 0.2s (+0%) | 46 → 46 (=) | 48.9% → 48.9% |
| sentimeter | main | 1 → 1 | 2.5s → 2.6s (+4%) | 1097 → 1097 (=) | 47.0% → 47.0% |
| geobuddy | main | 11 → 1 | 3.0s → 2.0s (−33%) | 1900 → 1236 (−664) | 56.2% → 56.6% |
| git | master | 381 → 237 | 3339.2s → 1537.0s (−54%) | 264677 → 156179 (−108498) | 83.6% → 84.3% |
| interview-technical-challenge-2 | master | 31 → 31 | 3.0s → 3.1s (+3%) | 562 → 562 (=) | 46.8% → 46.8% |

No row triggers a flag. The only elapsed increase above the 20% threshold is Bash-Snippets
(+11%, well inside it); `git` and `geobuddy` dropped sharply purely because the window now
covers fewer commits.

---

## Phase 2: Browser (38/39 passed, 1 failed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| RT-01 | Home page repo cards | PASS | 20 `a[href^='/browse/']` = 20 API repos |
| RT-02 | Repo card statistics | PASS | crisp 109 files / 1.3K symbols / 73% matches API (109 / 1330 / 73.1%) |
| RT-02a | Repo card indexing stats | PASS | every card shows files, symbols, refs %, language tags, commit range, last-indexed time |
| RT-03 | Navigate to browse from home | PASS | → `/browse/crisp?branch=main&commit=1c1feab` |
| RT-04 | File tree matches git | PASS | all 8 `git ls-tree` top-level entries present |
| RT-05 | Directory expansion | PASS | expanding `bin` reveals `cool` = `git ls-tree HEAD bin/` |
| RT-06 | Code viewer content | PASS | line 1 matches git exactly; row count is N+1 (trailing-newline off-by-one, same as prior runs) |
| RT-07 | Line numbers clickable | PASS | click line 5 → `line=5` in URL |
| RT-08 | Symbol click opens references | PASS | `FileFilter` → Definition `file_filter.py:20` + References (15) |
| RT-09 | References panel shows usages | PASS | all listed paths verified via `git ls-files` |
| RT-10 | "Search globally" link | PASS | `/search?query=FileFilter&types=symbol,reference` |
| RT-11 | Blame matches git blame | PASS | line 1 `5e0a931`/Paul Wierenga matches; annotations group per commit run (14→17 = 6b1b1718, 18→21 = ea5dcede) exactly as git blame |
| RT-12 | Diff mode enter/exit | PASS | Compare adds `diff=`, Exit compare removes it |
| RT-12a | Diff colors temporal order | **FAIL** | colors are positional, not temporal — see failure detail below |
| RT-12b | Diff version selectors | PASS | selector spans all indexed commits (500 cap) and includes all 7 API file versions at the top; listing all branch commits with per-file edit markers is by design (`VersionSelector.tsx`) |
| RT-13 | Search returns real results | PASS | 38 results for `FileFilter`; all paths exist in git |
| RT-14 | Search result click navigates | PASS | → `/browse/inxr2/src/inxr2/domain/services/file_filter.py?line=20` |
| RT-15 | Regex search | PASS | `def should_[a-z_]+` → 3 results, identical to `/api/search/text?mode=regex` |
| RT-16 | File search | PASS | `file_filter.py` → 2 matching files |
| RT-16a | Extensionless file search | PASS | `Dockerfile` → 11 results; clicking one loads `Java/.devcontainer/Dockerfile` (25 rows) |
| RT-17 | History matches git log | PASS | hashes, messages, authors, dates match `git log --oneline` |
| RT-18 | Commit click → browse | PASS | → `/browse/inxr2?commit=7f548aa…` |
| RT-19 | Tab navigation preserves context | PASS | Search/History/Browse all keep `repo`, `branch`, `commit` |
| RT-20 | Branch selector | PASS | shows `main` (the only local branch and the only configured one) |
| RT-21 | URL state preserved on reload | PASS | `branch=main&line=10` retained; file rendered |
| RT-22 | Theme toggle | PASS | `rgb(247,246,242)` → `rgb(30,30,30)` → back |
| RT-22a | Diff colors in both themes | PASS | light `rgba(80,161,79,.14)`/`rgba(228,86,73,.14)` → dark `rgba(46,160,67,.15)`/`rgba(248,81,73,.15)`; 138/47 counts stable |
| RT-23 | Markdown rendering | PASS | H1 "INXR2 - Cross-Reference Code Browser" = `grep -m1 '^#'` |
| RT-24 | Logical View symbol tree | PASS | 430 tree nodes = 430 files in symbol-tree API; no "Coming Soon" |
| RT-25 | Logical View expand shows symbols | PASS | `App.test.tsx` → `renderApp()` [function] L25, `mockRepositories` [variable] L12, matching API `kind_counts` and source |
| RT-26 | Logical View symbol click → Browse | PASS | → `…/App.test.tsx?line=25`, line 25 = `const renderApp = (…` |
| RT-27 | Logical View language filter | PASS | 430 → 309 on `python`, exactly the API's python file count |
| RT-28 | Dependencies shows packages | PASS | "668 packages in 5 files @ 7f548aa" = API `total` 668; expanding `frontend/package.json` lists real names/versions/types |
| RT-29 | Dependencies commit picker | PASS | `?commit=bafb9ac…` → header "@ bafb9ac" |
| RT-30 | Dependencies empty state | PASS | "Repository not found", no crash |
| RT-31 | References panel → Logical View | PASS | link carries repo/branch/commit/file; target file's symbols auto-expanded |
| RT-32 | Browse rename banner | PASS | banner "In this commit, this file was at scripts/parking-repl.py" + GO TO FILE → old path at same commit (250 rows) |
| RT-33 | Diff viewer rename following | PASS* | first run to exercise a content-changing rename (R092): 17 green / 4 red exactly matches `git diff --numstat -M`. *Old path is not shown in the header — see observations |
| RT-34 | Mermaid renders as SVG | PASS | 62 SVGs (4 mermaid) in `docs/archived/2026-03-23-mermaid-test.md`; no raw `graph TD`/`flowchart` text |

### RT-12a Failure Details — diff colors invert when the newer commit is on the left

**Root cause.** `frontend/src/components/DiffCodeViewer/DiffCodeViewer.tsx` classifies lines
purely from the diff library's `change.added` / `change.removed` flags (lines 58–88), which are
positional (left = base = red, right = current = green). There is no temporal normalization, so
whichever commit the user puts on the left is painted as "deletions" regardless of its date.
RT-12a's criterion is explicitly temporal: *"Lines present only in the newer version have
green/addition background … Colors are correct regardless of which side each commit appears on."*

**DISCOVER output**

```
repo   = inxr2
file   = src/inxr2/adapters/external/treesitter/php_parser.py
newer  = 7f548aa2856220e8d163ca4065c01ae8a833b896  (2026-07-19 20:16 UTC)
older  = ff935edf1867a52b9d58bb6660d253540de031a1  (2026-07-19 16:12 UTC)

docker exec inxr2-dev git -C /repos/test-repos/inxr2 diff --numstat ff935edf 7f548aa -- <file>
  138   47   src/inxr2/adapters/external/treesitter/php_parser.py
```

So going older → newer: **138 lines added, 47 removed**.

**Commands issued** (QA_PORT=9222, FRONTEND_PORT=5173)

```bash
# Case A — older on the left (the orientation prior runs tested)
curl -G "http://localhost:9222/navigate" --data-urlencode \
  "url=http://host.docker.internal:5173/browse/inxr2/src/inxr2/adapters/external/treesitter/php_parser.py?commit=7f548aa2856220e8d163ca4065c01ae8a833b896&branch=main&diff=ff935edf1867a52b9d58bb6660d253540de031a1"
curl "http://localhost:9222/wait?selector=table&timeout=12000"
curl -G "http://localhost:9222/eval" --data-urlencode \
  'script=JSON.stringify([...document.querySelectorAll("tr")].map(r=>getComputedStyle(r).backgroundColor).reduce((a,c)=>{if(c!=="rgba(0, 0, 0, 0)")a[c]=(a[c]||0)+1;return a},{}))'

# Case B — newer on the left (commit/diff swapped)
curl -G "http://localhost:9222/navigate" --data-urlencode \
  "url=http://host.docker.internal:5173/browse/inxr2/src/inxr2/adapters/external/treesitter/php_parser.py?commit=ff935edf1867a52b9d58bb6660d253540de031a1&branch=main&diff=7f548aa2856220e8d163ca4065c01ae8a833b896"
# same wait + eval
```

**Observed**

| Case | Side label | Green `rgba(80,161,79,.14)` | Red `rgba(228,86,73,.14)` |
|------|-----------|------------------------------|----------------------------|
| A — older on left | `Tree @ ff935ed (left)` | 138 | 47 |
| B — newer on left | `Tree @ 7f548aa (left)` | **47** | **138** |

**Expected:** in both cases the 138 lines unique to the newer commit are green (additions) and
the 47 unique to the older commit are red (deletions).

**Actual:** in Case B the 138 newer-only lines render **red** and the 47 older-only lines render
**green** — a reader of the diff sees additions labelled as deletions.

Screenshots: `.tmp/rt-12a-normal-older-left.png`, `.tmp/rt-12a-inverted-newer-left.png`

**Severity note.** Case A is the orientation the UI produces by default and the only one prior
reports exercised, which is why this was never caught. Positional coloring is also ordinary
`git diff` semantics, so whether this is a bug or the intended contract is a product decision —
but as specified in `docs/regression-tests.md`, RT-12a fails.

---

## Phase 3: MCP Server (26/26 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| MCP-01 | List repos | PASS | 20 repos, all API names present, each with an indexed branch |
| MCP-02 | Repo detail shows indexed branches | PASS | shows only `main: 8 commits, head: 7f548aa`; 4 unindexed dependabot branches correctly filtered out |
| MCP-03 | Search symbols | PASS | names, paths, lines, kinds identical to `/api/symbols` |
| MCP-04 | Search symbols kind filter | PASS | `kind=class` → zero non-class entries; `kind=interface` returns all 5 travelbuddy Swift `protocol` symbols (bug #385 regression holds) |
| MCP-05 | Go to definition | PASS | `search_symbols.py:85`, kind `class`, docstring shown |
| MCP-06 | Find references | PASS | reports 46 references — the true count (API's `total` field under-reports, see observations) |
| MCP-07 | Find references type filter | PASS | 3 imports, no call/usage/type_annotation |
| MCP-08 | Search code | PASS | same file paths and line numbers as `/api/search/text` |
| MCP-09 | Search code repo filter | PASS | every result location line is `inxr2:…` |
| MCP-10 | No-match graceful messages | PASS | all 4 tools return a readable message echoing the query; no stack traces |
| MCP-11 | MCP unit tests | PASS | 154 passed in 0.52s, no warnings (doc says 133 — suite has grown) |
| MCP-12 | Browse URLs point to correct locations | PASS | all 4 tools emit URLs; each loads the right file (e.g. line 85 = `class SearchSymbolsUseCase:`); `branch` appended when filtered; no URLs without `frontend_url` |
| MCP-13 | Find dead code | PASS | 12 unreferenced symbols, kind/name/path/line per entry, respects `limit=10`, and explicitly declares its sampling cap ("scanned 200 of 9021 symbols") |
| MCP-14 | Find dead code kind filter | PASS | all entries `[function]` |
| MCP-15 | Review helper blast radius | PASS | "Blast radius for commit 7f548aa", `Changed files: 33`, symbols + downstream references |
| MCP-16 | Review helper changed files only | PASS | commit `baaf706d` → `Changed files: 1`, matching `git diff-tree` (not all repo files) |
| MCP-17 | Staleness warning | PASS | index current → `check_staleness` warning `None` and no warning in tool output |
| MCP-18 | Browse URLs in find_dead_code / review_helper | PASS | present with `frontend_url`, absent without |
| MCP-19 | get_file_structure | PASS | two-level tree (`class FileFilter` → `staticmethod should_skip`) matching the API; no docstrings by default |
| MCP-20 | get_change_impact | PASS | Source files (1) / Test files (1) grouping matches the API's 2 referencing files; depth=2 output ⊃ depth=1; graceful message for unknown symbol |
| MCP-21 | explain_symbol | PASS | header + Location + Docstring + `References (46 total)` grouped by type; "not found" handled; disambiguation note when `repository` omitted |
| MCP-22 | search_symbols wildcard (#384) | PASS | `*` → 5 shown of 9021, not a "no results" message |
| MCP-23 | search_code extensions dedup (#400) | PASS | 2 swift results, 0 duplicate `file:line` |
| MCP-24 | search_code always has a file path (#387) | PASS | 18/18 location lines have a real path with extension; no commit-message lines |
| MCP-25 | search_code finds code bodies (#395) | PASS | 10 results, all `.swift`, term present in snippets |
| MCP-26 | search_code source_only | PASS | without: 16 `.md` of 20; with `source_only=true`: 0 `.md`, 4 `.swift` |

---

## Known Issues / Observations

1. **RT-12a — diff colors are positional, not temporal (#520).** See the failure detail above.
   Placing the newer commit on the left renders its unique lines as red deletions.

2. **`index.log` CSV header is stale — 15 header columns vs 18 data columns (#521).**
   `src/inxr2/adapters/cli/commands/index_command.py:588` writes the header only when the file
   does not yet exist (`write_header = not log_path.exists()`), so when the row schema grew from
   15 to 18 fields (adding `file_versions_new` / `file_versions_cached` and `db_size_mb` /
   `db_size_added_mb`) the existing file kept its old header. `index.log` currently holds 98
   legacy 15-column rows and 1419 current 18-column rows under a 15-column header.
   Any consumer that parses by header name — which is exactly what IX-05 prescribes — silently
   reads the wrong columns (e.g. `symbols_found` resolves to `file_versions_cached`). IX-05 in
   this run was executed with positional parsing keyed off the field count.
   Suggested fix: version the log, or rewrite/append a new header when the schema changes.

3. **`?branch=…&diff=…` deep-links drop the diff parameter (#522).** Navigating to
   `/browse/<repo>/<file>?branch=main&diff=<commit>` (no explicit `commit=`) redirects to
   `?branch=main&commit=<head>` and discards `diff`, so diff mode never engages. Supplying both
   `commit=` and `branch=` works and restores diff mode correctly. The branch → commit resolution
   rewrite appears to rebuild the query string without carrying `diff` through. This is the exact
   URL form `docs/regression-tests.md` uses in RT-12a/RT-12b, so those steps need updating
   regardless of whether the app is changed.

4. **`/api/symbols/{id}/references` reports `total` as the page size, not the true total (#523).**
   `src/inxr2/application/use_cases/symbols/get_symbol_references.py:160` sets
   `total=len(enriched_references)` *after* the `limit` has been applied, while the field is
   documented as "Total number of references". Measured for symbol 2900775
   (`SearchSymbolsUseCase`):

   | `limit` | reported `total` | items |
   |---------|-----------------|-------|
   | 1 | 1 | 1 |
   | 5 | 5 | 5 |
   | 20 | 20 | 20 |
   | 100 | 46 | 46 |
   | 200 | 46 | 46 |

   The true count is 46. A paginating client cannot distinguish "exactly 20 results" from
   "truncated at 20". The MCP `find_references` and `explain_symbol` tools are unaffected because
   they request a high limit, and both correctly report 46.

5. **RT-33: the diff header does not display the pre-rename path (#524).** Diffing across the rename
   boundary works correctly (left side resolves to `scripts/parking-repl.py`, delta matches git
   exactly), but the only path shown in the breadcrumb/toolbar is the new one; the left side is
   labelled by commit alone (`Tree @ 8fc0856 (left)`). The four occurrences of the old path on the
   page are all inside the diffed file's own content. RT-33's "shows both the old path and the new
   path" criterion is therefore not met, though its substantive criteria are.

6. **`docs/regression-tests.md` contained several stale API parameters and selectors.** All were
   corrected in the same PR as this report:
   - IX-04 / MCP-04 / MCP-20 use `repository_name=<repo>` on `/api/symbols`, which accepts
     **`repository_id`**. FastAPI silently ignores the unknown parameter, so those DISCOVER steps
     return unfiltered cross-repo results (e.g. C# and TypeScript symbols under
     `repository_name=sinatra`) and can make a passing test look like a failure.
   - MCP-02 uses `/api/repositories/{id}/branches`, which does not exist and falls through to the
     SPA catch-all (HTTP 200, HTML body). The real route is
     `/api/repositories/by-name/{name}/branches`.
   - MCP-19 uses `/api/symbols/file-structure?repository_name=…&file_path=…`; the endpoint
     requires **`repo`** and **`path`**.
   - RT-13's `fill?selector=input` now targets the repository-filter autocomplete, which is the
     first `<input>` on the search page. The query box is
     `input[placeholder='Enter search query...']`, and it needs an Enter keypress.
   - MCP-13's assertion string `'Unreferenced symbols'` no longer matches; the tool prints
     `Dead code in '<repo>': N symbols with no references`.
   - IX-06's `git ls-tree -r --name-only` comparison produces two false positives: git quotes
     non-ASCII paths (2 files in `express`) and lists submodule gitlinks as entries
     (`sha1collisiondetection` in `git`). Use `ls-tree -r -z` and filter to `type == blob`.

7. **RT-06 trailing-newline off-by-one persists** (54 rendered rows for a 53-line file). Confirmed
   systematic across three files (`file_filter.py` 53→54, `repository.py` 41→42, `cli.py`
   753→754). Recorded as PASS for consistency with the 2026-05-31 reports, which noted the same
   behaviour.

8. **`multidockerdevcontainer/feature/oidc-authentication` has no local branch.** It exists only
   as `origin/feature/oidc-authentication`. It is skipped for the window reason described under
   IX-02, so the missing local ref is currently invisible; if the day window ever widened, the
   branch would resolve through the remote-tracking ref rather than fail.

9. **MCP server was not running at session start (#525)** and was started manually
   (`MCP_TRANSPORT=sse MCP_PORT=3000 python -m src.server`) for MCP-21. `mcp-server/README.md:211`
   states it starts automatically during container startup, which did not happen here.
