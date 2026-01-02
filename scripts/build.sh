#!/bin/bash
# Build script for INXR2
# Builds images and starts containers

set -e

echo "🔨 INXR2 Build Script"
echo "====================="
echo ""

# Check if we should use --no-cache
NO_CACHE=""
if [ "$1" == "--no-cache" ]; then
    NO_CACHE="--no-cache"
    echo "📝 Building with --no-cache (clean build)"
else
    echo "📝 Building with cache (use --no-cache for clean build)"
fi

echo ""
echo "🔨 Building Docker images..."
docker-compose -f docker-compose.dev.yml build $NO_CACHE

echo ""
echo "🚀 Starting containers..."
docker-compose -f docker-compose.dev.yml up -d

echo ""
echo "⏳ Waiting for containers to be ready..."
sleep 10

echo ""
echo "📦 Verifying package installation..."
if docker exec inxr2-dev bash -c "python -c 'import fastapi' 2>/dev/null"; then
    echo "✅ Python packages OK"
else
    echo "⚠️  Python packages not installed yet (will auto-install on first use)"
fi

if docker exec inxr2-dev bash -c "cd /workspace/frontend && npm list vite >/dev/null 2>&1"; then
    echo "✅ Frontend packages OK"
else
    echo "⚠️  Frontend packages not installed yet (will auto-install on first use)"
fi

echo ""
echo "✅ Build complete!"
echo ""
echo "📊 Container status:"
docker-compose -f docker-compose.dev.yml ps
echo ""
echo "🎯 Next steps:"
echo "   Run all tests:     ./scripts/run-all-tests.sh"
echo "   Start backend:     docker exec -d inxr2-dev inxr2 serve --host 0.0.0.0"
echo "   Start frontend:    docker exec -d inxr2-dev bash -c 'cd /workspace/frontend && npm run dev'"
echo "   Open shell:        ./scripts/dev-shell.sh"
echo "   View logs:         ./scripts/dev-logs.sh"
