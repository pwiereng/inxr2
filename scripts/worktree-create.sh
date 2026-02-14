#!/bin/bash
# Create an isolated git worktree with its own Docker dev stack.
# Usage: ./scripts/worktree-create.sh <branch-name>
#
# This sets up a fully independent development environment:
#   - Git worktree at ~/source/wt-inxr2-<branch>/
#   - Separate Docker container with embedded PostgreSQL
#   - Unique ports so multiple stacks can run simultaneously

set -e

# ── Helpers ─────────────────────────────────────────────────────────────────

SLOTS_FILE="$HOME/.inxr2-worktree-slots"
MAX_SLOTS=2   # slots 1 and 2 (slot 0 is the main worktree)
MAIN_REPO="$HOME/source/inxr2"

die() { echo "❌ $*" >&2; exit 1; }

# Sanitize branch name: replace / with -
sanitize() { echo "$1" | tr '/' '-'; }

# ── Validate arguments ─────────────────────────────────────────────────────

[ -z "$1" ] && die "Usage: $0 <branch-name>"

RAW_BRANCH="$1"
BRANCH=$(sanitize "$RAW_BRANCH")
WORKTREE_DIR="$HOME/source/wt-inxr2-${BRANCH}"

# Ensure we're in the main repo
if [ ! -d "$MAIN_REPO/.git" ]; then
    die "Main repo not found at $MAIN_REPO"
fi

# Check worktree doesn't already exist
if [ -d "$WORKTREE_DIR" ]; then
    die "Worktree already exists at $WORKTREE_DIR"
fi

# ── Find next available slot ───────────────────────────────────────────────

touch "$SLOTS_FILE"

find_slot() {
    for slot in $(seq 1 $MAX_SLOTS); do
        if ! grep -q "^${slot}:" "$SLOTS_FILE" 2>/dev/null; then
            echo "$slot"
            return
        fi
    done
    echo ""
}

SLOT=$(find_slot)
[ -z "$SLOT" ] && die "No available slots (max $MAX_SLOTS worktrees). Remove one first with worktree-remove.sh"

# ── Port allocation ────────────────────────────────────────────────────────

APP_PORT=$((8000 + SLOT * 10))
FRONTEND_PORT=$((5173 + SLOT * 10))
PLAYWRIGHT_PORT=$((9222 + SLOT * 10))

# ── Create git worktree ───────────────────────────────────────────────────

echo "📂 Creating worktree for branch '$RAW_BRANCH' at $WORKTREE_DIR (slot $SLOT)..."

cd "$MAIN_REPO"

# Create branch if it doesn't exist
if git show-ref --verify --quiet "refs/heads/$RAW_BRANCH" 2>/dev/null; then
    echo "   Using existing branch '$RAW_BRANCH'"
    git worktree add "$WORKTREE_DIR" "$RAW_BRANCH"
else
    echo "   Creating new branch '$RAW_BRANCH' from HEAD"
    git worktree add "$WORKTREE_DIR" -b "$RAW_BRANCH"
fi

# ── Generate .env for the worktree ─────────────────────────────────────────

cat > "$WORKTREE_DIR/.env" <<EOF
COMPOSE_PROJECT_NAME=inxr2-${BRANCH}
COMPOSE_CONTAINER_PREFIX=inxr2-${BRANCH}
APP_PORT=${APP_PORT}
FRONTEND_PORT=${FRONTEND_PORT}
PLAYWRIGHT_PORT=${PLAYWRIGHT_PORT}
EOF

echo "📝 Generated .env (ports: backend=${APP_PORT}, frontend=${FRONTEND_PORT}, playwright=${PLAYWRIGHT_PORT})"

# ── Register slot ──────────────────────────────────────────────────────────

echo "${SLOT}:${BRANCH}:${WORKTREE_DIR}" >> "$SLOTS_FILE"

# ── Start the Docker stack ─────────────────────────────────────────────────

echo "🐳 Building and starting Docker stack..."
cd "$WORKTREE_DIR"
docker compose -f docker-compose.dev.yml up -d --build

# ── Summary ────────────────────────────────────────────────────────────────

DEV_CONTAINER="inxr2-${BRANCH}-dev"

echo ""
echo "✅ Worktree ready!"
echo ""
echo "  Branch:     $RAW_BRANCH"
echo "  Directory:  $WORKTREE_DIR"
echo "  Slot:       $SLOT"
echo "  Container:  $DEV_CONTAINER"
echo ""
echo "  Ports:"
echo "    Backend:    localhost:${APP_PORT}"
echo "    Frontend:   localhost:${FRONTEND_PORT}"
echo "    Playwright: localhost:${PLAYWRIGHT_PORT}"
echo ""
echo "  Shell into container:"
echo "    docker exec -it $DEV_CONTAINER bash"
echo ""
echo "  Or cd into the worktree and use scripts:"
echo "    cd $WORKTREE_DIR"
echo "    ./scripts/dev-shell.sh"
