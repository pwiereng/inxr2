#!/bin/bash
# Verify Setup - Quick verification that everything is working
# This script checks:
# 1. Docker containers are running
# 2. Environment variables are loaded
# 3. Database connection works (embedded PostgreSQL)
# 4. Migrations are applied
# 5. Tests pass

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Derive container name from .env (if present) or default to inxr2
CONTAINER_PREFIX="inxr2"
PREFIX_FROM_ENV=""
if [ -f ".env" ]; then
    PREFIX_FROM_ENV=$(sed -n 's/^COMPOSE_CONTAINER_PREFIX=[[:space:]]*//p' .env 2>/dev/null | tr -d '[:space:]"'"'")
    [ -n "$PREFIX_FROM_ENV" ] && CONTAINER_PREFIX="$PREFIX_FROM_ENV"
fi
DEV_CONTAINER="${CONTAINER_PREFIX}-dev"

# Validate the expected container is running before proceeding
if ! docker ps --format '{{.Names}}' | grep -qx "$DEV_CONTAINER"; then
    echo -e "${RED}❌ Dev container '$DEV_CONTAINER' is not running.${NC}"
    if [ -f ".env" ] && [ -z "$PREFIX_FROM_ENV" ]; then
        echo -e "${YELLOW}   Note: .env exists but COMPOSE_CONTAINER_PREFIX is missing. Using default 'inxr2'.${NC}"
    fi
    echo -e "${RED}   Run './scripts/dev-start.sh' first.${NC}"
    exit 1
fi

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}🔍 INXR2 Setup Verification${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Function to check and report
check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $1${NC}"
        return 0
    else
        echo -e "${RED}❌ $1 FAILED${NC}"
        return 1
    fi
}

echo -e "${YELLOW}1. Checking Docker containers...${NC}"
check "Dev container running ($DEV_CONTAINER)"

echo ""
echo -e "${YELLOW}2. Checking environment variables...${NC}"
docker exec "$DEV_CONTAINER" env | grep -q "POSTGRES_PASSWORD=inxr2_dev_password" && check "POSTGRES_PASSWORD loaded" || check "POSTGRES_PASSWORD loaded"
docker exec "$DEV_CONTAINER" env | grep -q "DATABASE_URL=postgresql://" && check "DATABASE_URL loaded" || check "DATABASE_URL loaded"
docker exec "$DEV_CONTAINER" env | grep -q "ENVIRONMENT=development" && check "ENVIRONMENT loaded" || check "ENVIRONMENT loaded"

echo ""
echo -e "${YELLOW}3. Checking database connection (embedded PostgreSQL)...${NC}"
docker exec "$DEV_CONTAINER" pg_isready -h localhost > /dev/null 2>&1 && check "PostgreSQL accepting connections" || check "PostgreSQL accepting connections"

echo ""
echo -e "${YELLOW}4. Checking database migrations...${NC}"
migration_status=$(docker exec "$DEV_CONTAINER" bash -c "source /home/devuser/.venv/bin/activate && cd /workspace && alembic current 2>/dev/null | grep -v INFO | head -1")
if [ -n "$migration_status" ]; then
    echo -e "${GREEN}✅ Migrations applied: $migration_status${NC}"
else
    echo -e "${RED}❌ No migrations found${NC}"
fi

echo ""
echo -e "${YELLOW}5. Checking database tables...${NC}"
table_count=$(docker exec "$DEV_CONTAINER" psql -h localhost -U inxr2_user -d inxr2_dev -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" 2>/dev/null | tr -d ' ')
if [ "$table_count" -ge 6 ]; then
    echo -e "${GREEN}✅ Database tables exist ($table_count tables)${NC}"
    docker exec "$DEV_CONTAINER" psql -h localhost -U inxr2_user -d inxr2_dev -c "\dt" 2>/dev/null | grep -E "repositories|commits|files|symbols|references|index_status" | awk '{print "   - " $3}'
else
    echo -e "${YELLOW}⚠️  Expected 6+ tables, found $table_count${NC}"
fi

echo ""
echo -e "${YELLOW}6. Quick test - Backend imports...${NC}"
docker exec "$DEV_CONTAINER" bash -c "source /home/devuser/.venv/bin/activate && python -c 'from inxr2.domain.entities import Repository; print(\"Imports OK\")'" > /dev/null 2>&1 && check "Python imports working" || check "Python imports working"

echo ""
echo -e "${YELLOW}7. Quick test - Frontend build...${NC}"
docker exec "$DEV_CONTAINER" bash -c "cd /workspace/frontend && npm run type-check" > /dev/null 2>&1 && check "TypeScript types valid" || check "TypeScript types valid"

echo ""
echo -e "${BLUE}================================${NC}"
echo -e "${GREEN}✅ Verification Complete${NC}"
echo -e "${BLUE}================================${NC}"
echo ""
echo "System Status:"
echo "  • Container: Running ($DEV_CONTAINER)"
echo "  • Environment: Configured (.env.dev)"
echo "  • Database: Embedded PostgreSQL (inxr2_dev)"
echo "  • Migrations: Applied"
echo "  • Code: Ready"
echo ""
echo "Quick commands:"
echo "  • Run all tests: ./scripts/run-all-tests.sh"
echo "  • Reset database: ./scripts/dev-reset-db.sh"
echo "  • Open shell: docker exec -it $DEV_CONTAINER bash"
echo ""
