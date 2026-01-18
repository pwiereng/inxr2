# Time Travel UI Ideas

Ideas for visualizing and navigating the temporal/git-based aspects of code in INXR2.

## Timeline Controls

| Control | Description | Complexity |
|---------|-------------|------------|
| **Commit slider** | Scrub through commits like a video timeline - drag to see code at any point | Medium |
| **Date picker** | Jump to "code as of Jan 15, 2025" | Low |
| **Branch selector** | Switch branches while staying on same file/symbol | Low |
| **"Previous/Next" buttons** | Step through commits that touched current file | Low |

## Code Visualizations

| Visualization | Description | Complexity |
|---------------|-------------|------------|
| **Side-by-side diff** | Compare current view with any other commit | Medium |
| **Inline blame** | Hover/toggle to see who changed each line and when | Medium |
| **Age heatmap** | Color-code lines by age (old=faded, new=bright) | Low |
| **Change sparklines** | Mini graph next to files showing change frequency | Medium |

## Symbol-Focused Time Travel

| Feature | Description | Complexity |
|---------|-------------|------------|
| **Symbol timeline** | Visual history: when was this function created, modified, deleted? | High |
| **"History" tab** | In ReferencesPanel, show all versions of a symbol | Medium |
| **Reference evolution** | How did callers of this function change over time? | High |
| **"Born in" badge** | Show commit where symbol first appeared | Low |

## Navigation Patterns

| Pattern | Description | Complexity |
|---------|-------------|------------|
| **Permalink with commit** | URLs like `/browse/repo/file/123?commit=abc123` | Low |
| **"Pin to commit"** | Lock view to specific point while exploring | Low |
| **Ghost symbols** | Show deleted symbols in gray with "removed in commit X" | Medium |
| **Time comparison mode** | Split view: left=old commit, right=new commit | High |

## UI Mockup Ideas

### Basic Timeline Header
```
┌─────────────────────────────────────────────────────────────┐
│  repo: inxr2    branch: main ▼   ◀ ● ● ● ● ● ● ● ▶  📅     │
│                                   ↑ commit timeline        │
└─────────────────────────────────────────────────────────────┘
```

### Age-Annotated Code View
```
┌─────────────────────────────────────────────────────────────┐
│  src/api/routes.py                                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 14 │ def get_users():                           3d    │  │
│  │ 15 │     """Fetch all users from database"""    3mo   │  │
│  │ 16 │     return db.query(User).all()            3d    │  │
│  └───────────────────────────────────────────────────────┘  │
│        ↑ line ages shown on right margin                    │
└─────────────────────────────────────────────────────────────┘
```

### Symbol History Panel
```
┌─────────────────────────────────────────────────────────────┐
│  Symbol: get_users()                                        │
│  ─────────────────────────────────────────────────────────  │
│  History:                                                   │
│    ● Created    abc1234  2024-06-15  "Add user API"        │
│    ● Modified   def5678  2024-08-20  "Add pagination"      │
│    ● Modified   ghi9012  2024-12-01  "Fix N+1 query"       │
│    ◉ Current    jkl3456  2025-01-10  "Add caching"         │
│  ─────────────────────────────────────────────────────────  │
│  [Compare versions]  [View at selected commit]              │
└─────────────────────────────────────────────────────────────┘
```

### Split Comparison View
```
┌────────────────────────────┬────────────────────────────────┐
│  abc1234 (3 months ago)    │  jkl3456 (current)             │
│  ──────────────────────    │  ──────────────────────        │
│  def get_users():          │  def get_users():              │
│      return db.query()     │      cached = cache.get()      │
│                            │      if cached:                │
│                            │          return cached         │
│                            │      result = db.query()       │
│                            │      cache.set(result)         │
│                            │      return result             │
└────────────────────────────┴────────────────────────────────┘
```

## Implementation Priority Suggestions

### Quick Wins (Low effort, high value)
1. Branch selector dropdown
2. "Born in" badge on symbols (commit where first defined)
3. Permalink with commit in URL
4. Date picker to jump to point in time

### Medium Effort
1. Previous/Next commit buttons for current file
2. Commit slider timeline
3. Inline blame on hover
4. History tab in ReferencesPanel

### Larger Features
1. Side-by-side diff comparison
2. Symbol timeline visualization
3. Ghost symbols for deleted code
4. Reference evolution tracking

## Database Considerations

The current schema already supports time travel:
- `files` table has `commit_id` - same file at different commits = different rows
- `symbols` table has `file_id` which links to specific commit
- `commits` table has `committed_at` timestamp and `branch`

Queries needed:
- Get file content at specific commit
- Get symbol history across commits
- Find when symbol was created/deleted
- Compare references between commits

## Questions to Consider

1. Should the default view be "latest on branch" or "specific commit"?
2. How do we handle symbols that exist in multiple branches?
3. Should deleted symbols be searchable?
4. How far back in history should we index by default?
5. Performance: how to make historical queries fast?

---

*Created: 2025-01-16*
*Status: Ideas for future implementation*
