#!/bin/bash
# Clean rebuild script for INXR2
# Combines clean.sh and build.sh for a complete rebuild

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🧹🔨 INXR2 Clean Rebuild"
echo "========================="
echo ""
echo "This will:"
echo "  1. Clean all containers, volumes, and images"
echo "  2. Rebuild everything from scratch"
echo "  3. Optionally run all tests"
echo ""

# Run clean script
"$SCRIPT_DIR/clean.sh"

echo ""
echo "=============================="
echo ""

# Run build script with --no-cache
"$SCRIPT_DIR/build.sh" --no-cache

echo ""
echo "=============================="
echo ""
read -p "Run automated tests now? (yes/no): " run_tests

if [ "$run_tests" == "yes" ]; then
    echo ""
    "$SCRIPT_DIR/run-all-tests.sh"
else
    echo ""
    echo "✅ Clean rebuild complete!"
    echo ""
    echo "🎯 Run tests later with: ./scripts/run-all-tests.sh"
fi
