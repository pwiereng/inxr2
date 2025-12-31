#!/bin/bash
# Reset the development database

set -e

echo "⚠️  WARNING: This will delete all data in the development database!"
read -p "Are you sure? (yes/no): " -r
echo

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Cancelled."
    exit 1
fi

echo "🗑️  Resetting development database..."

# Stop the database container
docker-compose -f docker-compose.dev.yml stop postgres

# Remove the database volume
docker volume rm inxr2_postgres_data || true

# Restart the database
docker-compose -f docker-compose.dev.yml up -d postgres

echo "✅ Database reset complete!"
echo "   The database will be recreated with a fresh schema."
