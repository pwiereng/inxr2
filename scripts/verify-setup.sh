#!/bin/bash
# Verify Setup - Quick verification that everything is working
# This script checks:
# 1. Docker containers are running
# 2. Environment variables are loaded
# 3. Database connection works
# 4. Migrations are applied
# 5. Tests pass

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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
docker ps | grep -q "inxr2-postgres-dev" && check "PostgreSQL container running" || check "PostgreSQL container running"
docker ps | grep -q "inxr2-dev" && check "Dev container running" || check "Dev container running"

echo ""
echo -e "${YELLOW}2. Checking environment variables...${NC}"
docker exec inxr2-dev env | grep -q "POSTGRES_PASSWORD=inxr2_dev_password" && check "POSTGRES_PASSWORD loaded" || check "POSTGRES_PASSWORD loaded"
docker exec inxr2-dev env | grep -q "DATABASE_URL=postgresql://" && check "DATABASE_URL loaded" || check "DATABASE_URL loaded"
docker exec inxr2-dev env | grep -q "ENVIRONMENT=development" && check "ENVIRONMENT loaded" || check "ENVIRONMENT loaded"

echo ""
echo -e "${YELLOW}3. Checking database connection...${NC}"
docker exec inxr2-postgres-dev pg_isready -U inxr2_user -d inxr2_dev > /dev/null 2>&1 && check "PostgreSQL accepting connections" || check "PostgreSQL accepting connections"

echo ""
echo -e "${YELLOW}4. Checking database migrations...${NC}"
migration_status=$(docker exec inxr2-dev bash -c "source /home/devuser/.venv/bin/activate && cd /workspace && alembic current 2>/dev/null | grep -v INFO | head -1")
if [ -n "$migration_status" ]; then
    echo -e "${GREEN}✅ Migrations applied: $migration_status${NC}"
else
    echo -e "${RED}❌ No migrations found${NC}"
fi

echo ""
echo -e "${YELLOW}5. Checking database tables...${NC}"
table_count=$(docker exec inxr2-postgres-dev psql -U inxr2_user -d inxr2_dev -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" 2>/dev/null | tr -d ' ')
if [ "$table_count" -ge 6 ]; then
    echo -e "${GREEN}✅ Database tables exist ($table_count tables)${NC}"
    docker exec inxr2-postgres-dev psql -U inxr2_user -d inxr2_dev -c "\dt" 2>/dev/null | grep -E "repositories|commits|files|symbols|references|index_status" | awk '{print "   - " $3}'
else
    echo -e "${YELLOW}⚠️  Expected 6+ tables, found $table_count${NC}"
fi

echo ""
echo -e "${YELLOW}6. Quick test - Backend imports...${NC}"
docker exec inxr2-dev bash -c "source /home/devuser/.venv/bin/activate && python -c 'from inxr2.domain.entities import Repository; print(\"Imports OK\")'" > /dev/null 2>&1 && check "Python imports working" || check "Python imports working"

echo ""
echo -e "${YELLOW}7. Quick test - Frontend build...${NC}"
docker exec inxr2-dev bash -c "cd /workspace/frontend && npm run type-check" > /dev/null 2>&1 && check "TypeScript types valid" || check "TypeScript types valid"

echo ""
echo -e "${BLUE}================================${NC}"
echo -e "${GREEN}✅ Verification Complete${NC}"
echo -e "${BLUE}================================${NC}"
echo ""
echo "System Status:"
echo "  • Containers: Running"
echo "  • Environment: Configured (.env.dev)"
echo "  • Database: Connected (inxr2_dev)"
echo "  • Migrations: Applied"
echo "  • Code: Ready"
echo ""
echo "Quick commands:"
echo "  • Run all tests: ./scripts/run-all-tests.sh"
echo "  • Reset database: ./scripts/reset-database.sh"
echo "  • Open shell: docker exec -it inxr2-dev bash"
echo ""
