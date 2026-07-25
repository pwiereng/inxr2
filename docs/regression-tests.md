# Regression Test Plan

End-to-end regression tests covering indexing pipeline and browser UI.
Executed after merging changes into main (worktree cleanup step 5).

## Testing Philosophy

**No hardcoded expected data.** Each test discovers what to expect by querying git or the API first, then verifies the UI displays it correctly. This makes tests resilient to repository changes.

**Pattern:**
1. **Discover** — Query git or the API to learn what data exists
2. **Navigate** — Use the QA agent to interact with the UI
3. **Verify** — Compare UI output against the discovered data

## Prerequisites

1. Dev container running:
   ```bash
   docker compose -f docker-compose.dev.yml up -d --build
   ```
2. QA agent running:
   ```bash
   docker compose -f docker-compose.dev.yml --profile qa up -d playwright
   curl http://localhost:9222/health  # verify
   ```

## Known Issues That Affect Expected Results

Open bugs found by previous runs. Where a test's stated criterion currently fails, the failure is
**expected** — record it and move on rather than re-investigating.

| Issue | Affects | What you'll see |
|-------|---------|-----------------|
| [#520](https://github.com/pwiereng/inxr2/issues/520) | RT-12a | Diff colours are positional, so they invert when the newer commit is on the left. Case A passes, Case B inverts. |
| [#521](https://github.com/pwiereng/inxr2/issues/521) | IX-05 | `index.log` header lists 15 columns but rows carry 18 — parse positionally, never by header name. |
| [#522](https://github.com/pwiereng/inxr2/issues/522) | RT-12a, RT-12b, RT-33 | `?branch=X&diff=Y` drops `diff`. Always pass **both** `commit=` and `branch=` alongside `diff=`. |
| [#523](https://github.com/pwiereng/inxr2/issues/523) | MCP-06, MCP-20 | `/api/symbols/{id}/references` returns `total` == page size. Query with `limit=500` before comparing counts. |
| [#524](https://github.com/pwiereng/inxr2/issues/524) | RT-33 | Diff header shows only the post-rename path. |
| [#525](https://github.com/pwiereng/inxr2/issues/525) | Phase 3 setup | MCP SSE server may not be running; start it manually before MCP-21. |

## Environment Notes

- **Python 3.11 f-strings.** The container runs Python 3.11, which cannot reuse the outer quote
  character inside an f-string expression. Snippets like `f"{s[\"name\"]}"` raise
  `SyntaxError: f-string: unmatched '['`. Use `%`-formatting or a different inner quote in any
  inline `python3 -c` you add.
- **Long-running step.** IX-01 takes ~27 min on a full 20-repo reset (the `git` repo alone is
  ~26 min of it). Run it in the background and poll rather than blocking.
- **Scratch files** belong in `.tmp/` in the project root (gitignored), not `/tmp`.

## Base URLs

- Frontend: `http://localhost:5173` (from host or dev container)
- Backend API: `http://localhost:8000` (from host or dev container)
- QA Agent: `http://localhost:9222` (from host)

**Important — QA agent browser URLs:** The QA agent's browser runs inside the `inxr2-playwright` container. When telling it to navigate to the frontend, use `host.docker.internal` instead of `localhost`:

```bash
# From host → QA agent API (localhost is fine)
curl "http://localhost:9222/navigate?url=..."

# URL the QA agent navigates TO (must use host.docker.internal)
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/"
```

This is because `localhost` inside the playwright container refers to itself, not the host machine. `host.docker.internal` resolves to the Docker host on macOS/Docker Desktop.

All `docker exec` commands (git, API curls inside the dev container) still use `localhost` since the backend listens inside that container.

## Browse URL Format

**Critical:** Browse URLs always use this exact structure:

```
/browse/{repo}/{filepath}?branch={branch}
```

- `{repo}` — repository name (e.g. `inxr2`)
- `{filepath}` — file path **without any branch prefix** (e.g. `src/inxr2/domain/entities.py`)
- `{branch}` — branch name goes in the **`?branch=` query param**, never in the path

**Correct:**
```bash
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/browse/inxr2/src/inxr2/domain/entities.py?branch=main"
```

**Wrong — branch must NOT be a path segment:**
```bash
# BAD: "main" is in the path — this will return "File not found"
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/browse/inxr2/main/src/inxr2/domain/entities.py"
```

When substituting `<repo>`, `<file>`, and `<branch>` placeholders in test steps below, always verify the resulting URL matches the correct pattern before navigating.

---

# Phase 1: Indexing Regression

Reset the database and re-index all repos from `config.yaml` (last 10 days).
Verifies: git integration, tree-sitter parsing, symbol extraction, reference resolution.

## IX-01: Reset Database and Index All Repos

**Steps:**
```bash
docker exec inxr2-dev inxr2 index --config config.yaml --reset-db --yes --days 10
```

**Pass criteria:**
- Command completes without fatal errors (warnings acceptable)
- Output shows files processed, symbols extracted, references found for each repo

---

## IX-02: Verify Indexing Status

**Steps:**
```bash
docker exec inxr2-dev inxr2 status
```

**Pass criteria:**
- Number of repositories listed matches number defined in `config.yaml`
- Each repo shows non-zero file count, symbol count, and reference count
- All configured branches appear as indexed

---

## IX-03: Verify API Serves Indexed Data

**Steps:**
```bash
# Get repo list from config
docker exec inxr2-dev grep 'name:' /workspace/config.yaml
# Get repo list from API
docker exec inxr2-dev bash -c "curl -s http://localhost:8000/api/repositories | python3 -m json.tool"
# Get stats from API
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/repositories/stats' | python3 -m json.tool"
```

**Pass criteria:**
- Every repo name from `config.yaml` appears in the API response
- Each repo's stats show non-zero file, symbol, and reference counts

---

## IX-04: Verify Multi-Language Symbol Extraction

For each language, pick a repo that uses it, find a real symbol name from git, and verify it
appears in the API.

> ⚠️ **`/api/symbols` filters by `repository_id`, not `repository_name`.** FastAPI silently ignores
> unknown query params, so passing `repository_name=<repo>` returns **unfiltered cross-repo
> results** — a symbol that genuinely exists can look missing because the response is full of
> same-named symbols from other repos. Resolve the id first.

**Steps (per language):**
```bash
# 0. DISCOVER: Resolve repository name -> id (needed for every filtered /api/symbols call)
docker exec inxr2-dev bash -c "curl -s http://localhost:8000/api/repositories | python3 -c '
import sys, json
print(json.dumps({r[\"name\"]: r[\"id\"] for r in json.load(sys.stdin)}, indent=2))
'"
# 1. DISCOVER: Find a source file in the repo
docker exec inxr2-dev bash -c "git -C /repos/test-repos/<repo> ls-files '*.py' | head -3"
# 2. DISCOVER: Extract a class/function name from that file
docker exec inxr2-dev bash -c "grep -E 'class |def |function |interface |struct ' /repos/test-repos/<repo>/<file> | head -3"
# 3. VERIFY: Search for that symbol name via API (repository_id, NOT repository_name)
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/symbols?q=<discovered_name>&repository_id=<repo_id>&limit=3' | python3 -m json.tool"
```

**Languages to cover (12).** Suggested repo per language — any repo in `config.yaml` declaring that
language works:

| Language | Globs | Suggested repo |
|----------|-------|----------------|
| Python | `*.py` | inxr2 |
| TypeScript | `*.ts` / `*.tsx` | inxr2 |
| JavaScript | `*.js` / `*.jsx` | express |
| C | `*.c` / `*.h` | cJSON |
| C++ | `*.cpp` / `*.hpp` | spdlog |
| Java | `*.java` | Java |
| C# | `*.cs` | clean-architecture |
| Go | `*.go` | bubbletea |
| Ruby | `*.rb` | sinatra |
| Bash | `*.sh` (also extensionless) | Bash-Snippets |
| Swift | `*.swift` | travelbuddy |
| PHP | `*.php` | interview-technical-challenge-2 |

**Pass criteria:**
- For each language, at least one symbol is found via the API
- Symbol kind matches what was found in the source (e.g., `grep 'class Foo'` → API returns symbol with kind=class)
- Some symbols legitimately carry more than one kind (e.g. Java `class` + `constructor`, Ruby
  `class` + `module`); the discovered kind being *among* them is a pass

---

## IX-04a: Verify Reference Extraction (Bare Identifiers, CommonJS, Constructor Properties)

Verify that reference extraction captures bare identifiers, CommonJS `require()` calls, and
constructor `this.property` assignments.

**Steps:**
```bash
# DISCOVER: Find a JS/TS file with require() or import statements
docker exec inxr2-dev bash -c "grep -rl 'require(' /repos/test-repos/<repo>/ --include='*.js' --include='*.ts' | head -1"
# DISCOVER: Extract a require target
docker exec inxr2-dev bash -c "grep -oP \"require\('\K[^']+\" /repos/test-repos/<repo>/<file> | head -3"
# VERIFY: Check references via API (response shape: {file_id, file_path, references:[{reference_type, reference_text, source_line, ...}]})
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/files/by-path/references?repo=<repo>&path=<file>' | python3 -m json.tool"
```

**Pass criteria:**
- References include `reference_type == "import"` entries for `require()` / `import` targets
- References include `reference_type == "usage"` entries for bare identifiers used in the file

**Note:** This endpoint's reference objects do **not** carry a `from_module` field — assert on
`reference_type` (`import` vs `usage`) and `reference_text` instead.

---

## IX-04b: Verify ES6 Export/Re-export References

Verify that named exports, re-exports, default export of identifier, and barrel exports
produce the correct references.

**Steps:**
```bash
# DISCOVER: Find a file with export statements
docker exec inxr2-dev bash -c "grep -rl 'export {' /repos/test-repos/<repo>/ --include='*.ts' --include='*.js' | head -1"
# DISCOVER: Extract export names
docker exec inxr2-dev bash -c "grep 'export' /repos/test-repos/<repo>/<file> | head -5"
# VERIFY: Check references via API for that file
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/files/by-path/references?repo=<repo>&path=<file>' | python3 -m json.tool"
```

**Pass criteria:**
- Named re-exports (`export { foo } from './module'`) appear as `reference_type == "import"` references
- Local named exports (`export { foo }`) appear as `reference_type == "usage"` references
- Default export of identifier (`export default myFunc`) appears as a `usage` reference
- Barrel re-exports (`export * from './module'`) appear as `import` references

**Note:** Assert on `reference_type` (`import` / `usage`); this endpoint does not return a
`from_module` field.

---

## IX-05: Compare Indexing Performance Against History

The indexing CLI appends timing data to `index.log` (CSV) after each run. Compare the
current run against the most recent historical run for the same repo+branch to catch
performance regressions.

**Steps:**
```bash
# Read the full index.log
docker exec inxr2-dev bash -c "cat /workspace/index.log"
```

> ⚠️ **Do not parse `index.log` by header name — the header is stale (issue #521).** Rows carry 18
> columns but the file's header row still lists the original 15, because the header is only written
> when the file does not yet exist. A `csv.DictReader` parse silently shifts columns (`symbols_found`
> reads `file_versions_cached`, `elapsed_seconds` reads `references_resolved`, …), producing
> nonsense like "resolution 592.4%". Parse **positionally, keyed off the field count**:
>
> ```
> 18-col: ts,repo,branch,commits,files_at_head,files_processed,files_failed,
>         file_versions_new,file_versions_cached,symbols,refs_found,refs_resolved,
>         elapsed,indexing,resolving,lines,db_mb,db_added_mb
> 15-col: ts,repo,branch,commits,files_at_head,files_processed,files_failed,
>         files_reused,symbols,refs_found,refs_resolved,elapsed,indexing,resolving,lines
> ```
>
> Check the split with:
> ```bash
> docker exec inxr2-dev bash -c "awk -F, 'NR==1{print NF\" header cols\"} NR>1{c[NF]++} END{for(k in c) print k\" cols: \"c[k]\" rows\"}' /workspace/index.log"
> ```

**Analysis:**

For each repo+branch combination, compare the **current run** (from IX-01) against the
**most recent previous run** for the same repo+branch. The key columns are:

| Column | What It Measures |
|--------|-----------------|
| `elapsed_seconds` | Total wall-clock time |
| `indexing_seconds` | Time spent parsing files and extracting symbols |
| `resolving_seconds` | Time spent resolving cross-references |
| `files_processed` | Total file versions processed |
| `symbols_found` | Total symbols extracted |
| `references_found` | Total references found |
| `references_resolved` | Total references successfully resolved |

**Pass criteria:**
- `elapsed_seconds` for each repo+branch is within **20%** of the previous run
  (allow for variance due to container load, but flag anything beyond 20%)
- `symbols_found` and `references_found` counts are the same or higher than previous
  (a drop may indicate a parser regression)
- `references_resolved` percentage (`resolved / found`) is the same or higher

**Reporting format:**

```
Indexing Performance Comparison:
| Repo | Branch | Commits (prev → now) | Elapsed (prev → now) | Symbols (prev → now) | Refs Resolved % |
|------|--------|---------------------|---------------------|---------------------|-----------------|
| crisp | main | 1 → 1 | 5.5s → 5.8s (+5%) | 1324 → 1324 (=) | 82.1% → 82.1% |
| inxr2 | main | 23 → 21 | 185.8s → 190.2s (+2%) | 36455 → 36455 (=) | ⚠ ... |
```

**⚠ Comparison caveat — the `--days 10` window slides:** absolute counts are only
apples-to-apples for **single-commit (snapshot) repos**, where the same lone commit is indexed
every run. For **multi-commit repos**, the rolling `--days 10` window shifts forward between runs,
so an older run indexed *more historical commits* than a later one — its symbol/reference counts
and elapsed time will legitimately be higher with no parser regression involved. **Always log the
commits-indexed count (the `Commits (prev → now)` column above) next to the timing data** so a
count/elapsed drop attributable to the sliding window isn't mistaken for a regression.

Flag any row with:
- Elapsed time increase > 20% **at an equal or lower commit count** (a higher commit count
  explains a higher elapsed time)
- Symbol count decrease **on a single-commit repo, or on a multi-commit repo at an equal/higher
  commit count**
- Reference resolution **percentage** (`resolved / found`) decrease — this ratio is
  window-independent, so a drop here is meaningful regardless of commit count

## IX-06: Verify All Git Files at HEAD Are Indexed (FileFilter Completeness)

Regression test for issue #349 — `FileFilter` silently dropping first-party files whose
path contains a directory name that happens to match a vendor signal (e.g. `external`).

For each indexed repo, compare the files git sees at HEAD against the files the API
returns. Any file present in git but absent from the API was silently dropped by the
indexer.

**Steps:**
```bash
# DISCOVER: Get HEAD commit hash for the repo
HEAD_HASH=$(docker exec inxr2-dev bash -c "git -C /repos/test-repos/<repo> rev-parse HEAD")

# DISCOVER: List all files git sees at HEAD (no filtering)
#   -z          -> no path quoting, so non-ASCII filenames compare correctly
#   type==blob  -> excludes submodule gitlinks (mode 160000), which are not files
docker exec inxr2-dev bash -c "git -C /repos/test-repos/<repo> ls-tree -r -z $HEAD_HASH" \
  | python3 -c "
import sys
for ent in sys.stdin.read().split('\0'):
    if not ent:
        continue
    meta, _, path = ent.partition('\t')
    if meta.split()[1] == 'blob':
        print(path)
" | sort > /tmp/git_files.txt

# VERIFY: Get all files the API knows about at that commit (flatten tree response)
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/repositories/by-name/<repo>/tree?commit=$HEAD_HASH' | python3 -c \"
import sys, json

def walk(nodes):
    for n in nodes:
        if n.get('type') == 'file':
            print(n['path'])
        for child in n.get('children') or []:
            walk([child])

walk(json.load(sys.stdin)['root'])
\"" | sort > /tmp/api_files.txt

# COMPARE: Files in git but not in API (silently dropped)
comm -23 /tmp/git_files.txt /tmp/api_files.txt
```

**For the `inxr2` repo specifically** (known to have `src/inxr2/adapters/external/`):
```bash
HEAD_HASH=$(docker exec inxr2-dev bash -c "git -C /workspace rev-parse HEAD")
docker exec inxr2-dev bash -c "git -C /workspace ls-tree -r --name-only $HEAD_HASH" | sort > /tmp/git_files.txt
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/repositories/by-name/inxr2/tree?commit=$HEAD_HASH' | python3 -c \"
import sys, json

def walk(nodes):
    for n in nodes:
        if n.get('type') == 'file':
            print(n['path'])
        for child in n.get('children') or []:
            walk([child])

walk(json.load(sys.stdin)['root'])
\"" | sort > /tmp/api_files.txt
comm -23 /tmp/git_files.txt /tmp/api_files.txt
```

**Pass criteria:**
- `comm -23` output is empty for all repos (no files dropped)
- `src/inxr2/adapters/external/` files appear in the API response for the `inxr2` repo
- If any files are listed: they should only be absent due to:
  1. A minified/bundled pattern match (`.min.js`, `.bundle.js`, bundler hash filenames)
  2. An explicit `exclude_paths` entry in the repo's config
  Any other missing file is a `FileFilter` regression

**Note:** Directory-based exclusions are opt-in via `exclude_paths` in config — there are
no hardcoded directory skip rules. If a committed file is missing and its path doesn't
match a minified/bundled pattern or a configured `exclude_paths` entry, that is a bug.

**Two known false positives** if you use a plain `ls-tree -r --name-only` (both fixed by the
DISCOVER command above):
1. **Quoted non-ASCII paths.** `core.quotePath` defaults to true, so git emits
   `"examples/downloads/files/CCTV\345\244\247..."` while the API returns the decoded UTF-8 path.
   Affects 2 files in `express`. Fixed by `-z`.
2. **Submodule gitlinks.** `ls-tree -r` lists mode-160000 entries (e.g. `sha1collisiondetection`
   in `git`), which are commits, not files, and are correctly absent from the API. Fixed by the
   `type == blob` filter.

---

# Phase 2: QA Browser Regression

Start backend and frontend, then verify UI features against the indexed data.
**All verifications cross-reference against git or API data — no hardcoded expectations.**

## Setup

```bash
# Start backend (if not running)
docker exec -d inxr2-dev inxr2 serve --reload

# Start frontend (if not running)
docker exec -d -w /workspace/frontend inxr2-dev npm run dev

# Wait for services to be ready
sleep 5
```

---

## RT-01: Home Page Loads with Repository Cards

**Steps:**
```bash
# DISCOVER: Count repos from API
docker exec inxr2-dev bash -c "curl -s http://localhost:8000/api/repositories | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))'"
# NAVIGATE + VERIFY: Check UI shows same count
curl "http://localhost:9222/navigate?url=http://localhost:5173/"
curl "http://localhost:9222/elements?selector=a[href^='/browse/']&limit=20"
```

**Pass criteria:**
- Number of repo card links matches API repo count

---

## RT-02: Repository Card Shows Statistics

**Steps:**
```bash
# DISCOVER: Get stats for first repo from API
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/repositories/stats' | python3 -m json.tool"
# NAVIGATE + VERIFY: Check UI displays stats
curl "http://localhost:9222/text?selector=main"
```

**Pass criteria:**
- Page text includes numeric statistics (file counts, symbol counts) that match API stats
- At least one language tag visible per repo

---

## RT-02a: Repository Card Shows Indexing Stats

**Steps:**
```bash
# DISCOVER: Get indexing stats from API
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/repositories/stats' | python3 -c '
import sys, json
stats = json.load(sys.stdin)
for s in stats:
    print(f\"{s[\"name\"]}: files={s.get(\"file_count\",0)}, symbols={s.get(\"symbol_count\",0)}, refs={s.get(\"reference_count\",0)}, langs={s.get(\"languages\",[])}\")
'"
# NAVIGATE + VERIFY: Check that repo cards show per-repo stats
curl "http://localhost:9222/navigate?url=http://localhost:5173/"
curl "http://localhost:9222/wait?selector=a[href^='/browse/']&timeout=5000"
curl "http://localhost:9222/text?selector=main"
```

**Pass criteria:**
- Each repo card displays file count, symbol count, and reference count
- Displayed counts match API stats values
- Language tags on each card match the languages from API stats

---

## RT-03: Navigate to Browse from Home

**Steps:**
```bash
curl "http://localhost:9222/navigate?url=http://localhost:5173/"
curl "http://localhost:9222/click?selector=a[href^='/browse/']"
curl "http://localhost:9222/url"
```

**Pass criteria:**
- URL contains `/browse/<repo_name>` where repo_name is one of the indexed repos

---

## RT-04: File Tree Matches Git

**Steps:**
```bash
# DISCOVER: Get the repo name from the current URL (from RT-03)
# Get top-level entries from git
docker exec inxr2-dev git -C /repos/test-repos/<repo> ls-tree --name-only HEAD
# NAVIGATE + VERIFY
curl "http://localhost:9222/wait?selector=.MuiList-root&timeout=5000"
curl "http://localhost:9222/elements?selector=.MuiListItemButton-root&limit=30"
```

**Pass criteria:**
- File tree items include the same top-level directory/file names as `git ls-tree`

---

## RT-05: Click Directory Expands Children

**Steps:**
```bash
# DISCOVER: Pick first directory from git and list its children
docker exec inxr2-dev git -C /repos/test-repos/<repo> ls-tree --name-only HEAD <dir>/
# NAVIGATE
curl "http://localhost:9222/click?selector=.MuiListItemButton-root"
curl "http://localhost:9222/elements?selector=.MuiListItemButton-root&limit=30"
```

**Pass criteria:**
- After click, expanded items match children from `git ls-tree`

---

## RT-06: Code Viewer Shows Correct File Content

**Steps:**
```bash
# DISCOVER: Pick a source file from the repo and get its line count
docker exec inxr2-dev bash -c "git -C /repos/test-repos/<repo> ls-files '*.c' '*.py' '*.java' '*.cs' '*.ts' | head -1"
docker exec inxr2-dev wc -l /repos/test-repos/<repo>/<file>
docker exec inxr2-dev head -5 /repos/test-repos/<repo>/<file>
# NAVIGATE
curl "http://localhost:9222/navigate?url=http://localhost:5173/browse/<repo>/<file>?branch=<branch>"
curl "http://localhost:9222/wait?selector=table&timeout=5000"
# VERIFY: Check line count and first few lines
curl "http://localhost:9222/elements?selector=tr[data-line]&limit=5"
curl "http://localhost:9222/text?selector=tr[data-line='1']"
```

**Pass criteria:**
- Number of `tr[data-line]` rows matches file line count
- First line content matches what `head -1` returned from git

---

## RT-07: Line Numbers Are Clickable

**Steps:**
```bash
# (Continuing from RT-06 with a file loaded)
# The line-number cell is the FIRST td in the row; the code content is the last td.
curl "http://localhost:9222/click?selector=tr[data-line='5'] td:first-child"
curl "http://localhost:9222/url"
```

**Pass criteria:**
- URL now contains `line=5` parameter

---

## RT-08: Symbol Click Opens References Panel

**Steps:**
```bash
# (Continuing from RT-06 with a file loaded)
# Clickable symbols render as styled <span> elements inside the code cells — each has a hashed
# emotion CSS class (e.g. css-jzqzon, css-1c6uefz). Plain (non-clickable) syntax-highlight text
# uses the class "css-0", so exclude it with :not(.css-0).
# List clickable symbols on the page
curl "http://localhost:9222/elements?selector=td span[class*='css-']:not(.css-0)&limit=10"
# Click first clickable symbol
curl "http://localhost:9222/click?selector=td span[class*='css-']:not(.css-0)"
# Check panel opened
curl "http://localhost:9222/text?selector=body"
```

**Pass criteria:**
- References panel appears with "Definition" and/or "References" sections
- The displayed symbol name exists in the file being viewed (cross-reference with file content)

---

## RT-09: References Panel Shows Usages

**Steps:**
```bash
# (Continuing from RT-08 with references panel open)
# DISCOVER: Note the symbol name from the panel header
# VERIFY: Check panel content
curl "http://localhost:9222/text?selector=body"
```

**Pass criteria:**
- Panel shows "Definition" or "References" section
- At least one reference listed with a file path and line number
- Referenced file paths exist in the repository (verify via `git ls-files`)

---

## RT-10: "Search Globally" Link Works

**Steps:**
```bash
# (Continuing from RT-08/09 with references panel open)
curl "http://localhost:9222/elements?selector=a[href*='/search']&limit=5"
curl "http://localhost:9222/click?selector=a[href*='/search?query=']"
curl "http://localhost:9222/url"
```

**Pass criteria:**
- Link contains the symbol name from RT-08
- Click navigates to `/search?query=<symbol_name>`

---

## RT-11: Blame Matches Git Blame

**Steps:**
```bash
# DISCOVER: Get git blame for line 1 of the file from RT-06
docker exec inxr2-dev bash -c "git -C /repos/test-repos/<repo> blame -L1,1 --porcelain <file> | head -1"
# NAVIGATE
curl "http://localhost:9222/navigate?url=http://localhost:5173/browse/<repo>/<file>?branch=<branch>"
curl "http://localhost:9222/wait?selector=table&timeout=5000"
# Toggle blame on
curl "http://localhost:9222/click?selector=[aria-label*='blame']"
curl "http://localhost:9222/wait?selector=td&timeout=3000"
# VERIFY
curl "http://localhost:9222/text?selector=tr[data-line='1']"
```

**Pass criteria:**
- Blame annotation on line 1 shows a commit hash prefix that matches the `git blame` output
- Author name visible and matches git blame

---

## RT-12: Diff Mode Enter and Exit

**Steps:**
```bash
# Navigate to a file
curl "http://localhost:9222/navigate?url=http://localhost:5173/browse/<repo>/<file>?branch=<branch>"
curl "http://localhost:9222/wait?selector=table&timeout=5000"
# Enter diff mode
curl "http://localhost:9222/click?selector=[aria-label*='Compare']"
curl "http://localhost:9222/url"
# Exit diff mode
curl "http://localhost:9222/click?selector=[aria-label*='Exit compare']"
curl "http://localhost:9222/url"
```

**Pass criteria:**
- After compare click: URL contains `diff=true`
- After exit click: URL no longer contains `diff=true`

---

## RT-12a: Diff Colors Follow Temporal Order

Verify that diff colors are always correct regardless of which commit is selected on which side:
additions (newer) are green, deletions (older) are red/pink, not inverted.

**Steps:**
```bash
# DISCOVER: Find a file with at least 2 versions (different content_hash)
# Response shape: {"path":..., "repository_name":..., "versions":[{"commit_hash","short_hash","commit_date",...}]}
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/files/history?repo=<repo>&path=<file>&branch=<branch>' | python3 -c '
import sys, json
versions = json.load(sys.stdin)[\"versions\"]
print(f\"Versions: {len(versions)}\")
for v in versions[:3]:
    print(f\"  commit={v[\"commit_hash\"][:8]} date={v.get(\"commit_date\",\"?\")}\")
'"
# DISCOVER: Ground truth for the delta, so the colour counts can be checked against git
docker exec inxr2-dev bash -c "git -C /repos/test-repos/<repo> diff --numstat <older_commit> <newer_commit> -- <file>"
#   -> "<added>  <removed>  <file>"   going older -> newer

# NAVIGATE: Both orientations must be exercised.
#   Case A - older on the left  (the orientation the UI produces by default)
curl -G "http://localhost:9222/navigate" --data-urlencode \
  "url=http://host.docker.internal:5173/browse/<repo>/<file>?commit=<newer_commit>&branch=<branch>&diff=<older_commit>"
curl "http://localhost:9222/wait?selector=table&timeout=12000"
# VERIFY: count row background colours (they are emotion classes, NOT inline styles)
curl -G "http://localhost:9222/eval" --data-urlencode \
  'script=JSON.stringify([...document.querySelectorAll("tr")].map(r=>getComputedStyle(r).backgroundColor).reduce((a,c)=>{if(c!=="rgba(0, 0, 0, 0)")a[c]=(a[c]||0)+1;return a},{}))'
curl "http://localhost:9222/screenshot/save?path=.tmp/rt-12a-normal-older-left.png"

#   Case B - newer on the left (commit/diff swapped)
curl -G "http://localhost:9222/navigate" --data-urlencode \
  "url=http://host.docker.internal:5173/browse/<repo>/<file>?commit=<older_commit>&branch=<branch>&diff=<newer_commit>"
curl "http://localhost:9222/wait?selector=table&timeout=12000"
# same eval + screenshot to .tmp/rt-12a-inverted-newer-left.png

# VERIFY: temporal chips are present on the panel headers in both cases
curl -G "http://localhost:9222/eval" --data-urlencode \
  'script=JSON.stringify([...document.querySelectorAll(".MuiChip-root")].map(e=>e.textContent.trim()))'
```

> ⚠️ **`diff` requires BOTH `commit=` and `branch=` in the URL (issue #522).** The older form
> `?branch=<branch>&diff=<commit>` is silently rewritten to `?branch=<branch>&commit=<head>` — the
> `diff` param is dropped during branch→commit resolution and diff mode never engages.

**Pass criteria:**
- Lines present only in the newer version have green/addition background
- Lines present only in the older version have red/pink/deletion background
- Green/red row counts match `git diff --numstat <older> <newer>`
- Colors are correct regardless of which side (left/right) each commit appears on
- `older` / `newer` chips appear on the panel headers, and a "Swap panels" control is available

> 🐞 **Known failure (issue #520):** the third criterion currently fails. Colouring is *positional*
> (left = red, right = green), so Case B inverts: the newer-only lines render red and the
> older-only lines render green. The `older`/`newer` chips and swap button from PR #201 are
> present and correct — only the colours are positional. Until #520 is resolved, Case A passing
> and Case B inverting is the **expected observed state**; record it rather than re-investigating.

---

## RT-12b: Diff Version Selectors Show All Indexed Commits

Verify that diff mode version selectors show all commits where the file's content changed,
going back to the earliest indexed commit.

**Steps:**
```bash
# DISCOVER: Get file history from API
# Response shape: {"path":..., "versions":[{"commit_hash","short_hash","commit_date",...}]}
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/files/history?repo=<repo>&path=<file>&branch=<branch>' | python3 -c '
import sys, json
versions = json.load(sys.stdin)[\"versions\"]
print(f\"Total versions: {len(versions)}\")
if versions:
    print(f\"Oldest: {versions[-1][\"commit_hash\"][:8]} {versions[-1].get(\"commit_date\",\"?\")}\")
    print(f\"Newest: {versions[0][\"commit_hash\"][:8]} {versions[0].get(\"commit_date\",\"?\")}\")
'"
# NAVIGATE: Enter diff mode (needs BOTH commit= and branch=, see #522 note in RT-12a)
curl -G "http://localhost:9222/navigate" --data-urlencode \
  "url=http://host.docker.internal:5173/browse/<repo>/<file>?commit=<head_commit>&branch=<branch>&diff=<older_commit>"
curl "http://localhost:9222/wait?selector=table&timeout=12000"

# VERIFY: open the version selector and list its options.
# MUI Select does NOT open on a programmatic .click() — dispatch a real mousedown.
curl -G "http://localhost:9222/eval" --data-urlencode \
  'script=(()=>{const t=[...document.querySelectorAll(".MuiSelect-select")].find(e=>/UTC/.test(e.textContent));if(!t)return "notfound";t.dispatchEvent(new MouseEvent("mousedown",{bubbles:true}));return "opened"})()'
curl -G "http://localhost:9222/eval" --data-urlencode \
  'script=JSON.stringify([...document.querySelectorAll(".MuiMenuItem-root, [role=option]")].map(e=>e.textContent.trim().replace(/\s+/g," ")))'
```

**Pass criteria:**
- Version selectors include commits spanning the full range (from oldest to newest indexed)
- Every distinct file version returned by `/api/files/history` appears among the options
- The file's own versions appear at the top of the list, newest first, with HEAD marked

**Note — the selector lists all branch commits, not just the file's versions.** This is by design:
`frontend/src/components/VersionSelector/VersionSelector.tsx` fetches up to **500** branch commits
and separately marks the ones that modified the file (`fileChangeHashes` → edit icon), so you can
diff against any commit. So "number of options == number of file versions" is **not** a valid
check — the options are a superset. Verify containment instead.

---

## RT-13: Search Returns Results That Exist in Git

**Steps:**
```bash
# DISCOVER: Pick a distinctive word from a real source file
docker exec inxr2-dev bash -c "grep -rh 'class \|def \|function ' /repos/test-repos/<repo>/ --include='*.py' --include='*.ts' | head -1"
# Extract a word from that line to use as search term
# NAVIGATE
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/search"
# NOTE: the FIRST <input> on the search page is the repository-filter autocomplete
# (placeholder "Repository..."), NOT the query box. selector=input fills the wrong field and the
# search never runs. Target the query box explicitly, then press Enter.
curl -G "http://localhost:9222/fill" \
  --data-urlencode "selector=input[placeholder='Enter search query...']" \
  --data-urlencode "value=<discovered_word>"
curl -G "http://localhost:9222/keyboard" --data-urlencode "key=Enter"
# Search results render as .MuiListItem-root rows (NOT .MuiListItemButton-root); each row wraps a
# clickable inner <button>. Match the row with .MuiListItem-root; click the inner button to navigate.
curl "http://localhost:9222/wait?selector=.MuiListItem-root&timeout=10000"
# VERIFY
curl "http://localhost:9222/elements?selector=.MuiListItem-root&limit=5"
curl -G "http://localhost:9222/eval" --data-urlencode \
  'script=JSON.stringify((document.body.innerText.match(/Found \d+ results|No results found/)||["?"])[0])'
```

Navigating straight to `/search?query=<term>` also runs the search and is fine for the
URL-driven tests (RT-15, RT-16, RT-16a); RT-13 specifically exercises the input box.

**Pass criteria:**
- At least 1 search result returned, and the "Found N results" header appears
- Result file paths exist in the repository (verify via `git ls-files`)

---

## RT-14: Search Result Click Navigates to Correct Location

**Steps:**
```bash
# (Continuing from RT-13 with results visible)
# Note the file path and line number shown in the first result
curl "http://localhost:9222/text?selector=.MuiListItem-root"
# Click it — each result is a .MuiListItem-root containing a clickable inner <button>
curl "http://localhost:9222/click?selector=.MuiListItem-root button"
curl "http://localhost:9222/url"
```

**Pass criteria:**
- URL changes to `/browse/<repo>/<path>` matching the result that was clicked
- Code viewer loads the correct file

---

## RT-15: Search — Regex Mode

**Steps:**
```bash
# DISCOVER: Find a function pattern in git
docker exec inxr2-dev bash -c "grep -rh 'def [a-z_]*(' /repos/test-repos/<repo>/ --include='*.py' | head -1"
# Use the function name as a regex search.
# ⚠️ Percent-encode regex metacharacters. A raw "+" in a query string decodes to a SPACE, so
#    query=def should_[a-z_]+  arrives as  "def should_[a-z_] "  and matches nothing.
#    Encode as %2B (and note the QA agent needs it double-encoded when passed inside ?url=).
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/search%3Fmode=regex%26query=def%2520should_%255Ba-z_%255D%252B"
curl "http://localhost:9222/wait?selector=.MuiListItem-root&timeout=10000"
curl "http://localhost:9222/elements?selector=.MuiListItem-root&limit=5"
# Cross-check the same pattern against the API — counts should agree
docker exec inxr2-dev bash -c "curl -s -G 'http://localhost:8000/api/search/text' \
  --data-urlencode 'q=<function_pattern>' --data-urlencode 'mode=regex' --data-urlencode 'limit=5' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"total\"])'"
```

**Pass criteria:**
- Results appear matching the regex pattern, and the count agrees with `/api/search/text?mode=regex`
- Result file paths exist in the repository

---

## RT-16: Search — File Mode

**Steps:**
```bash
# DISCOVER: Pick a real filename from git
docker exec inxr2-dev bash -c "git -C /repos/test-repos/<repo> ls-files | head -5"
# Search for that filename
curl "http://localhost:9222/navigate?url=http://localhost:5173/search?mode=file&query=<discovered_filename>"
curl "http://localhost:9222/wait?selector=.MuiListItem-root&timeout=5000"
curl "http://localhost:9222/elements?selector=.MuiListItem-root&limit=10"
```

**Pass criteria:**
- File results include the discovered filename

---

## RT-16a: Search — Extensionless File Filtering

Verify that file search can find extensionless files (e.g., `Makefile`, `Dockerfile`,
`Jenkinsfile`) and that extension-based filtering works correctly for them.

**Steps:**
```bash
# DISCOVER: Find extensionless files in the repo
docker exec inxr2-dev bash -c "git -C /repos/test-repos/<repo> ls-files | grep -v '\.' | head -5"
# Search for an extensionless file
curl "http://localhost:9222/navigate?url=http://localhost:5173/search?mode=file&query=<extensionless_file>"
curl "http://localhost:9222/wait?selector=.MuiListItem-root&timeout=5000"
curl "http://localhost:9222/elements?selector=.MuiListItem-root&limit=10"
```

**Pass criteria:**
- Extensionless files (Makefile, Dockerfile, etc.) appear in file search results
- Clicking an extensionless file result navigates to the correct file in the code viewer

---

## RT-17: History Page Matches Git Log

**Steps:**
```bash
# DISCOVER: Get recent commits from git
docker exec inxr2-dev git -C /repos/test-repos/<repo> log --oneline -5
# NAVIGATE
curl "http://localhost:9222/navigate?url=http://localhost:5173/history?repo=<repo>"
curl "http://localhost:9222/wait?selector=.MuiListItem-root&timeout=5000"
# VERIFY
curl "http://localhost:9222/elements?selector=.MuiListItem-root&limit=10"
curl "http://localhost:9222/text?selector=.MuiListItem-root"
```

**Pass criteria:**
- Commit list visible with multiple items
- Commit hashes shown in UI match those from `git log --oneline`
- Author names and dates are present

---

## RT-18: History — Click Commit Navigates to Browse

**Steps:**
```bash
# (Continuing from RT-17)
# Click first indexed commit. As in RT-14, the row itself is not clickable — the clickable
# element is the inner <button>. Clicking .MuiListItem-root alone does nothing.
curl "http://localhost:9222/click?selector=.MuiListItem-root button"
curl "http://localhost:9222/url"
```

**Pass criteria:**
- URL changes to `/browse/<repo>` with `commit=` parameter
- The commit hash in the URL matches one from the `git log` output in RT-17

---

## RT-19: Tab Navigation Preserves Context

**Steps:**
```bash
curl "http://localhost:9222/navigate?url=http://localhost:5173/browse/<repo>?branch=<branch>"
curl "http://localhost:9222/wait?selector=[role='tab']&timeout=3000"
# Click Search tab
curl "http://localhost:9222/click?selector=[role='tab']:nth-child(2)"
curl "http://localhost:9222/url"
# Click History tab
curl "http://localhost:9222/click?selector=[role='tab']:nth-child(3)"
curl "http://localhost:9222/url"
# Click Browse tab
curl "http://localhost:9222/click?selector=[role='tab']:nth-child(1)"
curl "http://localhost:9222/url"
```

**Pass criteria:**
- Search tab navigates to `/search` with `repo=<repo>` preserved
- History tab navigates to `/history` with `repo=<repo>` preserved
- Browse tab navigates back to `/browse/<repo>`

---

## RT-20: Branch Selector Shows Indexed Branches

**Steps:**
```bash
# DISCOVER: local branches (what the indexer can actually resolve) vs all refs
docker exec inxr2-dev git -C /repos/test-repos/inxr2 branch --format='%(refname:short)'
docker exec inxr2-dev git -C /repos/test-repos/inxr2 branch -a --format='%(refname:short)'
# DISCOVER: which branches the API considers INDEXED (commit_count > 0)
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/repositories/by-name/inxr2/branches' | python3 -c '
import sys, json
bs = json.load(sys.stdin)[\"branches\"]
print(\"indexed:\", [(b[\"name\"], b[\"commit_count\"]) for b in bs if b[\"commit_count\"] > 0])
print(\"unindexed:\", [b[\"name\"] for b in bs if b[\"commit_count\"] == 0][:5])
'"
# NAVIGATE
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/browse/inxr2?branch=main"
curl "http://localhost:9222/wait?selector=.MuiSelect-select&timeout=8000"
curl "http://localhost:9222/elements?selector=.MuiSelect-select&limit=5"
```

**Pass criteria:**
- Branch selector is present and shows the current branch name
- Every branch reported as **indexed** by the API is selectable

**Note — expect one indexed branch per repo in the default run.** `config.yaml` declares a second
branch only for `multidockerdevcontainer` (`feature/oidc-authentication`), and that branch is
skipped by design: non-primary branches with no commits inside the `--days` window are skipped by
`src/inxr2/cli.py` (it prints `Skipped: No commits within last N days`). So the selector legitimately
shows a single branch. The `inxr2` test repo also carries several remote-only `dependabot/*` refs
which have no local branch and are correctly reported as unindexed — do not expect them in the
selector. To exercise a genuinely multi-branch selector, index with a wider `--days` window.

---

## RT-21: URL State Preserved on Reload

**Steps:**
```bash
# DISCOVER: Pick a file and line number
# NAVIGATE with specific URL state
curl "http://localhost:9222/navigate?url=http://localhost:5173/browse/<repo>/<file>?branch=<branch>&line=10"
curl "http://localhost:9222/wait?selector=table&timeout=5000"
# Reload the same URL
curl "http://localhost:9222/navigate?url=http://localhost:5173/browse/<repo>/<file>?branch=<branch>&line=10"
curl "http://localhost:9222/url"
```

**Pass criteria:**
- URL retains `branch=` and `line=10` parameters after reload
- Code viewer loaded with the correct file

---

## RT-22: Theme Toggle

**Steps:**
```bash
# The theme toggle lives on browse/inner pages (NOT the home page) and has aria-label
# "Switch to dark mode" / "Switch to light mode" (DarkModeIcon/LightModeIcon).
# Match it with [aria-label*='mode'] — this works in both theme states and avoids the home-page
# grid/list view toggle, which is the only thing [aria-label*='Switch to'] matches on home.
curl "http://localhost:9222/navigate?url=http://localhost:5173/browse/<repo>/<file>?branch=<branch>"
curl "http://localhost:9222/wait?selector=table&timeout=8000"
# Get initial background color
curl "http://localhost:9222/eval?script=getComputedStyle(document.body).backgroundColor"
# Toggle theme
curl "http://localhost:9222/click?selector=[aria-label*='mode']"
# Get new background color
curl "http://localhost:9222/eval?script=getComputedStyle(document.body).backgroundColor"
# Toggle back
curl "http://localhost:9222/click?selector=[aria-label*='mode']"
curl "http://localhost:9222/eval?script=getComputedStyle(document.body).backgroundColor"
```

**Pass criteria:**
- Background color changes after first toggle (different from initial)
- Background color reverts after second toggle (matches initial)

---

## RT-22a: Diff Colors Render Correctly in Both Themes

Verify that diff addition/deletion colors are visible and distinguishable in both light and dark themes.

**Steps:**
```bash
# Navigate to a file in diff mode (use a file with known changes)
curl "http://localhost:9222/navigate?url=http://localhost:5173/browse/<repo>/<file>?branch=<branch>&diff=<older_commit>"
curl "http://localhost:9222/wait?selector=table&timeout=5000"
# Screenshot in current theme
curl "http://localhost:9222/screenshot/save?path=/tmp/rt-22a-diff-theme1.png"
# Get diff cell background colors
curl "http://localhost:9222/eval?script=JSON.stringify([...document.querySelectorAll('td[style]')].slice(0,4).map(e=>e.style.backgroundColor))"
# Toggle theme
curl "http://localhost:9222/click?selector=[aria-label*='mode']"
# Screenshot in other theme
curl "http://localhost:9222/screenshot/save?path=/tmp/rt-22a-diff-theme2.png"
# Get diff cell background colors in other theme
curl "http://localhost:9222/eval?script=JSON.stringify([...document.querySelectorAll('td[style]')].slice(0,4).map(e=>e.style.backgroundColor))"
# Toggle back
curl "http://localhost:9222/click?selector=[aria-label*='mode']"
```

**Pass criteria:**
- Diff addition/deletion colors are visible in both themes
- Colors are different between light and dark themes (adapted to theme)
- Addition (green) and deletion (red/pink) colors are distinguishable in both themes

---

## RT-23: Markdown Rendering Matches File Content

**Steps:**
```bash
# DISCOVER: Find a markdown file and extract its first heading
docker exec inxr2-dev bash -c "git -C /repos/test-repos/<repo> ls-files '*.md' | head -1"
docker exec inxr2-dev grep -m1 '^#' /repos/test-repos/<repo>/<md_file>
# NAVIGATE
curl "http://localhost:9222/navigate?url=http://localhost:5173/browse/<repo>/<md_file>?branch=<branch>"
curl "http://localhost:9222/wait?selector=h1,h2,h3&timeout=5000"
# VERIFY
curl "http://localhost:9222/elements?selector=h1,h2,h3&limit=5"
curl "http://localhost:9222/text?selector=h1,h2,h3"
```

**Pass criteria:**
- HTML heading element present (h1/h2/h3)
- Heading text matches the `# Heading` content from the markdown file (without the `#` prefix)

---

## RT-24: Logical View Loads Symbol Tree

**Steps:**
```bash
# DISCOVER: Get a repo with indexed symbols
REPO=$(docker exec inxr2-dev bash -c "curl -s http://localhost:8000/api/repositories | python3 -c 'import json,sys; repos=json.load(sys.stdin); print(repos[0][\"name\"])'")
# Get the symbol tree via API to know what to expect
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/repositories/by-name/$REPO/symbol-tree?limit=10' | python3 -m json.tool | head -30"
# NAVIGATE
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/logical-view?repo=$REPO"
curl "http://localhost:9222/wait?selector=[class*=tree],[class*=Tree]&timeout=10000"
# VERIFY: Check that files appear in the tree
curl "http://localhost:9222/elements?selector=[class*=file],[class*=File]&limit=10"
```

**Pass criteria:**
- Logical View page loads without errors
- File entries appear in the tree matching API response
- No "Coming Soon" placeholder visible

---

## RT-25: Logical View Expand File Shows Symbols

**Steps:**
```bash
# DISCOVER: Get symbols for a specific file from the API
REPO=$(docker exec inxr2-dev bash -c "curl -s http://localhost:8000/api/repositories | python3 -c 'import json,sys; repos=json.load(sys.stdin); print(repos[0][\"name\"])'")
FILE_DATA=$(docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/repositories/by-name/$REPO/symbol-tree?limit=5' | python3 -c 'import json,sys; d=json.load(sys.stdin); files=d.get(\"files\",[]); print(files[0][\"path\"] if files else \"\")'")
# NAVIGATE to logical view
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/logical-view?repo=$REPO"
# Container symbols (the file / top-level nodes) render as .MuiListItemButton-root rows
curl "http://localhost:9222/wait?selector=.MuiListItemButton-root&timeout=10000"
# VERIFY: Click a container to expand it; its leaf symbols render inside a nested .MuiCollapse-root
curl "http://localhost:9222/click?selector=.MuiListItemButton-root"
curl "http://localhost:9222/wait?timeout=2000"
# Leaf symbols are <button> elements inside the expanded .MuiCollapse-root
curl "http://localhost:9222/elements?selector=.MuiCollapse-root button&limit=10"
```

**Pass criteria:**
- Expanding a file shows its symbols (classes, functions, etc.)
- Symbol names match what the API returns for that file

---

## RT-26: Logical View Symbol Click Navigates to Browse

**Steps:**
```bash
# NAVIGATE to logical view with a repo
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/logical-view?repo=$REPO"
curl "http://localhost:9222/wait?selector=.MuiListItemButton-root&timeout=10000"
# Expand a container symbol (.MuiListItemButton-root), then click a leaf symbol
curl "http://localhost:9222/click?selector=.MuiListItemButton-root"
curl "http://localhost:9222/wait?timeout=2000"
# The navigating click is on the leaf symbol's <button> inside the nested .MuiCollapse-root
curl "http://localhost:9222/click?selector=.MuiCollapse-root button"
curl "http://localhost:9222/wait?timeout=3000"
# VERIFY: URL changed to /browse with file path and line
curl "http://localhost:9222/url"
```

**Pass criteria:**
- URL now contains `/browse/` with a file path
- URL contains a `line=` parameter pointing to the symbol's definition line
- Browse page displays the correct file content

---

## RT-27: Logical View Language and Kind Filters

**Steps:**
```bash
# NAVIGATE to logical view
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/logical-view?repo=$REPO"
curl "http://localhost:9222/wait?selector=[class*=tree],[class*=Tree]&timeout=10000"
# Count initial items
curl "http://localhost:9222/eval?script=document.querySelectorAll('[class*=file],[class*=File]').length"
# Apply a language filter (e.g., Python)
curl "http://localhost:9222/click?selector=[class*=language],[class*=Language]"
curl "http://localhost:9222/wait?timeout=1000"
# Count filtered items
curl "http://localhost:9222/eval?script=document.querySelectorAll('[class*=file],[class*=File]').length"
```

**Pass criteria:**
- Applying a language filter reduces the number of visible files
- Only files of the selected language remain visible

---

## RT-28: Dependencies Tab Shows Packages

**Steps:**
```bash
# DISCOVER: Get dependencies from API
REPO=$(docker exec inxr2-dev bash -c "curl -s http://localhost:8000/api/repositories | python3 -c 'import json,sys; repos=json.load(sys.stdin); print(repos[0][\"name\"])'")
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/repositories/by-name/$REPO/dependencies' | python3 -c 'import json,sys; d=json.load(sys.stdin); print(f\"Total: {d.get(\"total\",0)} dependencies\")'"
# NAVIGATE
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/dependencies?repo=$REPO"
curl "http://localhost:9222/wait?selector=[class*=dependency],[class*=Dependency],[class*=package],[class*=Package]&timeout=10000"
# VERIFY
curl "http://localhost:9222/elements?selector=[class*=dependency],[class*=Dependency],[class*=package],[class*=Package]&limit=10"
```

**Pass criteria:**
- Dependencies page loads without errors
- Package names are visible matching API response
- No "Coming Soon" placeholder visible

---

## RT-29: Dependencies Tab Respects Commit Picker

**Steps:**
```bash
# DISCOVER: Get two different commits
REPO=$(docker exec inxr2-dev bash -c "curl -s http://localhost:8000/api/repositories | python3 -c 'import json,sys; repos=json.load(sys.stdin); print(repos[0][\"name\"])'")
# Commits come from /api/commits?repo=<name> (response: {"commits":[{hash, short_hash, ...}]}).
# NOTE: /api/repositories/by-name/<repo>/commits does NOT exist — it falls through to the SPA HTML.
COMMITS=$(docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/commits?repo=$REPO&limit=2' | python3 -c 'import json,sys; cs=json.load(sys.stdin)[\"commits\"]; print(cs[0][\"hash\"][:7],cs[1][\"hash\"][:7])'")
# NAVIGATE to dependencies with specific commit
COMMIT1=$(echo $COMMITS | cut -d' ' -f1)
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/dependencies?repo=$REPO&commit=$COMMIT1"
curl "http://localhost:9222/wait?selector=[class*=dependency],[class*=Dependency],[class*=package],[class*=Package]&timeout=10000"
# VERIFY: Page loaded with commit context
curl "http://localhost:9222/url"
```

**Pass criteria:**
- Dependencies page loads with the specified commit
- URL contains the commit parameter
- Dependency data reflects the selected commit

---

## RT-30: Dependencies Empty State When Not Indexed

**Steps:**
```bash
# NAVIGATE to dependencies for a repo that might not have deps indexed
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/dependencies?repo=nonexistent-repo"
curl "http://localhost:9222/wait?timeout=5000"
# VERIFY: Empty state message shown
curl "http://localhost:9222/text?selector=[class*=empty],[class*=Empty],p"
```

**Pass criteria:**
- An appropriate empty state message is displayed
- No errors or crashes

---

## RT-31: References Panel "View in Logical View" Link

**Steps:**
```bash
# NAVIGATE to browse and click a symbol to open references panel
REPO=$(docker exec inxr2-dev bash -c "curl -s http://localhost:8000/api/repositories | python3 -c 'import json,sys; repos=json.load(sys.stdin); print(repos[0][\"name\"])'")
# Find a file with symbols
FILE=$(docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/repositories/by-name/$REPO/symbol-tree?limit=1' | python3 -c 'import json,sys; d=json.load(sys.stdin); files=d.get(\"files\",[]); print(files[0][\"path\"] if files else \"\")'")
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/browse/$REPO/$FILE"
curl "http://localhost:9222/wait?selector=[class*=code],[class*=Code]&timeout=10000"
# Click a symbol in the code to open references panel
curl "http://localhost:9222/click?selector=[data-symbol],[class*=symbol-link]:first-child"
curl "http://localhost:9222/wait?selector=[class*=reference],[class*=Reference]&timeout=5000"
# Look for "View in Logical View" link
curl "http://localhost:9222/elements?selector=a[href*=logical-view],button:has-text('Logical View')"
# Click the link
curl "http://localhost:9222/click?selector=a[href*=logical-view],button:has-text('Logical View')"
curl "http://localhost:9222/wait?timeout=3000"
# VERIFY: Navigated to logical view
curl "http://localhost:9222/url"
```

**Pass criteria:**
- References panel contains a link/button to view the symbol in Logical View
- Clicking it navigates to `/logical-view` with the correct repository context
- The symbol is visible or highlighted in the logical view

---

## RT-32: Browse Rename Banner — File Shows Rename Context at Old Commit

Verify that when a user browses a file at a commit where the file existed under a different path
(i.e., the file was later renamed), the UI shows an informational banner pointing to the new path.
Also verify the reverse: browsing the new path at an old commit shows the old path.

**Steps:**
```bash
# DISCOVER: Find a rename that was ACTUALLY INDEXED, across all repos.
#
# ⚠️ Do NOT assume the rename lives in `inxr2`. Which renames land in the index depends entirely on
# what the sliding `--days` window happened to cover; in the 2026-07-25 run inxr2's 8 indexed
# commits contained zero renames, while `interview-technical-challenge-2` and `git` had one each.
# There is no "list all renames" endpoint (the rename APIs are keyed by commit or by path), so
# query the table directly to find the candidates:
docker exec inxr2-dev bash -c 'PGPASSWORD=inxr2_dev_password psql -h 127.0.0.1 -U inxr2_user -d inxr2_dev -tAc "
  select r.name, c.commit_hash, fr.old_path, fr.new_path, fr.similarity
  from file_renames fr
  join commits c      on c.id = fr.commit_id
  join repositories r on r.id = c.repository_id
  order by fr.similarity"'

# Pick one and set REPO / RENAME_COMMIT / old_path / new_path from that row, then confirm via the
# API. Response shape: {"renames":[{old_path, new_path, similarity, commit_id, commit_hash}], "total":N}
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/renames/by-commit?repo=$REPO&commit=$RENAME_COMMIT' | python3 -m json.tool"

# (Optional) Confirm the resolve-path endpoint backs the banner: browsing <new_path> at the parent
# commit should report found=false with resolved_path=<old_path>:
PARENT=$(docker exec inxr2-dev bash -c "git -C /repos/test-repos/$REPO rev-parse ${RENAME_COMMIT}^")
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/renames/resolve-path?repo=$REPO&path=<new_path>&commit=$PARENT' | python3 -m json.tool"

# NAVIGATE: Browse the new_path at the commit just BEFORE the rename
# (the commit where old_path still existed)
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/browse/$REPO/<new_path>?commit=${PARENT}"
curl "http://localhost:9222/wait?timeout=5000"

# VERIFY: Rename banner is visible
curl "http://localhost:9222/text?selector=body"
```

**Pass criteria:**
- When browsing the new path at a commit where it didn't exist yet, a banner appears indicating
  the file was at a different path at that time, with a link to the old path
- The link in the banner navigates to the old path at the same commit
- The browse page does NOT show a generic "file not found" dead end

---

## RT-33: Diff Viewer Rename Following

Verify that when diffing a file across a rename boundary (comparing a commit before the rename
to a commit after), the diff viewer identifies both paths and shows the diff correctly.

**Steps:**
```bash
# DISCOVER: Reuse the SQL query from RT-32, which is already ordered by similarity ascending.
# Prefer a row with similarity < 100 — a rename that ALSO changed content, so the diff has an
# add/delete delta to render. Pure R100 renames have none (see note below).
#
# In the 2026-07-25 run the best candidate was:
#   repo       = interview-technical-challenge-2
#   commit     = 7d91f46900d6ca680ccc90dbe40ddcaf88e6028c   (similarity 92)
#   old_path   = scripts/parking-repl.py
#   new_path   = src/myapp/scripts/parking-repl.py
# Do not hardcode these — re-run the query, they move with the --days window.

# Get commit just before the rename, and the ground-truth delta
PARENT=$(docker exec inxr2-dev bash -c "git -C /repos/test-repos/$REPO rev-parse ${RENAME_COMMIT}^")
docker exec inxr2-dev bash -c "git -C /repos/test-repos/$REPO diff --numstat -M $PARENT $RENAME_COMMIT -- <old_path> <new_path>"
#   -> "<added>  <removed>  {old => new}/path"

# NAVIGATE: Open new_path at rename_commit in diff mode, comparing against parent.
# Needs BOTH commit= and branch= (see the #522 note in RT-12a).
BRANCH=$(docker exec inxr2-dev bash -c "git -C /repos/test-repos/$REPO rev-parse --abbrev-ref HEAD")
curl -G "http://localhost:9222/navigate" --data-urlencode \
  "url=http://host.docker.internal:5173/browse/$REPO/<new_path>?commit=$RENAME_COMMIT&branch=$BRANCH&diff=$PARENT"
curl "http://localhost:9222/wait?selector=table&timeout=12000"

# VERIFY: green/red row counts match the git delta
curl -G "http://localhost:9222/eval" --data-urlencode \
  'script=JSON.stringify([...document.querySelectorAll("tr")].map(r=>getComputedStyle(r).backgroundColor).reduce((a,c)=>{if(c!=="rgba(0, 0, 0, 0)")a[c]=(a[c]||0)+1;return a},{}))'
# VERIFY: look for the old path as chrome (not just inside the file's own content)
curl "http://localhost:9222/text?selector=body"
curl "http://localhost:9222/screenshot/save?path=.tmp/rt-33-diff-rename.png"
```

**Pass criteria:**
- Diff viewer loads without error even though the file had a different path on the left side
- Diff content renders correctly — green/red row counts match `git diff --numstat -M`
  (**when the rename also changed content**)
- The diff header or toolbar shows both the old path and the new path

> 🐞 **Known failure (issue #524):** the third criterion currently fails — only the post-rename path
> is displayed, and the left panel is labelled by commit hash alone. When grepping the page for the
> old path, note that matches inside the diffed file's own content don't count; the old path must
> appear as chrome.

**Note — pure renames have no diff delta:** if the only renames in the indexed window are R100
(100% similarity, pure move with no content change), there is no add/delete delta to show — the
delta criterion **cannot be exercised** and is not a failure. Prefer a rename with similarity < 100;
when none exists, verify only that rename-following works (left side resolves to the old path, diff
loads without error) and record that the rename was R100. The 2026-05-31 runs could only find R100
renames; 2026-07-25 was the first run to confirm the delta path (17 added / 4 removed, matching git).

---

## RT-34: Mermaid Diagrams Render as SVG

Verify that markdown files containing ` ```mermaid ` code fences render as SVG diagrams rather than raw text. Regression test for PR #383.

**Steps:**
```bash
# DISCOVER: Find a markdown file in the inxr2 repo that contains a mermaid fence
REPO="inxr2"
MD_FILE=$(docker exec inxr2-dev bash -c "git -C /repos/test-repos/$REPO ls-files '*.md' | xargs grep -rl '\`\`\`mermaid' | head -1")
echo "Found mermaid file: $MD_FILE"
BRANCH=$(docker exec inxr2-dev bash -c "git -C /repos/test-repos/$REPO rev-parse --abbrev-ref HEAD")

# NAVIGATE: Open the markdown file in the browser
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/browse/$REPO/$MD_FILE?branch=$BRANCH"
curl "http://localhost:9222/wait?selector=svg&timeout=8000"

# VERIFY: An SVG element is present (mermaid rendered)
curl "http://localhost:9222/elements?selector=svg&limit=3"
# Optionally screenshot
curl "http://localhost:9222/screenshot/save?path=.tmp/rt-34-mermaid.png"
```

**Pass criteria:**
- At least one `<svg>` element is present in the page (mermaid diagram rendered)
- The page does not display raw mermaid source text (no `graph TD` or `sequenceDiagram` visible as plain text)
- No JavaScript console errors related to mermaid (check via QA agent text output)

---

# Phase 3: MCP Server Regression

Verify that the MCP server correctly exposes INXR2 code intelligence via its tool handlers.
**All verifications cross-reference against the INXR2 API — no hardcoded expectations.**

## Setup

```bash
# Ensure backend is running (MCP server calls the API)
docker exec -d inxr2-dev inxr2 serve --reload

# Install MCP server dependencies (if not already installed)
docker exec inxr2-dev pip install -e "/workspace/mcp-server[dev]"

# MCP-21 goes over the SSE transport, so the MCP server must be listening on :3000.
# ⚠️ It does NOT always auto-start with the container despite mcp-server/README.md (issue #525).
docker exec inxr2-dev bash -c "ps aux | grep -c '[m]cp'"
curl -s -o /dev/null -w '%{http_code}\n' --max-time 3 http://localhost:3000/sse
# If not running, start it:
docker exec -d -w /workspace/mcp-server inxr2-dev bash -c \
  "MCP_TRANSPORT=sse MCP_PORT=3000 INXR2_API_URL=http://localhost:8000 python -m src.server > /tmp/mcp.log 2>&1"
```

Note: except for MCP-21, MCP tool tests are run by invoking the tool handlers directly with the
real HTTP client, not through MCP protocol. This tests the full path:
tool handler -> httpx -> INXR2 API -> PostgreSQL.

**Running the handlers directly requires `PYTHONPATH`** — `from src.client import ...` fails
otherwise, even with `-w /workspace/mcp-server`:

```bash
docker exec -w /workspace/mcp-server inxr2-dev bash -c "PYTHONPATH=/workspace/mcp-server python3 <<'PY'
...
PY"
```

---

## MCP-01: List Repositories Returns All Indexed Repos

**Steps:**
```bash
# DISCOVER: Count repos from API
docker exec inxr2-dev bash -c "curl -s http://localhost:8000/api/repositories | python3 -c 'import sys,json; data=json.load(sys.stdin); print(len(data)); [print(r[\"name\"]) for r in data]'"
# VERIFY: MCP tool returns same repos
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import list_repositories
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    print(await list_repositories.handle(client, {}))
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- MCP output lists the same number of repositories as the API
- Each repo name from the API appears in the MCP output
- Each repo shows at least one indexed branch

---

## MCP-02: List Repositories Detail Shows Indexed Branches

**Steps:**
```bash
# DISCOVER: Get branches from the API.
# ⚠️ The route is /api/repositories/by-name/{name}/branches. There is NO
#    /api/repositories/{id}/branches — that path falls through to the SPA catch-all and returns
#    HTTP 200 with an HTML body, which fails JSON parsing in a confusing way.
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/repositories/by-name/inxr2/branches' | python3 -c '
import sys, json
branches = json.load(sys.stdin)[\"branches\"]
indexed = [b for b in branches if b[\"commit_count\"] > 0]
print(f\"Indexed: {len(indexed)}\")
for b in indexed:
    name, cc = b[\"name\"], b[\"commit_count\"]
    print(f\"  {name} ({cc} commits)\")
'"
# VERIFY: MCP detail matches
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import list_repositories
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    print(await list_repositories.handle(client, {'repository': 'inxr2'}))
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- MCP output shows the same indexed branches as the API (unindexed branches filtered out)
- Commit counts match
- Commit hash prefixes match

---

## MCP-03: Search Symbols Returns Matching Definitions

**Steps:**
```bash
# DISCOVER: Pick a symbol name that exists in the API
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/symbols?q=Repository&limit=3' | python3 -c '
import sys, json
items = json.load(sys.stdin)[\"items\"]
for s in items:
    n, k, fp, sl = s[\"name\"], s[\"kind\"], s.get(\"file_path\",\"?\"), s.get(\"start_line\",\"?\")
    print(f\"{n} [{k}] at {fp}:{sl}\")
'"
# VERIFY: MCP tool returns same symbols
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_symbols
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    print(await search_symbols.handle(client, {'query': 'Repository', 'limit': 3}))
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- MCP output contains the same symbol names as the API
- File paths and line numbers match
- Symbol kinds (class, function, etc.) match

---

## MCP-04: Search Symbols Filters by Kind

**Steps:**
```bash
# VERIFY: Search with kind=class filter
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_symbols
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await search_symbols.handle(client, {'query': 'Repository', 'kind': 'class', 'limit': 10})
    print(result)
    await client.close()
asyncio.run(main())
"

# VERIFY: kind=interface expands to include Swift protocols (KIND_ALIASES regression — bug #385)
# DISCOVER: Confirm the repo has protocol-kinded symbols via API.
# ⚠️ Use repository_id — /api/symbols ignores repository_name (see the warning in IX-04).
# Resolve it with: curl -s .../api/repositories | python3 -c '...{r["name"]: r["id"]}...'
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/symbols?q=&repository_id=<travelbuddy_id>&kind=protocol&limit=3' | python3 -c '
import sys, json
items = json.load(sys.stdin)[\"items\"]
print(f\"Protocol symbols in travelbuddy: {len(items)}\")
for s in items[:3]:
    print(f\"  {s[\"name\"]} [{s[\"kind\"]}]\")
'"
# VERIFY: MCP kind=interface returns those same protocol symbols
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_symbols
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await search_symbols.handle(client, {'query': '*', 'kind': 'interface', 'repository': 'travelbuddy', 'limit': 10})
    print(result)
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- `kind=class` search: all returned symbols have kind `class`; no functions, methods, or other kinds appear
- `kind=interface` search: output includes Swift `protocol`-kinded symbols from travelbuddy (not just symbols literally named `interface`)
- If the API returns N protocol symbols, the MCP `kind=interface` result includes those same symbol names

---

## MCP-05: Go to Definition Finds Symbol

**Steps:**
```bash
# DISCOVER: Pick a specific symbol name from API
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/symbols/by-name/SearchSymbolsUseCase' | python3 -c '
import sys, json
items = json.load(sys.stdin)[\"items\"]
for s in items:
    n, fp, sl = s[\"name\"], s.get(\"file_path\",\"?\"), s.get(\"start_line\",\"?\")
    print(f\"{n} at {fp}:{sl}\")
'"
# VERIFY: MCP tool returns same definition
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import go_to_definition
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    print(await go_to_definition.handle(client, {'name': 'SearchSymbolsUseCase'}))
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- MCP output includes the correct file path and line number matching the API
- Symbol kind is shown
- If the symbol has a signature or docstring, they are displayed

---

## MCP-06: Find References Returns Cross-Repo Usages

**Steps:**
```bash
# DISCOVER: Get references for a symbol from API
docker exec inxr2-dev bash -c "
SYMBOL_ID=\$(curl -s 'http://localhost:8000/api/symbols?q=SearchSymbolsUseCase&limit=1' | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"items\"][0][\"id\"])')
curl -s \"http://localhost:8000/api/symbols/\$SYMBOL_ID/references?by_name=true&limit=5\" | python3 -c '
import sys, json
data = json.load(sys.stdin)
total = data[\"total\"]
print(f\"Total: {total}\")
for r in data[\"items\"][:5]:
    rt, fp, sl = r[\"reference_type\"], r.get(\"source_file_path\",\"?\"), r.get(\"source_line\",\"?\")
    print(f\"  [{rt}] {fp}:{sl}\")
'
"
# VERIFY: MCP tool returns same references
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import find_references
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    print(await find_references.handle(client, {'name': 'SearchSymbolsUseCase', 'repository': 'inxr2'}))
    await client.close()
asyncio.run(main())
"
```

> ⚠️ **The API's `total` here is the page size, not the true count (issue #523).**
> `/api/symbols/{id}/references` computes `total` *after* applying `limit`, so `limit=5` reports
> `total: 5` even when there are 46 references. Do **not** treat a larger MCP count as a mismatch —
> re-query with `limit=500` to get the real total before comparing.

**Pass criteria:**
- MCP reference count matches the API total **fetched with a limit above the real count**
- Reference types (import, call, usage, type_annotation) are shown
- File paths and line numbers match the API data

---

## MCP-07: Find References Filters by Type

**Steps:**
```bash
# VERIFY: Filter to imports only
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import find_references
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    print(await find_references.handle(client, {'name': 'SearchSymbolsUseCase', 'repository': 'inxr2', 'ref_type': 'import'}))
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- All returned references have type `import`
- No call, usage, or type_annotation references appear

---

## MCP-08: Search Code Returns Matching Content

**Steps:**
```bash
# DISCOVER: Search via API
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/search/text?q=async+def+execute&mode=phrase&limit=3' | python3 -c '
import sys, json
data = json.load(sys.stdin)
total = data[\"total\"]
print(f\"Total: {total}\")
for r in data[\"results\"][:3]:
    rn, fp, sl = r.get(\"repository_name\",\"?\"), r.get(\"file_path\",\"?\"), r.get(\"source_line\",\"?\")
    print(f\"  {rn}:{fp}:{sl}\")
'"
# VERIFY: MCP tool returns same results
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_code
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    print(await search_code.handle(client, {'query': 'async def execute', 'mode': 'phrase', 'limit': 3}))
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- MCP result count matches API total
- File paths and line numbers match
- Content snippets contain the search term

---

## MCP-09: Search Code with Repository Filter

**Steps:**
```bash
# VERIFY: Filtered search only returns results from specified repo
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_code
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    print(await search_code.handle(client, {'query': 'class', 'repository': 'inxr2', 'limit': 5}))
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- All results are from the `inxr2` repository
- No results from other repositories appear

---

## MCP-10: No-Match Queries Return Graceful Messages

**Steps:**
```bash
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio, uuid
from src.client import HttpInxr2Client
from src.tools import search_symbols, go_to_definition, find_references, search_code
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    print('search_symbols:', await search_symbols.handle(client, {'query': 'xyzzy_nonexistent_symbol_42'}))
    print('go_to_definition:', await go_to_definition.handle(client, {'name': 'xyzzy_nonexistent_symbol_42'}))
    print('find_references:', await find_references.handle(client, {'name': 'xyzzy_nonexistent_symbol_42'}))
    print('search_code:', await search_code.handle(client, {'query': uuid.uuid4().hex, 'mode': 'phrase'}))
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- Each tool returns a human-readable "no results" message (not an error or stack trace)
- Messages include the original query term

---

## MCP-11: MCP Unit Tests Pass

**Steps:**
```bash
docker exec -w /workspace/mcp-server inxr2-dev python -m pytest tests/ -q
```

**Pass criteria:**
- All tests pass (154 as of 2026-07-25; the count grows — treat it as a floor, not an equality check)
- No warnings or errors

---

## MCP-12: Browse URLs Point to Correct Code Locations

MCP tool responses include INXR2 frontend browse URLs when `INXR2_FRONTEND_URL` is set.
This test verifies that each URL loads the correct file and highlights the correct line.

**Prerequisites:**
- Backend and frontend running
- QA agent running
- `INXR2_FRONTEND_URL` set when invoking tool handlers

**Steps:**
```bash
# Frontend base URL that the QA agent's BROWSER will navigate to.
# Use host.docker.internal — the same host the rest of Phase 2 uses — so the generated URLs are
# directly clickable from the QA agent without rewriting.
FE_URL="http://host.docker.internal:5173"
QA="http://localhost:9222"

# --- Step 1: DISCOVER — Get browse URLs from all 4 MCP tools ---

# search_symbols: pick a known symbol
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_symbols
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await search_symbols.handle(
        client,
        {'query': 'Repository', 'repository': 'inxr2', 'limit': 1},
        frontend_url='$FE_URL',
    )
    print(result)
    await client.close()
asyncio.run(main())
"
# VERIFY: Output contains a browse URL with repo name, file path, and line number

# go_to_definition: jump to a specific symbol
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import go_to_definition
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await go_to_definition.handle(
        client,
        {'name': 'SearchSymbolsUseCase', 'repository': 'inxr2'},
        frontend_url='$FE_URL',
    )
    print(result)
    await client.close()
asyncio.run(main())
"
# VERIFY: Output contains a URL: line with browse link

# find_references: get references for a symbol
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import find_references
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await find_references.handle(
        client,
        {'name': 'SearchSymbolsUseCase', 'repository': 'inxr2'},
        frontend_url='$FE_URL',
    )
    # Print first few lines (references can be long)
    for line in result.splitlines()[:8]:
        print(line)
    await client.close()
asyncio.run(main())
"
# VERIFY: Each reference entry includes a browse URL

# search_code: full-text search
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_code
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await search_code.handle(
        client,
        {'query': 'cJSON_Parse', 'repository': 'cJSON', 'limit': 1},
        frontend_url='$FE_URL',
    )
    print(result)
    await client.close()
asyncio.run(main())
"
# VERIFY: Output contains a browse URL for the search result

# --- Step 2: NAVIGATE — Open each URL in QA agent browser ---

# Extract the first URL from each tool's output above (manually or via grep).
# For each URL, navigate the QA agent and check that the page loads:

# Example for search_symbols URL:
curl "$QA/navigate?url=<URL_FROM_SEARCH_SYMBOLS>&wait=4000"
# Check page loaded:
curl "$QA/text?selector=body"
# VERIFY: Body text contains the expected symbol/function name from the URL's file

# Repeat for go_to_definition, find_references, and search_code URLs.

# --- Step 3: VERIFY — No URLs without frontend_url ---

docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_symbols
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await search_symbols.handle(
        client,
        {'query': 'Repository', 'repository': 'inxr2', 'limit': 1},
    )
    print(result)
    assert 'http://' not in result, 'URL should not appear without frontend_url'
    print('PASS: No URLs without frontend_url')
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- All 4 tools (search_symbols, go_to_definition, find_references, search_code) include browse URLs in output when `frontend_url` is provided
- URLs follow pattern: `{frontend_url}/browse/{repo}/{path}?line=N`
- Navigating each URL in the QA agent browser loads the correct file with expected content visible
- When `frontend_url` is not provided, no URLs appear in the output
- URLs include `branch` or `commit` query params when those filters are specified

---

## MCP-13: Find Dead Code Returns Unreferenced Symbols

**Steps:**
```bash
# DISCOVER: Pick a repo and find symbols with zero references from the API
REPO="inxr2"
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/symbols?q=.&mode=regex&limit=50&repository_id=1' | python3 -c \"
import sys, json
symbols = json.load(sys.stdin).get('items', [])
print(f'Total symbols found: {len(symbols)}')
for s in symbols[:5]:
    print(f'  [{s.get(\"kind\")}] {s.get(\"name\")} ({s.get(\"file_path\")}:{s.get(\"start_line\")})  id={s[\"id\"]}')
\""

# VERIFY: MCP find_dead_code tool returns unreferenced symbols
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import find_dead_code
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await find_dead_code.handle(client, {'repository': '$REPO', 'limit': 10})
    print(result)
    # Verify output structure. The header reads:
    #   "Dead code in '<repo>': N symbols with no references (showing M)"
    assert 'symbols with no references' in result or 'No unreferenced symbols' in result
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- Tool returns symbols with zero references
- Each symbol entry includes kind, name, file path, and line number
- Output header shows count of unreferenced symbols found
- Results are limited to the requested `limit`
- The tool declares its sampling cap rather than truncating silently — expect a line like
  `Note: scanned 200 of 9021 symbols — results may be incomplete.`

---

## MCP-14: Find Dead Code Filters by Kind

**Steps:**
```bash
# VERIFY: Filter to functions only
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import find_dead_code
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await find_dead_code.handle(client, {'repository': 'inxr2', 'kind': 'function', 'limit': 10})
    print(result)
    # Every symbol line should be [function]
    for line in result.splitlines():
        if line.strip().startswith('['):
            assert '[function]' in line, f'Expected [function] but got: {line}'
    print('PASS: All results are functions')
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- All returned symbols have kind `function`
- No symbols of other kinds (class, method, variable, etc.) appear

---

## MCP-15: Review Helper Shows Blast Radius for a Commit

**Steps:**
```bash
# DISCOVER: Pick a recent commit and get its changed files from git
REPO="inxr2"
docker exec inxr2-dev bash -c "
cd /repos/test-repos/inxr2
COMMIT=\$(git log --oneline -10 | head -1 | awk '{print \$1}')
echo \"Commit: \$COMMIT\"
echo 'Changed files from git:'
git diff-tree --no-commit-id --name-only -r \$COMMIT
echo \"---\"
echo \$COMMIT
" > /tmp/mcp-15-discover.txt
cat /tmp/mcp-15-discover.txt
COMMIT=$(tail -1 /tmp/mcp-15-discover.txt)

# VERIFY: MCP review_helper returns matching changed files
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import review_helper
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await review_helper.handle(client, {'repository': '$REPO', 'commit': '$COMMIT'})
    print(result)
    assert 'Blast radius for commit' in result
    assert 'Changed files:' in result
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- Output shows "Blast radius for commit ..." with the correct commit hash
- Changed files section lists files that match `git diff-tree` output
- Symbols section lists symbols found in changed files
- Downstream references section shows where those symbols are used

---

## MCP-16: Review Helper Changed Files Only (Not All Repo Files)

**Steps:**
```bash
# DISCOVER: Find a commit that changed only 1-3 files
REPO="inxr2"
docker exec inxr2-dev bash -c "
cd /repos/test-repos/inxr2
for HASH in \$(git log --oneline -50 | awk '{print \$1}'); do
  COUNT=\$(git diff-tree --no-commit-id --name-only -r \$HASH | wc -l)
  if [ \$COUNT -ge 1 ] && [ \$COUNT -le 3 ]; then
    echo \"\$HASH \$COUNT\"
    git diff-tree --no-commit-id --name-only -r \$HASH
    break
  fi
done
" > /tmp/mcp-16-discover.txt
cat /tmp/mcp-16-discover.txt
COMMIT=$(head -1 /tmp/mcp-16-discover.txt | awk '{print $1}')
EXPECTED_COUNT=$(head -1 /tmp/mcp-16-discover.txt | awk '{print $2}')

# VERIFY: review_helper returns only changed files, not entire repo
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import review_helper
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await review_helper.handle(client, {'repository': '$REPO', 'commit': '$COMMIT'})
    print(result)
    # Extract 'Changed files: N' count
    for line in result.splitlines():
        if 'Changed files:' in line:
            count = int(line.split(':')[1].strip())
            print(f'Changed files count: {count}')
            assert count <= 5, f'Expected small number of changed files but got {count} — may be returning all repo files'
            break
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- Changed files count matches git's `diff-tree` output (1-3 files)
- Tool does NOT return hundreds of files (which would indicate the `changed_only` bug)

---

## MCP-17: Staleness Warning Appears When Index Is Behind

**Steps:**
```bash
# DISCOVER: Check if any repo has commits newer than the last indexed commit
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.staleness import check_staleness
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    staleness = await check_staleness(client, 'inxr2')
    print(f'Warning: {staleness.warning}')
    print(f'Repo ID: {staleness.repo_data[\"id\"]}')
    await client.close()
asyncio.run(main())
"

# VERIFY: Tool output starts with warning when stale
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_symbols
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await search_symbols.handle(client, {'query': 'Repository', 'repository': 'inxr2', 'limit': 1})
    if 'Warning:' in result and 'stale' in result.lower():
        print('PASS: Staleness warning present')
        # Extract the warning line
        for line in result.splitlines():
            if 'Warning:' in line:
                print(f'  {line}')
                break
    else:
        # If index is up to date, no warning is expected — still a PASS
        print('PASS: No staleness warning (index is current)')
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- When the index is behind git HEAD: output starts with `Warning: Indexed data may be stale`
- Warning includes the commit hash the index was last updated to
- When the index is current: no warning appears
- Warning appears consistently across all tools (search_symbols, find_references, find_dead_code, review_helper)

---

## MCP-18: Browse URLs in find_dead_code and review_helper

**Steps:**
```bash
FE_URL="http://inxr2-dev:5173"

# VERIFY: find_dead_code includes browse URLs
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import find_dead_code
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await find_dead_code.handle(
        client,
        {'repository': 'inxr2', 'limit': 3},
        frontend_url='$FE_URL',
    )
    print(result)
    has_url = any('$FE_URL/browse/' in line for line in result.splitlines())
    assert has_url, 'Expected browse URLs in find_dead_code output'
    print('PASS: find_dead_code includes browse URLs')
    await client.close()
asyncio.run(main())
"

# VERIFY: review_helper includes browse URLs
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import review_helper
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    # Use a recent commit
    commits = await client.get('/api/commits', params={'repo': 'inxr2', 'limit': 5})
    commit = commits['commits'][0]['short_hash']
    result = await review_helper.handle(
        client,
        {'repository': 'inxr2', 'commit': commit},
        frontend_url='$FE_URL',
    )
    print(result)
    has_url = any('$FE_URL/browse/' in line for line in result.splitlines())
    assert has_url, 'Expected browse URLs in review_helper output'
    print('PASS: review_helper includes browse URLs')
    await client.close()
asyncio.run(main())
"

# VERIFY: No URLs without frontend_url
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import find_dead_code
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await find_dead_code.handle(client, {'repository': 'inxr2', 'limit': 3})
    assert 'http://' not in result, 'URL should not appear without frontend_url'
    print('PASS: No URLs without frontend_url')
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- `find_dead_code` output includes browse URLs when `frontend_url` is provided
- `review_helper` output includes browse URLs for changed files and reference locations
- URLs follow pattern: `{frontend_url}/browse/{repo}/{path}?line=N`
- No URLs appear when `frontend_url` is not provided

---

## MCP-19: get_file_structure Returns Correct Symbol Tree

Verify that `get_file_structure` returns the two-level symbol tree for a file that matches
what the symbols API knows about that file.

**Steps:**
```bash
# DISCOVER: Pick a known file with symbols from the API.
# ⚠️ This endpoint's params are `repo` and `path` (NOT repository_name / file_path — those return
#    HTTP 422 "Field required").
REPO="inxr2"
FILE="src/inxr2/domain/services/file_filter.py"
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/symbols/file-structure?repo=$REPO&path=$FILE' | python3 -m json.tool | head -40"

# VERIFY: MCP tool returns the same structure
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import get_file_structure
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await get_file_structure.handle(client, {
        'file_path': '$FILE',
        'repository': '$REPO',
    })
    print(result)
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- Output shows a two-level indented symbol tree (classes/functions at top level, methods indented under them)
- Symbol names in the MCP output match names returned by the symbols API for that file
- When `include_signatures=True` (default), parameter signatures appear next to function/method names
- When `include_docstrings=False` (default), no docstring text appears in the output
- Structural symbols (class, function, method, interface) are present; variable/field-like symbols are excluded

---

## MCP-20: get_change_impact Returns Correct Dependent Files Grouped by Type

Verify that `get_change_impact` finds all files that reference the given symbol and correctly
categorizes them as source, test, or config files.

**Steps:**
```bash
# DISCOVER: Pick a symbol with known references from the API.
# ⚠️ Filter by repository_id (see the warning in IX-04); resolve REPO_ID from /api/repositories.
REPO="inxr2"
REPO_ID=$(docker exec inxr2-dev bash -c "curl -s http://localhost:8000/api/repositories | python3 -c '
import sys, json
print({r[\"name\"]: r[\"id\"] for r in json.load(sys.stdin)}[\"inxr2\"])'")
SYMBOL="FileFilter"
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/symbols?q=$SYMBOL&repository_id=$REPO_ID&limit=3' | python3 -c '
import sys, json
items = json.load(sys.stdin)[\"items\"]
for s in items:
    print(f\"{s[\"name\"]} [{s[\"kind\"]}] id={s[\"id\"]}\")
'"
# Get reference count for the symbol from API.
# ⚠️ Use a limit ABOVE the real count — `total` is the page size, not the true total (issue #523).
docker exec inxr2-dev bash -c "
SID=\$(curl -s 'http://localhost:8000/api/symbols?q=$SYMBOL&repository_id=$REPO_ID&limit=1' | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"items\"][0][\"id\"])')
curl -s \"http://localhost:8000/api/symbols/\$SID/references?by_name=true&limit=500\" | python3 -c '
import sys, json
data = json.load(sys.stdin)
print(f\"Total references: {data[\"total\"]}\")
for r in data[\"items\"][:5]:
    print(f\"  {r.get(\"source_file_path\",\"?\")}\")
'
"

# VERIFY: MCP tool returns correctly grouped dependents at depth=1
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import get_change_impact
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await get_change_impact.handle(client, {
        'name': '$SYMBOL',
        'repository': '$REPO',
        'depth': 1,
    })
    print(result)
    await client.close()
asyncio.run(main())
"

# VERIFY: depth=2 includes transitive dependents
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import get_change_impact
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await get_change_impact.handle(client, {
        'name': '$SYMBOL',
        'repository': '$REPO',
        'depth': 2,
    })
    print(result)
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- Output groups dependent files into **Source files**, **Test files**, and **Config files** sections.
  Empty groups are omitted — `FileFilter` has no config dependents, so no "Config files" section
  appears, which is correct, not a failure. Pick a symbol referenced from a config file to exercise
  that group.
- Test files (paths containing `test`, `spec`, `__tests__`) appear in the test section
- Source file count at depth=1 matches the direct reference count from the API
- depth=2 output contains at least as many files as depth=1 (transitive adds more)
- Each file entry shows which symbols within it reference the target
- "No dependents found" message returned gracefully when symbol has zero references

---

## MCP-21: explain_symbol Returns Rich Symbol Context

Verify that `explain_symbol` returns definition location, docstring, signature, and references grouped by type for a known well-documented symbol.

**Steps:**
```bash
# DISCOVER: Pick a documented symbol with known references
REPO="inxr2"
SYMBOL="SearchSymbolsUseCase"

# VERIFY: explain_symbol returns definition, docstring, and grouped references
docker exec inxr2-dev bash -c '
cd /workspace/mcp-server
python3 -c "
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def call(tool, args):
    async with sse_client(\"http://localhost:3000/sse\") as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool(tool, args)
            print(res.content[0].text)

asyncio.run(call(\"explain_symbol\", {\"name\": \"SearchSymbolsUseCase\", \"repository\": \"inxr2\"}))
"'
```

**Pass criteria:**
- Output header contains symbol name, kind (e.g. `class`), and repository name
- `Location:` line shows a file path and line number
- `Docstring:` line is present (non-null) for a well-documented Python class
- `References (N total):` section lists at least one reference type (e.g. `import`, `call`)
- Calling with an unknown symbol name returns `Symbol 'X' not found.` gracefully
- Calling without `repository` when symbol exists in multiple repos includes a disambiguation note

---

## MCP-22: search_symbols Wildcard Returns Results

Regression test for bug #384 — `query="*"` was silently returning no results because the wildcard guard was missing.

**Steps:**
```bash
# VERIFY: Wildcard query returns symbols (not an empty list)
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_symbols
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await search_symbols.handle(client, {'query': '*', 'repository': 'inxr2', 'limit': 5})
    print(result)
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- Output contains at least one symbol entry (not a "no results" message)
- Symbol names, file paths, and kinds are present in the output

---

## MCP-23: search_code Extensions Filter Does Not Return Duplicates

Regression test for bug #400 — after #395 added raw body indexing, `search_code` with an extensions filter returns the same `file:line` multiple times because `_index_non_code_file` creates multiple `file_content` rows with `commit_id=NULL` for the same file. The `latest_file_ids_subquery` dedup pass-through for `source_file_id IS NULL` rows allows all of them through.

**Steps:**
```bash
# DISCOVER: Find a Swift symbol name that exists in travelbuddy
docker exec inxr2-dev bash -c "git -C /repos/test-repos/travelbuddy ls-files '*.swift' | head -1 | xargs -I{} grep -m1 'class\|struct\|protocol' /repos/test-repos/travelbuddy/{} | head -3"

# VERIFY: extensions filter with a known term returns no duplicates
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_code
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await search_code.handle(client, {'query': 'TraceLogger', 'repository': 'travelbuddy', 'extensions': 'swift'})
    print(result)
    lines = [l for l in result.splitlines() if 'TraceLogger' in l and '.swift' in l]
    paths = [l.strip() for l in lines]
    unique_paths = set(paths)
    print(f'Total matching lines: {len(paths)}, unique: {len(unique_paths)}')
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- Each `file:line` appears at most once in the output — no duplicate entries for the same location
- Result count matches the number of unique file+line combinations, not the number of indexed commits

---

## MCP-24: search_code Results Always Have a File Path

Regression test for bug #387 — `search_code` was including commit message text content entries (which have `file_path=None`) in results, producing lines with no file location.

**Steps:**
```bash
# VERIFY: All results include a file path (no commit message entries leaking through)
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_code
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await search_code.handle(client, {'query': 'Repository', 'repository': 'inxr2', 'limit': 20})
    print(result)
    # Every non-header, non-blank line should contain a file path (has a colon separating path from line number)
    result_lines = [l for l in result.splitlines() if l.strip() and not l.startswith('Search results')]
    file_lines = [l for l in result_lines if ':' in l and '.' in l.split(':')[0]]
    print(f'Result lines: {len(result_lines)}, lines with file paths: {len(file_lines)}')
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- Every result line includes a file path with an extension (e.g. `repo:path/to/file.py:42`)
- No result line contains only commit message text without a file location
- Output does not contain lines that look like git commit messages (e.g. lines starting with `feat:`, `fix:`, `chore:`)

---

## MCP-25: search_code Finds Content in Code File Bodies

Regression test for bug #395 — code files (Swift, Python, etc.) were never storing raw body content in `text_contents`, so `search_code` returned no results for terms that appeared only in source bodies (class names, identifiers) rather than in comments or docstrings.

**Steps:**
```bash
# DISCOVER: Find a Swift symbol name via search_symbols (proves it exists in source)
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_symbols
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await search_symbols.handle(client, {'query': 'RouteLeg', 'repository': 'travelbuddy'})
    print(result)
    await client.close()
asyncio.run(main())
"

# VERIFY: search_code with extensions filter finds the same term in Swift files
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_code
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await search_code.handle(client, {'query': 'RouteLeg', 'repository': 'travelbuddy', 'extensions': 'swift', 'limit': 10})
    print(result)
    swift_results = [l for l in result.splitlines() if '.swift' in l]
    print(f'Swift results: {len(swift_results)}')
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- `search_code` with `extensions='swift'` returns at least one result
- All results have `.swift` file paths (not `.md` or `.yaml`)
- The term appears in the result content (confirming it came from the file body, not just a symbol name match)

---

## MCP-26: search_code source_only Filter Excludes Non-Source Files

Regression test for the `source_only` parameter — verifies that `source_only=true` removes documentation and config files from results while preserving code file results.

**Steps:**
```bash
# DISCOVER: Find a term that appears in both docs and Swift source
# (UserProfile appears in .md docs and in .swift files; the previously-documented "BucketList"
#  no longer exists in the indexed travelbuddy swift sources)

# VERIFY: Without filter, markdown results appear
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_code
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await search_code.handle(client, {'query': 'UserProfile', 'repository': 'travelbuddy', 'limit': 20})
    print(result)
    md_results = [l for l in result.splitlines() if '.md' in l]
    print(f'Markdown results (expect > 0): {len(md_results)}')
    await client.close()
asyncio.run(main())
"

# VERIFY: With source_only=true, markdown results are absent
docker exec -w /workspace/mcp-server inxr2-dev python3 -c "
import asyncio
from src.client import HttpInxr2Client
from src.tools import search_code
async def main():
    client = HttpInxr2Client('http://localhost:8000')
    result = await search_code.handle(client, {'query': 'UserProfile', 'repository': 'travelbuddy', 'source_only': True, 'limit': 20})
    print(result)
    md_results = [l for l in result.splitlines() if '.md' in l]
    swift_results = [l for l in result.splitlines() if '.swift' in l]
    print(f'Markdown results (expect 0): {len(md_results)}')
    print(f'Swift results (expect > 0): {len(swift_results)}')
    await client.close()
asyncio.run(main())
"
```

**Pass criteria:**
- Without `source_only`: at least one `.md` result appears
- With `source_only=true`: zero `.md` results, at least one `.swift` result
- No error or empty response when `source_only=true` is used

---

## Summary

### Phase 1: Indexing (8 tests)

| ID | Test | Validates |
|----|------|-----------|
| IX-01 | Reset DB and index all repos (10 days) | Full indexing pipeline |
| IX-02 | Verify indexing status | All repos indexed with data |
| IX-03 | Verify API serves indexed data | API returns all repos from config |
| IX-04 | Verify multi-language symbol extraction (12 langs) | Each parser produces correct symbols |
| IX-04a | Verify reference extraction (bare ids, require, this) | Reference extraction pipeline |
| IX-04b | Verify ES6 export/re-export references | Export/re-export reference patterns |
| IX-05 | Compare indexing performance vs history | No timing/count regressions |
| IX-06 | Verify all git files at HEAD are indexed | FileFilter completeness (no silent drops) |

### Phase 2: QA Browser (39 tests)

| ID | Test | Validates Against |
|----|------|-------------------|
| RT-01 | Home page shows repo cards | API repo count |
| RT-02 | Repo card shows statistics | API stats |
| RT-02a | Repo card shows indexing stats | API stats (files, symbols, refs, langs) |
| RT-03 | Navigate to browse from home | Repo name in URL |
| RT-04 | File tree matches git | `git ls-tree` |
| RT-05 | Directory expansion shows children | `git ls-tree <dir>/` |
| RT-06 | Code viewer shows correct content | `head` + `wc -l` of file |
| RT-07 | Line numbers are clickable | URL state |
| RT-08 | Symbol click opens references | File content |
| RT-09 | References panel shows usages | `git ls-files` |
| RT-10 | "Search globally" link works | Symbol name from panel |
| RT-11 | Blame matches git blame | `git blame --porcelain` |
| RT-12 | Diff mode enter and exit | URL state |
| RT-12a | Diff colors follow temporal order | Commit dates, background colors |
| RT-12b | Diff version selectors show all commits | File history API |
| RT-13 | Search returns real results | `git ls-files` |
| RT-14 | Search result navigates correctly | Result file path |
| RT-15 | Regex search works | `grep` pattern from git |
| RT-16 | File search works | `git ls-files` |
| RT-16a | Extensionless file search | `git ls-files` without extensions |
| RT-17 | History matches git log | `git log --oneline` |
| RT-18 | Commit click navigates to browse | `git log` hash |
| RT-19 | Tab navigation preserves context | URL repo param |
| RT-20 | Branch selector shows branches | `git branch` / config |
| RT-21 | URL state preserved on reload | URL params |
| RT-22 | Theme toggle | Background color change |
| RT-22a | Diff colors in both themes | Theme-adapted diff colors |
| RT-23 | Markdown rendering matches file | `grep '^#'` heading |
| RT-24 | Logical View loads symbol tree | Symbol tree API |
| RT-25 | Logical View expand shows symbols | Symbol tree API children |
| RT-26 | Logical View symbol click → Browse | URL navigation |
| RT-27 | Logical View language/kind filters | Filtered item count |
| RT-28 | Dependencies tab shows packages | Dependencies API |
| RT-29 | Dependencies respects commit picker | URL commit param |
| RT-30 | Dependencies empty state | Empty state message |
| RT-31 | References panel → Logical View link | URL navigation |
| RT-32 | Browse rename banner at old commit | `file_renames` API + rename banner visible |
| RT-33 | Diff viewer rename following across rename boundary | Both paths in diff header, diff renders |
| RT-34 | Mermaid diagrams render as SVG | SVG element present in DOM |

### Phase 3: MCP Server (26 tests)

| ID | Test | Validates Against |
|----|------|-------------------|
| MCP-01 | List repos returns all indexed repos | API repo list |
| MCP-02 | List repo detail shows indexed branches | API branches endpoint |
| MCP-03 | Search symbols returns matching definitions | API symbols endpoint |
| MCP-04 | Search symbols filters by kind | Kind filter consistency |
| MCP-05 | Go to definition finds symbol | API by-name endpoint |
| MCP-06 | Find references returns cross-repo usages | API references endpoint |
| MCP-07 | Find references filters by type | Type filter consistency |
| MCP-08 | Search code returns matching content | API search/text endpoint |
| MCP-09 | Search code with repository filter | Repo filter consistency |
| MCP-10 | No-match queries return graceful messages | Error handling |
| MCP-11 | MCP unit tests pass | Test suite |
| MCP-12 | Browse URLs point to correct code locations | QA agent navigation + page content |
| MCP-13 | Find dead code returns unreferenced symbols | API symbols + references |
| MCP-14 | Find dead code filters by kind | Kind filter consistency |
| MCP-15 | Review helper shows blast radius | `git diff-tree` changed files |
| MCP-16 | Review helper changed files only | Changed file count (not all repo) |
| MCP-17 | Staleness warning when index behind | Git HEAD vs last indexed commit |
| MCP-18 | Browse URLs in find_dead_code and review_helper | URL presence with frontend_url |
| MCP-19 | get_file_structure returns correct symbol tree | API file-structure endpoint |
| MCP-20 | get_change_impact returns dependents grouped by type | API references endpoint, grouping logic |
| MCP-21 | explain_symbol returns rich symbol context | API by-name + references endpoints |
| MCP-22 | search_symbols wildcard returns results (not empty) | API symbols endpoint |
| MCP-23 | search_code extensions filter returns no duplicates | Unique file:line per result |
| MCP-24 | search_code results always include a file path | No commit message entries in output |
| MCP-25 | search_code finds content in code file bodies | Swift results via extensions filter |
| MCP-26 | search_code source_only filter excludes non-source files | .md absent, .swift present |

**Total: 73 test cases** (8 indexing + 39 browser + 26 MCP) — all verified against git/API, no hardcoded data.
