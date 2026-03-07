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

# Create role if it doesn't exist (uses POSTGRES_PASSWORD from env, or default)
PG_ROLE="${POSTGRES_USER:-inxr2_user}"
PG_PASS="${POSTGRES_PASSWORD:-inxr2_dev_password}"
# Validate role/password don't contain shell metacharacters (dev-only safety)
if echo "$PG_ROLE" | grep -qE "[^a-zA-Z0-9_]" || echo "$PG_ROLE" | grep -qE "^[0-9]"; then
    echo "❌ POSTGRES_USER must start with a letter or underscore, and contain only alphanumeric and _"
    exit 1
fi
if echo "$PG_PASS" | grep -qE "['\\\";]"; then
    echo "❌ POSTGRES_PASSWORD contains invalid characters (no quotes, backslashes, or semicolons)"
    exit 1
fi
PG_DB="${POSTGRES_DB:-inxr2_dev}"
if echo "$PG_DB" | grep -qE "[^a-zA-Z0-9_]" || echo "$PG_DB" | grep -qE "^[0-9]"; then
    echo "❌ POSTGRES_DB must start with a letter or underscore, and contain only alphanumeric and _"
    exit 1
fi
if ! psql -h localhost -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$PG_ROLE'" | grep -q 1; then
    echo "🗄️  Creating $PG_ROLE role..."
    psql -h localhost -d postgres -c "CREATE ROLE $PG_ROLE WITH LOGIN PASSWORD '$PG_PASS' CREATEDB;"
    echo "✅ Role created"
fi

# Create databases if they don't exist
for db in "$PG_DB" inxr2_test; do
    if ! psql -h localhost -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1; then
        echo "🗄️  Creating database $db..."
        psql -h localhost -d postgres -c "CREATE DATABASE $db OWNER $PG_ROLE;"
        echo "✅ Database $db created"
    fi
done

echo "✅ PostgreSQL ready (databases: inxr2_dev, inxr2_test)"

# =============================================================================
# Python / Node Setup
# =============================================================================

# Python packages are pre-installed into system Python at image build time.
# No venv activation needed — Docker provides isolation.

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

# =============================================================================
# MCP Server (background — SSE transport on port 3000)
# =============================================================================

echo "Starting MCP server..."
cd /workspace/mcp-server && \
MCP_TRANSPORT=sse \
MCP_PORT="${MCP_PORT:-3000}" \
INXR2_API_URL="http://localhost:8000" \
INXR2_FRONTEND_URL="${INXR2_FRONTEND_URL-http://localhost:5173}" \
python -m src.server \
    > /tmp/mcp-server.log 2>&1 &
cd /workspace
echo "MCP server started (port ${MCP_PORT:-3000}, log: /tmp/mcp-server.log)"

echo "Container ready!"

# Execute the main command (e.g., /bin/bash)
exec "$@"
