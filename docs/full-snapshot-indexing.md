# Full Snapshot Indexing

## Overview

INXR2 uses **full snapshot indexing** — every indexed commit stores the complete file tree, not just changed files. Combined with **content-addressable file versions**, this makes indexing idempotent, correct at every commit, and efficient.

## Indexing Semantics

### Core Principle: Idempotency

Running the same indexing command multiple times produces the same result. There is no `--force` flag because it's never needed.

```bash
# These two sequences produce identical databases:

# Sequence A: incremental
inxr2 index --days 1
inxr2 index --days 10
inxr2 index --days 100

# Sequence B: one shot
inxr2 index --days 100
```

### Commit Selection

Every invocation performs two operations:

1. **Forward fill** (always): Index all commits between the last indexed commit and HEAD. This ensures no gaps in coverage.
2. **Backfill** (if `--days` specified): Also index commits from the last N days.

The union is deduplicated and processed newest-first. Commits already in the database are skipped after a single cheap lookup.

```
Timeline:  ... ──── C1 ──── C2 ──── C3 ──── C4 ──── C5 (HEAD)
                                     ↑                ↑
                              last indexed         current

Forward fill: C4, C5           (always happens)
--days 10:    C1, C2, C3, ...  (if they fall within 10 days)
Result:       union of both, deduplicated
```

### What Happens at Each Commit

For a **new commit** (not yet in database):
1. Save commit record, link to branch
2. Index commit message as searchable text
3. For each file in the commit's tree:
   - Check if this file version already exists (same path + same content)
   - If yes: just link the existing file version to this commit (cheap)
   - If no: create file version, parse for symbols/references (only happens once per unique file content)

For an **existing commit** (already in database):
1. Link commit to the current branch (idempotent)
2. Skip all file processing (already done)

### CLI Options

```
inxr2 index                           # Fresh: just HEAD. Subsequent: forward fill to HEAD.
inxr2 index --days 10                 # Forward fill + last 10 days of commits.
inxr2 index --days 100                # Extends backward. Already-indexed commits skipped.
inxr2 index --config config.yaml      # Index all repos in config file.
inxr2 index --config config.yaml --repo myrepo   # Index one specific repo.
```

| Option | Description |
|--------|-------------|
| `--path` | Path to a git repository to index |
| `--config` | YAML config file with repository definitions |
| `--repo` | Index only this repository (from config) |
| `--branch` | Branch to index (default: repo's default branch) |
| `--languages` | Comma-separated list of languages to parse |
| `--days` | Index commits from the last N days (plus forward fill) |
| `--verbose` | Show detailed output |
| `--log-level` | Set log level (DEBUG, INFO, WARNING, ERROR) |
| `--reset-db` | Reset database before indexing |
| `--yes` | Skip confirmation prompts |

**Removed options** (no longer needed):
- ~~`--force`~~: Idempotent indexing makes this unnecessary.
- ~~`--history`/`--max-commits`~~: Replaced by `--days`, which is additive and idempotent.

### Examples

```bash
# First time: indexes HEAD commit only (fast baseline)
inxr2 index --config config.yaml

# Add 30 days of history
inxr2 index --config config.yaml --days 30

# Later, extend to 90 days — only new commits are processed
inxr2 index --config config.yaml --days 90

# After some development, catch up to HEAD (forward fill)
inxr2 index --config config.yaml

# Full reset and re-index
inxr2 db reset --yes && inxr2 index --config config.yaml --days 30

# Check indexing status
inxr2 index status --path /repos/myrepo
```

### Branch Behavior

- **Primary branch** (first in config, or specified with `--branch`): Always indexed — at minimum HEAD, or N days if `--days` is specified.
- **Other branches** (from config): Only indexed if they have commits within the `--days` window. Forward fill still applies per branch.
- Commits shared across branches (e.g., before a branch point) are stored once and linked to all relevant branches.

### No Gaps Guarantee

The forward fill step runs on every invocation, ensuring the indexed commit range is always contiguous from the oldest indexed commit to HEAD. You can never end up with a "hole" in your indexed history.

---

## Content-Addressable File Versions (Schema)

### Problem

The naive approach to full snapshot indexing stores symbols and references **per commit** — even when file content is identical across commits. A file unchanged across 100 commits gets 100 copies of its symbols and 100 copies of its references. For a repo with ~330 files and ~930 commits, this means millions of redundant rows and multi-hour indexing times.

### Solution

A file version is identified by `(repository_id, path, content_hash)`. Symbols and references belong to the file version, not the commit. A lightweight junction table `commit_files` links file versions to commits.

```
Before (per-commit storage):
  files:      1 row per (commit, path)     → ~306K rows
  symbols:    1 set per file row           → ~3.7M rows (copies)
  references: 1 set per file row           → ~17.4M rows (copies)

After (content-addressable):
  files:        1 row per unique version   → ~350 rows
  commit_files: 1 row per (commit, file)   → ~306K rows (2 integers each)
  symbols:      1 set per file version     → ~4K rows
  references:   1 set per file version     → ~19K rows
```

**~100x fewer symbol/reference rows.** Indexing a commit where no files changed = 330 junction table inserts (trivially fast).

### Schema

#### `commit_files` (new junction table)
```sql
CREATE TABLE commit_files (
    commit_id  INTEGER NOT NULL REFERENCES commits(id) ON DELETE CASCADE,
    file_id    INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    PRIMARY KEY (commit_id, file_id)
);
CREATE INDEX ix_commit_files_file_id ON commit_files(file_id);
```

#### `files` (changed)
- `commit_id` column **removed** — files are versions, not file-at-commit
- Unique constraint: `UNIQUE(repository_id, path, content_hash)`

#### `symbols` and `references` (changed)
- `commit_id` column **removed** — commit context comes through `commit_files` JOIN

#### `text_contents` (changed)
- `commit_id` made **nullable** — still used for commit messages, not needed for file-derived text

### Query Patterns

| Query | How |
|-------|-----|
| Files at commit X | `JOIN commit_files WHERE commit_id = X` |
| Latest files on branch | Get latest commit on branch, then JOIN commit_files |
| Symbols at commit X | `symbols JOIN commit_files ON file_id WHERE commit_id = X` |
| File history (versions) | `DISTINCT file versions JOIN commit_files` |
| Reference resolution | `GROUP BY` on symbol name — no commit_id needed (symbols are unique per file version) |

Window function queries (`ROW_NUMBER() OVER PARTITION BY path`) are replaced by simple JOINs through `commit_files`. With full snapshot indexing, every commit has its complete file tree in the junction table.

### Performance Expectations

| Metric | HEAD only | 929 commits (old) | 929 commits (new) |
|--------|-----------|--------------------|--------------------|
| File rows | 329 | ~306K | ~350 versions + ~306K junction |
| Symbol rows | ~4K | ~3.7M | ~4K |
| Reference rows | ~19K | ~17.4M | ~19K |
| DB size | ~19 MB | est. >1 GB | est. ~25 MB |
| Indexing time | ~24s | est. ~15 hours | est. <5 min |

---

## Implementation Phases

### Phase 1: Schema Migration + Domain Entities

- Alembic migration: create `commit_files`, drop `commit_id` from `files`/`symbols`/`references`, add unique constraint on files, make `text_contents.commit_id` nullable
- Update domain entities (`File`, `Symbol`, `Reference`): remove `commit_id`
- Update ORM models and mappers
- New `CommitFileModel` with composite PK
- **Requires `db reset` before running** (breaking schema change)

### Phase 2: Repository Ports + Adapters

- `FileRepositoryPort`: add `find_or_create_version`, `link_file_to_commit`; remove `copy`/`cache` methods; rewrite temporal queries to use `commit_files` JOIN
- `SymbolRepositoryPort`: remove `copy_symbols_to_file`; update search queries
- `ReferenceRepositoryPort`: remove `copy_references_to_file`; update resolution queries
- Simplify or remove `_latest_file_query.py` (window functions no longer needed)

### Phase 3: Indexing Use Cases

- Delete `OptimizeFileIndexingUseCase` (no longer needed — no copying)
- Rewrite `ProcessFileUseCase`: check-or-create file version, parse only new versions
- Simplify `ProcessCommitUseCase`: bulk-insert `commit_files` links
- Simplify `DefaultOrchestrator`: remove content hash cache, blob-to-content-hash dict
- Fix [#35](https://github.com/pwiereng/inxr2/issues/35): replace hardcoded `_detect_language()` (9 extensions) with `LanguageDetector.detect()` (60+ extensions)

### Phase 4: CLI + Rendering

- Update `IndexingStats`: replace reuse metrics with file version metrics
- Update summary table display

### Phase 5: Tests

- Update test doubles, unit tests, and adapter tests for new schema
- Test idempotency, file version dedup, commit_files linking

### Phase 6: API Layer

- Update queries that filter by commit to join through `commit_files`
- Most API changes transparent (File objects still have path, language, etc.)

## Code Simplifications

The new model eliminates significant complexity:

| Removed | Reason |
|---------|--------|
| `OptimizeFileIndexingUseCase` | No symbol/reference copying needed |
| `copy_symbols_to_file` / `copy_references_to_file` | Symbols/refs stored once per file version |
| `_detect_language` hardcoded map | Replaced by `LanguageDetector` (fixes #35) |
| `_fast_reuse` / `_reuse_from_donor` | Replaced by `find_or_create_version` |
| Content hash cache + blob-to-content-hash dict | File version lookup replaces these |
| `_latest_file_query.py` window functions | Simple `commit_files` JOINs instead |
| `find_one_by_content_hash_in_repo` | Replaced by unique constraint + find_or_create |
| `get_content_hash_to_file_id_map` | No longer needed |

## Verification

1. `db reset` + `alembic upgrade head`
2. `pytest --cov=src --cov-report=term-missing` — all tests pass
3. `mypy src/ tests/` — clean
4. `black . && isort .` — formatted
5. `inxr2 index --config config.yaml` — HEAD only, works as before
6. `inxr2 index --config config.yaml --days 10` — completes in minutes, not hours
7. Run again — completes in seconds (all file versions cached, all commits skipped)
8. Browse older commits in UI — time-travel still works
