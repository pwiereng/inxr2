---
name: critique-pr
description: "Independent code review of a PR authored by another Claude session. Uses the code-review skill as its finding engine, adds inxr2-specific supplemental agents, scores issues by confidence, and posts inline comments via the GitHub Reviews API. On re-runs, checks whether prior review comments were addressed and posts a follow-up verdict. Does NOT fix anything."
user-invocable: true
argument-hint: "<PR number>"
---

# Independent PR Review Skill

You are a **code reviewer**, not the author. Your job is to find problems and post them as GitHub PR inline comments via the Reviews API. Do NOT fix anything. Do NOT commit anything. Do NOT run tests.

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

- **No prior reviews from you** → run **First Review Mode** (Steps 3–8)
- **Prior reviews exist** → run **Re-review Mode** (Steps 3R–8R)

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

## Step 4: Generate Findings

The finding engine is the **`code-review` skill** plus three inxr2-specific supplemental
agents that `code-review` does not cover. Run both, then merge their issues into one list
using the format below:

```
ISSUE: <one-line description>
FILE: <path>
LINE: <line number in the new file, or 0 if file-level>
CATEGORY: <Bugs|Architecture|Tests|TypeSafety|ErrorHandling|Security|CodeQuality|History>
DETAIL: <specific evidence — quote the problematic code>
```

### Step 4A — Run the code-review skill as the primary engine

Invoke the `code-review` skill (`Skill` tool, name `code-review:code-review`, args = the PR
number). It launches parallel review agents (CLAUDE.md compliance, bug scan, git blame/history,
prior-PR comments, code-comment adherence) and scores each finding 0–100 for confidence.

**Use it as the engine only — do NOT let it post.** Run its review + scoring methodology
(its steps 3–6) and **capture the surviving scored findings**, but STOP before its final
posting step (its step 8 `gh pr comment`) — critique-pr owns posting (Step 7, inline via the
Reviews API). Likewise ignore its eligibility-skip: the user explicitly invoked critique-pr,
so proceed even if code-review would skip a "trivial" PR. Convert each surviving finding into
the ISSUE format above, keeping its confidence score.

### Step 4B — Supplemental inxr2 agents (not covered by code-review)

Launch these three agents in parallel. Each receives the PR number, full diff, changed-file
list, and PR description, and returns issues in the ISSUE format above.

**Supplement 1 — Clean Architecture**

Reads the changed files in full (not just diff) from the PR branch:
```bash
git show origin/<headRefName>:<file_path>
```

Looks for:
- Domain layer importing from adapters, infrastructure, or frameworks
- Use cases directly instantiating infrastructure classes (should use dependency injection)
- Business logic leaking into API controllers or persistence adapters
- Domain entities confused with ORM models — use mappers, not direct assignment
  - Domain entities use field `metadata` (dict); ORM models use `extra_metadata` (JSONB)
- Ports violated — adapter implementing more than its port specifies
- Error handling: exceptions swallowed silently, generic `except Exception` without re-raise
- API endpoints returning 200 with an error string instead of a proper HTTP status
- SQL injection via string concatenation (use parameterized queries)
- Path traversal (unsanitized file paths from user input)

**Supplement 2 — Test Quality**

Reads the test files changed and the code they test. Looks for:
- Missing tests for new behavior — every code change needs a test
- Tests that only cover the happy path, missing edge cases
- Tests that use `mock`/`patch`/`MagicMock` — project rule: **no mocking, use fakes**
- Tests that depend on external filesystem repos or real git history — use `tmp_path`
- Tests that touch the live database instead of `TEST_DATABASE_URL` / `inxr2_test` DB
- Bug fixes without a regression test — project rule: **every bug fix needs a regression test**
- Missing test for the specific scenario the PR describes fixing

**Supplement 3 — MCP Navigation (blast radius)**

Uses inxr2 MCP tools to check the blast radius of changed symbols:

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

asyncio.run(call(\"get_change_impact\", {\"name\": \"ChangedSymbol\", \"repository\": \"inxr2\"}))
"'
```

For each non-trivial symbol modified (function signature, class, type alias):
- Run `get_change_impact` — flags if callers are not updated
- Run `find_references` — checks for call sites that may be broken

### Step 4C — Merge

Combine the code-review findings (Step 4A) with the supplemental findings (Step 4B) into one
list. De-duplicate: if code-review and a supplement flag the same file+line concern, keep one
(prefer the entry with the more specific evidence). code-review findings arrive pre-scored;
supplemental findings are scored next in Step 5.

## Step 5: Score Issues by Confidence

code-review findings (Step 4A) already carry a confidence score — reuse it. Score only the
**supplemental** findings (Step 4B) here.

For each supplemental issue (Step 4B), launch a parallel **Haiku agent** to score it:

Give each Haiku agent the issue description, the relevant code snippet, and this scoring rubric verbatim:

```
Score on 0–100:
0:   False positive. Doesn't stand up to scrutiny, or is a pre-existing issue unrelated to this PR.
25:  Might be real but unverified. Stylistic issue not explicitly required by CLAUDE.md.
50:  Real but minor — a nitpick, or happens rarely in practice.
75:  Verified real issue. Very likely to be hit in practice. Important for functionality or
     explicitly required by CLAUDE.md or project rules (no mocking, regression tests, etc.).
100: Definitely a real issue. Happens frequently. Evidence is direct and unambiguous.
```

**False positives to filter:**
- Pre-existing issues not touched by this PR
- Something that looks like a bug but is not
- Issues a linter/typechecker/formatter would catch (assume CI handles those)
- CLAUDE.md issues that are silenced in the code (e.g., a lint ignore comment with justification)
- Changes in functionality that are clearly intentional per the PR description

**Filter:** Drop any issue with a score < 75. If nothing remains, the PR has no significant issues.

## Step 6: Verify Line Numbers

For each surviving issue with a specific line number:
```bash
git show origin/<headRefName>:<file_path> | grep -n "<code snippet>"
```
Line numbers must exist in the diff (added lines or unchanged context lines). Adjust if needed.

## Step 7: Draft and Post Review

For each issue, prepare an inline comment:
- **File path** (relative to repo root)
- **Line number** (verified in Step 6)
- **Comment body**: specific and constructive. Describe the problem. Do NOT provide the fix. End with:
  ```
  ---
  🤖 *Automated review via [critique-pr](https://github.com/pwiereng/inxr2/blob/main/.claude/skills/critique-pr/SKILL.md) (Claude)*
  ```

Prepare an **overall review summary** (1–3 paragraphs). End with:
```
---
🤖 *Automated review via [critique-pr](https://github.com/pwiereng/inxr2/blob/main/.claude/skills/critique-pr/SKILL.md) (Claude)*
```

Post using the GitHub Reviews API with a JSON input file:

```bash
HEAD_SHA=$(gh pr view $PR --json headRefOid --jq '.headRefOid')
```

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

```bash
gh api repos/pwiereng/inxr2/pulls/$PR/reviews \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  --input /workspace/.tmp/pr${PR}-review.json
```

**Important:**
- `event` must be `"COMMENT"` — never `"REQUEST_CHANGES"` or `"APPROVE"`
- Save JSON to `.tmp/pr${PR}-review.json` in the project root (gitignored)
- If a line number is rejected (422 error), verify with `git show origin/<branch>:<file> | grep -n` and adjust

Verify after posting:
```bash
gh pr view $PR --json reviews --jq '.reviews[-1]'
```

## Step 8: Report to User

```
---
🔍 **Code Review posted on PR #<number>:** <url>
   <N> inline comments | event: COMMENT
   Engine: code-review skill + 3 inxr2 supplements, <M> issues found, <K> survived confidence filter (≥75)
   Top issues: <1-line summary>
```

---

## RE-REVIEW MODE

Triggered when prior reviews from you already exist on this PR.

## Step 3R: Fetch Prior Review Comments

```bash
# Inline comments you posted
gh api repos/pwiereng/inxr2/pulls/$PR/comments \
  --jq '[.[] | select(.user.login == "pwiereng") | {id, path, line, body, created_at}]'

# Overall review summaries you posted
gh pr view $PR --json reviews \
  --jq '[.reviews[] | select(.author.login == "pwiereng") | {id, body, submittedAt}]'
```

Build a list of every distinct issue you raised, with file/line.

## Step 4R: Fetch Updated Diff and Files

```bash
gh pr diff $PR
gh pr view $PR --json headRefName,headRefOid
```

For each file touched by prior comments, read the current version:
```bash
git show origin/<headRefName>:<file_path>
```

## Step 5R: Assess Each Prior Issue

For every issue previously raised, determine:
- ✅ **Addressed** — problem is gone or feedback acted on reasonably
- ⚠️ **Partially addressed** — something changed but concern not fully resolved
- ❌ **Not addressed** — code unchanged or fix introduces a new problem

## Step 5bR: Fresh Parallel Scan

Re-run the full finding engine from Step 4 (the `code-review` skill as the primary engine, Step 4A, plus the three supplemental agents, Step 4B) on the current diff, treating the PR as if seen for the first time. Apply the same confidence-scoring pass (Step 5). Any issues surviving the filter that were **not** flagged in the original review are new findings.

## Step 6R: Post Follow-up Review

Post a single follow-up review that:

1. **Opens with a verdict:**
   - ✅ "All prior review comments have been addressed. The PR looks good to merge."
   - ⚠️ "Some issues remain. See below."
   - ❌ "The prior issues have not been addressed. See below."

2. **Lists each prior issue with status** (✅ / ⚠️ / ❌ and one-line explanation)

3. **Flags new issues** (inline comments for new issues only, same format as Step 7)

4. Ends overall body with the attribution footer.

```bash
gh api repos/pwiereng/inxr2/pulls/$PR/reviews \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  --input /workspace/.tmp/pr${PR}-rereview.json
```

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
- If no issues survive the confidence filter, post a clean "no issues found" review explaining what was checked
