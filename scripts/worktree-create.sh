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

# Derive main repo path from this script's location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

die() { echo "❌ $*" >&2; exit 1; }

# Sanitize branch name: replace / with -, validate safe characters
sanitize() {
    local name
    name=$(echo "$1" | tr '/' '-')
    # Only allow alphanumeric, dash, underscore, dot
    if ! echo "$name" | grep -qE '^[a-zA-Z0-9._-]+$'; then
        die "Branch name contains unsafe characters (allowed: a-z A-Z 0-9 . _ -): $1"
    fi
    # Block path traversal
    if echo "$name" | grep -qE '\.\.'; then
        die "Branch name cannot contain '..': $1"
    fi
    echo "$name"
}

# Check if a port is available on the host
check_port() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        if lsof -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
            return 1
        fi
    fi
    return 0
}

# ── Validate arguments ─────────────────────────────────────────────────────

[ -z "$1" ] && die "Usage: $0 <branch-name>"

RAW_BRANCH="$1"
BRANCH=$(sanitize "$RAW_BRANCH")
WORKTREE_DIR="$(dirname "$MAIN_REPO")/wt-inxr2-${BRANCH}"

# Ensure we're in the main repo
if [ ! -d "$MAIN_REPO/.git" ]; then
    die "Main repo not found at $MAIN_REPO"
fi

# Check worktree doesn't already exist
if [ -d "$WORKTREE_DIR" ]; then
    die "Worktree already exists at $WORKTREE_DIR"
fi

# ── Find next available slot (with file locking) ──────────────────────────

touch "$SLOTS_FILE"

find_slot() {
    (
        flock -x 200 || die "Could not acquire lock on slots file"

        for slot in $(seq 1 $MAX_SLOTS); do
            if ! grep -q "^${slot}:" "$SLOTS_FILE" 2>/dev/null; then
                echo "$slot"
                return
            fi
        done
        echo ""
    ) 200>"${SLOTS_FILE}.lock"
}

SLOT=$(find_slot)
[ -z "$SLOT" ] && die "No available slots (max $MAX_SLOTS worktrees). Remove one first with worktree-remove.sh"

# ── Port allocation ────────────────────────────────────────────────────────

APP_PORT=$((8000 + SLOT * 10))
FRONTEND_PORT=$((5173 + SLOT * 10))
PLAYWRIGHT_PORT=$((9222 + SLOT * 10))

# Check ports are available
for port in $APP_PORT $FRONTEND_PORT $PLAYWRIGHT_PORT; do
    if ! check_port "$port"; then
        die "Port $port is already in use. Free it before creating this worktree."
    fi
done

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

# This .env is gitignored (intentionally — it's unique per worktree instance)
cat > "$WORKTREE_DIR/.env" <<EOF
COMPOSE_PROJECT_NAME=inxr2-${BRANCH}
COMPOSE_CONTAINER_PREFIX=inxr2-${BRANCH}
APP_PORT=${APP_PORT}
FRONTEND_PORT=${FRONTEND_PORT}
PLAYWRIGHT_PORT=${PLAYWRIGHT_PORT}
EOF

echo "📝 Generated .env (ports: backend=${APP_PORT}, frontend=${FRONTEND_PORT}, playwright=${PLAYWRIGHT_PORT})"

# ── Register slot (with file locking) ──────────────────────────────────────

(
    flock -x 200 || die "Could not acquire lock on slots file"
    echo "${SLOT}:${BRANCH}:${WORKTREE_DIR}" >> "$SLOTS_FILE"
) 200>"${SLOTS_FILE}.lock"

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
