#!/bin/bash
# Start both backend and frontend development servers
#
# Works from anywhere:
#   ./scripts/dev-serve.sh          # auto-detects host vs container
#   docker exec -it <name> ./scripts/dev-serve.sh  # explicit

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# If running on host, delegate to container
if ! { [ -f /.dockerenv ] || grep -q docker /proc/1/cgroup 2>/dev/null; }; then
    # Derive container name from .env (if present) or default to inxr2-dev
    CONTAINER_PREFIX="inxr2"
    if [ -f ".env" ]; then
        PREFIX_FROM_ENV=$(sed -n 's/^COMPOSE_CONTAINER_PREFIX=[[:space:]]*//p' .env 2>/dev/null | tr -d '[:space:]"'"'")
        [ -n "$PREFIX_FROM_ENV" ] && CONTAINER_PREFIX="$PREFIX_FROM_ENV"
    fi
    DEV_CONTAINER="${CONTAINER_PREFIX}-dev"

    if ! docker ps --format '{{.Names}}' | grep -qx "$DEV_CONTAINER"; then
        echo -e "${RED}Error: $DEV_CONTAINER is not running. Run './scripts/dev-start.sh' first.${NC}"
        exit 1
    fi

    echo -e "${BLUE}Delegating to container $DEV_CONTAINER...${NC}"
    exec docker exec -it "$DEV_CONTAINER" /workspace/scripts/dev-serve.sh
fi

# --- Running inside the container from here ---

cd /workspace

# Track PIDs for cleanup
BACKEND_PID=""
FRONTEND_PID=""
EXIT_CODE=0

cleanup() {
    # Preserve exit code from caller
    local saved_exit_code=$?
    if [ $saved_exit_code -ne 0 ]; then
        EXIT_CODE=$saved_exit_code
    fi

    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"

    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill "$FRONTEND_PID" 2>/dev/null
        echo -e "  ${RED}Frontend stopped${NC}"
    fi

    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null
        echo -e "  ${RED}Backend stopped${NC}"
    fi

    # Kill any remaining child processes (check first to avoid error)
    if pgrep -P $$ >/dev/null 2>&1; then
        pkill -P $$ 2>/dev/null
    fi

    echo -e "${GREEN}Done.${NC}"
    exit $EXIT_CODE
}

# Set up trap for Ctrl+C and exit
trap cleanup SIGINT SIGTERM EXIT

echo -e "${BLUE}Starting INXR2 development servers...${NC}"
echo ""

# Start backend in background
echo -e "${GREEN}Starting backend...${NC}"
inxr2 serve --reload &
BACKEND_PID=$!
echo -e "  Backend PID: $BACKEND_PID"
echo -e "  URL: ${BLUE}http://localhost:8000${NC}"
echo -e "  API docs: ${BLUE}http://localhost:8000/docs${NC}"
echo ""

# Give backend a moment to start
sleep 2

# Verify backend is still running before starting frontend
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo -e "${RED}Error: Backend failed to start${NC}"
    exit 1
fi

# Start frontend in background
echo -e "${GREEN}Starting frontend...${NC}"
if [ ! -d "frontend" ]; then
    echo -e "${RED}Error: frontend directory not found${NC}"
    exit 1
fi
npm --prefix frontend run dev &
FRONTEND_PID=$!
echo -e "  Frontend PID: $FRONTEND_PID"
echo -e "  URL: ${BLUE}http://localhost:5173${NC}"
echo ""

echo -e "${GREEN}Both services running. Press Ctrl+C to stop.${NC}"
echo ""

# Wait for either process to exit (EXIT trap will run cleanup)
# Note: wait -n returns the exit status of the process that exited
wait -n $BACKEND_PID $FRONTEND_PID 2>/dev/null

# If we get here, one process died - cleanup will be called by EXIT trap
