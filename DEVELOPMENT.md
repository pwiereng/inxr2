# Development Quick Reference

Quick reference for common development tasks and checklist.

## Docker Development Environment (Recommended)

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and running
- [VS Code](https://code.visualstudio.com/) or [Cursor](https://cursor.sh/) with the Dev Containers extension

### Quick Start with Dev Container (Recommended for Cursor/VS Code)

This is the easiest way to get started:

1. **Open in Cursor/VS Code**:
   ```bash
   git clone <repo-url>
   cd inxr2
   code .  # or: cursor .
   ```

2. **Reopen in Container**:
   - Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
   - Select: `Dev Containers: Reopen in Container`
   - Wait for the container to build (first time only, ~5 minutes)

3. **You're ready!** The container includes:
   - Python 3.11 with all dev tools
   - Node.js 18 with npm
   - PostgreSQL database (embedded inside the dev container)
   - All dependencies auto-installed on startup
   - VS Code extensions configured

   **Note**: Dependencies are automatically installed when the container starts. If you use docker-compose directly (not via VS Code/Cursor), the entrypoint script ensures packages are always installed.

### Alternative: Manual Docker Compose

If you prefer to run Docker manually without the dev container:

```bash
# Start the development environment
./scripts/dev-start.sh

# View logs
./scripts/dev-logs.sh

# Open a shell in the container
./scripts/dev-shell.sh

# Stop the environment
./scripts/dev-stop.sh

# Reset the database (WARNING: deletes all data)
./scripts/dev-reset-db.sh
```

### Services and Ports

When running, the following services are available:

- **PostgreSQL**: Embedded inside the dev container (`localhost:5432` from within container)
  - Database: `inxr2_dev`
  - User: `inxr2_user`
  - Password: `inxr2_dev_password`
- **Backend (FastAPI)**: `localhost:8000` (when started)
- **Frontend (Vite)**: `localhost:5173` (when started)

### Running Tests in Docker

```bash
# From inside the dev container (or use ./scripts/dev-shell.sh)
pytest --cov=src          # Run Python tests
npm test                  # Run TypeScript tests (in frontend/)
pytest --watch            # Watch mode for Python
npm test -- --watch      # Watch mode for TypeScript
```

### Troubleshooting Docker

**Container won't start?**
```bash
# Check if Docker is running
docker ps

# Rebuild the container
docker-compose -f docker-compose.dev.yml build --no-cache
./scripts/dev-start.sh
```

**Database connection issues?**
PostgreSQL is embedded inside the dev container. Check it's running:
```bash
docker exec inxr2-dev pg_isready -h localhost

# Reset the database
./scripts/dev-reset-db.sh
```

**Permission issues?**
The dev container runs as a non-root user (`devuser`). If you encounter permission issues, ensure your files are owned by UID 1000.

---

## Local Development (Without Docker)

> **⚠️ NOT RECOMMENDED:** Docker-based development is the supported workflow. Local development may have environment inconsistencies and is not officially supported. Use at your own risk.

If you prefer to develop without Docker:

### Quick Start

```bash
# Setup
git clone <repo-url>
cd inxr2

# Install PostgreSQL locally (required)
# macOS: brew install postgresql
# Ubuntu: sudo apt-get install postgresql

# Install Python dependencies
pip install -e ".[dev]"

# Install Node.js dependencies
cd frontend
npm install
cd ..

# Setup pre-commit hooks
pre-commit install

# Development
pytest --cov=src          # Run Python tests
npm test                  # Run TypeScript tests
pytest --watch            # Watch mode for Python
npm test -- --watch      # Watch mode for TypeScript
```

## Pre-Commit Checklist

Before every commit, ensure:

- [ ] **Tests pass**: `pytest && npm test`
- [ ] **Code formatted**: `black . && isort . && npm run format`
- [ ] **No lint errors**: `ruff check . && npm run lint`
- [ ] **Types check**: `mypy . && npm run type-check`
- [ ] **Tests added** for new features/fixes
- [ ] **Coverage maintained** (>80%)

## Pre-Push Checklist

Before pushing to remote:

- [ ] **All commits** have passed pre-commit checks
- [ ] **Full test suite** passes: `pytest --cov=src && npm test -- --coverage`
- [ ] **No typing errors**: `mypy src/ && tsc --noEmit`
- [ ] **Coverage report** reviewed (no significant decrease)
- [ ] **Integration tests** pass (if applicable)

## Quick Commands

### Python Backend

```bash
# Format code
black .
isort .

# Lint
ruff check .
ruff check . --fix  # Auto-fix issues

# Type check
# Run type checking inside the dev container to ensure consistent environment
docker exec inxr2-dev bash -c "cd /workspace && mypy src/inxr2"

# Test
pytest                              # All tests
pytest -v                          # Verbose
pytest --cov=src                   # With coverage
pytest --cov=src --cov-report=html # HTML coverage report
pytest tests/unit                  # Only unit tests
pytest -k "test_indexing"          # Run specific test pattern
pytest --watch                     # Watch mode

# Coverage report
open htmlcov/index.html  # View HTML coverage report
```

### TypeScript Frontend

```bash
# Format code
npm run format
npm run format:check  # Check without modifying

# Lint
npm run lint
npm run lint:fix  # Auto-fix issues

# Type check
npm run type-check

# Test
npm test                    # All tests
npm test -- --coverage     # With coverage
npm test -- --watch        # Watch mode
npm test -- CodeViewer     # Specific component
```

### Pre-commit Hooks

```bash
# Install hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Run on staged files only
pre-commit run

# Update hook versions
pre-commit autoupdate
```

## Common Development Workflows

### Adding a New Feature

1. **Create branch**: `git checkout -b feature/my-feature`
2. **Write tests first** (TDD approach):
   ```bash
   # Create test file
   touch tests/unit/test_my_feature.py
   # Write failing test
   # Run: pytest tests/unit/test_my_feature.py
   ```
3. **Implement feature** to make tests pass
4. **Run all tests**: `pytest && npm test`
5. **Format and lint**: `pre-commit run --all-files`
6. **Check coverage**: `pytest --cov=src --cov-report=term-missing`
7. **Commit**: `git commit -m "feat: add my feature"`

### Fixing a Bug

1. **Create branch**: `git checkout -b fix/bug-description`
2. **Write regression test** that reproduces the bug:
   ```python
   def test_bug_description():
       # Arrange: Set up conditions that trigger bug
       # Act: Execute code that has the bug
       # Assert: Verify expected behavior (test should fail initially)
   ```
3. **Fix the bug** to make test pass
4. **Run all tests**: `pytest && npm test`
5. **Verify fix**: `pytest tests/unit/test_bug_fix.py -v`
6. **Commit**: `git commit -m "fix: resolve bug description"`

### Refactoring

1. **Create branch**: `git checkout -b refactor/description`
2. **Run tests BEFORE refactoring**: `pytest && npm test` (ensure all pass)
3. **Make incremental changes**, running tests after each step
4. **Ensure tests still pass**: `pytest && npm test`
5. **Verify coverage unchanged**: `pytest --cov=src`
6. **Commit**: `git commit -m "refactor: improve description"`

## Testing Best Practices

### Python Tests

```python
# Good test structure
def test_index_file_extracts_function_symbols():
    # Arrange - set up test data and dependencies
    db = create_in_memory_db()
    parser = TreeSitterParser(language="python")
    test_file = "fixtures/simple.py"

    # Act - execute the code under test
    symbols = index_file(test_file, parser, db)

    # Assert - verify expected outcome
    assert len(symbols) > 0
    assert any(s.name == "calculate_total" and s.kind == "function"
               for s in symbols)
```

### TypeScript Tests

```typescript
// Good test structure
describe('SymbolSearch', () => {
  it('displays search results when query is entered', async () => {
    // Arrange
    const mockSymbols = [
      { name: 'calculate', kind: 'function', location: { ... } }
    ];
    render(<SymbolSearch />);

    // Act
    await userEvent.type(screen.getByRole('searchbox'), 'calculate');

    // Assert
    await waitFor(() => {
      expect(screen.getByText('calculate')).toBeInTheDocument();
    });
  });
});
```

### Avoid Over-Mocking

```python
# Bad - too much mocking
@patch('module.Database')
@patch('module.Parser')
@patch('module.GitClient')
def test_indexing(mock_git, mock_parser, mock_db):
    mock_db.return_value.save.return_value = None
    # ... lots of mock setup
    # Tests become brittle and don't catch real issues

# Good - use real lightweight implementations
def test_indexing():
    db = create_test_db()  # Real PostgreSQL test database
    parser = TreeSitterParser()  # Real parser
    git_client = TestGitClient(fixture="test-repo")  # Lightweight test impl
    # ... test with real behavior
```

## Debugging

### Python

```bash
# Run with debugger
pytest --pdb                    # Drop into debugger on failure
pytest --pdb --trace            # Start debugger immediately

# Debug specific test
python -m pdb -m pytest tests/unit/test_file.py::test_function

# Print debugging (temporarily)
import pprint
pprint.pprint(variable)
```

### TypeScript

```bash
# Run with Chrome DevTools
npm test -- --inspect-brk

# Debug in VS Code
# Add breakpoints, then use "Debug Test" code lens
# or use launch configuration
```

## Code Coverage

### View Coverage Reports

```bash
# Python - HTML report
pytest --cov=src --cov-report=html
open htmlcov/index.html

# Python - terminal report with missing lines
pytest --cov=src --cov-report=term-missing

# TypeScript - HTML report
npm test -- --coverage
open coverage/index.html
```

### Interpreting Coverage

- **Green (80%+)**: Good coverage
- **Yellow (60-80%)**: Needs improvement
- **Red (<60%)**: Insufficient coverage

Focus on:
- Covering edge cases
- Error handling paths
- Boundary conditions

Don't obsess over 100% - some code (like `__repr__`, error messages) doesn't need tests.

## Performance

### Profiling Python Code

```bash
# Profile with cProfile
python -m cProfile -o profile.stats script.py
python -m pstats profile.stats

# Line profiler
pip install line_profiler
kernprof -l -v script.py
```

### Benchmarking

```bash
# Python - use pytest-benchmark
pytest tests/benchmarks/ --benchmark-only

# Track performance over time
pytest tests/benchmarks/ --benchmark-autosave
```

## Continuous Integration

CI will automatically run on every PR:

1. **Formatting checks** (Black, Prettier)
2. **Linting** (Ruff, ESLint)
3. **Type checking** (mypy, tsc)
4. **Unit tests** (pytest, vitest)
5. **Integration tests**
6. **Coverage report** (must be >80%)

If CI fails, fix issues locally and push again.

## Environment Setup

### Python

```bash
# Dependencies are pre-installed in the Docker dev container
pip install -e ".[dev]"

# Verify setup
python --version  # Should be 3.11+
pytest --version
black --version
```

### TypeScript

```bash
# Install dependencies
npm install

# Verify setup
node --version   # Should be 18+
npm test -- --version
tsc --version
```

## Troubleshooting

### Tests Failing After Pull

```bash
# Update dependencies
pip install -e ".[dev]"
npm install

# Clear caches
pytest --cache-clear
npm test -- --clearCache

# Reset database migrations (if applicable)
# ...
```

### Import Errors in Tests

```bash
# Reinstall in development mode
pip install -e .

# Check Python path
python -c "import sys; print(sys.path)"
```

### Pre-commit Hooks Failing

```bash
# Update hooks
pre-commit autoupdate

# Clear cache and retry
pre-commit clean
pre-commit run --all-files
```

---

**For detailed guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md)**
