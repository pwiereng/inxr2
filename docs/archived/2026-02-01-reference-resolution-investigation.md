# Reference Resolution Rate Investigation

**Date:** 2026-02-01
**Issue:** Reference resolution dropped from ~38% to ~20%
**Branch:** `2026-02-01-further-optimizations`

---

## Problem Statement

After recent changes, reference resolution rate dropped significantly:
- **Previous:** ~38% resolution rate
- **Current:** ~19.8% resolution rate (13,905 / 70,400)

## Root Cause Analysis

### Change That Triggered the Issue

In commit `9b4b5ad`, `commit_aware` was changed from `False` to `True`:

```python
# Before:
commit_aware=False,  # Cross-commit resolution by default

# After:
commit_aware=True,  # Time-travel consistent: resolve to symbols at same commit
```

### Why This Matters

With `commit_aware=True`, references can **only resolve to symbols at the same commit**. This is correct for time-travel consistency (clicking a reference at commit X should navigate to the symbol as it existed at commit X, not some other commit).

### The Actual Bug

The indexing logic processes commits like this:

1. **HEAD commit:** Process ALL files (symbols created at HEAD)
2. **Older commits:** Only process CHANGED files (symbols only for modified files)

This worked fine with `commit_aware=False` because references at any commit could resolve to symbols at any other commit (typically HEAD).

But with `commit_aware=True`:
- References at commit X have `commit_id = X`
- Symbols in unchanged files only exist at HEAD (not at commit X)
- References at X cannot find matching symbols at X
- Resolution fails

**Example:**
- Commit X: only `utils.py` was modified
- `main.py` wasn't modified (no symbols at commit X)
- But `main.py` HAS references at commit X (we extract refs from all files)
- Those references can't resolve because `main.py` has no symbols at commit X

## Options Considered

### Option 1: Fix Properly - Process All Files at Each Commit
Process ALL files at each commit, using content-hash optimization to copy symbols for unchanged files.

**Pros:**
- Correct time-travel behavior
- References resolve to symbols at the same commit
- Click-to-navigate works correctly at any point in history

**Cons:**
- More records in database (symbols duplicated per commit)
- Slightly more indexing work (though content-hash makes it fast)

### Option 2: Revert to commit_aware=False
Keep delta indexing, use cross-commit resolution.

**Pros:**
- Faster indexing
- Smaller database
- Higher resolution rate

**Cons:**
- Time-travel navigation may be incorrect
- Clicking reference at commit A might go to symbol from commit B
- Anachronistic results

### Option 3: Hybrid Approach
Use `commit_aware=False` but document the trade-off. Consider making it configurable.

**Pros:**
- User can choose based on their needs
- Flexibility

**Cons:**
- More complexity
- Two code paths to maintain

---

## Decision

**Chosen:** Option 2 - Revert to `commit_aware=False`

### Rationale

Option 1 would require creating symbol records for ALL files at EVERY commit:
- 65 commits × 270 files = ~17,550 file records (vs current ~900)
- Symbol and reference records would scale similarly
- Significant database bloat for marginal benefit

The "mostly correct" behavior of `commit_aware=False` is acceptable because:
- Most users browse code at HEAD anyway
- Time-travel is a secondary feature
- The anachronistic edge case (reference at commit A resolving to symbol from commit B) is rare and usually harmless
- The symbol definition is typically the same content anyway (content-hash match)

### Trade-off Accepted

With `commit_aware=False`:
- **Pro:** Higher resolution rate (~35-40%)
- **Pro:** Smaller database, faster indexing
- **Con:** Clicking a reference at historical commit X might navigate to the symbol definition from a different commit (usually HEAD)
- **Impact:** Low - the code shown will usually be identical since unchanged files have the same content

---

## Baseline Metrics

**Before fix (commit_aware=True, delta indexing):**
```
Commits: 65
Files at HEAD: 270
Files Processed: 652
Files Unchanged: 15,413
Symbols Found: 13,344
References Found: 70,400
References Resolved: 13,905 (19.8%)
Files Reused: 260
Symbols Reused: 5,504
Total Time: 48.1s
```

**Target:** Resolution rate should improve significantly (closer to 35-40%)

---

## Progress Log

### 2026-02-01: Reverted to commit_aware=False

**Change:** Set `commit_aware=False` in `default_orchestrator.py` (lines 311, 562)

**Result:** Success

| Metric | Before | After |
|--------|--------|-------|
| References Found | 70,400 | 70,400 |
| References Resolved | 13,905 (19.8%) | 24,970 (35.5%) |
| Total Time | 48.1s | 46.3s |

Resolution rate improved from **19.8% → 35.5%** as expected. Slightly faster too.
