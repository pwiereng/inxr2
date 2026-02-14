#!/bin/bash
# Stop the development environment

set -e

echo "🛑 Stopping INXR2 development environment..."

docker compose -f docker-compose.dev.yml down

echo "✅ Development environment stopped!"
