#!/bin/bash
# Reset the development database (truncates all tables)

set -e

# Derive container prefix from .env (if present) or default to inxr2
CONTAINER_PREFIX="inxr2"
if [ -f ".env" ]; then
    PREFIX_FROM_ENV=$(grep -E '^COMPOSE_CONTAINER_PREFIX=' .env 2>/dev/null | cut -d= -f2)
    [ -n "$PREFIX_FROM_ENV" ] && CONTAINER_PREFIX="$PREFIX_FROM_ENV"
fi
DEV_CONTAINER="${CONTAINER_PREFIX}-dev"

echo "Resetting INXR2 database..."

# Kill any running indexing processes
docker exec "$DEV_CONTAINER" bash -c "pkill -f 'inxr2 index'" 2>/dev/null || true

# Truncate all tables
docker exec "$DEV_CONTAINER" inxr2 db reset --yes

echo "Database reset complete."
