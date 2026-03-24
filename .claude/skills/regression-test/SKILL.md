---
name: regression-test
description: "Runs the full regression test suite: resets DB, re-indexes all repos, starts services, then runs all 75 browser/indexing/MCP tests via the QA agent. Runs autonomously without prompting."
user-invocable: true
argument-hint: "[optional: 'indexing' or 'browser' to run only one phase]"
---

# Regression Test Skill

Runs the full regression test suite (75 tests) autonomously. See `docs/regression-tests.md` for detailed test procedures.

## CRITICAL: Autonomy Rule

**Run ALL steps without asking for confirmation.** Do NOT prompt the user between tests. Only stop if something fatally fails (e.g., container not running, database unreachable). Warnings and individual test failures should be logged and continued past.

## Phase Selection

Check `$ARGUMENTS`:
- **No argument or empty** → Run both Phase 1 (Indexing) and Phase 2 (Browser)
- **`indexing`** → Run only Phase 1
- **`browser`** → Run only Phase 2 (skip re-indexing, assume data exists)

## Container and Port Detection

Detect the correct container name and ports for the current environment (main or worktree):

```bash
# Detect container name
if [ -f .env ]; then
  CONTAINER=$(grep COMPOSE_CONTAINER_PREFIX .env | cut -d= -f2)-dev
else
  CONTAINER=inxr2-dev
fi

# Detect ports from .env or use defaults
BACKEND_PORT=$(grep APP_PORT .env 2>/dev/null | cut -d= -f2 || echo 8000)
FRONTEND_PORT=$(grep FRONTEND_PORT .env 2>/dev/null | cut -d= -f2 || echo 5173)
QA_PORT=$(grep QA_PORT .env 2>/dev/null | cut -d= -f2 || echo 9222)
```

Use `$CONTAINER`, `$BACKEND_PORT`, `$FRONTEND_PORT`, and `$QA_PORT` in all commands throughout the run. For `docker exec` commands, use `$CONTAINER` instead of hardcoded `inxr2-dev`. For curl commands to the QA agent, use `localhost:$QA_PORT`. For API calls inside the container, always use `localhost:8000` (internal port).

**QA agent browser URLs:** The QA agent's browser runs inside a separate container. When telling it to navigate to the frontend, use `host.docker.internal` instead of `localhost`:

```bash
# Issuing commands TO the QA agent (localhost is fine — QA API port is mapped to host)
curl "http://localhost:$QA_PORT/navigate?url=..."

# URLs the QA agent's BROWSER navigates to (must use host.docker.internal)
curl "http://localhost:$QA_PORT/navigate?url=http://host.docker.internal:$FRONTEND_PORT/"
```

This is because `localhost` inside the playwright container refers to itself, not the host. All `docker exec` commands still use `localhost` since the backend listens inside the dev container.

## Browse URL Format

**Critical:** Browse URLs always use this exact structure:

```
/browse/{repo}/{filepath}?branch={branch}
```

- The **file path** goes in the URL path (no branch prefix)
- The **branch** goes in `?branch=` query param — NEVER as a path segment

```bash
# CORRECT
curl "http://localhost:$QA_PORT/navigate?url=http://host.docker.internal:$FRONTEND_PORT/browse/inxr2/src/inxr2/domain/entities.py?branch=main"

# WRONG — "main" must not be a path segment
curl "http://localhost:$QA_PORT/navigate?url=http://host.docker.internal:$FRONTEND_PORT/browse/inxr2/main/src/inxr2/domain/entities.py"
```

Before issuing any navigate command, verify the URL matches the correct pattern.

## Result Tracking

Maintain a running tally of results. For each test:
- Record: test ID, PASS/FAIL, brief reason if failed
- On failure: take a screenshot (`curl "http://localhost:$QA_PORT/screenshot/save?path=/tmp/rt-fail-<ID>.png"`) for browser tests
- Continue to the next test (do NOT stop on failure)

## Failure Capture — Precise Reproduction Steps

When a test fails, record the **full sequence of steps that led to the failure**, not just the failure itself. This is critical for creating actionable bug reports.

For each failure, capture:

1. **Exact DISCOVER output** — the raw output of every API/git command that produced the values used in the failing step (e.g., the actual repo name, file path, branch name, commit hash that was substituted)

2. **Exact commands issued** — the literal curl/docker commands, with all `<placeholders>` fully substituted with the real values used

3. **Exact observed output** — full response body, URL after navigation, visible page text, screenshot path

4. **Expected vs actual** — what should have happened, what did happen

Example failure record format:
```
FAIL RT-06 — Code Viewer Shows Correct File Content

DISCOVER output:
  repo = inxr2
  file = src/inxr2/domain/entities.py
  branch = main
  line count (docker exec $CONTAINER bash -c "git -C /repos/test-repos/inxr2 show main:src/inxr2/domain/entities.py | wc -l"): 142

Commands issued (ports already substituted: QA_PORT=9222, FRONTEND_PORT=5173):
  curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/browse/inxr2/src/inxr2/domain/entities.py?branch=main"
  curl "http://localhost:9222/wait?selector=table&timeout=5000"
  curl "http://localhost:9222/elements?selector=tr[data-line]&limit=5"

Observed:
  navigate: {"status": "ok"}
  wait: timed out after 5000ms — selector "table" not found
  page text: "File not found"
  screenshot: /tmp/rt-fail-RT-06.png

Expected: 142 table rows with file content
Actual: Page shows "File not found" error
```

The goal is that any developer reading the failure record can reproduce it exactly from the captured steps without needing to re-run the test suite.

---

## Phase 1: Indexing Regression (7 tests)

### Prerequisites Check

Verify the dev container is running:
```bash
docker exec $CONTAINER echo "Container OK"
```
If this fails, stop and report — the container must be running.

### IX-01: Reset Database and Index All Repos

```bash
docker exec $CONTAINER inxr2 index --config config.yaml --reset-db --yes --days 10
```

**Pass:** Command completes without fatal errors. Output shows files processed, symbols extracted, references found.

### IX-02 through IX-05

Follow the detailed steps in `docs/regression-tests.md` for each test:

- **IX-02:** Run `inxr2 status`, verify repo count matches `config.yaml`, all have non-zero counts
- **IX-03:** Verify API (`curl -s http://localhost:8000/api/repositories` and `/api/repositories/stats`), cross-reference against `config.yaml`
- **IX-04:** For each of the 10 languages (Python, TypeScript, JavaScript, C, C++, Java, C#, Go, Ruby, Bash), discover a real symbol from git and verify it appears in the API
- **IX-04a:** Verify reference extraction — bare identifiers, CommonJS `require()`, constructor `this.property`
- **IX-04b:** Verify ES6 export/re-export references — named re-exports, local exports, default export of identifier, barrel re-exports
- **IX-05:** Read `index.log`, compare current run against previous run for each repo+branch. Flag: elapsed >20% increase, symbol count decrease, reference resolution % decrease

---

## Phase 2: QA Browser Regression (29 tests)

### Prerequisites Check

1. Start backend if not running:
   ```bash
   docker exec -d $CONTAINER inxr2 serve --reload
   ```

2. Start frontend if not running:
   ```bash
   docker exec -d -w /workspace/frontend $CONTAINER npm run dev
   ```

3. Start QA agent if not running:
   ```bash
   docker compose -f docker-compose.dev.yml --profile qa up -d playwright
   ```

4. Verify all services:
   ```bash
   # Wait for services to be ready
   sleep 5
   docker exec $CONTAINER curl -sf http://localhost:8000/api/repositories > /dev/null && echo "Backend OK"
   curl -sf http://localhost:$QA_PORT/health && echo "QA Agent OK"
   ```

If QA agent is not running and cannot be started, stop Phase 2 and report.

### RT-01 through RT-23

Run all 29 browser tests following the detailed Discover → Navigate → Verify steps in `docs/regression-tests.md`:

| Tests | Area | Key Commands |
|-------|------|-------------|
| RT-01 to RT-03 | Home page | Repo cards, stats, navigation |
| RT-04 to RT-05 | File tree | `git ls-tree` comparison |
| RT-06 to RT-07 | Code viewer | File content, line numbers |
| RT-08 to RT-10 | References | Symbol click, panel, search link |
| RT-11 | Blame | `git blame` comparison |
| RT-12, RT-12a, RT-12b | Diff mode | Enter/exit, colors, version selectors |
| RT-13 to RT-16, RT-16a | Search | Keyword, regex, file, extensionless |
| RT-17 to RT-18 | History | `git log` comparison, commit click |
| RT-19 | Navigation | Tab context preservation |
| RT-20 | Branches | Branch selector |
| RT-21 | URL state | Reload preservation |
| RT-22, RT-22a | Theme | Toggle, diff colors in both themes |
| RT-23 | Markdown | Heading rendering |

For each test, use `curl http://localhost:$QA_PORT/...` for all browser interactions. Use `docker exec $CONTAINER ...` for git/API commands.

---

## Final Report

After all tests complete, output a summary:

```
## Regression Test Results

### Phase 1: Indexing (X/7 passed)
| ID | Test | Result |
|----|------|--------|
| IX-01 | Reset DB and index | PASS/FAIL |
| IX-02 | Verify status | PASS/FAIL |
| ... | ... | ... |

### Phase 2: Browser (X/29 passed)
| ID | Test | Result |
|----|------|--------|
| RT-01 | Home page repo cards | PASS/FAIL |
| RT-02 | Repo card stats | PASS/FAIL |
| ... | ... | ... |

### Phase 3: MCP Server (X/18 passed)
| ID | Test | Result |
|----|------|--------|
| MCP-01 | List repos | PASS/FAIL |
| MCP-13 | Find dead code | PASS/FAIL |
| MCP-15 | Review helper blast radius | PASS/FAIL |
| ... | ... | ... |

### Summary
- Indexing: X/7 passed
- Browser: X/29 passed
- MCP: X/18 passed
- **Total: X/54 passed**
- Failed: [list failures with ID and brief reason]
- Screenshots: [list screenshot paths for any failures]
```

If all pass: **"Regression suite: 54/54 passed (7 indexing + 29 browser + 18 MCP)."**

### Performance Comparison (from IX-05)

Include the indexing performance table:
```
| Repo | Branch | Elapsed (prev -> now) | Symbols (prev -> now) | Refs Resolved % |
|------|--------|-----------------------|-----------------------|-----------------|
| ... | ... | ... | ... | ... |
```

---

## Save Report to Docs

After outputting the final report to the user, **always** save it as a dated markdown file under `docs/`:

```bash
DATE=$(date +%Y-%m-%d)
REPORT_PATH="docs/regression-report-${DATE}.md"
```

Write the file using the Write tool (not bash echo/heredoc). The file must follow this structure exactly, matching the format of `docs/regression-report-2026-03-08.md`:

```markdown
# Regression Test Report — <YYYY-MM-DD>

## Summary

| Phase | Passed | Total | Notes |
|-------|--------|-------|-------|
| Indexing | X | 7 | |
| Browser | X | 29 | X skipped (list IDs) |
| MCP | X | 18 | X failed (list IDs) |
| **Total** | **X** | **54** | **X skipped, X failed** |

---

## Phase 1: Indexing (X/7 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| IX-01 | Reset DB and index all repos | PASS | <key stats: repo count, file count, line count, resolution %, elapsed> |
| IX-02 | Verify indexing status | PASS/FAIL | |
| IX-03 | Verify API serves indexed data | PASS/FAIL | |
| IX-04 | Multi-language symbols (10 langs) | PASS/FAIL | |
| IX-04a | Reference extraction | PASS/FAIL | |
| IX-04b | ES6 export/re-export references | PASS/FAIL | |
| IX-05 | Performance comparison | PASS/FAIL | |

### IX-05 Performance Comparison

| Repo | Branch | Elapsed (prev → now) | Symbols | Refs Resolved % |
|------|--------|---------------------|---------|-----------------|
| <repo> | <branch> | <prev>s → <now>s (<delta>%) | <count> (=/<delta>) | <pct>% |
...

---

## Phase 2: Browser (X/29 passed, X skipped)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| RT-01 | Home page repo cards | PASS/FAIL/SKIP | |
...

---

## Phase 3: MCP Server (X/18 passed)

| ID | Test | Result | Notes |
|----|------|--------|-------|
| MCP-01 | List repos | PASS/FAIL | |
...

### <ID> Failure Details  ← include only for failing tests

<Root cause and reproduction steps>

---

## Known Issues / Observations

<Numbered list of any notable observations, even from passing tests>
```

After writing the file, `git add` it so it's staged for the user to commit:

```bash
git add docs/regression-report-${DATE}.md
```

Then report the path to the user:
```
📄 Report saved to docs/regression-report-<DATE>.md (staged, ready to commit)
```
