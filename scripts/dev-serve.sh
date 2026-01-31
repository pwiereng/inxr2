#!/bin/bash
# Start both backend and frontend development servers
#
# Usage (inside dev container):
#   ./scripts/dev-serve.sh
#
# Or from host:
#   docker exec -it inxr2-dev ./scripts/dev-serve.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track PIDs for cleanup
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
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
    exit 0
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
cd frontend && npm run dev &
FRONTEND_PID=$!
echo -e "  Frontend PID: $FRONTEND_PID"
echo -e "  URL: ${BLUE}http://localhost:5173${NC}"
echo ""

echo -e "${GREEN}Both services running. Press Ctrl+C to stop.${NC}"
echo ""

# Wait for either process to exit
wait -n $BACKEND_PID $FRONTEND_PID 2>/dev/null || true

# If we get here, one process died - clean up the other
cleanup
