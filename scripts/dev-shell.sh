#!/bin/bash
# Open a shell in the development container

# Derive container prefix from .env (if present) or default to inxr2
CONTAINER_PREFIX="inxr2"
if [ -f ".env" ]; then
    PREFIX_FROM_ENV=$(grep -E '^COMPOSE_CONTAINER_PREFIX=' .env 2>/dev/null | cut -d= -f2)
    [ -n "$PREFIX_FROM_ENV" ] && CONTAINER_PREFIX="$PREFIX_FROM_ENV"
fi
DEV_CONTAINER="${CONTAINER_PREFIX}-dev"

echo "🐚 Opening shell in $DEV_CONTAINER..."
docker exec -it "$DEV_CONTAINER" /bin/bash
