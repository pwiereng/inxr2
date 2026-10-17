# Regression Test Report — 2026-10-17

Run against branch `fix-548-dead-code-accuracy` (HEAD `ebf6574`, issue #548) in the slot-1
worktree container `inxr2-fix-548-dead-code-accuracy-dev`, with the QA agent
`inxr2-fix-548-dead-code-accuracy-playwright` (ports: backend 8010, frontend 5183, QA 9232,
MCP 3010). `config.yaml` and `index.log` were copied from main, so IX-05 compares against main's
last full index (2026-10-16 01:32 UTC, one commit per branch).

## Summary

| Phase | Passed | Total | Notes |
|-------|--------|-------|-------|
| Indexing | 8 | 8 | IX-05 flags explained (added references, see below) |
| Browser | 36 | 39 | 1 failed (RT-12a, known #520), 2 skipped (RT-32, RT-33: no renames in the window) |
| MCP | 26 | 26 | |
| **Total** | **70** | **73** | **2 skipped, 1 failed** |

**PR-specific results.** On the real index, `find_dead_code` now scans every symbol at the branch
head: inxr2 9,059 / 9,059 and carbingo 2,492 / 2,492 (the `/api/symbols` head totals), not 200.
Every false positive named in #548 is gone from carbingo's full list (`CarbingoApp`,
`GameActionsTests`, `AppDependenciesTests`, `CarbingoUITests`, `GameActionError`,
`GazetteerAreaKeys`, `GazetteerRangeKeys`, `AnyCodingKey`), and the issue's real candidates
`llm`, `agent` and `fullCard` are listed. No regressions were found.

**IX-01 was run twice.** The first run (14m 43s) overlapped heavy host load (15-minute load average
~249), which inflated elapsed times up to 14× on single-commit repos, including Ruby and C repos
whose parsers this PR does not touch. A parser-only A/B on the same files showed no cost difference
(below), so IX-01 was re-run once the host was quiet (load ~2–12). All Phase 1–3 results use the
second run.

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
| Codebase HEAD | ebf6574 |

---

## Phase 1: Indexing (8/8 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| IX-01 | Reset DB and index all repos | PASS | 20/20 repo+branch combos OK; 306,281 files, 3,845,545 lines, resolution 1,452,530/1,886,203 (77.0%), 10m 17s (re-run; first run 14m 43s under host load). Multi-commit windows: carbingo 112, git 57, spdlog 6, express 4, Java 3, bubbletea 2 |
| IX-02 | Verify indexing status | PASS | 20 repos = 20 in `config.yaml`; all non-zero files/symbols/refs; `multidockerdevcontainer/feature/oidc-authentication` skipped by design |
| IX-03 | Verify API serves indexed data | PASS | `/api/repositories` = 20, every config name present; all stats non-zero, `is_stale=false` |
| IX-04 | Multi-language symbols (12 langs) | PASS | 12/12 (see table) |
| IX-04a | Reference extraction | PASS | express `lib/application.js`: `require()` targets → `import` (`finalhandler`, `http`, `View`, `Router`, `once`); 381 `usage` refs; all 5 `this.<prop> =` properties present |
| IX-04b | ES6 export/re-export references | PASS | `export { CodeHeader, type TabValue } from` → `import`; `export { customRender as render }` → `usage`; `export default App` → `usage`; `export * from` → `import` |
| IX-05 | Performance comparison | PASS | no elapsed flag beyond sub-second rounding; symbols unchanged on every single-commit repo; resolution-% dips explained by added references (resolved counts rose); see below |
| IX-06 | FileFilter completeness (#349) | PASS | 20/20 repos: 0 missing and 0 extra files vs `git ls-tree -r -z` (blobs) at HEAD; 38 `src/inxr2/adapters/external/` files present |

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
| Bash | Bash-Snippets | `tarwrite` | function |
| Swift | travelbuddy | `KeychainAdapter` | struct |
| PHP | interview-technical-challenge-2 | `VehicleRecord` | class |

### IX-05 Performance Comparison

Previous run = main's 2026-10-16 01:32 UTC full index (one commit per branch). Current = this
branch's second IX-01 run. Parsed positionally (98 legacy 15-column rows, 1,539 18-column rows).

| Repo | Branch | Commits (prev → now) | Elapsed (prev → now) | Symbols | Refs found | Refs resolved | Refs Resolved % |
|------|--------|---------------------|---------------------|---------|-----------|---------------|-----------------|
| crisp | main | 1 → 1 | 1.6s → 1.5s (−6%) | 1330 (=) | 7879 (=) | 5760 (=) | 73.1% → 73.1% |
| inxr | master | 1 → 1 | 0.4s → 0.5s (+25%, rounding) | 253 (=) | 2422 → 2440 | 958 → 966 | 39.6% → 39.6% |
| inxr2 | main | 1 → 1 | 21.5s → 19.6s (−9%) | 9059 (=) | 106299 → 107236 | 60390 → 60783 | 56.8% → 56.7% ⚠ |
| multidockerdevcontainer | main | 1 → 1 | 2.3s → 2.4s (+4%) | 975 (=) | 11858 → 12019 | 4248 → 4345 | 35.8% → 36.2% |
| soccer-stats | main | 1 → 1 | 0.4s → 0.4s (+0%) | 210 (=) | 1364 (=) | 884 (=) | 64.8% → 64.8% |
| cJSON | master | 1 → 1 | 3.7s → 3.7s (+0%) | 2623 (=) | 17624 → 17639 | 9974 → 9986 | 56.6% → 56.6% |
| clean-architecture | main | 1 → 1 | 1.5s → 1.6s (+7%) | 745 (=) | 3340 (=) | 1500 (=) | 44.9% → 44.9% |
| Java | master | 1 → 3 | 20.8s → 21.5s (+3%) | 13281 (=) | 93240 (=) | 56007 (=) | 60.1% → 60.1% |
| bubbletea | main | 1 → 2 | 4.2s → 3.2s (−24%) | 1772 (=) | 12803 → 13635 | 6448 → 7041 | 50.4% → 51.6% |
| spdlog | v1.x | 1 → 6 | 6.7s → 9.4s (+40%) | 2043 → 2148 | 46127 → 63945 | 16140 → 24264 | 35.0% → 37.9% |
| sinatra | main | 1 → 1 | 5.0s → 5.2s (+4%) | 954 (=) | 16336 (=) | 8757 (=) | 53.6% → 53.6% |
| Bash-Snippets | master | 1 → 1 | 1.0s → 1.0s (+0%) | 453 (=) | 3684 (=) | 1171 (=) | 31.8% → 31.8% |
| express | master | 1 → 4 | 4.7s → 4.7s (+0%) | 594 → 618 | 25993 → 27055 | 15325 → 15910 | 59.0% → 58.8% ⚠ |
| travelbuddy | main | 1 → 1 | 3.8s → 4.4s (+16%) | 2230 (=) | 14268 → 19069 | 8380 → 10736 | 58.7% → 56.3% ⚠ |
| appbase | main | 1 → 1 | 0.2s → 0.2s (+0%) | 49 (=) | 229 → 240 | 111 → 115 | 48.5% → 47.9% ⚠ |
| carbingo | main | 1 → 112 | 4.0s → 15.1s (+278%) | 2492 → 6124 | 16337 → 39561 | 11392 → 26349 | 69.7% → 66.6% ⚠ |
| sentimeter | main | 1 → 1 | 2.6s → 2.7s (+4%) | 1097 (=) | 7971 → 8226 | 3743 → 3885 | 47.0% → 47.2% |
| geobuddy | main | 1 → 1 | 2.1s → 2.5s (+19%) | 1236 (=) | 5113 → 6880 | 2896 → 3765 | 56.6% → 54.7% ⚠ |
| git | master | 1 → 57 | 148.6s → 515.6s (+247%) | 40651 → 85799 | 578971 → 1439487 | 476415 → 1208841 | 82.3% → 84.0% |
| interview-technical-challenge-2 | master | 1 → 1 | 1.7s → 1.7s (+0%) | 457 (=) | 2925 → 2928 | 1464 → 1465 | 50.1% → 50.0% |

**Elapsed.** The only single-commit increase above 20% is inxr's 0.4s → 0.5s, which is
sub-second rounding. Every other increase above 20% comes with a higher commit count.

**Resolution-% dips (⚠).** This PR adds references in type position: Swift navigation heads
(`T.self`, `T.member`, `throw T.case(...)`), Python capitalized names used as values
(`isinstance`, `except`, `raise`, arguments), PHP `instanceof`, Go `pkg.T`, and C++ `T::` qualifiers.
In every flagged single-commit repo **both** refs found **and** refs resolved rose. For example,
travelbuddy gained 4,801 references, of which 2,356 resolve. The added references resolve at a
lower rate than the existing ones because Swift navigation heads also include local-variable
receivers (`decoder.container(...)`), which cannot resolve. So the ratio dips while absolute
resolution improves. express and carbingo are multi-commit (1 → 4, 1 → 112) and also carry the
#551 head-only target narrowing documented in the 2026-10-16 report.

**First IX-01 run under host load.** The first run's elapsed times were 2–14× the baseline on
single-commit repos, including sinatra (Ruby, +192%) and crisp (C, +169%), whose extraction this PR
does not change. A parser-only A/B on the same files, best of 3, showed no meaningful difference.
Main's parser vs this branch: sentimeter 0.12s / 0.10s, travelbuddy 0.27s / 0.30s, geobuddy
0.11s / 0.11s, sinatra 0.18s / 0.18s, crisp 0.08s / 0.08s, inxr2 1.59s / 1.47s.

---

## Phase 2: Browser (36/39 passed, 2 skipped)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| RT-01 | Home page repo cards | PASS | 20 distinct `/browse/<repo>` links = API's 20 |
| RT-02 | Repo card stats | PASS | e.g. crisp 109 files / 1.3K symbols / 14.5K lines = API 109 / 1330 / 14471 |
| RT-02a | Repo card indexing stats | PASS | files, symbols, lines, resolved % and last-indexed time per card; language tags = API's top languages |
| RT-03 | Navigate to browse | PASS | → `/browse/crisp?branch=main&commit=1c1feab…` |
| RT-04 | File tree matches git | PASS | 8/8 top-level entries = `git ls-tree` |
| RT-05 | Directory expands | PASS | `src/` → `cool crisp platform ptime udptrans` = git |
| RT-06 | Code viewer content | PASS | `file_filter.py` line 1 matches git; 54 rows for 53 lines (known trailing-newline off-by-one) |
| RT-07 | Line numbers clickable | PASS | `line=5` added to URL |
| RT-08 | Symbol click opens panel | PASS | `FileFilter` → class, Definition `:20`, 15 references |
| RT-09 | References panel usages | PASS | `process_commit.py` and `tests/unit/domain/test_file_filter.py`; both in `git ls-files` |
| RT-10 | Search globally link | PASS | → `/search?query=FileFilter&types=symbol,reference` |
| RT-11 | Blame matches git | PASS | line 1: `5e0a931`, Paul Wierenga = `git blame --porcelain` |
| RT-12 | Diff mode enter/exit | PASS | Compare adds `diff=`, Exit compare removes it |
| RT-12a | Diff colors temporal order | **FAIL** (known #520) | carbingo `PreviewDependencies.swift` `78a3d9c`→`b1e219b`: git numstat 32/19. Case A: 32 green / 19 red ✓. Case B: 19 green / 32 red, inverted. `older`/`newer` chips present; Swap button shown when newer is on the left |
| RT-12b | Diff version selectors | PASS | 280 branch-commit options; all 8 `/api/files/history` versions present with `EditIcon`; HEAD `740ba9f` badged |
| RT-13 | Search via input | PASS | "FileFilter" → "Found 42 results"; result paths exist in git |
| RT-14 | Search result click | PASS | → `file_filter.py?line=20`, file loads |
| RT-15 | Regex search | PASS | `def should_[a-z_]+` → 3 results = `/api/search/text` regex total 3 |
| RT-16 | File search | PASS | `file_filter.py` → `src/inxr2/domain/services/file_filter.py` (+ test file) |
| RT-16a | Extensionless file search | PASS | `Dockerfile` → 6 hits across repos; click opens `Java/.devcontainer/Dockerfile` |
| RT-17 | History matches git log | PASS | carbingo: first 5 hashes/authors = `git log` (280 entries) |
| RT-18 | History commit click | PASS | → `/browse/carbingo?commit=740ba9f…` |
| RT-19 | Tab navigation context | PASS | `repo=inxr2&branch=main` preserved on Search, History, Browse |
| RT-20 | Branch selector | PASS | shows `main`; the API's only indexed inxr2 branch is `main` (1 commit) |
| RT-21 | URL state on reload | PASS | `branch=main&line=10` retained; file loads |
| RT-22 | Theme toggle | PASS | `rgb(247,246,242)` → `rgb(30,30,30)` → `rgb(247,246,242)` |
| RT-22a | Diff colors in both themes | PASS | light `rgba(80,161,79,.14)`/`rgba(228,86,73,.14)` → dark `rgba(46,160,67,.15)`/`rgba(248,81,73,.15)`; 32/19 stable |
| RT-23 | Markdown rendering | PASS | `.claude/skills/close/SKILL.md` → `H1: Close Skill` (front matter still renders as an H2, known #553) |
| RT-24 | Logical View loads | PASS | crisp file list = `symbol-tree` API order; no "Coming Soon" |
| RT-25 | Expand file shows symbols | PASS | `examples/abp1/extern.c` → 6 functions = file-structure API |
| RT-26 | Symbol click → browse | PASS | → `extern.c?…&line=28` |
| RT-27 | Language and kind filters | PASS | language `cpp`: 51 → 18 files, all `.h`; kind `struct` switches to a 51-symbol struct list |
| RT-28 | Dependencies tab | PASS | inxr2 "668 packages" = API total; groups 581+36+7+40+4; `react`, `vite` visible when expanded. (crisp, the first repo, has 0 deps) |
| RT-29 | Dependencies commit picker | PASS | carbingo `95701c9`: 17 packages = API at that commit; URL keeps `commit=` |
| RT-30 | Dependencies empty state | PASS | "Repository not found", no crash |
| RT-31 | References → Logical View | PASS | link `/logical-view?repo=inxr2&…&file=…file_filter.py`; FileFilter visible |
| RT-32 | Browse rename banner | SKIP | `file_renames` is empty; `git log -M --diff-filter=R --since='10 days ago'` is empty for every multi-commit repo |
| RT-33 | Diff viewer rename following | SKIP | same reason as RT-32 |
| RT-34 | Mermaid renders as SVG | PASS | `docs/archived/2026-03-23-mermaid-test.md`: 4 mermaid SVGs, no raw source |

### RT-12a Failure Details (known #520)

```
DISCOVER: git -C /repos/test-repos/carbingo diff --numstat 78a3d9c b1e219b -- Carbingo/Infrastructure/PreviewDependencies.swift
          -> 32  19
Case A: /browse/carbingo/Carbingo/Infrastructure/PreviewDependencies.swift?commit=b1e219ba…&branch=main&diff=78a3d9ca…
        -> rgba(80,161,79,.14): 32, rgba(228,86,73,.14): 19   (correct)
Case B: …?commit=78a3d9ca…&branch=main&diff=b1e219ba…
        -> rgba(80,161,79,.14): 19, rgba(228,86,73,.14): 32   (inverted)
```

Colouring is positional (#520). Unrelated to this PR.

---

## Phase 3: MCP Server (26/26 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| MCP-01 | List repos | PASS | 20 = API; every name present; each shows its indexed branch |
| MCP-02 | Detail branches | PASS | `main: 1 commits, head: e26145f, commits_behind: 0` = API |
| MCP-03 | Search symbols | PASS | same 3 names, kinds, paths, lines as `/api/symbols` |
| MCP-04 | Kind filter | PASS | `kind=class` → only `[class]`; `kind=interface` includes travelbuddy protocols `KeychainPort`, `LLMPort`, `LocationPort` |
| MCP-05 | Go to definition | PASS | `search_symbols.py:85`, kind and docstring shown |
| MCP-06 | Find references | PASS | 47 = API (`limit=500`); types call/import/type_annotation/usage; sample locations match |
| MCP-07 | Ref-type filter | PASS | `ref_type=import` → 3, all `[import]` |
| MCP-08 | Search code | PASS | same paths/lines as `/api/search/text` (phrase) |
| MCP-09 | Repo filter | PASS | all 5 results `inxr2:` |
| MCP-10 | No-match messages | PASS | each tool returns a readable "No … found" message with the query |
| MCP-11 | MCP unit tests | PASS | 159 passed |
| MCP-12 | Browse URLs | PASS | all 4 tools emit URLs; each opens the right line (e.g. `search_symbols.py:85` = `class SearchSymbolsUseCase:`); `branch=main` appended when filtered; none without `frontend_url` |
| MCP-13 | Find dead code | PASS | inxr2: "Scanned all 9059 symbols; 2876 entry points excluded", 163 dead, header names `offset=10`; carbingo: 2492/2492 scanned, 471 entry points, 132 dead; scanned = `/api/symbols` head total; no "may be incomplete" |
| MCP-14 | Dead code by kind | PASS | `kind=function`: "Scanned all 1021 functions", all entries `[function]` |
| MCP-15 | Review helper blast radius | PASS | carbingo `9808690`: 3 changed files = `git diff-tree`; 11 symbols; 52 downstream refs (34 on 2026-10-16; this PR adds the Swift type-position references) |
| MCP-16 | Changed files only | PASS | `Changed files: 3` = git |
| MCP-17 | Staleness warning | PASS | inxr2/carbingo/git current → warning `None`; no warning on `search_symbols` |
| MCP-18 | URLs in dead_code / review_helper | PASS | present with `frontend_url`, absent without |
| MCP-19 | get_file_structure | PASS | `FileFilter` [L20-53] › `should_skip` [L24-53]; structural symbols match the API (module constants excluded by design) |
| MCP-20 | get_change_impact | PASS | Source (1) / Test (1) = API's 15 refs in 2 files; depth=2 ⊇ depth=1; graceful unknown-symbol message |
| MCP-21 | explain_symbol (SSE) | PASS | header, `Location`, `Docstring`, `References (47 total)` grouped by type; unknown → "Symbol 'xyzzy_nope_42' not found."; no-repo call includes the disambiguation note |
| MCP-22 | Wildcard search | PASS | "5 shown (of 9059 total)" |
| MCP-23 | No duplicate results | PASS | `TraceLogger` swift: 2 lines, 2 unique |
| MCP-24 | Results have file paths | PASS | 18/18 result lines `inxr2:<path>.<ext>:<line>`; no commit-message lines |
| MCP-25 | Code body content | PASS | `RouteLeg`: 10 `.swift` results, no non-swift |
| MCP-26 | source_only filter | PASS | without: 16 `.md`; `source_only=true`: 0 `.md`, 4 `.swift` |

---

## Known Issues / Observations

1. **#548 verified on real data.** carbingo's full dead list (132 names) contains none of the eight
   false positives from the issue and includes `llm`, `agent`, `fullCard`. The issue's other real
   candidates `app`, `summary` and `timeline` are **not** listed, because dead-code matching is by
   name and other symbols with those names are referenced. This limitation is documented in the PR.
2. **Remaining false-positive classes**, to be filed as a follow-up: Swift `init` and SwiftUI
   `body`, which the framework calls (both appear in carbingo's list), and decorator-registered
   framework handlers such as FastAPI routes in `qa-agent/src/server.py` (`get_html`,
   `list_elements`, `screenshot_save` appear in inxr2's function list). These, like dunder
   methods and overrides, are invoked implicitly.
3. **Resolution-% dips are expected with this PR** (IX-05): more references are extracted and
   more resolve, but the ratio falls slightly where Swift navigation heads are local variables.
4. **Host load inflated the first IX-01 run** (15-minute load average ~249). It was re-run under low
   load; see Summary.
5. **RT-12a `older`/`newer` chips need full commit hashes.** With short hashes in `commit=`/`diff=`
   (e.g. `diff=78a3d9c`), `temporalOrderKnown` stays false and neither chip nor the Swap button
   renders, because `useBrowseState` compares the URL hash against full `commit_hash` values. UI
   navigation always produces full hashes, so this only affects hand-built URLs. Pre-existing.
6. **RT-06 trailing-newline off-by-one persists** (54 rows for a 53-line file), as in prior reports.
7. **RT-23 front matter rendered as an H2** (#553), as in the previous report.
8. **No renames in the 10-day window**, so RT-32/RT-33 could not run (same as 2026-10-16).
