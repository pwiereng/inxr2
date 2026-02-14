#!/bin/bash
# Remove an isolated git worktree and its Docker stack.
# Usage: ./scripts/worktree-remove.sh <branch-name>

set -e

# ── Helpers ─────────────────────────────────────────────────────────────────

SLOTS_FILE="$HOME/.inxr2-worktree-slots"
MAIN_REPO="$HOME/source/inxr2"

die() { echo "❌ $*" >&2; exit 1; }

sanitize() { echo "$1" | tr '/' '-'; }

# ── Validate arguments ─────────────────────────────────────────────────────

[ -z "$1" ] && die "Usage: $0 <branch-name>"

RAW_BRANCH="$1"
BRANCH=$(sanitize "$RAW_BRANCH")
WORKTREE_DIR="$HOME/source/wt-inxr2-${BRANCH}"

# ── Stop Docker stack ──────────────────────────────────────────────────────

if [ -d "$WORKTREE_DIR" ] && [ -f "$WORKTREE_DIR/docker-compose.dev.yml" ]; then
    echo "🛑 Stopping Docker stack..."
    cd "$WORKTREE_DIR"
    docker compose -f docker-compose.dev.yml down -v 2>/dev/null || true
    echo "✅ Docker stack stopped and volumes removed"
else
    echo "⚠️  No Docker stack found at $WORKTREE_DIR"
fi

# ── Remove worktree ───────────────────────────────────────────────────────

cd "$MAIN_REPO"

if git worktree list | grep -q "$WORKTREE_DIR"; then
    echo "📂 Removing worktree..."
    git worktree remove "$WORKTREE_DIR" --force
    echo "✅ Worktree removed"
else
    echo "⚠️  Worktree not found in git worktree list"
    # Clean up directory if it still exists
    if [ -d "$WORKTREE_DIR" ]; then
        echo "   Removing leftover directory..."
        rm -rf "$WORKTREE_DIR"
    fi
fi

# ── Free slot ──────────────────────────────────────────────────────────────

if [ -f "$SLOTS_FILE" ]; then
    # Remove the line matching this branch
    grep -v ":${BRANCH}:" "$SLOTS_FILE" > "${SLOTS_FILE}.tmp" 2>/dev/null || true
    mv "${SLOTS_FILE}.tmp" "$SLOTS_FILE"
    echo "✅ Slot freed"
fi

echo ""
echo "✅ Worktree '$RAW_BRANCH' fully removed."
