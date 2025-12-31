#!/bin/bash
# Open a shell in the development container

echo "🐚 Opening shell in development container..."
docker-compose -f docker-compose.dev.yml exec dev /bin/bash
