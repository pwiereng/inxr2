---
name: critique-pr
description: "Independent code review of a PR authored by another Claude session. Reads the diff, reviews for bugs/architecture/tests/style, and posts comments directly to the GitHub PR. Does NOT fix anything."
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

## Step 2: Fetch PR Context

```bash
PR=$ARGUMENTS

# PR metadata
gh pr view $PR --json number,title,body,headRefName,headSha,baseRefName,additions,deletions,changedFiles

# Files changed (names only for overview)
gh pr view $PR --json files --jq '.files[].path'

# Full diff
gh pr diff $PR
```

Read the PR title and description carefully — the description explains intent.

## Step 3: Read Relevant Source Files

For each changed file, read the **full file** (not just the diff) to understand context:
- What class/module does it belong to?
- What layer of Clean Architecture is it in?
- What are the surrounding functions doing?

Also read related files that the changes interact with (e.g., if a use case changes, read its port interface and any callers).

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

## Step 4: Review — What to Look For

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

## Step 5: Draft Review Comments

For each issue found, prepare an inline comment:
- **File path** (relative to repo root)
- **Line number** (from the diff — use the new file's line number)
- **Comment body**: be specific and constructive. Describe the problem clearly. If it's a rule violation, cite the rule. Do NOT provide the fix — just explain what's wrong and why it matters.

Format your draft internally as:
```
FILE: src/inxr2/foo.py
LINE: 42
ISSUE: The `items` variable is not checked for None before iteration on line 42.
If the API returns null instead of an empty list, this will raise a TypeError.
Per the project's error handling guidelines, validate at system boundaries.
```

Also prepare an **overall review summary** (1-3 paragraphs): what the PR does, general assessment, and a brief overview of the issues found.

## Step 6: Post Review to GitHub

Get the head commit SHA for the review:
```bash
HEAD_SHA=$(gh pr view $PR --json headSha --jq '.headSha')
```

Post a single review with all inline comments using the GitHub API:

```bash
gh api repos/pwiereng/inxr2/pulls/$PR/reviews \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  --field commit_id="$HEAD_SHA" \
  --field body="<OVERALL SUMMARY>" \
  --field event="COMMENT" \
  --field "comments[][path]"="src/inxr2/foo.py" \
  --field "comments[][line]"=42 \
  --field "comments[][body]"="<COMMENT TEXT>" \
  --field "comments[][path]"="src/inxr2/bar.py" \
  --field "comments[][line]"=17 \
  --field "comments[][body]"="<COMMENT TEXT>"
```

**Important notes for posting:**
- Use `--field` (not `-f`) for each array entry so gh handles encoding correctly
- `event` must be `"COMMENT"` (not `"REQUEST_CHANGES"` or `"APPROVE"`) — you are a reviewer, not a gatekeeper
- Line numbers must be lines that appear in the diff (added or unchanged context lines). If a line is not in the diff, use the nearest line that is, and note the actual location in the comment body.
- If the API call fails due to a line not being in the diff, split into separate reviews or adjust line numbers.

If there are too many comments to fit cleanly in one API call, post a second review for the remainder.

## Step 7: Confirm and Report

After posting, verify the review was created:
```bash
gh pr view $PR --json reviews --jq '.reviews[-1]'
```

Report to the user:
- How many inline comments were posted
- A brief summary of the top issues found
- The PR URL for reference

```
---
🔍 **Code Review posted on PR #<number>:** <url>
   <N> inline comments | event: COMMENT
   Top issues: <1-line summary of most important findings>
```

## Constraints

- **DO NOT** run `./scripts/run-all-tests.sh` or any tests
- **DO NOT** edit any files
- **DO NOT** commit or push anything
- **DO NOT** approve or request changes — always use `event: "COMMENT"`
- **DO NOT** summarize what the PR does without also finding something to critique — a review with no comments is not useful
- If you find no issues, post a review saying so explicitly with your reasoning — don't just skip posting
