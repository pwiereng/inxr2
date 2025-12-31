#!/bin/bash
# Start the development environment

set -e

echo "🚀 Starting INXR2 development environment..."

# Build and start containers
docker-compose -f docker-compose.dev.yml up -d --build

echo ""
echo "✅ Development environment started!"
echo ""
echo "Services:"
echo "  - PostgreSQL:  localhost:5432"
echo "  - Backend:     localhost:8000 (once started)"
echo "  - Frontend:    localhost:5173 (once started)"
echo ""
echo "To view logs:   ./scripts/dev-logs.sh"
echo "To stop:        ./scripts/dev-stop.sh"
echo "To open shell:  ./scripts/dev-shell.sh"
echo ""
echo "Dev container is running. Open in VS Code/Cursor with 'Dev Containers: Reopen in Container'"
