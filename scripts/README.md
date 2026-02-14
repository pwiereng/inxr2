# INXR2 Scripts

Utility scripts for development and testing.

## Starting INXR2

```bash
./scripts/dev-start.sh                                    # Start Docker environment
docker exec -it inxr2-dev ./scripts/dev-serve.sh          # Start backend + frontend
```

Or start services separately:
```bash
docker exec -d inxr2-dev inxr2 serve --reload             # Backend on :8000
docker exec -d inxr2-dev bash -c 'cd frontend && npm run dev'  # Frontend on :5173
```

## Monitoring Logs

```bash
docker logs -f inxr2-dev             # Backend access + error logs
./scripts/dev-logs.sh                # All container logs
./scripts/dev-logs.sh postgres       # PostgreSQL logs only
```

## Scripts Reference

### Development

| Script | Run from | Purpose |
|--------|----------|---------|
| `dev-start.sh` | Host | Start Docker environment (`docker-compose up -d --build`) |
| `dev-stop.sh` | Host | Stop Docker environment |
| `dev-shell.sh` | Host | Open bash shell in dev container |
| `dev-serve.sh` | Container | Start backend + frontend together (Ctrl+C to stop both) |
| `dev-logs.sh` | Host | Tail container logs (optionally filter by service name) |

### Testing

| Script | Run from | Purpose |
|--------|----------|---------|
| `run-all-tests.sh` | Host or Container | Backend tests, frontend tests, linting, security audit |

### Other

| File | Purpose |
|------|---------|
| `verify-setup.sh` | Check containers, env vars, DB connection, migrations, imports |
| `docker-entrypoint.sh` | Container entrypoint — installs deps, fixes permissions |
| `init-test-db.sql` | Creates `inxr2_test` database on first postgres boot |

## Common Workflows

### First Time Setup
```bash
./scripts/dev-start.sh
docker exec inxr2-dev alembic upgrade head    # Apply migrations
./scripts/run-all-tests.sh                    # Verify everything works
```

### Daily Development
```bash
./scripts/dev-start.sh                                    # Start containers
docker exec -it inxr2-dev ./scripts/dev-serve.sh          # Start servers
```

### Clean Rebuild (fresh database)
```bash
docker-compose -f docker-compose.dev.yml down -v          # Stop + delete volumes
docker-compose -f docker-compose.dev.yml up -d --build    # Rebuild + start
docker exec inxr2-dev alembic upgrade head                # Apply migrations
```

### Before Committing
```bash
./scripts/run-all-tests.sh
```

## Docker Commands Reference

```bash
# Container management
docker-compose -f docker-compose.dev.yml up -d            # Start
docker-compose -f docker-compose.dev.yml down             # Stop
docker-compose -f docker-compose.dev.yml down -v          # Stop + delete volumes (DB reset)
docker-compose -f docker-compose.dev.yml ps               # Status

# Execute commands in container
docker exec inxr2-dev <command>                           # Run command
docker exec -it inxr2-dev bash                            # Interactive shell

# Indexing
docker exec inxr2-dev inxr2 index --config config.yaml                # Index all repos
docker exec inxr2-dev inxr2 index --config config.yaml --repo inxr2   # Index one repo
docker exec inxr2-dev inxr2 index --config config.yaml --force        # Force re-index
```

## Package Management

All package management must happen inside the container:

```bash
# Python
docker exec inxr2-dev uv pip install <package>
docker exec inxr2-dev uv pip install -e '.[dev]'

# Node.js
docker exec inxr2-dev bash -c 'cd frontend && npm install <package>'
```
