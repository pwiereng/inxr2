#!/bin/bash
set -e

echo "🚀 Starting INXR2 dev container..."

# Check if Python packages are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "📦 Installing Python packages..."
    uv pip install -e '.[dev]'
    echo "✅ Python packages installed"
else
    echo "✅ Python packages already installed"
fi

# Check if frontend packages are installed
if [ ! -d "/workspace/frontend/node_modules" ]; then
    echo "📦 Installing frontend packages..."
    cd /workspace/frontend && npm install
    echo "✅ Frontend packages installed"
else
    echo "✅ Frontend packages already installed"
fi

echo "🎉 Container ready!"

# Execute the main command (e.g., /bin/bash)
exec "$@"
