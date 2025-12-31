#!/bin/bash
# View logs from development containers

# If argument provided, show logs for that service
if [ -n "$1" ]; then
    echo "📋 Viewing logs for $1..."
    docker-compose -f docker-compose.dev.yml logs -f "$1"
else
    echo "📋 Viewing logs for all services..."
    echo "   (Ctrl+C to exit)"
    docker-compose -f docker-compose.dev.yml logs -f
fi
