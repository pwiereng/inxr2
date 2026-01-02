#!/bin/bash
set -e

echo "🚀 Starting INXR2 dev container..."

# Ensure we're using the virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    export VIRTUAL_ENV="/home/devuser/.venv"
    export PATH="$VIRTUAL_ENV/bin:$PATH"
fi

# Check if Python packages are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "📦 Installing Python packages with uv..."
    uv pip install -e '.[dev]'
    echo "✅ Python packages installed"
else
    echo "✅ Python packages already installed"
fi

# Ensure node_modules directory exists and has correct permissions
echo "🔍 Checking node_modules permissions..."
ls -la /workspace/frontend/ 2>&1 | grep node_modules || echo "node_modules doesn't exist yet"

if [ ! -d "/workspace/frontend/node_modules" ]; then
    echo "📁 Creating node_modules directory..."
    sudo mkdir -p /workspace/frontend/node_modules
    sudo chown -R devuser:devuser /workspace/frontend/node_modules
fi

# Fix permissions if they're wrong
if [ -d "/workspace/frontend/node_modules" ]; then
    echo "📝 Current node_modules ownership:"
    ls -ld /workspace/frontend/node_modules

    # Check if we can write to node_modules
    if [ ! -w "/workspace/frontend/node_modules" ]; then
        echo "⚠️  node_modules not writable, fixing permissions..."
        sudo chown -R devuser:devuser /workspace/frontend/node_modules
        echo "✅ Permissions fixed"
    else
        echo "✅ node_modules is writable"
    fi
fi

echo "📝 Final node_modules permissions:"
ls -ld /workspace/frontend/node_modules

# Check if frontend packages are installed and valid
if [ ! -d "/workspace/frontend/node_modules" ] || [ ! -f "/workspace/frontend/node_modules/.package-lock.json" ]; then
    echo "📦 Installing frontend packages..."
    cd /workspace/frontend && npm install
    echo "✅ Frontend packages installed"
else
    # Verify installation is valid by checking if vite works
    cd /workspace/frontend
    if ! npm list vite >/dev/null 2>&1; then
        echo "📦 Re-installing frontend packages (previous installation invalid)..."
        rm -rf node_modules package-lock.json
        npm install
        echo "✅ Frontend packages re-installed"
    else
        echo "✅ Frontend packages already installed"
    fi
fi

echo "🎉 Container ready!"

# Execute the main command (e.g., /bin/bash)
exec "$@"
