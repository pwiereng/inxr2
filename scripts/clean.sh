#!/bin/bash
# Clean script for INXR2
# Removes all containers, volumes, images, and local packages

set -e

echo "🧹 INXR2 Clean Script"
echo "====================="
echo ""
echo "⚠️  WARNING: This will remove:"
echo "   - All INXR2 Docker containers"
echo "   - All INXR2 Docker volumes (including node_modules, database data)"
echo "   - All INXR2 Docker images"
echo "   - Local frontend/node_modules"
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Aborted"
    exit 1
fi

echo ""
echo "🛑 Stopping all containers..."
docker-compose -f docker-compose.dev.yml down 2>/dev/null || true
docker-compose down 2>/dev/null || true

echo ""
echo "🗑️  Removing containers..."
docker rm -f inxr2-dev inxr2-postgres-dev inxr2-app inxr2-postgres 2>/dev/null || true

echo ""
echo "🗑️  Removing volumes..."
docker volume rm inxr2_postgres_data inxr2_pip_cache inxr2_node_modules 2>/dev/null || true

echo ""
echo "🗑️  Removing images..."
docker rmi inxr2-dev inxr2 2>/dev/null || true

echo ""
echo "🗑️  Cleaning local node_modules..."
rm -rf frontend/node_modules frontend/package-lock.json

echo ""
echo "✅ Clean complete!"
echo ""
echo "🎯 Next step: Run './scripts/build.sh' to rebuild"
