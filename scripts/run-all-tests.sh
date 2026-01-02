#!/bin/bash
# Run all automated tests for INXR2
# Tests both backend and frontend

set -e

echo "🧪 INXR2 Automated Test Suite"
echo "=============================="
echo ""

# Check if container is running
if ! docker ps | grep -q inxr2-dev; then
    echo "❌ Error: inxr2-dev container is not running"
    echo "   Run './scripts/build.sh' first"
    exit 1
fi

# Track overall status
BACKEND_STATUS=0
FRONTEND_STATUS=0
LINT_STATUS=0

echo "📦 Step 1: Backend Tests (Python)"
echo "=================================="
if docker exec inxr2-dev bash -c "cd /workspace && pytest --cov=src --cov-report=term-missing -v"; then
    echo "✅ Backend tests PASSED"
else
    echo "❌ Backend tests FAILED"
    BACKEND_STATUS=1
fi

echo ""
echo "📦 Step 2: Frontend Tests (TypeScript)"
echo "======================================="
if docker exec inxr2-dev bash -c "cd /workspace/frontend && npm test -- --run --coverage"; then
    echo "✅ Frontend tests PASSED"
else
    echo "❌ Frontend tests FAILED"
    FRONTEND_STATUS=1
fi

echo ""
echo "📦 Step 3: Code Quality Checks"
echo "==============================="
echo ""
echo "🔍 Python: Black, isort, ruff, mypy..."
PYTHON_QUALITY=0

docker exec inxr2-dev bash -c "cd /workspace && black --check ." >/dev/null 2>&1 || PYTHON_QUALITY=1
docker exec inxr2-dev bash -c "cd /workspace && isort --check ." >/dev/null 2>&1 || PYTHON_QUALITY=1
docker exec inxr2-dev bash -c "cd /workspace && ruff check ." >/dev/null 2>&1 || PYTHON_QUALITY=1
docker exec inxr2-dev bash -c "cd /workspace && mypy src/inxr2" >/dev/null 2>&1 || PYTHON_QUALITY=1

if [ $PYTHON_QUALITY -eq 0 ]; then
    echo "✅ Python code quality PASSED"
else
    echo "❌ Python code quality FAILED"
    LINT_STATUS=1
fi

echo ""
echo "🔍 TypeScript: ESLint, Prettier, tsc..."
TYPESCRIPT_QUALITY=0

docker exec inxr2-dev bash -c "cd /workspace/frontend && npm run lint" >/dev/null 2>&1 || TYPESCRIPT_QUALITY=1
docker exec inxr2-dev bash -c "cd /workspace/frontend && npm run format:check" >/dev/null 2>&1 || TYPESCRIPT_QUALITY=1
docker exec inxr2-dev bash -c "cd /workspace/frontend && npm run type-check" >/dev/null 2>&1 || TYPESCRIPT_QUALITY=1

if [ $TYPESCRIPT_QUALITY -eq 0 ]; then
    echo "✅ TypeScript code quality PASSED"
else
    echo "❌ TypeScript code quality FAILED"
    LINT_STATUS=1
fi

echo ""
echo "📦 Step 4: Security Audit"
echo "========================="
docker exec inxr2-dev bash -c "cd /workspace/frontend && npm audit" || true

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

if [ $LINT_STATUS -eq 0 ]; then
    echo "✅ Code quality: PASSED"
else
    echo "❌ Code quality: FAILED"
fi

echo ""

# Exit with error if any tests failed
if [ $BACKEND_STATUS -ne 0 ] || [ $FRONTEND_STATUS -ne 0 ] || [ $LINT_STATUS -ne 0 ]; then
    echo "❌ Some tests FAILED"
    exit 1
else
    echo "✅ All tests PASSED!"
    exit 0
fi
