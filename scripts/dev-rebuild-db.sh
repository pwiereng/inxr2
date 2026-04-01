#!/bin/bash
# Rebuild the development database from scratch: drop, recreate, and apply all migrations.
#
# Use this when `alembic upgrade head` won't help — e.g. after a migration that alters
# a column that already exists in the DB with the wrong definition, or when the schema
# has drifted and truncating tables isn't enough.
#
# WARNING: destroys all indexed data. Re-index after running this.

set -e

# Derive container prefix from .env (if present) or default to inxr2
CONTAINER_PREFIX="inxr2"
if [ -f ".env" ]; then
    PREFIX_FROM_ENV=$(sed -n 's/^COMPOSE_CONTAINER_PREFIX=[[:space:]]*//p' .env 2>/dev/null | tr -d '[:space:]"'"'")
    [ -n "$PREFIX_FROM_ENV" ] && CONTAINER_PREFIX="$PREFIX_FROM_ENV"
fi
DEV_CONTAINER="${CONTAINER_PREFIX}-dev"

echo "Rebuilding INXR2 database (drop + recreate + migrate)..."

# Kill any running indexing processes
docker exec "$DEV_CONTAINER" bash -c "pkill -f 'inxr2 index'" 2>/dev/null || true

# Drop and recreate both dev and test databases
docker exec "$DEV_CONTAINER" bash -c "
    psql -U inxr2_user -h localhost -d postgres -c 'DROP DATABASE IF EXISTS inxr2_dev'
    psql -U inxr2_user -h localhost -d postgres -c 'CREATE DATABASE inxr2_dev'
    psql -U inxr2_user -h localhost -d postgres -c 'DROP DATABASE IF EXISTS inxr2_test'
    psql -U inxr2_user -h localhost -d postgres -c 'CREATE DATABASE inxr2_test'
"

# Apply all migrations from scratch
docker exec "$DEV_CONTAINER" bash -c "cd /workspace && alembic upgrade head"

echo "Database rebuild complete. Re-index with: ./scripts/dev-index.sh"
