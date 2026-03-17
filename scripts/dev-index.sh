#!/bin/bash
# Run inxr2 indexing inside the dev container
# Can be run from host (uses docker exec) or inside the dev container directly
#
# Usage: ./scripts/dev-index.sh [--config <file>] [--days <n>] [--repo <name>] [-- <extra args>]
# Defaults: --config config.yaml (no --days = full HEAD index on first run, incremental forward-fill thereafter)

set -e

# Parse arguments
CONFIG="config.yaml"
DAYS=""
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --days)
            DAYS="$2"
            shift 2
            ;;
        --)
            shift
            EXTRA_ARGS=("$@")
            break
            ;;
        *)
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

# Detect if we're inside the dev container or on the host
if [ -f /.dockerenv ] || grep -q docker /proc/1/cgroup 2>/dev/null; then
    # Inside container — run commands directly
    IN_CONTAINER=true
    WORKDIR="/workspace"
else
    # On host — run commands via docker exec
    IN_CONTAINER=false
    CONTAINER_PREFIX="inxr2"
    if [ -f ".env" ]; then
        PREFIX_FROM_ENV=$(sed -n 's/^COMPOSE_CONTAINER_PREFIX=[[:space:]]*//p' .env 2>/dev/null | tr -d '[:space:]"'"'")
        [ -n "$PREFIX_FROM_ENV" ] && CONTAINER_PREFIX="$PREFIX_FROM_ENV"
    fi
    DEV_CONTAINER="${CONTAINER_PREFIX}-dev"
    if ! docker ps | grep -q "$DEV_CONTAINER"; then
        echo "❌ Error: $DEV_CONTAINER container is not running"
        echo "   Run './scripts/dev-start.sh' first"
        exit 1
    fi
    WORKDIR="/workspace"
fi

# Build command as an array to preserve quoting of all arguments
CMD_ARGS=(inxr2 index --config "$CONFIG")
[[ -n "$DAYS" ]] && CMD_ARGS+=(--days "$DAYS")
[[ ${#EXTRA_ARGS[@]} -gt 0 ]] && CMD_ARGS+=("${EXTRA_ARGS[@]}")

echo "🔍 Running: ${CMD_ARGS[*]}"
echo ""

if $IN_CONTAINER; then
    (cd "$WORKDIR" && "${CMD_ARGS[@]}")
else
    # Serialize the array to a safely-escaped string for bash -c inside docker exec
    docker exec "$DEV_CONTAINER" bash -c "cd $WORKDIR && $(printf '%q ' "${CMD_ARGS[@]}")"
fi
