# Branch Indexing Strategy

**Date:** 2026-02-01
**Branch:** `2026-02-01-further-optimizations`

---

## Problem Statement

When indexing multiple repositories with multiple branches, stale feature branches (those without recent commits) consume unnecessary database space and indexing time. However, the primary branch (main/master/trunk) should always be indexed to ensure users can browse the current state of the codebase.

## Decision

### Branch Filtering Rules

When using `--days` to filter by commit age:

1. **Primary branch** (first branch listed in config):
   - Always indexed, never skipped
   - If it has commits within the `--days` window: indexes those commits (respects `--days`)
   - If it has NO commits within `--days`: falls back to HEAD only (`max_history=1`)
   - Ensures every configured repository has at least its main branch current

2. **Feature branches** (all other branches):
   - Only indexed if they have commits within the `--days` window
   - Skipped entirely with a message if no recent activity
   - When indexed, use merge-base optimization to only index commits unique to that branch

### Rationale

This approach balances several concerns:

1. **Always have current code**: The primary branch is always indexed, so users can always browse the latest code
2. **Smart history depth**: Primary branches with recent activity get full `--days` history; stale ones just get HEAD
3. **Skip stale branches**: Feature branches that haven't been touched in N days are likely merged or abandoned
4. **Clear configuration**: First branch in config is the "primary" - simple to understand and configure

### Example Configuration

```yaml
repositories:
  - name: myrepo
    branches:
      - main        # Primary - always indexed (at least HEAD)
      - feature-a   # Only indexed if has commits within --days
      - feature-b   # Only indexed if has commits within --days
    languages:
      - python
```

### Command Examples

```bash
# Index all repos, skip feature branches older than 10 days
inxr2 index full --config config.yaml --days 10

# Primary branches indexed: Always (at HEAD)
# Feature branches indexed: Only if commits within last 10 days
```

## Related Decisions

- **Merge-base optimization** (`base_branch` parameter): For feature branches that are indexed, only commits after the merge-base with the primary branch are processed. This avoids re-indexing shared history.

- **Reference resolution** (`commit_aware=False`): References resolve across commits for better resolution rates, accepting "mostly correct" time-travel behavior. See `2026-02-01-reference-resolution-investigation.md`.

## Implementation

Changes in `src/inxr2/cli.py`:
- First branch in config list is treated as primary
- Primary branch checks for recent commits within `--days` window
- If primary has recent commits: uses `--days` filter (indexes recent history)
- If primary has no recent commits: falls back to `max_history=1` (HEAD only)
- Feature branches use normal `--days` filtering and are skipped if no recent activity

Tests in `tests/adapters/cli/test_cli.py`:
- `test_old_branch_skipped_with_days_filter`: Verifies non-primary branches are skipped
- `test_primary_branch_always_indexed_with_days_filter`: Verifies primary branch is never skipped
- `test_primary_branch_with_recent_commits_uses_days_filter`: Verifies primary uses `--days` when active
- `test_primary_branch_no_recent_commits_falls_back_to_head`: Verifies primary falls back to HEAD when stale
