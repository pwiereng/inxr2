# Regression Test Report — 2026-11-17

Run against branch `upgrade-498-react-router-v7` (issue #498: react-router-dom 6.30.6 → react-router
7.18.5, uncommitted working tree on base `cff4a83`) in the slot-1 worktree container
`inxr2-upgrade-498-react-router-v7-dev`, with the QA agent
`inxr2-upgrade-498-react-router-v7-playwright` (ports: backend 8010, frontend 5183, QA 9232,
MCP 3010). The QA agent image was rebuilt with this branch's `qa-agent/Dockerfile` fix
(`libatomic1`, needed by Playwright 1.65.2's Node driver). `config.yaml` was copied from main.
IX-05 compares against main's last full reset run (`index.log`, 2026-11-03 19:42 UTC, one commit
per branch).

## Summary

| Phase | Passed | Total | Notes |
|-------|--------|-------|-------|
| Indexing | 8 | 8 | IX-05 elapsed flags are environmental (no backend change; all counts identical) |
| Browser | 36 | 39 | 1 failed (RT-12a, known #520), 2 skipped (RT-32, RT-33: no renames in the window) |
| MCP | 25 | 26 | 1 failed (MCP-15 symbols section, known #567) |
| **Total** | **69** | **73** | **2 skipped, 2 failed (both known, pre-existing)** |

**PR-specific results.** No routing regressions were found. Every route was exercised through the
QA agent on the v7 build: the `/browse/:repoName/*` splat route (deep paths, `?line=`,
`?branch=`, `?commit=`, `?diff=`, `?refs=1&q=`), `/search` (input-driven and URL-driven, including
a percent-encoded regex), `/history`, `/logical-view` (`?file=`, `?language=`), `/dependencies`
(`?commit=`, unknown repo), and the 404 catch-all. Back/forward was checked at each stage: browse
→ search → back restores the refs panel; exiting compare mode → back restores the diff;
logical view → symbol → back restores the `?file=` expansion; tab switches → back/forward keep the
URL and the selected tab in sync. A `console.error`/`console.warn` hook installed across a sequence
of in-app navigations captured nothing (no React Router warnings). The two failures are known
issues in code this PR does not touch.

**Comparison against main (v6).** One behaviour looked suspicious and was A/B-tested against main's
frontend (react-router-dom 6, :5173) on the same URL: when the references panel is restored from the
URL (`refs=1&q=FileFilter`, by deep link or by Back), the header subtitle ("class · 15 references")
is absent while the Definition and References sections render. Main behaves identically, so this is
pre-existing, not a v7 regression.

## Component Versions

| Component | Version |
|-----------|---------|
| inxr2 | 0.1.0 |
| Python | 3.11.18 |
| FastAPI | 0.120.4 |
| PostgreSQL | 17.11 |
| Tree-sitter | 0.25.2 |
| Node | v20.20.2 |
| React | ^19.2.7 |
| React Router | ^7.18.5 (installed 7.18.5; was react-router-dom ^6.30.6) |
| Vite | ^6.4.4 |
| TypeScript | ^6.0.3 |
| MUI | ^5.15.0 |
| Vitest | ^4.1.12 |
| MCP lib | 1.30.0 |
| Playwright (QA agent) | 1.65.2 |
| Docker engine | 29.8.0 |
| Codebase HEAD | cff4a83 (+ uncommitted #498 changes) |

---

## Phase 1: Indexing (8/8 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| IX-01 | Reset DB and index all repos | PASS | 21/21 repo+branch combos OK; 2,515,229 file versions, 11,671,792 lines, resolution 3,982,946/4,911,776 (81.1%), 1h 3m 25s. Multi-commit windows: git 320, carbingo 318, bubbletea 19, Java 14, sinatra 13, temporal-basics 2. `multidockerdevcontainer/feature/oidc-authentication` skipped by design (no commits in window) |
| IX-02 | Verify indexing status | PASS | 21 repos = 21 in `config.yaml`; all non-zero files/symbols/refs; all `Completed` |
| IX-03 | Verify API serves indexed data | PASS | `/api/repositories` = 21, every config name present; all stats non-zero. `is_stale=true` on inxr2, Java, sinatra, carbingo: their test repos received new commits (17:39–18:45 UTC) after they were indexed (17:22–17:28) during the hour-long run |
| IX-04 | Multi-language symbols (12 langs) | PASS | 12/12 (see table) |
| IX-04a | Reference extraction | PASS | express `lib/application.js`: `require()` targets → `import` (`finalhandler`, `View`, `http`, `once`, `Router`); 381 `usage` refs; all 5 `this.<prop> =` properties present |
| IX-04b | ES6 export/re-export references | PASS | `export { CodeHeader, type TabValue } from` → `import`; `export { customRender as render }` → `usage`; `export default App` → `usage`; `export * from` → `import` |
| IX-05 | Performance comparison | PASS | symbols, refs found and refs resolved identical on every single-commit repo; elapsed flags explained below |
| IX-06 | FileFilter completeness (#349) | PASS | 21/21 repos: 0 missing and 0 extra files vs `git ls-tree -r -z` (blobs) at each repo's last indexed commit; 65 `src/inxr2/adapters/external/` files present |

### IX-04 detail

| Language | Repo | Symbol discovered from git | API kind |
|----------|------|---------------------------|----------|
| Python | inxr2 | `Inxr2Client` | class |
| TypeScript | inxr2 | `FlatFileEntry` | interface |
| JavaScript | express | `authenticate` | function |
| C | cJSON | `case_insensitive_strcmp` | function |
| C++ | spdlog | `my_formatter_flag` | class |
| Java | Java | `EMAFilter` | class, constructor |
| C# | clean-architecture | `ApiController` | class |
| Go | bubbletea | `SetClipboard` | function |
| Ruby | sinatra | `Request` | class, module |
| Bash | Bash-Snippets | `askInstall` | function |
| Swift | travelbuddy | `KeychainAdapter` | struct |
| PHP | interview-technical-challenge-2 | `VehicleRecord` | class |

### IX-05 Performance Comparison

Previous = main's 2026-11-03 19:42 UTC full reset run (one commit per branch). Current = this run.
Parsed positionally (18-column rows).

| Repo | Branch | Commits (prev → now) | Elapsed (prev → now) | Symbols | Refs found | Refs resolved | Refs Resolved % | Flag |
|------|--------|---------------------|---------------------|---------|-----------|---------------|-----------------|------|
| crisp | main | 1 → 1 | 2.1s → 2.4s (+14%) | 1330 (=) | 7879 (=) | 5760 (=) | 73.1% → 73.1% | |
| inxr | master | 1 → 1 | 0.5s → 0.6s (+20%) | 253 (=) | 2430 (=) | 966 (=) | 39.8% → 39.8% | |
| inxr2 | main | 1 → 1 | 25.9s → 43.7s (+69%) | 9435 (=) | 111676 (=) | 63671 (=) | 57.0% → 57.0% | ⚠ elapsed |
| multidockerdevcontainer | main | 1 → 1 | 2.6s → 5.7s (+119%) | 975 (=) | 11985 (=) | 4345 (=) | 36.3% → 36.3% | ⚠ elapsed |
| soccer-stats | main | 1 → 1 | 0.5s → 2.1s (+320%) | 210 (=) | 1364 (=) | 884 (=) | 64.8% → 64.8% | ⚠ elapsed |
| cJSON | master | 1 → 1 | 4.2s → 6.4s (+52%) | 2623 (=) | 17636 (=) | 9986 (=) | 56.6% → 56.6% | ⚠ elapsed |
| clean-architecture | main | 1 → 1 | 1.8s → 2.4s (+33%) | 745 (=) | 4389 (=) | 2098 (=) | 47.8% → 47.8% | ⚠ elapsed |
| Java | master | 1 → 14 | 28.8s → 42.9s (+49%) | 13342 → 13490 | 93665 → 94495 | 56241 → 56706 | 60.0% → 60.0% | |
| bubbletea | main | 1 → 19 | 3.2s → 12.7s (+297%) | 1776 → 3720 | 13656 → 34273 | 7049 → 19295 | 51.6% → 56.3% | |
| spdlog | v1.x | 1 → 1 | 8.2s → 8.4s (+2%) | 2055 (=) | 51269 (=) | 20268 (=) | 39.5% → 39.5% | |
| sinatra | main | 1 → 13 | 5.5s → 8.1s (+47%) | 954 → 1032 | 16336 → 18669 | 8757 → 10075 | 53.6% → 54.0% | |
| Bash-Snippets | master | 1 → 1 | 1.0s → 1.2s (+20%) | 453 (=) | 3684 (=) | 1171 (=) | 31.8% → 31.8% | |
| express | master | 1 → 1 | 5.3s → 5.9s (+11%) | 599 (=) | 26835 (=) | 15862 (=) | 59.1% → 59.1% | |
| travelbuddy | main | 1 → 1 | 4.5s → 4.9s (+9%) | 2230 (=) | 14910 (=) | 8860 (=) | 59.4% → 59.4% | |
| appbase | main | 1 → 1 | 0.3s → 0.3s (+0%) | 49 (=) | 232 (=) | 112 (=) | 48.3% → 48.3% | |
| carbingo | main | 1 → 318 | 17.9s → 191.4s (+969%) | 8162 → 35699 | 54524 → 253199 | 39893 → 190960 | 73.2% → 75.4% | |
| sentimeter | main | 1 → 1 | 2.8s → 3.5s (+25%) | 1097 (=) | 8096 (=) | 3846 (=) | 47.5% → 47.5% | ⚠ elapsed |
| geobuddy | main | 1 → 1 | 2.3s → 2.8s (+22%) | 1236 (=) | 5463 (=) | 3162 (=) | 57.9% → 57.9% | ⚠ elapsed |
| git | master | 1 → 320 | 194.9s → 3455.8s (+1673%) | 40787 → 237651 | 581196 → 4239963 | 478385 → 3563346 | 82.3% → 84.0% | |
| interview-technical-challenge-2 | master | 1 → 1 | 2.1s → 2.2s (+5%) | 457 (=) | 2926 (=) | 1465 (=) | 50.1% → 50.1% | |
| temporal-basics | main | — → 2 | — → 0.2s | 42 | 403 | 108 | — → 26.8% | new repo, no baseline |

(The `--days 10` window slides, so absolute counts are only apples-to-apples for single-commit
repos; the resolution % is window-independent.)

**Elapsed flags are environmental.** This branch changes no Python, indexer, MCP or lockfile code
against its base (`git diff HEAD -- src/ mcp-server/ pyproject.toml requirements*.lock` is empty);
it touches only the frontend, `osv-scanner.toml`, `CONTRIBUTING.md` and `qa-agent/Dockerfile`. Every
flagged repo produced byte-identical counts (symbols, refs found, refs resolved). The flagged repos
are the small ones indexed first (17:22–17:23 UTC), when the host was also running the other dev
stacks; most deltas are sub-second to ~2s. No resolution-% decreased anywhere.

---

## Phase 2: Browser (36/39 passed, 2 skipped)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| RT-01 | Home page repo cards | PASS | 21 distinct `/browse/<repo>` links = API's 21 |
| RT-02 | Repo card stats | PASS | e.g. crisp 14.5K lines / 109 files / 1.3K symbols / 73% = API 14471 / 109 / 1330 / 5760÷7879 |
| RT-02a | Repo card indexing stats | PASS | lines, files, symbols, resolved %, language tags, commit range, last-indexed time and duration per card; "Index outdated" shown on exactly the 4 `is_stale` repos |
| RT-03 | Navigate to browse | PASS | → `/browse/crisp?branch=main&commit=1c1feab…` |
| RT-04 | File tree matches git | PASS | 8/8 top-level entries = `git ls-tree` |
| RT-05 | Directory expands | PASS | `bin/` → `cool` = git |
| RT-06 | Code viewer content | PASS | inxr2 `file_filter.py` line 1 matches git; 54 rows for 53 lines (known trailing-newline off-by-one); `branch=main` resolved to indexed commit `cff4a83` |
| RT-07 | Line numbers clickable | PASS | `line=5` added to URL |
| RT-08 | Symbol click opens panel | PASS | `FileFilter` → class, Definition `:20`, 15 references; URL gains `refs=1&q=FileFilter` |
| RT-09 | References panel usages | PASS | `process_commit.py` and `tests/unit/domain/test_file_filter.py`; both in `git ls-files` |
| RT-10 | Search globally link | PASS | → `/search?query=FileFilter&types=symbol,reference`, "Found 23 results"; Back restores browse + refs panel URL, Forward returns to search |
| RT-11 | Blame matches git | PASS | line 1: `5e0a931`, Paul Wierenga = `git blame --porcelain` |
| RT-12 | Diff mode enter/exit | PASS | Compare adds `diff=`, Exit compare removes it; Back re-enters diff (2 panels) |
| RT-12a | Diff colors temporal order | **FAIL** (known #520) | carbingo `ArtVariantTests.swift` `6e3109c`→`dd492a4`: git numstat 11/17. Case A: 11 green / 17 red ✓. Case B: 17 green / 11 red, inverted. `older`/`newer` chips present; Swap shown when newer is on the left |
| RT-12b | Diff version selectors | PASS | 500 branch-commit options; all 4 `/api/files/history` versions present with `EditIcon`; HEAD `a36daa3` badged (4 newer, not-yet-indexed commits listed above it because carbingo moved during the run) |
| RT-13 | Search via input | PASS | "FileFilter" → `/search?query=FileFilter`, "Found 48 results"; result paths exist in git |
| RT-14 | Search result click | PASS | → `file_filter.py?repo=inxr2&line=20&commit=…`, line 20 = `class FileFilter:` |
| RT-15 | Regex search | PASS | `def should_[a-z_]+` (percent-encoded `+`) → 3 results = `/api/search/text` regex total 3 |
| RT-16 | File search | PASS | `file_filter.py` → `file_filter.py`, `test_file_filter.py` |
| RT-16a | Extensionless file search | PASS | `Dockerfile` → 8+ hits across repos; click opens `Java/.devcontainer/Dockerfile` (25 lines) |
| RT-17 | History matches git log | PASS | carbingo: from indexed head `a36daa3` down, hashes/authors = `git log`; 4 newer unindexed commits listed first with disabled buttons |
| RT-18 | History commit click | PASS | first indexed commit → `/browse/carbingo?commit=a36daa3…` |
| RT-19 | Tab navigation context | PASS | `repo=inxr2&branch=main&commit=…` preserved on Search, History, Browse; back/back/forward keep URL and selected tab in sync |
| RT-20 | Branch selector | PASS | shows `main`; options `main (default)` = API's only indexed inxr2 branch |
| RT-21 | URL state on reload | PASS | `branch=main&line=10` retained after `location.reload()`; file loads |
| RT-22 | Theme toggle | PASS | `rgb(247,246,242)` → `rgb(30,30,30)` → `rgb(247,246,242)` |
| RT-22a | Diff colors in both themes | PASS | light `rgba(80,161,79,.14)`/`rgba(228,86,73,.14)` → dark `rgba(46,160,67,.15)`/`rgba(248,81,73,.15)`; 11/17 stable |
| RT-23 | Markdown rendering | PASS | `.claude/skills/close/SKILL.md` → `H1: Close Skill` = first `# ` heading in git |
| RT-24 | Logical View loads | PASS | crisp file list = `symbol-tree` API order; no "Coming Soon" |
| RT-25 | Expand file shows symbols | PASS | `examples/abp1/extern.c` → 6 functions = file-structure API (UI sorts alphabetically) |
| RT-26 | Symbol click → browse | PASS | `cool_finalize` → `extern.c?…&line=28`, line 28 highlighted; Back restores `?file=` expansion |
| RT-27 | Language and kind filters | PASS | language `cpp`: 51 → 18 files, all `.h`; URL gains `language=cpp` |
| RT-28 | Dependencies tab | PASS | inxr2 "678 packages" = API total 678 (crisp, the first repo, has 0 deps) |
| RT-29 | Dependencies commit picker | PASS | carbingo `c64e8d0`: 22 packages = API at that commit (HEAD has 32); URL keeps `commit=` |
| RT-30 | Dependencies empty state | PASS | "Repository not found", no crash |
| RT-31 | References → Logical View | PASS | link `/logical-view?repo=inxr2&…&file=…file_filter.py`; `FileFilter` expanded and visible |
| RT-32 | Browse rename banner | SKIP | `file_renames` is empty; `git log -M --diff-filter=R --since='10 days ago'` is empty for every multi-commit repo |
| RT-33 | Diff viewer rename following | SKIP | same reason as RT-32 |
| RT-34 | Mermaid renders as SVG | PASS | `docs/archived/2026-03-23-mermaid-test.md`: 4 mermaid SVGs, no raw source |

### RT-12a Failure Details (known #520)

```
DISCOVER: /api/files/history?repo=carbingo&path=SpotamusTests/Unit/Application/ArtVariantTests.swift&branch=main
          -> versions dd492a45 (2026-11-16), 6e3109cf (2026-11-09), 39303e56, c64e8d0b
          git -C /repos/test-repos/carbingo diff --numstat 6e3109cf dd492a45 -- <file>  -> 11  17
Case A: /browse/carbingo/<file>?commit=dd492a457b36…&branch=main&diff=6e3109cfab1b…
        -> rgba(80,161,79,.14): 11, rgba(228,86,73,.14): 17   (correct)
Case B: /browse/carbingo/<file>?commit=6e3109cfab1b…&branch=main&diff=dd492a457b36…
        -> rgba(80,161,79,.14): 17, rgba(228,86,73,.14): 11   (inverted)
```

Colouring is positional (#520). Unrelated to this PR.

---

## Phase 3: MCP Server (25/26 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| MCP-01 | List repos | PASS | 21 = API; every name present; each shows its indexed branch |
| MCP-02 | Detail branches | PASS | `main: 1 commits, head: cff4a83` = API; `commits_behind: ? (stale)` because the test repo moved during the run |
| MCP-03 | Search symbols | PASS | same 3 names, kinds, paths, lines as `/api/symbols` |
| MCP-04 | Kind filter | PASS | `kind=class` → 10 results, all `[class]`; `kind=interface` includes travelbuddy protocols `KeychainPort`, `LLMPort`, `LocationPort` |
| MCP-05 | Go to definition | PASS | `search_symbols.py:85`, kind and docstring shown |
| MCP-06 | Find references | PASS | 47 = API total; types call/import/type_annotation/usage; sample locations match |
| MCP-07 | Ref-type filter | PASS | `ref_type=import` → 3, all `[import]` |
| MCP-08 | Search code | PASS | same 3 paths/lines as `/api/search/text` (phrase, limit 3; API total 60) |
| MCP-09 | Repo filter | PASS | all 5 results `inxr2:` |
| MCP-10 | No-match messages | PASS | each tool returns a readable "No … found" message with the query |
| MCP-11 | MCP unit tests | PASS | 170 passed |
| MCP-12 | Browse URLs | PASS | all 4 tools emit URLs; each opened in the QA browser (v7 build) on the right file with the requested line highlighted (e.g. `search_symbols.py:85` = `class SearchSymbolsUseCase:`); `branch=main` appended when filtered; none without `frontend_url` |
| MCP-13 | Find dead code | PASS | inxr2: "Scanned all 9435 symbols; 3046 entry points excluded", 163 dead, header names `offset=10`; carbingo: 12218/12218 scanned, 614 dead; scanned = `/api/symbols` head total; no "may be incomplete" |
| MCP-14 | Dead code by kind | PASS | `kind=function`: "Scanned all 1079 functions", all entries `[function]` |
| MCP-15 | Review helper blast radius | **FAIL** (known #567) | carbingo `bcd9155`: 12 changed files = `git diff-tree` (same set), but "Symbols in changed files: 0 — scanned 200 of 12218 symbols — results may be incomplete", so downstream refs are 0 |
| MCP-16 | Changed files only | PASS | carbingo `72d331b`: `Changed files: 1` = git, same path |
| MCP-17 | Staleness warning | PASS | inxr2 and carbingo (moved during the run) → `Warning: Indexed data may be stale … indexed up to <hash>`; crisp current → `None`; warning present on search_symbols, find_references, find_dead_code and review_helper |
| MCP-18 | URLs in dead_code / review_helper | PASS | present with `frontend_url`, absent without |
| MCP-19 | get_file_structure | PASS | `FileFilter` [L20-53] › `should_skip` [L24-53]; structural symbols match the API (module constants excluded by design) |
| MCP-20 | get_change_impact | PASS | Source (1) / Test (1) = API's 15 refs in 2 files; depth=2 ⊇ depth=1; unknown symbol → "No symbols found matching 'xyzzy_nope_42' in 'inxr2'." |
| MCP-21 | explain_symbol (SSE) | PASS | via the worktree SSE server (started manually, #525): header, `Location`, `Docstring`, `References (47 total)` grouped by type; unknown → "Symbol 'xyzzy_nope_42' not found."; `Request` without repo → "Note: 2 definitions found … Specify 'repository' to disambiguate." |
| MCP-22 | Wildcard search | PASS | "5 shown (of 9435 total)" |
| MCP-23 | No duplicate results | PASS | `TraceLogger` swift: 2 lines, 2 unique |
| MCP-24 | Results have file paths | PASS | 18/18 result lines `inxr2:<path>.<ext>:<line>`; no commit-message lines |
| MCP-25 | Code body content | PASS | `RouteLeg`: 10 `.swift` results, no non-swift |
| MCP-26 | source_only filter | PASS | without: 16 `.md`; `source_only=true`: 0 `.md`, 4 `.swift` |

### MCP-15 Failure Details (known #567)

```
DISCOVER: git -C /repos/test-repos/carbingo diff-tree --no-commit-id --name-status -r bcd9155
          -> 12 files, all M/A, including SpotamusTests/Integration/ItemLibraryIntegrationTests.swift
review_helper.handle(client, {'repository': 'carbingo', 'commit': 'bcd9155'})
          -> Changed files: 12 (same set as git)
             Symbols in changed files: 0
               Note: scanned 200 of 12218 symbols — results may be incomplete.
             Downstream references: 0
```

`mcp-server/src/tools/review_helper.py` fetches `/api/symbols?q=.&mode=regex&limit=200` and filters
that sample by changed path. With carbingo now at 12,218 head symbols (2,492 a month ago), the
200-symbol sample no longer covers the changed files. Tracked in #567 (and #617). The branch does
not touch `mcp-server/`.

---

## Known Issues / Observations

1. **No react-router v7 regressions.** All URL-driven state (splat path, `line`, `branch`,
   `commit`, `diff`, `refs`/`q`, search `query`/`mode`/`types`, logical-view `file`/`language`,
   dependencies `commit`) round-trips through deep links, reload and back/forward. No router
   warnings in the console.
2. **References-panel subtitle missing when restored from the URL.** With `refs=1&q=<symbol>` from a
   deep link or Back, the panel header omits "class · N references" (sections still render).
   Identical on main (react-router-dom 6), so pre-existing.
3. **`review_helper` omits deleted files.** carbingo `a36daa3` changed 2 files (`M` + `D`), but
   `Changed files: 1`. The tool derives changed files from the tree at the commit
   (`changed_only=true`), where deleted paths no longer exist. MCP-15/16 were run on add/modify-only
   commits. Worth a follow-up alongside #617.
4. **Test repos moved during IX-01.** inxr2, Java, sinatra and carbingo gained commits after they
   were indexed, so they report `is_stale`, the UI shows "Index outdated", and MCP prepends the
   staleness warning. All of that is correct behaviour.
5. **IX-01 took 1h 3m**, dominated by `git` (320 commits, 57.6 min) and carbingo (318 commits).
6. **RT-06 trailing-newline off-by-one persists** (54 rows for a 53-line file), as in prior reports.
7. **No renames in the 10-day window**, so RT-32/RT-33 could not run (same as 2026-10-16/17).
8. **QA agent image fix verified.** The Playwright container built from this branch's
   `qa-agent/Dockerfile` (adds `libatomic1`) ran the whole browser phase with Playwright 1.65.2.
