#!/bin/bash
# Run all automated tests for INXR2
# Can be run from host (uses docker exec) or inside the dev container directly

set -e

echo "🧪 INXR2 Automated Test Suite"
echo "=============================="
echo ""

# Detect if we're inside the dev container or on the host
if [ -f /.dockerenv ] || grep -q docker /proc/1/cgroup 2>/dev/null; then
    # Inside container — run commands directly
    RUN=""
    WORKDIR="/workspace"
else
    # On host — run commands via docker exec
    # Derive container name from .env (if present) or default to inxr2-dev
    CONTAINER_PREFIX="inxr2"
    if [ -f ".env" ]; then
        PREFIX_FROM_ENV=$(sed -n 's/^COMPOSE_CONTAINER_PREFIX=[[:space:]]*//p' .env 2>/dev/null | tr -d '[:space:]"'"'")
        [ -n "$PREFIX_FROM_ENV" ] && CONTAINER_PREFIX="$PREFIX_FROM_ENV"
    fi
    DEV_CONTAINER="${CONTAINER_PREFIX}-dev"
    if ! docker ps | grep -q "$DEV_CONTAINER"; then
        echo "❌ Error: $DEV_CONTAINER container is not running"
        echo "   Run './scripts/dev-start.sh' first"
        exit 1
    fi
    RUN="docker exec $DEV_CONTAINER bash -c"
    WORKDIR="/workspace"
fi

# Helper to run a command in the right context
run_cmd() {
    if [ -z "$RUN" ]; then
        bash -c "cd $WORKDIR && $1"
    else
        $RUN "cd $WORKDIR && $1"
    fi
}

# Wait for PostgreSQL to be ready (handles container rebuild timing)
echo "⏳ Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if run_cmd "pg_isready -h localhost -q 2>/dev/null"; then
        echo "✅ PostgreSQL is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "❌ PostgreSQL failed to become ready after 30 retries (15s)"
        exit 1
    fi
    sleep 0.5
done
echo ""

# Track overall status
BACKEND_STATUS=0
FRONTEND_STATUS=0
MCP_STATUS=0
LINT_STATUS=0

echo "📦 Step 1: Backend Tests (Python)"
echo "=================================="
if run_cmd "pytest --cov=src --cov-report=term-missing -v"; then
    echo "✅ Backend tests PASSED"
else
    echo "❌ Backend tests FAILED"
    BACKEND_STATUS=1
fi

echo ""
echo "📦 Step 2: Frontend Tests (TypeScript)"
echo "======================================="
if run_cmd "cd frontend && npm test -- --run --coverage"; then
    echo "✅ Frontend tests PASSED"
else
    echo "❌ Frontend tests FAILED"
    FRONTEND_STATUS=1
fi

echo ""
echo "📦 Step 3: MCP Server Tests (Python)"
echo "====================================="
if run_cmd "cd mcp-server && pytest -v"; then
    echo "✅ MCP server tests PASSED"
else
    echo "❌ MCP server tests FAILED"
    MCP_STATUS=1
fi

echo ""
echo "📦 Step 4: Code Quality Checks"
echo "==============================="
echo ""
echo "🔍 Python: Black, isort, ruff, mypy..."
PYTHON_QUALITY=0

run_cmd "black --check ." >/dev/null 2>&1 || PYTHON_QUALITY=1
run_cmd "isort --check ." >/dev/null 2>&1 || PYTHON_QUALITY=1
run_cmd "ruff check ." >/dev/null 2>&1 || PYTHON_QUALITY=1
run_cmd "mypy src/ tests/" >/dev/null 2>&1 || PYTHON_QUALITY=1

if [ $PYTHON_QUALITY -eq 0 ]; then
    echo "✅ Python code quality PASSED"
else
    echo "❌ Python code quality FAILED"
    LINT_STATUS=1
fi

echo ""
echo "🔍 TypeScript: ESLint, Prettier, tsc..."
TYPESCRIPT_QUALITY=0

run_cmd "cd frontend && npm run lint" >/dev/null 2>&1 || TYPESCRIPT_QUALITY=1
run_cmd "cd frontend && npm run format:check" >/dev/null 2>&1 || TYPESCRIPT_QUALITY=1
run_cmd "cd frontend && npm run type-check" >/dev/null 2>&1 || TYPESCRIPT_QUALITY=1

if [ $TYPESCRIPT_QUALITY -eq 0 ]; then
    echo "✅ TypeScript code quality PASSED"
else
    echo "❌ TypeScript code quality FAILED"
    LINT_STATUS=1
fi

echo ""
echo "📦 Step 5: Security Audit"
echo "========================="
run_cmd "cd frontend && npm audit" || true

echo ""
echo "=============================="
echo "📊 Test Summary"
echo "=============================="
echo ""

if [ $BACKEND_STATUS -eq 0 ]; then
    echo "✅ Backend tests: PASSED"
else
    echo "❌ Backend tests: FAILED"
fi

if [ $FRONTEND_STATUS -eq 0 ]; then
    echo "✅ Frontend tests: PASSED"
else
    echo "❌ Frontend tests: FAILED"
fi

if [ $MCP_STATUS -eq 0 ]; then
    echo "✅ MCP server tests: PASSED"
else
    echo "❌ MCP server tests: FAILED"
fi

if [ $LINT_STATUS -eq 0 ]; then
    echo "✅ Code quality: PASSED"
else
    echo "❌ Code quality: FAILED"
fi

echo ""

# Exit with error if any tests failed
if [ $BACKEND_STATUS -ne 0 ] || [ $FRONTEND_STATUS -ne 0 ] || [ $MCP_STATUS -ne 0 ] || [ $LINT_STATUS -ne 0 ]; then
    echo "❌ Some tests FAILED"
    exit 1
else
    echo "✅ All tests PASSED!"
    exit 0
fi
