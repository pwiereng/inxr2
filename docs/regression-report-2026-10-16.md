# Regression Test Report — 2026-10-16

Run against PR #551 (`fix-547-548-stale-files-dead-code`, HEAD `a770d09`) in the slot-1 worktree
container `inxr2-fix-547-548-stale-files-dead-code-dev`, with the QA agent
`inxr2-fix-547-548-stale-files-dead-code-playwright` (ports: backend 8010, frontend 5183,
QA 9232, MCP 3010).

## Summary

| Phase | Passed | Total | Notes |
|-------|--------|-------|-------|
| Indexing | 8 | 8 | |
| Browser | 36 | 39 | 1 failed (RT-12a, known #520), 2 skipped (RT-32, RT-33: no renames in the window) |
| MCP | 26 | 26 | |
| **Total** | **70** | **73** | **2 skipped, 1 failed** |

**PR-specific finding:** `/api/search/extensions` (`PostgresFileSearchRepository.get_distinct_extensions`)
was missed by PR #551. Scoped to a repository with no branch, it reads every file version, so
carbingo lists `.pyc`, which no file at HEAD has (#547 class). With a branch, it picks the head with
the old `commit_date, id` tie-break, which selects `e378409` instead of `f57c9a7` on git/master
(#549 class). **Fixed in `af3b6bc`** after this run; see [Known Issues](#known-issues--observations) item 1.

New issues filed (all pre-existing, none caused by PR #551): **#552** (file history same-second
tie-break), **#553** (markdown front matter rendered as an H2), **#554** (fake extensions from dotted
filenames). Follow-up exploratory testing filed **#555**–**#557**; see
[Exploratory Testing](#exploratory-testing-after-af3b6bc).

## Component Versions

| Component | Version |
|-----------|---------|
| inxr2 | 0.1.0 |
| Python | 3.11.17 |
| FastAPI | 0.120.4 |
| SQLAlchemy | 2.0.50 |
| PostgreSQL | 17.11 |
| Tree-sitter | 0.25.2 |
| Node | v20.20.2 |
| React | ^19.2.7 |
| Vite | ^6.0.0 |
| TypeScript | ^6.0.3 |
| MUI | ^5.15.0 |
| Vitest | ^4.1.7 |
| MCP lib | 1.28.1 |
| Docker engine | 29.8.0 |
| Codebase HEAD | a770d09 |

---

## Phase 1: Indexing (8/8 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| IX-01 | Reset DB and index all repos | PASS | 20/20 repo+branch combos OK; 390,536 file versions, 3,856,871 lines, resolution 1,445,866/1,874,439 (77.1%), 10m 33s total. Multi-commit windows this run: carbingo 112, git 74, express 8, spdlog 6, Java 4, bubbletea 2 |
| IX-02 | Verify indexing status | PASS | 20 repos = 20 in `config.yaml`; all non-zero files/symbols/refs; `multidockerdevcontainer/feature/oidc-authentication` skipped by design ("No commits within last 10 days") |
| IX-03 | Verify API serves indexed data | PASS | `/api/repositories` = 20, every config name present; all stats non-zero, `is_stale=false` |
| IX-04 | Multi-language symbols (12 langs) | PASS | 12/12 (see table) |
| IX-04a | Reference extraction | PASS | express `lib/application.js`: `require()` targets → `import` refs (`finalhandler`, `http`, `View`…); 381 `usage` refs; all 5 `this.<prop> =` properties present |
| IX-04b | ES6 export/re-export references | PASS | named re-export → `import`; local `export { customRender as render }` → `usage`; `export default App` → `usage`; `export * from` → `import` |
| IX-05 | Performance comparison | PASS | no elapsed flag at equal/lower commit count; resolution-% drops on spdlog/express/carbingo follow commit-count growth (1 → N); see note |
| IX-06 | FileFilter completeness (#349) | PASS | 20/20 repos: 0 missing **and 0 extra** files vs `git ls-tree -r -z` (blobs) at HEAD; 38 `src/inxr2/adapters/external/` files present |

### IX-04 detail

| Language | Repo | Symbol discovered from git | API kind |
|----------|------|---------------------------|----------|
| Python | inxr2 | `Inxr2Client` | class |
| TypeScript | inxr2 | `FlatFileEntry` | interface |
| JavaScript | express | `logerror` | function |
| C | cJSON | `case_insensitive_strcmp` | function |
| C++ | spdlog | `my_formatter_flag` | class |
| Java | Java | `EMAFilter` | class, constructor |
| C# | clean-architecture | `ApiController` | class |
| Go | bubbletea | `SetClipboard` | function |
| Ruby | sinatra | `Request` | class, module |
| Bash | Bash-Snippets | `tarwrite` | function |
| Swift | travelbuddy | `KeychainAdapter` | struct |
| PHP | interview-technical-challenge-2 | `VehicleRecord` | class |

### IX-05 Performance Comparison

The previous run for every row is this worktree's earlier fresh full index (2026-10-16 01:18 UTC,
one commit per branch, no `--days`). Multi-commit rows are therefore 1 → N and not
apples-to-apples. The `index.log` header and all 62 rows have 18 columns (#521 does not apply to this
worktree's log).

| Repo | Branch | Commits (prev → now) | Elapsed (prev → now) | Symbols | Refs Resolved % |
|------|--------|---------------------|---------------------|---------|-----------------|
| crisp | main | 1 → 1 | 1.6s → 1.7s (+6%) | 1330 (=) | 73.1% → 73.1% |
| inxr | master | 1 → 1 | 0.5s → 0.5s (+0%) | 253 (=) | 39.6% → 39.6% |
| inxr2 | main | 1 → 1 | 20.1s → 20.0s (−0%) | 9059 (=) | 56.8% → 56.8% |
| multidockerdevcontainer | main | 1 → 1 | 2.3s → 2.4s (+4%) | 975 (=) | 35.8% → 35.8% |
| soccer-stats | main | 1 → 1 | 0.5s → 0.4s (−20%) | 210 (=) | 64.8% → 64.8% |
| cJSON | master | 1 → 1 | 3.7s → 3.9s (+5%) | 2623 (=) | 56.6% → 56.6% |
| clean-architecture | main | 1 → 1 | 1.6s → 1.6s (+0%) | 745 (=) | 44.9% → 44.9% |
| Java | master | 1 → 4 | 21.7s → 22.7s (+5%) | 13281 (=) | 60.1% → 60.1% |
| bubbletea | main | 1 → 2 | 4.2s → 3.1s (−26%) | 1772 (=) | 50.4% → 50.4% |
| spdlog | v1.x | 1 → 6 | 6.9s → 8.9s (+29%) | 2043 → 2148 (+105) | 35.0% → 33.0% |
| sinatra | main | 1 → 1 | 5.1s → 5.3s (+4%) | 954 (=) | 53.6% → 53.6% |
| Bash-Snippets | master | 1 → 1 | 1.0s → 1.1s (+10%) | 453 (=) | 31.8% → 31.8% |
| express | master | 1 → 8 | 4.8s → 6.4s (+33%) | 594 → 709 (+115) | 59.0% → 57.8% |
| travelbuddy | main | 1 → 1 | 3.9s → 4.0s (+3%) | 2230 (=) | 58.7% → 58.7% |
| appbase | main | 1 → 1 | 0.2s → 0.2s (+0%) | 49 (=) | 48.5% → 48.5% |
| carbingo | main | 1 → 112 | 4.2s → 16.5s (+293%) | 2427 → 6124 (+3697) | 69.7% → 67.0% |
| sentimeter | main | 1 → 1 | 2.6s → 2.9s (+12%) | 1097 (=) | 47.0% → 47.0% |
| geobuddy | main | 1 → 1 | 2.1s → 2.3s (+10%) | 1236 (=) | 56.6% → 56.6% |
| git | master | 1 → 74 | 150.1s → 526.5s (+251%) | 40651 → 86025 (+45374) | 82.3% → 84.0% |
| interview-technical-challenge-2 | master | 1 → 1 | 1.7s → 1.7s (+0%) | 457 (=) | 50.1% → 50.1% |

Every single-commit row is unchanged in symbols and resolution %. Every elapsed increase above 20%
comes with a higher commit count.

**Resolution-% drops (spdlog, express, carbingo).** These are not purely window effects, because PR
#551 deliberately narrows resolution targets to the files of the indexed head commit. To separate
the two, I counted the unresolved references whose text matches a symbol name found **only** in
the old target pool (the latest-by-id version of each path, not at head):

| Repo | Extra files in old pool | Names only in old pool | Unresolved refs that match them | Share of refs |
|------|------------------------|------------------------|-------------------------------|---------------|
| carbingo | 150 | 183 | 436 | 1.25% |
| express | 10 | 1 | 8 | 0.03% |
| spdlog | 6 | 0 | 0 | 0% |
| git | 932 | 135 | 899 | 0.06% |
| Java, bubbletea | 0 | 0 | 0 | 0% |

So the PR accounts for at most 1.25 of carbingo's 2.7-point drop, and none of spdlog's. Those 436
references would otherwise link to symbols in files that are deleted or superseded at HEAD, which
is the wrong-version linking #547 and #550 aim to stop. The rest of each drop comes from indexing
older file versions. Older code shows the same pattern: the 2026-07-25 report has spdlog at 34.7%
with 8 commits against 35.0% with 1.

### Extra PR-focused check (IX-06b)

The branch-head tree with **no** `commit=` (the latest-files path #547 fixed) matches git exactly on
every multi-commit repo:

| Repo | git files | API files | Deleted files served | Missing |
|------|-----------|-----------|---------------------|---------|
| carbingo | 280 | 280 | 0 | 0 |
| git | 4856 | 4856 | 0 | 0 |
| express | 214 | 214 | 0 | 0 |
| Java | 1683 | 1683 | 0 | 0 |
| spdlog | 186 | 186 | 0 | 0 |
| bubbletea | 233 | 233 | 0 | 0 |

The carbingo Logical View symbol tree (153 files) contains no path absent from HEAD. git/master's head
is the indexed `f57c9a7`, not `e378409` (one of 5 commits sharing timestamp 2026-10-15 14:44:31), so
#549 holds.

---

## Phase 2: Browser (36/39 passed, 1 failed, 2 skipped)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| RT-01 | Home page repo cards | PASS | 20 `a[href^='/browse/']` = 20 API repos |
| RT-02 | Repo card statistics | PASS | e.g. crisp 109 files / 1.3K symbols / 73% = API 109 / 1330 / 73.1%; git 4.9K / 86.0K / 84% = API 4856 / 86025 / 84.0% |
| RT-02a | Repo card indexing stats | PASS | every card shows lines, files, symbols, resolved %, language tags, commit range, last-indexed time, duration |
| RT-03 | Navigate to browse from home | PASS | → `/browse/crisp?branch=main&commit=1c1feab…` |
| RT-04 | File tree matches git | PASS | all 8 `git ls-tree` top-level entries present |
| RT-05 | Directory expansion | PASS | `bin` → `cool` = `git ls-tree HEAD bin/` |
| RT-06 | Code viewer content | PASS | `file_filter.py` line 1 matches git; 54 rows for 53 lines (known trailing-newline off-by-one) |
| RT-07 | Line numbers clickable | PASS | click line 5 → `line=5` |
| RT-08 | Symbol click opens references | PASS | `FileFilter` → Definition `file_filter.py:20`, References (15) |
| RT-09 | References panel shows usages | PASS | `process_commit.py:18` (import) and `test_file_filter.py` verified via `git ls-files`; line 18 is the import |
| RT-10 | "Search globally" link | PASS | `/search?query=FileFilter&types=symbol,reference` |
| RT-11 | Blame matches git blame | PASS | line 1 `5e0a931` / Paul Wierenga = `git blame --porcelain` |
| RT-12 | Diff mode enter/exit | PASS | Compare adds `diff=`, Exit compare removes it |
| RT-12a | Diff colors temporal order | **FAIL** (known #520) | carbingo `PreviewDependencies.swift` `78a3d9c`→`b1e219b`: git numstat 32/19. Case A (older left): 32 green / 19 red ✓. Case B (newer left): 19 green / 32 red, inverted. `older`/`newer` chips and "Swap panels" present |
| RT-12b | Diff version selectors | PASS | 280 branch-commit options; all 8 `/api/files/history` versions carry the edit marker; HEAD `740ba9f` badged |
| RT-13 | Search returns real results | PASS | query box + Enter → "Found 42 results" for `FileFilter`; paths verified in git (inxr2, cJSON) |
| RT-14 | Search result click navigates | PASS | → `/browse/inxr2/src/inxr2/domain/services/file_filter.py?line=20` (54 rows loaded) |
| RT-15 | Regex search | PASS | `def should_[a-z_]+` → 3 results, same 3 paths/lines as `/api/search/text?mode=regex` |
| RT-16 | File search | PASS | `file_filter.py` → `src/…/file_filter.py`, `tests/…/test_file_filter.py` |
| RT-16a | Extensionless file search | PASS | `Dockerfile` → Java, sentimeter, interview-…, inxr2; click loads `Java/.devcontainer/Dockerfile` (25 rows) |
| RT-17 | History matches git log | PASS | carbingo: hashes/messages/authors of the top 5 = `git log -5`; 280 entries |
| RT-18 | Commit click → browse | PASS | → `/browse/carbingo?commit=740ba9f…` |
| RT-19 | Tab navigation preserves context | PASS | Search/History/Browse keep `repo`, `branch`, `commit` |
| RT-20 | Branch selector | PASS | inxr2 shows `main (default)`, the only indexed branch; worktree and dependabot branches correctly unindexed |
| RT-21 | URL state preserved on reload | PASS | `branch=main&line=10` retained; file rendered |
| RT-22 | Theme toggle | PASS | `rgb(247,246,242)` → `rgb(30,30,30)` → back |
| RT-22a | Diff colors in both themes | PASS | light `rgba(80,161,79,.14)`/`rgba(228,86,73,.14)` → dark `rgba(46,160,67,.15)`/`rgba(248,81,73,.15)`; 32/19 counts stable |
| RT-23 | Markdown rendering | PASS* | H1 "Close Skill" = `grep -m1 '^#'` of `.claude/skills/close/SKILL.md`. *Front matter renders as an H2 above it, filed as #553 |
| RT-24 | Logical View symbol tree | PASS | carbingo: 153 tree nodes = 153 files in the symbol-tree API; no "Coming Soon"; no file absent from HEAD |
| RT-25 | Logical View expand shows symbols | PASS | `BundledItemLibrary.swift` → `BundledItemLibrary` class (extends `ItemLibraryPort`), methods, properties, `GazetteerAreaKeys` enum…; matches source |
| RT-26 | Logical View symbol click → Browse | PASS | "Go to line 13" → `…/BundledItemLibrary.swift?line=13`, line 13 = `final class BundledItemLibrary: ItemLibraryPort {` |
| RT-27 | Logical View language filter | PASS | 153 → 38 on `python` (API: 38 python files); all remaining are `.py` |
| RT-28 | Dependencies shows packages | PASS | inxr2 "668 packages in 5 files @ e26145f" = API total 668; `package.json` expands to real names/versions/types |
| RT-29 | Dependencies commit picker | PASS | carbingo `?commit=888259e` → "17 packages in 3 files @ 888259e" = API total 17 at that commit |
| RT-30 | Dependencies empty state | PASS | "Repository not found", no crash |
| RT-31 | References panel → Logical View | PASS | link carries repo/branch/commit/file; lands with `FileFilter class` expanded |
| RT-32 | Browse rename banner | SKIP | `file_renames` is empty: no renames in any repo's 10-day window (`git log -M --diff-filter=R --since='10 days ago'` is empty for every multi-commit repo) |
| RT-33 | Diff viewer rename following | SKIP | same reason as RT-32 |
| RT-34 | Mermaid renders as SVG | PASS | `docs/archived/2026-03-23-mermaid-test.md`: 62 SVGs (4 mermaid), no raw `graph TD`/`flowchart`/`sequenceDiagram` text |

### RT-12a Failure Details (known #520)

```
repo  = carbingo, file = Carbingo/Infrastructure/PreviewDependencies.swift, branch = main
older = 78a3d9caa7d79709cc27406bd63d76df074a70bc (2026-10-12 16:36 UTC)
newer = b1e219ba15e0465e01fbfda137e4002d3d8958b4 (2026-10-14 00:21 UTC)
git diff --numstat older newer -> 32 added, 19 removed

Case A /browse/carbingo/<file>?commit=<newer>&branch=main&diff=<older>
  -> {"rgba(80, 161, 79, 0.14)": 32, "rgba(228, 86, 73, 0.14)": 19}     (correct)
Case B /browse/carbingo/<file>?commit=<older>&branch=main&diff=<newer>
  -> {"rgba(80, 161, 79, 0.14)": 19, "rgba(228, 86, 73, 0.14)": 32}     (inverted)
```

This is the expected observed state until #520 is fixed.

---

## Phase 3: MCP Server (26/26 passed)

Handlers ran in the worktree container against its own API (`PYTHONPATH=/workspace/mcp-server`).
MCP-21 used the SSE server, started manually on container port 3000 (#525).

| ID | Test | Result | Notes |
|----|------|--------|-------|
| MCP-01 | List repos | PASS | 20 repos, all API names present, each with an indexed branch and `commits_behind: 0` |
| MCP-02 | Repo detail shows indexed branches | PASS | carbingo `main: 112 commits, head: 740ba9f` = API (main, 112) |
| MCP-03 | Search symbols | PASS | names/paths/lines/kinds identical to `/api/symbols` |
| MCP-04 | Search symbols kind filter | PASS | `kind=class` → classes only; `kind=interface` returns all 7/7 travelbuddy `protocol` symbols (#385 holds) |
| MCP-05 | Go to definition | PASS | `search_symbols.py:85`, class, docstring shown |
| MCP-06 | Find references | PASS | 46 = API total at `limit=500` |
| MCP-07 | Find references type filter | PASS | 3 imports only |
| MCP-08 | Search code | PASS | same paths/lines as `/api/search/text` (phrase) |
| MCP-09 | Search code repo filter | PASS | all 5 results `inxr2:` |
| MCP-10 | No-match graceful messages | PASS | all 4 tools return readable messages echoing the query |
| MCP-11 | MCP unit tests | PASS | 154 passed in 0.51s |
| MCP-12 | Browse URLs point to correct locations | PASS | all 4 tools emit URLs; each loads the right line in the QA browser (e.g. `search_symbols.py:85` = `class SearchSymbolsUseCase:`); `branch=main` appended when filtered; no URLs without `frontend_url` |
| MCP-13 | Find dead code | PASS | 11 unreferenced, shows 10 (limit), kind/name/path/line per entry, declares "scanned 200 of 9059 symbols" |
| MCP-14 | Find dead code kind filter | PASS | all entries `[function]` |
| MCP-15 | Review helper blast radius | PASS | carbingo `9808690`: 3 changed files = `git diff-tree`; 11 symbols; 34 downstream refs |
| MCP-16 | Review helper changed files only | PASS | `Changed files: 3` = git |
| MCP-17 | Staleness warning | PASS | inxr2/carbingo/git current → warning `None` |
| MCP-18 | Browse URLs in find_dead_code / review_helper | PASS | present with `frontend_url`, absent without |
| MCP-19 | get_file_structure | PASS | `class FileFilter` → `staticmethod should_skip`, matches the API; constants excluded; no docstrings |
| MCP-20 | get_change_impact | PASS | Source (1) / Test (1) = API's 15 refs in 2 files; depth=2 ⊇ depth=1; graceful unknown-symbol message |
| MCP-21 | explain_symbol | PASS | header, Location, Docstring, `References (46 total)` by type; unknown → "not found"; `CodingKeys` without repo → disambiguation note (31 definitions) |
| MCP-22 | search_symbols wildcard (#384) | PASS | `*` → 5 shown of 9059 |
| MCP-23 | search_code extensions dedup (#400) | PASS | 2 swift results, 2 unique |
| MCP-24 | search_code always has a file path (#387) | PASS | every result has `repo:path.ext:line`; no commit-message lines |
| MCP-25 | search_code finds code bodies (#395) | PASS | 10 `.swift` results, 0 `.md`; term in snippets |
| MCP-26 | search_code source_only | PASS | without: 16 `.md`; with `source_only=true`: 0 `.md`, 4 `.swift` |

---

## Known Issues / Observations

1. **PR #551 missed `get_distinct_extensions` — fixed in `af3b6bc`.**
   `src/inxr2/adapters/persistence/repositories/file_search_adapter.py` `get_distinct_extensions`
   still has its own head logic:
   - `repository_id` with no branch: no head filter at all, so every file version counts.
     `GET /api/search/extensions?repository_id=56` (carbingo) returns `.pyc`. The only `.pyc`
     (`scripts/__pycache__/corpus-expand.cpython-314.pyc`) is linked only to `0d4500e` and
     `ac32db9` and is absent at HEAD. With `&branch=main` the list matches HEAD exactly.
   - With a branch: the head is `ORDER BY commit_date DESC, id DESC LIMIT 1`. On git/master five
     commits share 2026-10-15 14:44:31 (ids 188–192), and this picks `e378409` (id 192, the oldest
     of the run) instead of the indexed head `f57c9a7` (id 188).

   Fixed in `af3b6bc`: it now filters with `latest_file_ids_subquery(repository_id, branch)` like
   the other adapters, and the in-memory fake (which ignored `branch`) does the same. New contract
   cases (with/without branch × distinct/same-second commits) failed 7 of 8 before the fix. After
   it, carbingo's list with no branch matches the extensions in `git ls-tree HEAD` exactly.

2. **File history breaks same-second ties by `commits.id` (#552, pre-existing).** For carbingo
   `PreviewDependencies.swift`, `22864d1` is listed above the newer `df6ca24`, and one version is
   attributed to `97bb909` instead of `768e3c6`, the commit git says introduced it. Same root cause as
   #549, in `file_version_adapter.py` (`list_versions_by_path`, `get_commit_ids_for_files`, prior-commit
   lookup) and `file_adapter.py:175`. This run surfaced it because carbingo has many same-second
   commits (merge + log commits).

3. **Markdown front matter renders as an H2 (#553, pre-existing).** RT-23's file
   (`.claude/skills/close/SKILL.md`) has its YAML front matter shown as a heading above the real H1.

4. **No renames in the 10-day window**, so RT-32/RT-33 could not run. A wider `--days` or a
   purpose-built fixture repo would keep them exercised.

5. **The git card shows "Duration: 4m 10s (resolve: 4m 36s)".** Resolve time exceeds the duration, so
   "Duration" is evidently indexing-only (stats: indexing 250s, resolving 276s). The label could
   mislead; cosmetic.

6. **RT-06 trailing-newline off-by-one persists** (54 rows for a 53-line file), as in prior reports.

7. **MCP SSE server and backend/frontend were not running** in the worktree container at session
   start (#525) and were started manually.

8. **`search_code` keyword mode tokenises `cJSON_Parse` into `cJSON` + `parse`.** The MCP-12 URL for
   it points to `cJSON.c:1081` (a prototype block matching both tokens), not to a literal
   `cJSON_Parse`. This is existing keyword semantics; use `mode=phrase` for exact identifiers.

9. **`Home.test.tsx` loading-state test left a 1s timer pending** (fixed in `88cd234`). The first
   full-suite run after the extensions fix failed the frontend step with an unhandled
   `ReferenceError: window is not defined` from `Home.tsx` `setLoading`, fired after jsdom
   teardown. The test now resolves its own promise and waits for the spinner to clear.

10. **#554: fake extensions from dotted filenames.** git's extension list has 323 entries, mostly
    fixture-name fragments (`t/t4013/diff.log_--cc_-m_-p_main` → `.log_--cc_-m_-p_main`).
    `process_file.py:389` stores `Path(path).suffix` verbatim.

---

## Exploratory Testing (after `af3b6bc`)

Target: `Carbingo/Domain/ValueObjects/RegionTag.swift`, deleted in `19f08a8`; the last indexed
commit containing it is `306df25`. At HEAD `740ba9f` the name `RegionTag` appears only in docs.

| Area | At head `740ba9f` | At `306df25` | Result |
|------|-------------------|--------------|--------|
| Browse | "File … not found at commit 740ba9f" | Renders, 118 lines (= git) | PASS |
| Search (keyword) | 15 hits, all `docs/*.md`; no Swift | 42 results incl. the struct | PASS |
| Search (file mode) | 0 results | — | PASS |
| Extension filter (UI) | 22 options = API = git HEAD; no `.pyc` | — | PASS |
| Logical View | `RegionTag.swift` absent | Present | PASS |
| MCP `search_symbols` / `go_to_definition` / `find_references` | Nothing found | — | PASS |
| MCP `search_code "struct RegionTag"` | 1 hit, markdown only | — | PASS |
| git/master same-second head (UI) | Picker and tree show `f57c9a7` (= indexed head = git HEAD) | — | PASS |

Findings (all pre-existing; on main too):

- **#555: commit picker shows "latest" for a short-hash URL.** `?commit=306df25` renders the
  old commit's content and tree, but the picker reads "latest". `CommitSelect.tsx:41` matches by
  exact hash equality. The full hash displays correctly. MCP links use full hashes.
- **#556: resolution links across languages.** Pass 3 ("any-match",
  `reference_adapter.py` ~L380/L505) falls back to the lowest-id symbol with the name in any
  language. carbingo at head: `.py→.swift` 321, `.jsx→.swift` 264, `.js→.swift` 163, `.py→.js`
  121; counts match main's index. Example: `corpus` in `tools/corpus/carbingo_corpus/rules.py:184`
  resolves to a Swift test method.
- **#557: MCP returns raw HTTP 404 text** for a file not at head (`get_file_structure` on the
  deleted path). This now happens more often, because deleted files correctly 404.
- Not a bug: the History page is repo-level only (it ignores `path`). Per-file history lives in
  Browse's version selector (#552).
