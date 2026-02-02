# TODO: Test Database Isolation

**Created:** 2026-02-02
**Source:** PR #18 review comments

---

## Issue

CLI tests in `tests/adapters/cli/test_cli.py` (class `TestBranchActivityFiltering`) invoke actual indexing commands that hit the live database. This was flagged as violating the database isolation principle documented in CLAUDE.md.

### Affected Tests

- `test_old_branch_skipped_with_days_filter`
- `test_all_branches_indexed_without_days_filter`
- `test_primary_branch_always_indexed_with_days_filter`
- `test_primary_branch_with_recent_commits_uses_days_filter`
- `test_primary_branch_no_recent_commits_falls_back_to_head`

### Current Mitigation

- Tests use unique temp repo paths (`test-repo`, `primary-old-test`) that won't collide with real repos
- Tests only verify CLI output text, not database state
- If indexing fails due to DB issues, tests still pass if output format is correct

---

## Options

### Option 1: Keep As-Is (Current)
**Effort:** None
**Isolation:** Partial

The current mitigation is adequate for what we're testing (CLI output formatting and branch filtering logic).

**Pros:**
- No changes needed
- Tests are fast and simple

**Cons:**
- Accumulates test data in DB over time
- Theoretically could cause issues if test repo names collide with real ones

### Option 2: Add Cleanup Fixture
**Effort:** Low
**Isolation:** Partial (with cleanup)

Add teardown fixture to delete test repos from DB after tests complete.

```python
@pytest.fixture(autouse=True)
def cleanup_test_repos(self):
    yield
    # Delete test repos from DB
    # Would need async DB access in fixture
```

**Pros:**
- Keeps DB clean
- Minimal code change

**Cons:**
- Adds complexity to test fixtures
- Still touches live DB during test

### Option 3: Mock Database Layer
**Effort:** High
**Isolation:** Full

Refactor CLI to accept injected repositories, then mock them in tests.

**Pros:**
- True isolation
- Tests never touch DB

**Cons:**
- Significant refactoring of CLI code
- Over-engineering for output format tests
- Mocking violates project philosophy (prefer fakes)

### Option 4: Separate Test Database
**Effort:** Medium
**Isolation:** Full

Use `DATABASE_URL` env var to point to a dedicated test database.

```python
@pytest.fixture
def runner(self) -> CliRunner:
    return CliRunner(env={"DATABASE_URL": "postgresql://...test_db..."})
```

**Pros:**
- True isolation
- No code changes to CLI
- Best practice for CI/CD

**Cons:**
- Requires test DB infrastructure
- More complex local dev setup

---

## Recommendation

**Short term:** Keep Option 1 (current mitigation is adequate)

**If issues arise:** Implement Option 2 (cleanup fixture)

**For CI/CD:** Consider Option 4 (separate test DB) when setting up automated pipelines

---

## Related PR Review Comments

Also noted in PR #18 but not requiring action:

1. **base_branch optimization scope** - Only applies when multiple branches defined in YAML config, not with `--branch` CLI override. This is intentional behavior.

2. **--branch override makes branch "primary"** - When using `--branch feature-x`, that branch is treated as primary and always indexed. This seems correct (explicit branch = user wants it indexed).
