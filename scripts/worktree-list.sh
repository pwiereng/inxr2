#!/bin/bash
# List all INXR2 worktrees with their status.
# Usage: ./scripts/worktree-list.sh

SLOTS_FILE="$HOME/.inxr2-worktree-slots"

# ── Header ─────────────────────────────────────────────────────────────────

printf "%-6s %-24s %-20s %-28s %s\n" "SLOT" "BRANCH" "PORTS" "CONTAINER" "STATUS"
printf "%-6s %-24s %-20s %-28s %s\n" "----" "------------------------" "--------------------" "----------------------------" "-------"

# ── Slot 0: main worktree ─────────────────────────────────────────────────

MAIN_CONTAINER="inxr2-dev"
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${MAIN_CONTAINER}$"; then
    STATUS="running"
else
    STATUS="stopped"
fi

printf "%-6s %-24s %-20s %-28s %s\n" "0" "main" "8000/5173/9222" "$MAIN_CONTAINER" "$STATUS"

# ── Slots 1-3 ─────────────────────────────────────────────────────────────

for slot in 1 2 3; do
    if [ -f "$SLOTS_FILE" ] && grep -q "^${slot}:" "$SLOTS_FILE" 2>/dev/null; then
        LINE=$(grep "^${slot}:" "$SLOTS_FILE")
        BRANCH=$(echo "$LINE" | cut -d: -f2)
        CONTAINER="inxr2-${BRANCH}-dev"

        APP_PORT=$((8000 + slot * 10))
        FRONTEND_PORT=$((5173 + slot * 10))
        PLAYWRIGHT_PORT=$((9222 + slot * 10))
        PORTS="${APP_PORT}/${FRONTEND_PORT}/${PLAYWRIGHT_PORT}"

        if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER}$"; then
            STATUS="running"
        else
            STATUS="stopped"
        fi

        printf "%-6s %-24s %-20s %-28s %s\n" "$slot" "$BRANCH" "$PORTS" "$CONTAINER" "$STATUS"
    else
        APP_PORT=$((8000 + slot * 10))
        FRONTEND_PORT=$((5173 + slot * 10))
        PLAYWRIGHT_PORT=$((9222 + slot * 10))
        PORTS="${APP_PORT}/${FRONTEND_PORT}/${PLAYWRIGHT_PORT}"

        printf "%-6s %-24s %-20s %-28s %s\n" "$slot" "(available)" "$PORTS" "-" "-"
    fi
done
