#!/bin/bash
# Reset Database - Delete and recreate database from scratch
# This script removes the database volume and recreates it with fresh migrations

set -e  # Exit on error

echo "🗑️  Database Reset Script"
echo "================================"
echo ""
echo "⚠️  WARNING: This will DELETE ALL DATABASE DATA!"
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Aborted."
    exit 0
fi

echo ""
echo "📋 Step 1: Stopping containers..."
docker-compose -f docker-compose.dev.yml down

echo ""
echo "🗑️  Step 2: Removing database volume..."
docker volume rm inxr2_postgres_data 2>/dev/null || echo "Volume doesn't exist, skipping..."

echo ""
echo "🚀 Step 3: Starting fresh database..."
docker-compose -f docker-compose.dev.yml up -d postgres

echo ""
echo "⏳ Step 4: Waiting for database to be ready..."
until docker exec inxr2-postgres-dev pg_isready -U inxr2_user -d inxr2_dev > /dev/null 2>&1; do
    echo "   Waiting for PostgreSQL..."
    sleep 2
done
echo "✅ Database is ready!"

echo ""
echo "🔧 Step 5: Starting dev container..."
docker-compose -f docker-compose.dev.yml up -d dev

echo ""
echo "⏳ Step 6: Waiting for dev container..."
sleep 5

echo ""
echo "📦 Step 7: Applying migrations..."
docker exec inxr2-dev bash -c "source /home/devuser/.venv/bin/activate && cd /workspace && alembic upgrade head"

echo ""
echo "✅ Step 8: Verifying migration..."
docker exec inxr2-dev bash -c "source /home/devuser/.venv/bin/activate && cd /workspace && alembic current"

echo ""
echo "🎉 Database reset complete!"
echo ""
echo "Database: inxr2_dev"
echo "User: inxr2_user"
echo "Host: localhost:5432"
echo ""
echo "Current migration:"
docker exec inxr2-dev bash -c "source /home/devuser/.venv/bin/activate && cd /workspace && alembic current 2>/dev/null | grep -v INFO | head -1"
