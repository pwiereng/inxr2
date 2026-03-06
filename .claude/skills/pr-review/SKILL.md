---
name: pr-review
description: "Manages the full PR lifecycle. On first run: runs tests/checks, commits, pushes, and creates a PR. On subsequent runs or when 'check comments' is typed: retrieves, reviews, summarizes PR comments, and advises on next steps."
user-invocable: true
argument-hint: "[optional: issue number to link]"
---

# PR Review Skill

Manages the full pull request lifecycle for the current branch.

## Mode Detection

Determine which mode to run by checking for an open PR on the current branch:

```
BRANCH=$(git branch --show-current)
gh pr list --head "$BRANCH" --state open --json number,title,url
```

- **If no open PR exists** → Run **Create Mode**
- **If an open PR exists** → Run **Review Mode**
- **If the user said "check comments"** → Always run **Review Mode**

## Create Mode (No Open PR)

### Step 1: Run Tests and Checks

Run the full test suite:

```bash
./scripts/run-all-tests.sh
```

If tests or checks fail:
1. Report what failed clearly
2. DO NOT proceed to commit
3. Ask the user if they want you to fix the issues

If all tests and checks pass, proceed to Step 2.

### Step 2: Commit

Follow the standard git commit workflow:

1. Run `git status` to see all changes
2. Run `git diff` and `git diff --staged` to review changes
3. Run `git log --oneline -5` to see recent commit style
4. Stage relevant files (prefer specific files over `git add -A`)
5. Draft a commit message that follows the repo's conventions
6. Show the user the proposed commit message and staged files
7. Ask the user to confirm before committing
8. Create the commit with:
   ```
   Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
   ```

### Step 3: Push

Push the current branch to origin:

```bash
git push -u origin $(git branch --show-current)
```

If the push fails (e.g., rejected), report the error and suggest resolution.

After a successful push, always display the PR reference at the end of your output (see "Always Display PR Reference" below).

### Step 4: Create PR

Create a pull request using `gh pr create`:

1. Run `git log main..HEAD --oneline` to understand all commits in this branch
2. Run `git diff main...HEAD --stat` to see the scope of changes
3. Draft a PR title (under 70 characters) and body
4. If an issue number was provided as argument (`$ARGUMENTS`), link it with "Closes #N" in the body
5. Create the PR:

```bash
gh pr create --title "..." --body "$(cat <<'EOF'
## Summary
<1-3 bullet points summarizing what this PR does>

## Changes
<Brief description of key changes>

## Test plan
- [ ] All tests pass (`./scripts/run-all-tests.sh`)
- [ ] <additional test items relevant to this PR>

Closes #<issue-number-if-applicable>

Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

6. Report the PR URL to the user
7. Request Copilot review:
   ```bash
   gh pr edit <PR_NUMBER> --add-reviewer copilot
   ```

### On Subsequent Pushes (PR Already Exists)

When pushing additional commits to a branch that already has an open PR:

1. Push the changes:
   ```bash
   git push origin $(git branch --show-current)
   ```

2. Re-request Copilot review (dismiss stale review first, then re-add):
   ```bash
   gh pr edit <PR_NUMBER> --add-reviewer copilot
   ```

## Review Mode (Open PR Exists)

### Step 1: Gather PR Information

```bash
# Get PR number and details
gh pr view --json number,title,state,body,reviews,url

# Get review comments (inline code comments)
gh api repos/pwiereng/inxr2/pulls/<PR_NUMBER>/comments

# Get general PR comments
gh pr view <PR_NUMBER> --comments
```

### Step 2: Analyze Comments

For each comment:
- Identify who left it
- Classify it: actionable feedback, question, nitpick, approval, or informational
- Note if it's on a specific file/line or general

### Step 3: Summarize

Present a concise summary:

```
## PR #<number>: <title>
**Status:** <open/changes-requested/approved>
**Reviews:** <count and status of each review>

### Comments (<count> total)

**Actionable:**
1. [file:line] <summary of what needs to change>
2. ...

**Questions:**
1. <question that needs answering>
2. ...

**Nitpicks/Style:**
1. <minor suggestion>
2. ...

**Resolved/Informational:**
1. <already addressed or FYI comments>
```

### Step 4: Advise

Based on the comments, recommend next steps:
- Which comments require code changes
- Which can be addressed with a reply
- Suggested order of addressing feedback
- Whether any comments conflict with each other

DO NOT make any code changes or push anything in Review Mode. Just summarize and advise. Wait for the user to decide what to do next.

### Step 5: Triage Comments

After the user reviews the summary and decides what to address, update each PR review comment with a disposition and resolve it:

For each comment the user wants to **fix**:
```bash
# Reply to the comment indicating it will be fixed
gh api repos/pwiereng/inxr2/pulls/<PR_NUMBER>/comments/<COMMENT_ID>/replies \
  -f body="Fixing this."
```

For each comment the user wants to **dismiss**:
```bash
# Reply with reason for dismissing, then resolve
gh api repos/pwiereng/inxr2/pulls/<PR_NUMBER>/comments/<COMMENT_ID>/replies \
  -f body="Dismissing — <reason provided by user>"
```

After replying, resolve each conversation thread:
```bash
# Get the GraphQL node ID for the review thread
# The thread ID can be found from the pull_request_review_thread_id in the comment data
gh api graphql -f query='
  mutation {
    resolveReviewThread(input: {threadId: "<THREAD_NODE_ID>"}) {
      thread { isResolved }
    }
  }
'
```

To get the thread node ID, fetch the review threads:
```bash
gh api graphql -f query='
  query {
    repository(owner: "pwiereng", name: "inxr2") {
      pullRequest(number: <PR_NUMBER>) {
        reviewThreads(first: 100) {
          nodes {
            id
            isResolved
            comments(first: 1) {
              nodes { body databaseId }
            }
          }
        }
      }
    }
  }
'
```

This keeps the PR clean — every comment gets an explicit response and resolved conversations don't clutter the review.

## Always Display PR Reference

**At the end of EVERY `/pr-review` run**, regardless of mode, display the PR number and URL prominently so the user can easily match this Claude window to the corresponding PR:

```
---
🔗 **PR #<number>:** <url>
   Branch: <branch-name>
```

In Create Mode, display this after the PR is created. In Review Mode, display it after the summary. If a push was done (Create Mode step 3) but PR creation hasn't happened yet, display the branch name and note that the PR will be created next.
