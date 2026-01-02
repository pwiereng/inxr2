# INXR2 Scripts

Utility scripts for development, building, testing, and deployment.

## 🔨 Build & Clean Scripts

### `clean.sh`
Removes all Docker containers, volumes, images, and local packages.

```bash
./scripts/clean.sh
```

**What it removes:**
- Docker containers (dev and postgres)
- Docker volumes (postgres_data, pip_cache, node_modules)
- Docker images
- Local `frontend/node_modules/`

### `build.sh`
Builds Docker images and starts containers.

```bash
./scripts/build.sh                # Build with cache
./scripts/build.sh --no-cache     # Clean build (no cache)
```

**What it does:**
- Builds Docker images
- Starts containers
- Verifies package installation

### `clean-rebuild.sh`
Combines clean + build for a complete rebuild.

```bash
./scripts/clean-rebuild.sh
```

**What it does:**
1. Runs `clean.sh`
2. Runs `build.sh --no-cache`
3. Optionally runs `run-all-tests.sh`

## 🧪 Testing Scripts

### `run-all-tests.sh`
Runs complete test suite: backend tests, frontend tests, and code quality checks.

```bash
./scripts/run-all-tests.sh
```

**What it tests:**
- Backend: pytest with coverage
- Frontend: vitest with coverage
- Python: black, isort, ruff, mypy
- TypeScript: eslint, prettier, tsc
- Security: npm audit

**Exit codes:**
- `0` - All tests passed
- `1` - One or more tests failed

## 🛠️ Development Scripts

### `dev-start.sh`
Start the development environment.

```bash
./scripts/dev-start.sh
```

### `dev-stop.sh`
Stop the development environment.

```bash
./scripts/dev-stop.sh
```

### `dev-shell.sh`
Open a bash shell in the development container.

```bash
./scripts/dev-shell.sh
```

### `dev-logs.sh`
View logs from the development container.

```bash
./scripts/dev-logs.sh
```

### `dev-reset-db.sh`
Reset the PostgreSQL database.

```bash
./scripts/dev-reset-db.sh
```

⚠️ **Warning:** This deletes all database data!

## 📋 Common Workflows

### First Time Setup
```bash
./scripts/build.sh
./scripts/run-all-tests.sh
```

### Clean Rebuild (after major changes)
```bash
./scripts/clean-rebuild.sh
```

### Daily Development
```bash
./scripts/dev-start.sh        # Start containers
./scripts/dev-shell.sh        # Open shell

# Inside container:
inxr2 serve --reload          # Start backend
cd frontend && npm run dev    # Start frontend

# Run tests before committing:
pytest --cov=src              # Backend tests
cd frontend && npm test       # Frontend tests
```

### Before Pushing to Git
```bash
./scripts/run-all-tests.sh    # Ensure everything passes
```

### Troubleshooting
```bash
./scripts/clean.sh            # Clean everything
./scripts/build.sh --no-cache # Rebuild from scratch
./scripts/dev-logs.sh         # Check logs for errors
```

## 🐳 Docker Commands Reference

```bash
# Manual container management
docker-compose -f docker-compose.dev.yml up -d     # Start
docker-compose -f docker-compose.dev.yml down      # Stop
docker-compose -f docker-compose.dev.yml ps        # Status
docker-compose -f docker-compose.dev.yml logs -f   # Follow logs

# Execute commands in container
docker exec inxr2-dev <command>                    # Run command
docker exec -it inxr2-dev bash                     # Interactive shell

# Clean up
docker system prune -a --volumes                   # Remove all unused
```

## 📦 Package Management

### Python (using uv)
```bash
docker exec inxr2-dev bash -c "cd /workspace && uv pip install <package>"
docker exec inxr2-dev bash -c "cd /workspace && uv pip list --outdated"
```

### Node.js
```bash
docker exec inxr2-dev bash -c "cd /workspace/frontend && npm install <package>"
docker exec inxr2-dev bash -c "cd /workspace/frontend && npm outdated"
```

## 🔐 CI/CD Integration

For continuous integration, use:

```bash
# In CI pipeline
./scripts/build.sh --no-cache
./scripts/run-all-tests.sh

# Check exit code
if [ $? -eq 0 ]; then
  echo "All tests passed"
else
  echo "Tests failed"
  exit 1
fi
```
