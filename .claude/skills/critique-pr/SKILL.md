---
name: critique-pr
description: "Independent code review of a PR authored by another Claude session. Reads the diff, reviews for bugs/architecture/tests/style, and posts comments directly to the GitHub PR. On re-runs, checks whether prior review comments were addressed and posts a follow-up verdict. Does NOT fix anything."
user-invocable: true
argument-hint: "<PR number>"
---

# Independent PR Review Skill

You are a **code reviewer**, not the author. Your job is to find problems and post them as GitHub PR comments. Do NOT fix anything. Do NOT commit anything. Do NOT run tests.

## Step 1: Get PR Number

Read the PR number from `$ARGUMENTS`. If not provided, run:
```bash
gh pr list --state open --json number,title,headRefName
```
and ask the user which PR to review.

## Step 2: Detect Mode — First Review or Re-review

Check whether you have already posted a review on this PR:

```bash
PR=$ARGUMENTS
gh pr view $PR --json reviews --jq '.reviews[] | select(.author.login == "pwiereng") | {id, submittedAt, state}'
```

- **No prior reviews from you** → run **First Review Mode** (Steps 3–7)
- **Prior reviews exist** → run **Re-review Mode** (Steps 3R–7R)

---

## FIRST REVIEW MODE

## Step 3: Fetch PR Context

```bash
# PR metadata
gh pr view $PR --json number,title,body,headRefName,headRefOid,baseRefName,additions,deletions,changedFiles

# Files changed
gh pr view $PR --json files --jq '.files[].path'

# Full diff
gh pr diff $PR
```

Read the PR title and description carefully — the description explains intent.

## Step 4: Read Relevant Source Files

For each changed file, read the **full file** (not just the diff) from the PR branch to understand context:
- What class/module does it belong to?
- What layer of Clean Architecture is it in?
- What are the surrounding functions doing?

Also read related files the changes interact with (e.g., if a use case changes, read its port interface and callers).

Use MCP tools when helpful:
```bash
docker exec inxr2-dev bash -c '
cd /workspace/mcp-server && python -c "
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def call(tool, args):
    async with sse_client(\"http://localhost:3000/sse\") as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool(tool, args)
            print(res.content[0].text)

asyncio.run(call(\"find_references\", {\"name\": \"SymbolName\", \"repository\": \"inxr2\"}))
"'
```

## Step 5: Review — What to Look For

Review each changed file systematically. Flag issues in these categories:

### Bugs & Correctness
- Off-by-one errors, wrong conditions, incorrect logic
- Unhandled edge cases (empty lists, None values, empty strings)
- Race conditions or ordering issues
- Wrong variable used (copy-paste errors)
- Incorrect type handling (e.g., treating `str | None` as `str`)

### Architecture (Clean Architecture)
- Domain layer importing from adapters, infrastructure, or frameworks
- Use cases directly instantiating infrastructure classes (should use dependency injection)
- Business logic leaking into API controllers or persistence adapters
- Domain entities confused with ORM models (use mappers, not direct assignment)
- Ports violated — adapter implementing more than its port specifies

### Tests
- Missing tests for the new behavior
- Tests that only test happy path, missing edge cases
- Tests that mock instead of using fakes (project rule: no mocking)
- Tests that depend on external state (filesystem, live DB) instead of `tmp_path` or `TEST_DATABASE_URL`
- Regression tests missing for bug fixes (project rule: every bug fix needs a regression test)

### Type Safety
- Python: missing type hints, use of `Any` where a proper type exists, mypy violations
- TypeScript: use of `any`, missing null checks on indexed access, assertions hiding actual types
- Return types that are broader than necessary

### Error Handling
- Exceptions swallowed silently
- Generic `except Exception` without re-raise or proper logging
- API endpoints returning 200 with an error string instead of a proper HTTP error status
- Missing validation at system boundaries (user input, external API responses)

### Security
- SQL injection via string concatenation (use parameterized queries)
- Path traversal (unsanitized file paths from user input)
- Information leakage in error messages (stack traces, internal paths)
- Missing authorization checks

### Code Quality
- Functions doing too many things (should be split)
- Duplicated logic that should be shared
- Magic numbers/strings that should be named constants
- Misleading variable or function names

## Step 6: Draft Review Comments

For each issue found, prepare an inline comment:
- **File path** (relative to repo root)
- **Line number** (use the new file's line number — verify against the PR branch with `git show origin/<branch>:<file> | grep -n ...`)
- **Comment body**: be specific and constructive. Describe the problem. Do NOT provide the fix.

Also prepare an **overall review summary** (1-3 paragraphs).

## Step 7: Post Review to GitHub

```bash
HEAD_SHA=$(gh pr view $PR --json headRefOid --jq '.headRefOid')
```

Post using the GitHub API with a JSON input file (use `--input` to avoid shell quoting issues with multi-line bodies):

```bash
gh api repos/pwiereng/inxr2/pulls/$PR/reviews \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  --input /workspace/.tmp/pr${PR}-review.json
```

Where the JSON file contains:
```json
{
  "commit_id": "<HEAD_SHA>",
  "body": "<OVERALL SUMMARY>",
  "event": "COMMENT",
  "comments": [
    {"path": "src/inxr2/foo.py", "line": 42, "body": "<COMMENT>"},
    {"path": "src/inxr2/bar.py", "line": 17, "body": "<COMMENT>"}
  ]
}
```

**Important:**
- `event` must be `"COMMENT"` — never `"REQUEST_CHANGES"` or `"APPROVE"`
- Line numbers must be lines present in the diff (added or unchanged context lines)
- If a line number is rejected (422 error), verify with `git show origin/<branch>:<file> | grep -n` and adjust
- Save the JSON to `.tmp/pr${PR}-review.json` in the project root (gitignored)

Verify after posting:
```bash
gh pr view $PR --json reviews --jq '.reviews[-1]'
```

Report to the user:
```
---
🔍 **Code Review posted on PR #<number>:** <url>
   <N> inline comments | event: COMMENT
   Top issues: <1-line summary>
```

---

## RE-REVIEW MODE

Triggered when prior reviews from you already exist on this PR.

## Step 3R: Fetch Prior Review Comments

Retrieve everything you previously flagged:

```bash
# Get all review comment bodies you posted (inline comments)
gh api repos/pwiereng/inxr2/pulls/$PR/comments \
  --jq '[.[] | select(.user.login == "pwiereng") | {id, path, line, body, created_at}]'

# Get your prior review bodies (overall summaries)
gh pr view $PR --json reviews \
  --jq '[.reviews[] | select(.author.login == "pwiereng") | {id, body, submittedAt}]'
```

Build a list of every distinct issue you raised, with the file/line it was on.

## Step 4R: Fetch the Updated Diff

```bash
gh pr diff $PR
gh pr view $PR --json headRefOid --jq '.headRefOid'
```

For each file touched by your prior comments, read the **current version** of that file from the PR branch:
```bash
git show origin/<headRefName>:<file_path>
```

## Step 5R: Assess Each Prior Issue

For every issue you previously raised, determine one of:

- ✅ **Addressed** — the problem is gone or the feedback was acted on in a reasonable way
- ⚠️ **Partially addressed** — something changed but the concern is not fully resolved; explain what remains
- ❌ **Not addressed** — the code is unchanged or the fix introduces a new problem; explain concisely

## Step 5bR: Fresh Full Scan

Treat the PR as if you are seeing it for the first time. Re-read the **full diff** and all changed files end-to-end with fresh eyes — do not rely on memory of the first review. Apply the same checklist from Step 5 (Bugs, Architecture, Tests, Type Safety, Error Handling, Security, Code Quality) across the entire change set.

The goal is to catch anything that was missed in the first review pass, regardless of whether it was introduced before or after the fix commits. Flag any issues found here as new findings in the re-review body.

## Step 6R: Post Follow-up Review

Post a single follow-up review that:

1. **Opens with a clear verdict**: one of:
   - ✅ "All prior review comments have been addressed. The PR looks good to merge."
   - ⚠️ "Some issues remain. See below."
   - ❌ "The prior issues have not been addressed. See below."

2. **Lists each prior issue with its status** (✅ / ⚠️ / ❌ and a one-line explanation)

3. **Flags any new issues** introduced since the last review (treat these like first-review inline comments)

Post via the API (same method as Step 7 above, using a fresh JSON file):
```bash
gh api repos/pwiereng/inxr2/pulls/$PR/reviews \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  --input /workspace/.tmp/pr${PR}-rereview.json
```

Inline comments in the re-review should only be added for **new issues** introduced after the last review. For prior issues, the verdict goes in the overall review body (not as new inline comments on old lines).

## Step 7R: Report to User

```
---
🔄 **Re-review posted on PR #<number>:** <url>
   Verdict: <✅ Looks good / ⚠️ Some issues remain / ❌ Issues not addressed>
   Prior issues: <N> addressed, <N> partial, <N> unresolved
   New issues: <N> (or "none")
```

---

## Constraints (all modes)

- **DO NOT** run `./scripts/run-all-tests.sh` or any tests
- **DO NOT** edit any files
- **DO NOT** commit or push anything
- **DO NOT** approve or request changes — always use `event: "COMMENT"`
- **DO NOT** summarize without substance — every review must contain a verdict with reasoning
- If you find no issues (first review) or all issues are resolved (re-review), say so explicitly and explain why
