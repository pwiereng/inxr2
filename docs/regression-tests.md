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

## Base URLs

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- QA Agent: `http://localhost:9222`

All QA `curl` commands target `http://localhost:9222`. All git/API commands run inside the dev container.

---

# Phase 1: Indexing Regression

Reset the database and re-index all repos from `config.yaml` (last 30 days).
Verifies: git integration, tree-sitter parsing, symbol extraction, reference resolution.

## IX-01: Reset Database and Index All Repos

**Steps:**
```bash
docker exec inxr2-dev inxr2 index --config config.yaml --reset-db --yes --days 30
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

For each language (Python, TypeScript, JavaScript, C, Java, C#), pick a repo that uses it,
find a real symbol name from git, and verify it appears in the API.

**Steps (per language):**
```bash
# 1. DISCOVER: Find a source file in the repo
docker exec inxr2-dev bash -c "git -C /repos/test-repos/<repo> ls-files '*.py' | head -3"
# 2. DISCOVER: Extract a class/function name from that file
docker exec inxr2-dev bash -c "grep -E 'class |def |function |interface |struct ' /repos/test-repos/<repo>/<file> | head -3"
# 3. VERIFY: Search for that symbol name via API
docker exec inxr2-dev bash -c "curl -s 'http://localhost:8000/api/symbols?q=<discovered_name>&repository_name=<repo>&limit=3' | python3 -m json.tool"
```

**Pass criteria:**
- For each language, at least one symbol is found via the API
- Symbol kind matches what was found in the source (e.g., `grep 'class Foo'` → API returns symbol with kind=class)

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
curl "http://localhost:9222/click?selector=tr[data-line='5'] td:last-child"
curl "http://localhost:9222/url"
```

**Pass criteria:**
- URL now contains `line=5` parameter

---

## RT-08: Symbol Click Opens References Panel

**Steps:**
```bash
# (Continuing from RT-06 with a file loaded)
# Look for clickable symbol spans
curl "http://localhost:9222/elements?selector=span[style*='cursor']&limit=10"
# Click first symbol
curl "http://localhost:9222/click?selector=span[style*='cursor']"
# Check panel opened
curl "http://localhost:9222/text?selector=body"
```

**Pass criteria:**
- References panel appears with a symbol name and kind
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

## RT-13: Search Returns Results That Exist in Git

**Steps:**
```bash
# DISCOVER: Pick a distinctive word from a real source file
docker exec inxr2-dev bash -c "grep -rh 'class \|def \|function ' /repos/test-repos/<repo>/ --include='*.py' --include='*.ts' | head -1"
# Extract a word from that line to use as search term
# NAVIGATE
curl "http://localhost:9222/navigate?url=http://localhost:5173/search"
curl "http://localhost:9222/wait?selector=input&timeout=3000"
curl "http://localhost:9222/fill?selector=input&value=<discovered_word>"
curl "http://localhost:9222/wait?selector=.MuiListItemButton-root&timeout=5000"
# VERIFY
curl "http://localhost:9222/elements?selector=.MuiListItemButton-root&limit=5"
```

**Pass criteria:**
- At least 1 search result returned
- Result file paths exist in the repository (verify via `git ls-files`)

---

## RT-14: Search Result Click Navigates to Correct Location

**Steps:**
```bash
# (Continuing from RT-13 with results visible)
# Note the file path and line number shown in the first result
curl "http://localhost:9222/text?selector=.MuiListItemButton-root"
# Click it
curl "http://localhost:9222/click?selector=.MuiListItemButton-root"
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
# Use the function name as a regex search
curl "http://localhost:9222/navigate?url=http://localhost:5173/search?mode=regex&query=<function_pattern>"
curl "http://localhost:9222/wait?selector=.MuiListItemButton-root&timeout=5000"
curl "http://localhost:9222/elements?selector=.MuiListItemButton-root&limit=5"
```

**Pass criteria:**
- Results appear matching the regex pattern
- Result file paths exist in the repository

---

## RT-16: Search — File Mode

**Steps:**
```bash
# DISCOVER: Pick a real filename from git
docker exec inxr2-dev bash -c "git -C /repos/test-repos/<repo> ls-files | head -5"
# Search for that filename
curl "http://localhost:9222/navigate?url=http://localhost:5173/search?mode=file&query=<discovered_filename>"
curl "http://localhost:9222/wait?selector=.MuiListItemButton-root&timeout=5000"
curl "http://localhost:9222/elements?selector=.MuiListItemButton-root&limit=10"
```

**Pass criteria:**
- File results include the discovered filename

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
# Click first indexed commit
curl "http://localhost:9222/click?selector=.MuiListItem-root"
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
# DISCOVER: Get branches from git for a multi-branch repo (e.g., inxr2)
docker exec inxr2-dev git -C /repos/test-repos/inxr2 branch -a --format='%(refname:short)'
# NAVIGATE
curl "http://localhost:9222/navigate?url=http://localhost:5173/browse/inxr2?branch=main"
curl "http://localhost:9222/wait?selector=.MuiSelect-select&timeout=5000"
curl "http://localhost:9222/elements?selector=.MuiSelect-select&limit=5"
```

**Pass criteria:**
- Branch selector is present and shows current branch name
- At least the branches listed in `config.yaml` for that repo are available

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
curl "http://localhost:9222/navigate?url=http://localhost:5173/"
# Get initial background color
curl "http://localhost:9222/eval?script=getComputedStyle(document.body).backgroundColor"
# Toggle theme
curl "http://localhost:9222/click?selector=[aria-label*='Switch to']"
# Get new background color
curl "http://localhost:9222/eval?script=getComputedStyle(document.body).backgroundColor"
# Toggle back
curl "http://localhost:9222/click?selector=[aria-label*='Switch to']"
curl "http://localhost:9222/eval?script=getComputedStyle(document.body).backgroundColor"
```

**Pass criteria:**
- Background color changes after first toggle (different from initial)
- Background color reverts after second toggle (matches initial)

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

## Summary

### Phase 1: Indexing (4 tests)

| ID | Test | Validates |
|----|------|-----------|
| IX-01 | Reset DB and index all repos (30 days) | Full indexing pipeline |
| IX-02 | Verify indexing status | All repos indexed with data |
| IX-03 | Verify API serves indexed data | API returns all repos from config |
| IX-04 | Verify multi-language symbol extraction | Each parser produces correct symbols |

### Phase 2: QA Browser (23 tests)

| ID | Test | Validates Against |
|----|------|-------------------|
| RT-01 | Home page shows repo cards | API repo count |
| RT-02 | Repo card shows statistics | API stats |
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
| RT-13 | Search returns real results | `git ls-files` |
| RT-14 | Search result navigates correctly | Result file path |
| RT-15 | Regex search works | `grep` pattern from git |
| RT-16 | File search works | `git ls-files` |
| RT-17 | History matches git log | `git log --oneline` |
| RT-18 | Commit click navigates to browse | `git log` hash |
| RT-19 | Tab navigation preserves context | URL repo param |
| RT-20 | Branch selector shows branches | `git branch` / config |
| RT-21 | URL state preserved on reload | URL params |
| RT-22 | Theme toggle | Background color change |
| RT-23 | Markdown rendering matches file | `grep '^#'` heading |

**Total: 27 test cases** (4 indexing + 23 browser) — all verified against git/API, no hardcoded data.
