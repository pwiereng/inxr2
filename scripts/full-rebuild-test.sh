#!/bin/bash
# Full Rebuild and Test - Complete from-scratch rebuild and test
# This script:
# 1. Stops all containers
# 2. Removes all volumes (database)
# 3. Removes all images
# 4. Rebuilds images from scratch
# 5. Starts containers
# 6. Applies migrations
# 7. Runs full test suite (backend + frontend)
# 8. Verifies everything works

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}🔄 Full Rebuild and Test${NC}"
echo -e "${BLUE}================================${NC}"
echo ""
echo -e "${YELLOW}⚠️  WARNING: This will:${NC}"
echo "   - Delete ALL containers"
echo "   - Delete ALL volumes (DATABASE DATA)"
echo "   - Delete ALL images"
echo "   - Rebuild everything from scratch"
echo ""
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo -e "${RED}❌ Aborted.${NC}"
    exit 0
fi

# Function to print step headers
step() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Function to check command status
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $1${NC}"
    else
        echo -e "${RED}❌ $1 FAILED${NC}"
        exit 1
    fi
}

step "📋 Step 1/10: Stopping all containers"
docker-compose -f docker-compose.dev.yml down -v 2>/dev/null || true
check_status "Containers stopped"

step "🗑️  Step 2/10: Removing volumes"
docker volume rm inxr2_postgres_data 2>/dev/null || echo "   Volume doesn't exist, skipping..."
docker volume rm inxr2_pip_cache 2>/dev/null || echo "   Pip cache volume doesn't exist, skipping..."
docker volume rm inxr2_node_modules 2>/dev/null || echo "   Node modules volume doesn't exist, skipping..."
check_status "Volumes removed"

step "🗑️  Step 3/10: Removing Docker images"
echo "   Removing inxr2-dev image..."
docker rmi inxr2-inxr2-dev 2>/dev/null || echo "   Dev image doesn't exist, skipping..."
echo "   Removing inxr2-app image..."
docker rmi inxr2-inxr2-app 2>/dev/null || echo "   App image doesn't exist, skipping..."
check_status "Images removed"

step "🔨 Step 4/10: Rebuilding images (this may take 5-10 minutes)"
docker-compose -f docker-compose.dev.yml build --no-cache
check_status "Images rebuilt"

step "🚀 Step 5/10: Starting PostgreSQL"
docker-compose -f docker-compose.dev.yml up -d postgres
check_status "PostgreSQL started"

step "⏳ Step 6/10: Waiting for PostgreSQL to be ready"
echo "   Waiting for database to accept connections..."
timeout=60
counter=0
until docker exec inxr2-postgres-dev pg_isready -U inxr2_user -d inxr2_dev > /dev/null 2>&1; do
    if [ $counter -ge $timeout ]; then
        echo -e "${RED}❌ Timeout waiting for PostgreSQL${NC}"
        exit 1
    fi
    echo "   Still waiting... ($counter/$timeout)"
    sleep 2
    ((counter+=2))
done
check_status "PostgreSQL is ready"

step "🚀 Step 7/10: Starting dev container"
docker-compose -f docker-compose.dev.yml up -d dev
check_status "Dev container started"

echo ""
echo "   Waiting for dependencies to install (this may take 2-3 minutes)..."
# Wait for entrypoint to complete by checking if alembic is installed
timeout=180
counter=0
until docker exec inxr2-dev bash -c "source /home/devuser/.venv/bin/activate && which alembic" > /dev/null 2>&1; do
    if [ $counter -ge $timeout ]; then
        echo -e "${RED}❌ Timeout waiting for dependencies${NC}"
        exit 1
    fi
    if [ $((counter % 10)) -eq 0 ]; then
        echo "   Still installing dependencies... ($counter/$timeout seconds)"
    fi
    sleep 2
    ((counter+=2))
done
echo "   ✅ Dependencies installed"

step "📦 Step 8/10: Applying database migrations"
echo "   Running: alembic upgrade head"
docker exec inxr2-dev bash -c "source /home/devuser/.venv/bin/activate && cd /workspace && alembic upgrade head"
check_status "Migrations applied"

echo ""
echo "   Current migration:"
docker exec inxr2-dev bash -c "source /home/devuser/.venv/bin/activate && cd /workspace && alembic current 2>/dev/null | grep -v INFO | head -1"

echo ""
echo "   Verifying tables created:"
docker exec inxr2-postgres-dev psql -U inxr2_user -d inxr2_dev -c "\dt" | grep -E "repositories|commits|files|symbols|references|index_status" || echo "   Tables check..."

step "🧪 Step 9/10: Running backend tests"
echo "   Running pytest with coverage..."
docker exec inxr2-dev bash -c "source /home/devuser/.venv/bin/activate && cd /workspace && pytest --cov=src --cov-report=term-missing -v"
check_status "Backend tests passed"

step "🧪 Step 10/10: Running frontend tests"
echo "   Running vitest..."
docker exec inxr2-dev bash -c "cd /workspace/frontend && npm test -- --run"
check_status "Frontend tests passed"

step "🎉 SUCCESS - Full rebuild and test complete!"

echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✅ All systems operational!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo "Summary:"
echo "  • Docker images: Built from scratch"
echo "  • Database: Created and migrated"
echo "  • Backend tests: PASSED"
echo "  • Frontend tests: PASSED"
echo ""
echo "Services:"
echo "  • PostgreSQL: running on localhost:5432"
echo "  • Backend API: ready on port 8000 (start with: inxr2 serve --reload)"
echo "  • Frontend: ready on port 5173 (start with: cd frontend && npm run dev)"
echo ""
echo "Environment:"
echo "  • Database: inxr2_dev"
echo "  • User: inxr2_user"
echo "  • Config: .env.dev"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  • Start backend: docker exec -d inxr2-dev bash -c 'source /home/devuser/.venv/bin/activate && inxr2 serve --reload'"
echo "  • Start frontend: docker exec -d inxr2-dev bash -c 'cd /workspace/frontend && npm run dev'"
echo "  • Open shell: docker exec -it inxr2-dev bash"
echo ""
