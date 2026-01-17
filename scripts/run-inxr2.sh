#!/bin/bash
# Start INXR2 with a custom repositories directory
#
# Usage:
#   ./scripts/run-inxr2.sh /path/to/repos
#   ./scripts/run-inxr2.sh /path/to/repos --config /path/to/config.yaml
#   ./scripts/run-inxr2.sh --dev /path/to/repos    # Use dev compose
#
# Examples:
#   ./scripts/run-inxr2.sh ~/projects
#   ./scripts/run-inxr2.sh ~/projects --config ~/my-inxr2-config.yaml
#   ./scripts/run-inxr2.sh --dev ~/projects

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 [--dev] <repos-directory> [--config <config-file>]"
    echo ""
    echo "Arguments:"
    echo "  <repos-directory>    Path to directory containing git repositories"
    echo ""
    echo "Options:"
    echo "  --dev                Use development docker-compose (with hot reload)"
    echo "  --config <file>      Path to custom inxr2 config.yaml file"
    echo "  --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 ~/projects                              # Index repos in ~/projects"
    echo "  $0 ~/projects --config ~/inxr2.yaml        # With custom config"
    echo "  $0 --dev ~/projects                        # Development mode"
    exit 1
}

# Parse arguments
DEV_MODE=false
REPOS_DIR=""
CONFIG_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            DEV_MODE=true
            shift
            ;;
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        -*)
            echo -e "${RED}Error: Unknown option $1${NC}"
            usage
            ;;
        *)
            if [ -z "$REPOS_DIR" ]; then
                REPOS_DIR="$1"
            else
                echo -e "${RED}Error: Unexpected argument $1${NC}"
                usage
            fi
            shift
            ;;
    esac
done

# Validate repos directory
if [ -z "$REPOS_DIR" ]; then
    echo -e "${RED}Error: Repositories directory is required${NC}"
    usage
fi

# Expand ~ and resolve to absolute path
REPOS_DIR="${REPOS_DIR/#\~/$HOME}"
REPOS_DIR="$(cd "$REPOS_DIR" 2>/dev/null && pwd)" || {
    echo -e "${RED}Error: Directory does not exist: $REPOS_DIR${NC}"
    exit 1
}

# Count git repos in directory
REPO_COUNT=$(find "$REPOS_DIR" -maxdepth 2 -name ".git" -type d 2>/dev/null | wc -l | tr -d ' ')
if [ "$REPO_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}Warning: No git repositories found in $REPOS_DIR${NC}"
    echo "Looking for .git directories..."
fi

# Validate config file if provided
if [ -n "$CONFIG_FILE" ]; then
    CONFIG_FILE="${CONFIG_FILE/#\~/$HOME}"
    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "${RED}Error: Config file does not exist: $CONFIG_FILE${NC}"
        exit 1
    fi
    CONFIG_FILE="$(cd "$(dirname "$CONFIG_FILE")" && pwd)/$(basename "$CONFIG_FILE")"
fi

# Export environment variables
export INXR2_REPOS_DIR="$REPOS_DIR"
if [ -n "$CONFIG_FILE" ]; then
    export INXR2_CONFIG="$CONFIG_FILE"
fi

# Select compose file
if [ "$DEV_MODE" = true ]; then
    COMPOSE_FILE="docker-compose.dev.yml"
    echo -e "${GREEN}Starting INXR2 in development mode...${NC}"
else
    COMPOSE_FILE="docker-compose.yml"
    echo -e "${GREEN}Starting INXR2...${NC}"
fi

echo ""
echo "Configuration:"
echo "  Repos directory: $REPOS_DIR"
echo "  Repos found:     $REPO_COUNT"
if [ -n "$CONFIG_FILE" ]; then
    echo "  Config file:     $CONFIG_FILE"
fi
echo "  Compose file:    $COMPOSE_FILE"
echo ""

# Start containers
docker-compose -f "$COMPOSE_FILE" up -d --build

echo ""
echo -e "${GREEN}INXR2 started successfully!${NC}"
echo ""
echo "Services:"
echo "  - Web UI:      http://localhost:8000"
echo "  - API Docs:    http://localhost:8000/docs"
if [ "$DEV_MODE" = true ]; then
    echo "  - Frontend:    http://localhost:5173"
fi
echo ""
echo "Repositories are mounted at /repos inside the container."
echo ""

# Determine container name for instructions
if [ "$DEV_MODE" = true ]; then
    CONTAINER_NAME="inxr2-dev"
else
    CONTAINER_NAME="inxr2-app"
fi

echo "To index repositories, run:"
echo "  docker exec $CONTAINER_NAME inxr2 index full --path /repos/<repo-name>"
echo ""
echo "Or with a config file:"
echo "  docker exec $CONTAINER_NAME inxr2 index full --config /app/config.yaml"
echo ""
echo "To stop: docker-compose -f $COMPOSE_FILE down"
