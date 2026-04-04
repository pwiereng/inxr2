---
name: close
description: "Closes a worktree branch. From a worktree session: merges the PR and closes associated issues. From the main session: tears down the worktree and Docker stack, pulls main, and runs tests. /pr-review must have been run first to push and open the PR."
user-invocable: true
argument-hint: "[branch-name] — required when run from main session, omit when run from within the worktree"
---

# Close Skill

Handles the merge and teardown of a worktree branch. There are two modes depending on where
the skill is invoked.

**Prerequisite:** `/pr-review` must already have pushed the branch and opened a PR before `/close` is run.

## Mode Detection

```bash
BRANCH=$(git branch --show-current)
```

- **`BRANCH` is `main`** → **Mode B (Main Session)**: `$ARGUMENTS` must contain the branch name to close
- **`BRANCH` is a feature/refactor/fix branch** → **Mode A (Worktree Session)**: operates on the current branch

---

## MODE A — Worktree Session

Run `/close` (no argument needed) from inside a worktree session when the work is done.

### Step 1: Verify working tree is clean

```bash
git status --short
git log origin/main..HEAD --oneline
```

- If there are uncommitted changes → stop. Report what is uncommitted and ask the user whether to commit them first or abandon them.
- If there are commits not yet on origin → stop. Tell the user to run `/pr-review` first to push and open the PR.

### Step 2: Find the PR for this branch

```bash
BRANCH=$(git branch --show-current)
gh pr list --head "$BRANCH" --state open --json number,title,url,reviews,body
```

- If **no open PR** → stop. Tell the user: "No open PR found for `$BRANCH`. Run `/pr-review` first, then run `/close` here."
- If **PR exists** → proceed.

### Step 3: Check PR review status

```bash
gh pr view $PR_NUMBER --json reviews,state \
  --jq '.reviews[] | {author: .author.login, state: .state, submittedAt: .submittedAt}'
```

- If no reviews have been posted → warn: "PR #N has no reviews yet. Run `/critique-pr $PR_NUMBER` from the main session before merging." Ask the user: "Merge anyway, wait for review, or cancel?"
- If reviews exist → proceed.

### Step 4: Confirm with user

Display:
```
PR #<number>: <title>
URL: <url>
Reviews: <count> (<states>)
Closes: <issues extracted from PR body>

Merge this PR? (yes / abandon / cancel)
```

- **cancel** → do nothing, exit
- **abandon** → see Abandon Flow below
- **yes** → proceed to Step 5

### Step 5: Merge the PR

```bash
gh pr merge $PR_NUMBER --merge
```

Use `--merge` (not squash, not rebase) — this matches the project's merge convention.

Verify the merge succeeded:
```bash
gh pr view $PR_NUMBER --json state --jq '.state'
# Expect: "MERGED"
```

### Step 6: Verify issues are closed

Extract issue numbers from the PR body (lines matching `Closes #N` or `Fixes #N`):

```bash
gh pr view $PR_NUMBER --json body --jq '.body' | grep -oE '(Closes|Fixes) #[0-9]+' | grep -oE '[0-9]+'
```

For each issue number found:
```bash
gh issue view $ISSUE_NUMBER --json state --jq '.state'
```

- If any issue is still open → close it manually:
  ```bash
  gh issue close $ISSUE_NUMBER --comment "Closed by PR #$PR_NUMBER"
  ```

### Step 7: Report and instruct

```
✅ PR #<number> merged.
   Issues closed: #N, #N
   Branch: <branch>

Now run /close <branch> from the main session to tear down the worktree and Docker stack.
```

### Abandon Flow

If the user chooses to abandon (discard the work without merging):

1. Confirm explicitly: "This will close the PR without merging and delete the branch. All uncommitted and unmerged work will be lost. Type 'abandon' to confirm."
2. If confirmed:
   ```bash
   gh pr close $PR_NUMBER --comment "Abandoning this branch — work not needed."
   ```
3. Tell the user: "Now run /close <branch> from the main session to tear down the worktree."

---

## MODE B — Main Session

Run `/close <branch>` from the main repo session to tear down a completed (or abandoned) worktree.

`$ARGUMENTS` is the branch name, e.g. `mcp-list-repos-staleness`.

### Step 1: Resolve the worktree path

```bash
BRANCH="$ARGUMENTS"
cat ~/.inxr2-worktree-slots | grep "$BRANCH"
```

Derive the worktree path:
```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
WORKTREE_PATH="$(dirname $REPO_ROOT)/wt-inxr2-${BRANCH}"
```

Verify it exists:
```bash
git worktree list | grep "$WORKTREE_PATH"
```

If not found → report: "No active worktree found for branch `$BRANCH`. It may already be deleted." and stop.

### Step 2: Check that the branch is merged into main

```bash
git fetch origin
git branch -r --merged origin/main | grep "$BRANCH"
```

- **Branch IS merged** → proceed to Step 3 (teardown)
- **Branch is NOT merged** → investigate

```bash
gh pr list --head "$BRANCH" --state all --json number,title,state,url | head -5
```

Present the user with what you find and ask:

```
Branch '$BRANCH' is not merged into main.

PR status: <open/closed/none>

Options:
  1. merge   — merge the open PR now, then tear down
  2. abandon — delete the worktree without merging (work is lost)
  3. cancel  — do nothing

What would you like to do?
```

- **merge**: merge the PR (same as Mode A Step 5), then continue to Step 3
- **abandon**: confirm once more ("Type 'abandon' to confirm discarding all work on `$BRANCH`"), then proceed to Step 3
- **cancel**: stop, do nothing

### Step 3: Tear down the worktree

```bash
./scripts/worktree-remove.sh "$BRANCH"
```

This script stops the Docker stack, removes the worktree directory, and releases the slot in `~/.inxr2-worktree-slots`. Verify:

```bash
git worktree list | grep "$WORKTREE_PATH"
# Should return nothing
```

If the script fails (e.g. worktree already deleted, Docker already stopped), note it and continue — partial cleanup is fine.

### Step 4: Pull latest main

```bash
git pull --rebase
git log --oneline -5
```

If rebase fails (conflicting diverged history), report it and stop — do not force-pull.

### Step 5: Run tests

```bash
docker exec inxr2-dev ./scripts/run-all-tests.sh
```

Report:
- ✅ All tests pass — good to go
- ❌ Any failure — show the failing test name(s) and ask the user if they want to investigate

### Step 6: Report

```
---
✅ /close complete for '<branch>'

  Merged:   PR #<number> (or "abandoned")
  Worktree: deleted (<path>)
  Stack:    Docker stack for slot <N> stopped and removed
  Tests:    ✅ passed (or ❌ N failures)
  Main:     <latest commit hash> — <commit message>
```

---

## Constraints

- Never delete a worktree without either confirming the branch is merged OR getting explicit "abandon" confirmation from the user
- Never force-push or reset main
- Always run tests after pulling main — even if the merge looked clean
- Use `--merge` for `gh pr merge` — never squash or rebase
