#!/bin/bash
set -e

echo "🚀 Starting INXR2 dev container..."

# =============================================================================
# PostgreSQL Setup (embedded — runs as devuser)
# =============================================================================

PGDATA="${PGDATA:-/home/devuser/pgdata}"
export PGDATA

# Find the PostgreSQL binary directory
PG_BIN=$(dirname "$(find /usr/lib/postgresql -name pg_ctl -type f 2>/dev/null | head -1)")
if [ -z "$PG_BIN" ] || [ ! -x "$PG_BIN/pg_ctl" ]; then
    echo "❌ PostgreSQL binaries not found"
    exit 1
fi
export PATH="$PG_BIN:$PATH"

# Initialize data directory if empty
if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo "🗄️  Initializing PostgreSQL data directory..."
    initdb --username=devuser --auth=trust --no-locale --encoding=UTF8 -D "$PGDATA"

    # ⚠️  TRUST AUTH — development only, no password required for local connections.
    # This is safe because Postgres only listens on localhost inside the container.
    # DO NOT use this configuration in any internet-facing deployment.
    cat > "$PGDATA/pg_hba.conf" <<'PGHBA'
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
PGHBA

    echo "✅ PostgreSQL data directory initialized"
fi

# Clean up stale PID file from unclean shutdown
if [ -f "$PGDATA/postmaster.pid" ] && ! pg_isready -h localhost -q 2>/dev/null; then
    echo "⚠️  Removing stale postmaster.pid..."
    rm -f "$PGDATA/postmaster.pid"
fi

# Start PostgreSQL if not already running
if ! pg_isready -h localhost -q 2>/dev/null; then
    echo "🗄️  Starting PostgreSQL..."
    pg_ctl start -D "$PGDATA" -l "$PGDATA/logfile" -o "-k /tmp" -w
    echo "✅ PostgreSQL started"
else
    echo "✅ PostgreSQL already running"
fi

# Wait for readiness
for i in $(seq 1 30); do
    if pg_isready -h localhost -q 2>/dev/null; then
        break
    fi
    sleep 0.5
done

if ! pg_isready -h localhost -q 2>/dev/null; then
    echo "❌ PostgreSQL failed to start"
    cat "$PGDATA/logfile" 2>/dev/null || true
    exit 1
fi

# Create role if it doesn't exist
if ! psql -h localhost -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='inxr2_user'" | grep -q 1; then
    echo "🗄️  Creating inxr2_user role..."
    psql -h localhost -d postgres -c "CREATE ROLE inxr2_user WITH LOGIN PASSWORD 'inxr2_dev_password' CREATEDB;"
    echo "✅ Role created"
fi

# Create databases if they don't exist
for db in inxr2_dev inxr2_test; do
    if ! psql -h localhost -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1; then
        echo "🗄️  Creating database $db..."
        psql -h localhost -d postgres -c "CREATE DATABASE $db OWNER inxr2_user;"
        echo "✅ Database $db created"
    fi
done

echo "✅ PostgreSQL ready (databases: inxr2_dev, inxr2_test)"

# =============================================================================
# Python / Node Setup
# =============================================================================

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

# Apply database migrations (non-fatal — container still starts on failure)
if [ "${SKIP_DB_MIGRATIONS:-}" = "true" ]; then
    echo "⏭️  Skipping database migrations (SKIP_DB_MIGRATIONS=true)"
else
    echo "🗄️  Applying database migrations..."
    if cd /workspace && alembic upgrade head; then
        echo "✅ Migrations applied"
    else
        echo "⚠️  Migration failed — container will start, but the database may be out of date."
        echo "   Fix the migration and run 'alembic upgrade head' manually."
        echo "   Set SKIP_DB_MIGRATIONS=true to suppress this on startup."
    fi
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
