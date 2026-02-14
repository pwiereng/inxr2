#!/bin/bash
# Start the development environment

set -e

# Derive container prefix from .env (if present) or default to inxr2
CONTAINER_PREFIX="inxr2"
if [ -f ".env" ]; then
    PREFIX_FROM_ENV=$(sed -n 's/^COMPOSE_CONTAINER_PREFIX=[[:space:]]*//p' .env 2>/dev/null | tr -d '[:space:]"'"'")
    [ -n "$PREFIX_FROM_ENV" ] && CONTAINER_PREFIX="$PREFIX_FROM_ENV"
fi
DEV_CONTAINER="${CONTAINER_PREFIX}-dev"

echo "🚀 Starting INXR2 development environment..."

# Build and start containers
docker compose -f docker-compose.dev.yml up -d --build

echo ""
echo "✅ Development environment started!"
echo ""
echo "Services (inside $DEV_CONTAINER):"
echo "  - PostgreSQL:  embedded (localhost:5432 inside container)"
echo "  - Backend:     localhost:${APP_PORT:-8000} (once started)"
echo "  - Frontend:    localhost:${FRONTEND_PORT:-5173} (once started)"
echo ""
echo "To view logs:   ./scripts/dev-logs.sh"
echo "To stop:        ./scripts/dev-stop.sh"
echo "To open shell:  ./scripts/dev-shell.sh"
echo ""
echo "Dev container is running. Open shell with: docker exec -it $DEV_CONTAINER bash"
