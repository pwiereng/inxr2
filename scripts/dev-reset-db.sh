#!/bin/bash
# Reset the development database (truncates all tables)

set -e

echo "Resetting INXR2 database..."

# Kill any running indexing processes
docker exec inxr2-dev bash -c "pkill -f 'inxr2 index'" 2>/dev/null || true

# Truncate all tables
docker exec inxr2-dev inxr2 db reset --yes

echo "Database reset complete."
