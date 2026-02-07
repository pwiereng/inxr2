# UX Cleanup Proposal

## URL Structure

| View | URL Pattern | Example |
|------|-------------|---------|
| Home | `/` | `http://localhost:5173/` |
| Browse | `/browse/:repo/*path` | `/browse/crisp/src/crisp/actor.c?branch=main&commit=abc123` |
| Search | `/search` | `/search?repo=inxr2&branch=main&commit=abc123&query=TODO` |
| History | `/history` | `/history?repo=inxr2&branch=main&commit=abc123` |

### Query Parameters

| Parameter | Used In | Description |
|-----------|---------|-------------|
| `branch` | All | Branch name |
| `commit` | All | Commit hash |
| `repo` | Search, History | Repository name (Browse has it in path) |
| `symbols` | Browse | Symbol search query |
| `query` | Search | Text search query |
| `file` | Browse | File path (in URL path, not query) |
| `line` | Browse | Line number to highlight |
| `refs` | Browse | Show references panel (1=show) |
| `diff` | Browse | Diff mode (1=enabled) |
| `diffBranch` | Browse | Right panel branch in diff mode |
| `diffCommit` | Browse | Right panel commit in diff mode |

---

## Global Header (Two Rows)

### Row 1: Navigation & Context
```
[Home Icon] | [Repository ▼] | [Branch ▼] | [Commit ▼]
```

### Row 2: Tabs
```
[Browse] | [Search] | [History]
```

### Component Behaviors

**Home Icon**
- Always visible
- Click → Navigate to `/` (home page with repo cards)

**Repository Dropdown**
- Lists all indexed repositories
- Always has a value when on Browse/Search/History (required)
- Change → Reset to new repo's default branch + HEAD, stay on current tab

**Branch Dropdown**
- Shows branches for selected repository
- Defaults to repository's default branch
- Change → Reset to HEAD of new branch, refresh view

**Commit Dropdown**
- Shows commits for selected branch
- Defaults to HEAD (latest)
- Change → Refresh view at selected commit

---

## Home Page (`/`)

- Display repository cards (clickable)
- Each card shows repo name (future: stats like languages, files, LOC, % refs indexed)
- Click card → Navigate to `/browse/:repo?branch=default&commit=HEAD`

---

## Tab Behaviors

### Browse (`/browse/:repo/*`)

**On Enter:**
- Preserve repo/branch/commit from URL or use defaults
- Display source tree

**Diff Mode:**
- Main header controls Branch/Commit for LEFT panel
- Compact inline Branch/Commit selector above RIGHT panel
- Enter diff mode → Right defaults to same branch, previous version (or same if no previous)
- Exit diff mode → Return to single-panel view

**References Panel:**
- Dropdown relative to associated panel's branch (left or right)
- Future: Global free-text search option

**Symbol Search:**
- Uses `symbols=X` parameter in URL

### Search (`/search`)

**On Enter:**
- Preserve repo/branch/commit from URL
- If all present: search filtered to that repo/branch/commit

**Features:**
- Text search with `query=X` parameter
- Filter by mode (keyword/phrase/regex)
- Filter by languages, source types

**Future:**
- Filename-only search mode
- Click result → Jump to Browse at that file

### History (`/history`)

**On Enter:**
- Preserve repo/branch/commit from URL
- Show commits starting from selected commit (or HEAD)
- Scroll down for older history

**Future:**
- List changed files per commit
- Links to Browse/Diff view for each file
- Blame/commit reference from Browse (jump from line to commit)

---

## State Transitions

### From Home → Browse (click repo card)
```
/ → /browse/repoName?branch=defaultBranch&commit=HEAD
```

### Switch Repository (from any tab)
```
Current: /browse/oldRepo/path?branch=X&commit=Y
Action: Select newRepo from dropdown
Result: /browse/newRepo?branch=defaultBranch&commit=HEAD
```

### Switch Branch
```
Current: /browse/repo/path?branch=old&commit=abc
Action: Select newBranch from dropdown
Result: /browse/repo/path?branch=newBranch&commit=HEAD
```

### Switch Commit
```
Current: /browse/repo/path?branch=main&commit=abc
Action: Select newCommit from dropdown
Result: /browse/repo/path?branch=main&commit=newCommit
```

### Switch Tabs
```
Browse → Search: /browse/repo/path?branch=X&commit=Y → /search?repo=repo&branch=X&commit=Y
Search → History: /search?repo=repo&branch=X&commit=Y → /history?repo=repo&branch=X&commit=Y
History → Browse: /history?repo=repo&branch=X&commit=Y → /browse/repo?branch=X&commit=Y
```

---

## Implementation Checklist

- [x] Create shared header component with Home/Repo/Branch/Commit controls (`CodeHeader`)
- [x] Update Browse to use shared header
- [x] Create History page at `/history`
- [x] Update Search page to use `/search` route with `query` param
- [x] Update Home page to navigate to `/browse/:repo` on card click
- [x] Update tab switching to preserve and transfer state correctly
- [x] Remove `/code` route (no longer needed)
- [x] Remove obsolete `CodeExplorer` component
- [x] Add compact diff controls above right panel in Browse
- [x] Update diff mode to default right panel to previous version
- [ ] Rename URL params: `q` → `symbols` (Browse refs panel) - *low priority, existing param works*
