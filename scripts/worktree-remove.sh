#!/bin/bash
# Remove an isolated git worktree and its Docker stack.
# Usage: ./scripts/worktree-remove.sh <branch-name>

set -e

# ── Helpers ─────────────────────────────────────────────────────────────────

SLOTS_FILE="$HOME/.inxr2-worktree-slots"

# Derive main repo path from this script's location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

die() { echo "❌ $*" >&2; exit 1; }

sanitize() { echo "$1" | tr '/' '-'; }

# ── Validate arguments ─────────────────────────────────────────────────────

[ -z "$1" ] && die "Usage: $0 <branch-name>"

RAW_BRANCH="$1"
BRANCH=$(sanitize "$RAW_BRANCH")
WORKTREE_DIR="$(dirname "$MAIN_REPO")/wt-inxr2-${BRANCH}"

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

# ── Free slot (with file locking) ─────────────────────────────────────────

if [ -f "$SLOTS_FILE" ]; then
    (
        flock -x 200 || die "Could not acquire lock on slots file"
        # Anchored match: ^SLOT:BRANCH: to avoid substring collisions
        grep -v "^[0-9]*:${BRANCH}:" "$SLOTS_FILE" > "${SLOTS_FILE}.tmp" 2>/dev/null || true
        mv "${SLOTS_FILE}.tmp" "$SLOTS_FILE"
    ) 200>"${SLOTS_FILE}.lock"
    echo "✅ Slot freed"
fi

echo ""
echo "✅ Worktree '$RAW_BRANCH' fully removed."
