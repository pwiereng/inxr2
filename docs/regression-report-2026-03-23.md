# Regression Test Report — 2026-03-23

## Summary

| Phase | Passed | Total | Notes |
|-------|--------|-------|-------|
| Indexing | 6 | 7 | 1 failed (IX-02) |
| Browser | 34 | 34 | |
| MCP | 23 | 24 | 1 failed (MCP-23) |
| **Total** | **63** | **65** | **2 failed** |

---

## Phase 1: Indexing (6/7 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| IX-01 | Reset DB and index all repos | PASS | 14 repos, 28756 symbols in inxr2/main, 169806 refs resolved, 56.0s |
| IX-02 | Verify indexing status | FAIL | travelbuddy shows 0 files/0 symbols in `inxr2 status` output due to duplicate config.yaml entry — second incremental run reports 0 delta; API correctly shows 66 files/856 symbols |
| IX-03 | Verify API serves indexed data | PASS | All 14 repos returned by `/api/repositories`, stats endpoint returns per-repo counts |
| IX-04 | Multi-language symbols (10 langs) | PASS | Python, TypeScript, JavaScript, C, C++, Java, C#, Go, Ruby, Bash all producing symbols |
| IX-04a | Reference extraction | PASS | Bare identifiers, CommonJS require(), constructor this.property references all extracted |
| IX-04b | ES6 export/re-export references | PASS | Named re-exports, local exports, default export of identifier, barrel re-exports all found |
| IX-05 | Performance comparison | PASS | No main/master branches exceeded 20% threshold: inxr2/main +0.9% (55.5s→56.0s), Java/master +1.2%, cJSON/master +3.1% |

### IX-05 Performance Comparison

| Repo | Branch | Elapsed (prev → now) | Symbols | Delta |
|------|--------|---------------------|---------|-------|
| crisp | main | 1.4s → 1.4s | 1330 | +0.0% |
| inxr | master | 0.4s → 0.4s | 253 | +0.0% |
| inxr2 | main | 55.5s → 56.0s | 28756 | +0.9% |
| multidockerdevcontainer | main | 2.2s → 2.2s | 975 | +0.0% |
| soccer-stats | main | 0.4s → 0.4s | 210 | +0.0% |
| cJSON | master | 3.2s → 3.3s | 2622 | +3.1% |
| clean-architecture | main | 1.4s → 1.4s | 745 | +0.0% |
| Java | master | 16.7s → 16.9s | 11540 | +1.2% |
| bubbletea | main | 2.2s → 2.2s | 1677 | +0.0% |
| spdlog | v1.x | 6.1s → 6.1s | 2966 | +0.0% |
| sinatra | main | 4.3s → 4.5s | 954 | +4.7% |
| Bash-Snippets | master | 0.8s → 0.9s | 453 | +12.5% |
| express | master | 3.6s → 3.6s | 592 | +0.0% |
| travelbuddy | main | 2.5s → 2.5s | 856 | +0.0% |

---

## Phase 2: Browser (34/34 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| RT-01 | Home page repo cards | PASS | 14 repo cards visible |
| RT-02 | Repo card stats | PASS | File/symbol/ref counts match API |
| RT-03 | Navigate to browse | PASS | Repo name in URL after click |
| RT-04 | File tree matches git | PASS | `git ls-tree` output matches tree items |
| RT-05 | File tree directory expansion | PASS | Subdirectory children visible after expand |
| RT-06 | Code viewer shows correct content | PASS | Line count and content match git |
| RT-07 | Line numbers clickable | PASS | URL updates with line anchor |
| RT-08 | Symbol click opens references | PASS | References panel opens with symbol name |
| RT-09 | References panel shows usages | PASS | File paths in panel match indexed files |
| RT-10 | "Search globally" link works | PASS | Navigates to search with symbol query |
| RT-11 | Blame matches git blame | PASS | Commit hashes match `git blame --porcelain` |
| RT-12 | Diff mode enter and exit | PASS | URL diff param set/cleared correctly |
| RT-12a | Diff colors follow temporal order | PASS | Newer = green, older = blue |
| RT-12b | Diff version selectors show all commits | PASS | Commit count matches file history API |
| RT-13 | Search returns real results | PASS | Results contain indexed file names |
| RT-14 | Search result navigates correctly | PASS | Click navigates to correct file |
| RT-15 | Regex search works | PASS | Regex pattern returns matching results |
| RT-16 | File search works | PASS | Filename search finds correct files |
| RT-16a | Extensionless file search | PASS | Files without extensions findable |
| RT-17 | History matches git log | PASS | Commit hashes match `git log --oneline` |
| RT-18 | Commit click navigates to browse | PASS | URL contains commit hash after click |
| RT-19 | Tab navigation preserves context | PASS | Repo param preserved when switching tabs |
| RT-20 | Branch selector shows branches | PASS | Branch names match config branches |
| RT-21 | URL state preserved on reload | PASS | All URL params survive page reload |
| RT-22 | Theme toggle | PASS | Background color changes on toggle |
| RT-22a | Diff colors in both themes | PASS | Theme-appropriate diff colors in light and dark |
| RT-23 | Markdown rendering | PASS | Headings rendered as heading elements |
| RT-24 | Logical View symbol tree | PASS | Symbol tree visible in Logical View tab |
| RT-25 | Logical View expand shows symbols | PASS | Expanding file shows symbol list |
| RT-26 | Logical View symbol click → Browse | PASS | Click navigates to browse at correct line |
| RT-27 | Logical View language/kind filters | PASS | Filter reduces visible item count |
| RT-28 | Dependencies tab shows packages | PASS | Dependencies listed with names/versions |
| RT-29 | Dependencies respects commit picker | PASS | URL commit param applied to dependencies |
| RT-30 | Dependencies empty state | PASS | Empty state message shown for repo with no deps |
| RT-31 | References panel → Logical View link | PASS | Link navigates to Logical View for symbol |
| RT-32 | Rename banner at old commit | PASS | Rename banner visible with old/new path |
| RT-33 | Diff viewer rename following | PASS | Both file paths shown in diff header |
| RT-34 | Mermaid diagrams render as SVG | PASS | 4 SVGs with aria-roledescription: flowchart-v2, sequence, class, gitGraph |

---

## Phase 3: MCP Server (23/24 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| MCP-01 | List repos returns all indexed repos | PASS | 14 repos, matches API count |
| MCP-02 | List repo detail shows indexed branches | PASS | inxr2: main, 161 commits, head=8904c22 |
| MCP-03 | Search symbols returns matching definitions | PASS | 141 total matching "Repository" in inxr2 |
| MCP-04 | Search symbols filters by kind | PASS | kind=class returns only class symbols |
| MCP-05 | Go to definition finds symbol | PASS | FileFilter found at domain/services/file_filter.py:20 |
| MCP-06 | Find references returns cross-repo usages | PASS | FileFilter: 15 references across 2 files |
| MCP-07 | Find references filters by type | PASS | ref_type=import returns only import refs |
| MCP-08 | Search code returns matching content | PASS | should_skip found in 3 files |
| MCP-09 | Search code with repository filter | PASS | Results scoped to inxr2 repo only |
| MCP-10 | No-match queries return graceful messages | PASS | "No symbols found" / "No definition found" |
| MCP-11 | MCP unit tests pass | PASS | 141/141 tests passed |
| MCP-12 | Browse URLs in all 4 tools | PASS | search_symbols, go_to_definition, find_references, search_code all generate browse URLs; no URLs without frontend_url |
| MCP-13 | Find dead code returns unreferenced symbols | PASS | 12 symbols found (note: output says "Dead code in..." not "Unreferenced symbols" — test doc assertion string outdated) |
| MCP-14 | Find dead code filters by kind | PASS | kind=function returns only function symbols (16 found) |
| MCP-15 | Review helper shows blast radius | PASS | commit 8904c22: changed files, symbols, downstream refs shown |
| MCP-16 | Review helper changed files only | PASS | commit 1ab3dbd: 1 changed file, not entire repo |
| MCP-17 | Staleness warning when index behind | PASS | No warning (index current with HEAD) |
| MCP-18 | Browse URLs in find_dead_code and review_helper | PASS | Both tools include browse URLs with frontend_url; no URLs without it |
| MCP-19 | get_file_structure returns correct symbol tree | PASS | FileFilter class with should_skip method, matches API |
| MCP-20 | get_change_impact returns dependents grouped by type | PASS | FileFilter: Source (1 file) + Test (1 file) at depth=1 |
| MCP-21 | explain_symbol returns rich symbol context | PASS | SearchSymbolsUseCase: location, docstring, 46 references grouped by call/import/type_annotation |
| MCP-22 | search_symbols wildcard returns results | PASS | query="*" returns 8439 symbols, not empty |
| MCP-23 | search_code extensions filter no duplicates | FAIL | travelbuddy TraceLogger.swift:4 appears twice in results — API returns duplicate entries for file_content rows with null commit_hash; dedup from PR #392/#394 does not cover this case |
| MCP-24 | search_code results always have file path | PASS | No commit message lines in 20-result response |

### MCP-23 Failure Details

**Root cause:** `search_code` with `extensions='swift'` and `repository='travelbuddy'` returns duplicate entries for the same `file:line`.

**Reproduction:**
```bash
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_code
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await search_code.handle(client, {'query': 'TraceLogger', 'repository': 'travelbuddy', 'extensions': 'swift'})
    print(result)
    await client.close()
asyncio.run(main())
"
```

**Observed:** `travelbuddy:travelbuddy/Infrastructure/TraceLogger.swift:4` appears twice with identical content "MARK: - TraceLogger".

**API-level evidence:**
```bash
curl "http://localhost:8000/api/search/text?q=TraceLogger&repository_id=998&extensions=.swift&limit=20"
```
Returns 3 results total; `TraceLogger.swift:4` appears twice with `commit_hash=null`. The deduplication added in PR #394 does not eliminate duplicates for `file_content` rows where `commit_hash` is NULL (non-git-versioned content entries).

---

## Known Issues / Observations

1. **IX-02 travelbuddy duplicate config**: `config.yaml` has a duplicate entry for travelbuddy. The second incremental index run reports 0 new files (correct: nothing changed), but `inxr2 status` displays 0 files/0 symbols for the second entry. The API correctly returns data for the single travelbuddy repo object. This is a pre-existing issue, not a regression.

2. **MCP-13 assertion string outdated**: The test doc checks for `"Unreferenced symbols"` in the output, but the actual output format is `"Dead code in '{repo}': N symbols with no references"`. The pass criteria (returns unreferenced symbols with kind/name/path/line) are met. The test doc should be updated.

3. **MCP-23 duplicate search results**: PR #394 fixed duplicates for file-backed content with commit_hash, but `file_content` rows with `commit_hash=NULL` (non-versioned content entries like markdown files indexed as raw content) are not deduplicated by the current logic. Affects travelbuddy's TraceLogger.swift:4.

4. **MCP-12 `frontend_url` not in schema**: `go_to_definition` has `frontend_url` in the Python function signature but NOT in `TOOL_SCHEMA`. When called directly via Python (as in MCP-12), browse URLs are generated correctly. When called through the MCP protocol (standard Claude tool call), the `frontend_url` parameter would need to be injected server-side. The MCP server injects it via `INXR2_FRONTEND_URL` env var, so this is by design.

5. **Mermaid diagrams (RT-34)**: The `.mermaid` CSS selector matches SVG elements from git graph visualizations in addition to mermaid-rendered content. The correct verification method is checking `aria-roledescription` on SVG elements: confirmed flowchart-v2, sequence, class, gitGraph all render correctly.
