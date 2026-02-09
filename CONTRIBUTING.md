# Contributing to INXR2

This document outlines the coding standards, development practices, and guidelines for contributing to the INXR2 cross-reference code browser.

## Table of Contents

- [⚠️ CRITICAL: Docker-Only Development](#️-critical-docker-only-development)
- [Development Philosophy](#development-philosophy)
- [Code Style](#code-style)
- [Testing Requirements](#testing-requirements)
- [Development Workflow](#development-workflow)
- [Python Backend Standards](#python-backend-standards)
- [TypeScript Frontend Standards](#typescript-frontend-standards)
- [Git Commit Guidelines](#git-commit-guidelines)

## ⚠️ CRITICAL: Docker-Only Development

**ALL development work MUST be done within Docker containers. This is non-negotiable.**

### Docker Development Rules

1. **Package Management in Docker ONLY**
   - ❌ NEVER run `pip install`, `uv pip install`, or `npm install` on your host machine
   - ✅ ALWAYS install packages inside the Docker container
   - Python packages: `docker exec inxr2-dev bash -c "cd /workspace && uv pip install <package>"`
   - Node packages: `docker exec inxr2-dev bash -c "cd /workspace/frontend && npm install <package>"`

2. **Use Virtual Environments (Python)**
   - Python packages MUST use `uv` with the virtual environment at `/home/devuser/.venv`
   - The `VIRTUAL_ENV` environment variable is set automatically in the container
   - Never use `pip` directly - always use `uv pip` for consistency

3. **Volume Permissions**
   - `node_modules` uses a named Docker volume to avoid Mac/Linux binary incompatibility
   - Changes to package files must be made in the container or via docker exec
   - If you encounter permission errors, check `scripts/docker-entrypoint.sh`

4. **Running Commands**
   ```bash
   # Correct - inside container
   docker exec inxr2-dev bash -c "cd /workspace && pytest"
   docker exec inxr2-dev bash -c "cd /workspace/frontend && npm test"

   # Or use the provided scripts
   ./scripts/run-all-tests.sh
   ./scripts/dev-shell.sh  # Opens interactive shell in container
   ```

5. **Clean Rebuild Workflow**
   ```bash
   # When things are broken or after major changes
   ./scripts/clean-rebuild.sh

   # This will:
   # - Remove all Docker containers, volumes, and images
   # - Rebuild everything from scratch
   # - Optionally run all automated tests
   ```

### Package Quality Requirements

**CRITICAL: All packages must meet these criteria:**

1. **No Deprecated Packages**
   - Before adding a package, check if it's actively maintained
   - Check GitHub last commit date (< 6 months old preferred)
   - Check npm/PyPI download trends
   - Check for deprecation warnings

2. **No Vulnerable Packages**
   - Run `npm audit` for Node packages (zero vulnerabilities required)
   - Check Python package security advisories
   - Use latest stable versions when possible

3. **Well-Supported Packages**
   - Prefer packages with:
     - Active maintenance (recent commits)
     - Good documentation
     - Strong community (stars, downloads, issues resolved)
     - Compatible with our stack (Python 3.11+, React 18+)

4. **Version Pinning**
   - Use caret (`^`) for minor version updates in package.json
   - Pin major versions in pyproject.toml
   - Document why specific versions are chosen if pinned exactly

## Development Philosophy

### Core Principles

1. **Modularity**: Design components with clear, single responsibilities
2. **Clean Code**: Write self-documenting code that is easy to understand and maintain
3. **Testability**: All code must be testable with high coverage
4. **Simplicity**: Prefer simple, straightforward solutions over clever abstractions
5. **Dependency Injection**: Use constructor injection and interfaces over mocking

### Clean Code Principles

- **Single Responsibility**: Each module, class, and function should do one thing well
- **DRY (Don't Repeat Yourself)**: Extract common logic into reusable components
- **SOLID Principles**: Follow SOLID design principles, especially:
  - Single Responsibility Principle
  - Dependency Inversion Principle (depend on abstractions, not concretions)
- **Meaningful Names**: Use descriptive, intention-revealing names
- **Small Functions**: Keep functions focused and concise
- **Minimal Comments**: Code should be self-explanatory; use comments only for "why" not "what"

## Code Style

### Formatting and Linting

**⚠️ CRITICAL: All code must pass formatting and linting checks BEFORE committing.**

**Python:**
- **Black** for code formatting (line length: 88)
- **isort** for import sorting (profile: black)
- **Ruff** for linting
- **mypy** for type checking (strict mode)

**TypeScript:**
- **Prettier** for code formatting
- **ESLint** for linting (ESLint 9 flat config)
- **TypeScript strict mode** enabled

### Running Formatters

**All formatters MUST run in Docker containers:**

```bash
# Python (run in container)
docker exec inxr2-dev bash -c "cd /workspace && black ."
docker exec inxr2-dev bash -c "cd /workspace && isort ."
docker exec inxr2-dev bash -c "cd /workspace && ruff check ."
docker exec inxr2-dev bash -c "cd /workspace && mypy src/inxr2"

# IMPORTANT: Always run `mypy` inside the development container. Do NOT run
# type checks against your host environment — the project is configured and
# validated against the container's Python environment. Example:
#
# ```bash
# docker exec inxr2-dev bash -c "cd /workspace && mypy src/inxr2"
# ```

# TypeScript (run in container)
docker exec inxr2-dev bash -c "cd /workspace/frontend && npm run format"
docker exec inxr2-dev bash -c "cd /workspace/frontend && npm run lint"
docker exec inxr2-dev bash -c "cd /workspace/frontend && npm run type-check"

# Check everything with one command (RECOMMENDED)
./scripts/run-all-tests.sh
```

**The test script will fail if any formatting or linting issues exist.**

## Testing Requirements

**CRITICAL: All code changes MUST include tests. No exceptions.**

### Test Coverage

- **Minimum coverage**: 80% overall (enforced in CI)
- **Target coverage**: 90%+
- All new features must include tests BEFORE code review
- All bug fixes must include regression tests
- Coverage must not decrease with any PR

### Test Philosophy

**⚠️ CRITICAL: Dependency Injection Over Mocking**

This is a core principle of our testing approach:

- ✅ **USE**: Dependency injection with real or lightweight implementations
- ❌ **AVOID**: Mocking libraries (jest.fn(), unittest.mock, etc.) wherever possible

**Why Dependency Injection:**
- Tests real behavior, not mocked behavior
- Catches integration issues early
- Makes tests more maintainable
- Forces better architecture (loose coupling)

**Implementation Guidelines:**
- Inject dependencies through constructors/parameters
- Use a PostgreSQL test database instead of mocking DB calls
- Create lightweight test fixtures and factories
- Inject fake/stub implementations that follow the same interface
- Only mock external services you can't control (third-party APIs, network calls)

**Example:**
```python
# ✅ GOOD - Dependency injection
def test_search_symbols():
    fake_repo = InMemorySymbolRepository([symbol1, symbol2])
    use_case = SearchSymbolsUseCase(repository=fake_repo)
    result = use_case.execute(SearchRequest(query="test"))
    assert len(result.symbols) == 2

# ❌ BAD - Mocking
def test_search_symbols():
    mock_repo = Mock()
    mock_repo.search.return_value = [symbol1, symbol2]
    use_case = SearchSymbolsUseCase(repository=mock_repo)
    # ...
```

**Test Structure:**
- Use Arrange-Act-Assert pattern
- One logical assertion per test (multiple assertions on same object are fine)
- Tests should be independent and isolated
- Tests should be deterministic (no flaky tests)

### Running Tests

**⚠️ CRITICAL: ALWAYS run tests before and after making changes**

**All tests must run in Docker containers:**

```bash
# Use the comprehensive test script (RECOMMENDED)
./scripts/run-all-tests.sh    # Runs ALL tests, linting, and security checks

# Or run tests individually in container
docker exec inxr2-dev bash -c "cd /workspace && pytest --cov=src"
docker exec inxr2-dev bash -c "cd /workspace/frontend && npm test -- --coverage"

# Backend tests (Python)
docker exec inxr2-dev bash -c "cd /workspace && pytest"
docker exec inxr2-dev bash -c "cd /workspace && pytest -v"
docker exec inxr2-dev bash -c "cd /workspace && pytest tests/unit"

# Frontend tests (TypeScript)
docker exec inxr2-dev bash -c "cd /workspace/frontend && npm test"
docker exec inxr2-dev bash -c "cd /workspace/frontend && npm test -- --watch"
```

### Test Organization

```
tests/
├── unit/              # Fast, isolated unit tests
│   ├── domain/        # Domain entity tests
│   ├── application/   # Use case tests with fakes
│   └── adapters/      # Adapter-specific tests
├── integration/       # Tests with real dependencies (DB, file system)
│   ├── adapters/      # Database integration tests
│   └── api/           # API endpoint tests
├── adapters/          # Adapter tests
│   ├── cli/           # CLI command tests
│   └── external/      # External service tests (Git, TreeSitter)
└── fixtures/          # Shared test data and factories

frontend/              # Frontend tests (separate)
└── src/
    └── test/          # Vitest tests
```

## Development Workflow

### Before Making Changes

1. **Pull latest changes**: `git pull origin main`
2. **Create a feature branch**: `git checkout -b feature/your-feature-name`
3. **Run existing tests**: Ensure all tests pass before you start
   ```bash
   pytest
   npm test
   ```

### During Development

1. **Write tests first** (TDD approach encouraged)
2. **Implement the feature/fix**
3. **Run tests frequently**: After each logical change
   ```bash
   pytest tests/unit/your_test.py  # Run specific test file
   npm test -- YourComponent      # Run specific component tests
   ```
4. **Format code**: Run formatters before committing
5. **Run full test suite**: Before pushing
   ```bash
   pytest --cov=src
   npm test -- --coverage
   ```

### Before Committing

**⚠️ MANDATORY: Run this command BEFORE every commit:**

```bash
./scripts/run-all-tests.sh
```

Note: `./scripts/run-all-tests.sh` runs `mypy` inside the `inxr2-dev` container
as part of the Python quality checks. If you need to run `mypy` manually,
use the container command shown above.

**This script is REQUIRED and checks:**
- ✅ All backend tests with coverage
- ✅ All frontend tests with coverage
- ✅ Python code quality (black, isort, ruff, mypy)
- ✅ TypeScript code quality (eslint, prettier, tsc)
- ✅ Security audit (npm audit)

**If this script fails, DO NOT commit. Fix the issues first.**

**Pre-commit Checklist:**
- [ ] `./scripts/run-all-tests.sh` passes with zero errors
- [ ] All tests pass (21+ backend, 17+ frontend)
- [ ] Code is formatted (Black, Prettier)
- [ ] No linting errors (Ruff, ESLint)
- [ ] Type checks pass (mypy, tsc --noEmit)
- [ ] New code has tests with good coverage
- [ ] Test coverage hasn't decreased
- [ ] No security vulnerabilities (npm audit clean)
- [ ] All changes run in Docker (not on host machine)

### Automated Checks

Use pre-commit hooks to automate these checks:

```bash
# Install pre-commit hooks (run in container)
docker exec inxr2-dev bash -c "cd /workspace && pre-commit install"

# Run manually
docker exec inxr2-dev bash -c "cd /workspace && pre-commit run --all-files"
```

## Python Backend Standards

### Code Organization (Clean Architecture)

```
src/inxr2/
├── domain/                # Layer 1: Pure business logic
│   ├── entities/          # Repository, Commit, File, Symbol, Reference
│   ├── value_objects/     # SymbolKind, CommitHash, ReferenceType
│   ├── exceptions/        # Domain-specific exceptions
│   └── services/          # Domain services (LanguageDetector)
├── application/           # Layer 2: Use cases & ports
│   ├── use_cases/         # Business workflows
│   ├── ports/             # Abstract interfaces (ABC)
│   └── dtos/              # Data Transfer Objects
├── adapters/              # Layer 3: Interface adapters
│   ├── api/               # FastAPI controllers
│   ├── cli/               # CLI commands
│   ├── persistence/       # Database adapters & ORM models
│   └── external/          # Git, TreeSitter, filesystem
└── infrastructure/        # Layer 4: Framework setup
    ├── fastapi/           # FastAPI app configuration
    ├── database/          # Database connection & migrations
    └── config/            # Settings & DI container
```

### Type Hints

**Always use type hints:**

```python
# Good
def index_file(file_path: str, repo_id: int) -> list[Symbol]:
    """Index a single file and return extracted symbols."""
    symbols: list[Symbol] = []
    # ...
    return symbols

# Bad - no type hints
def index_file(file_path, repo_id):
    symbols = []
    # ...
    return symbols
```

### Dependency Injection

**Use constructor injection:**

```python
# Good - dependencies injected
class IndexingService:
    def __init__(
        self,
        db: Database,
        parser: CodeParser,
        git_client: GitClient
    ):
        self.db = db
        self.parser = parser
        self.git_client = git_client

    def index_repository(self, repo_url: str) -> None:
        # Use injected dependencies
        files = self.git_client.list_files(repo_url)
        # ...

# Bad - hard-coded dependencies
class IndexingService:
    def __init__(self):
        self.db = PostgresDatabase()  # Hard to test
        self.parser = TreeSitterParser()  # Hard to test
```

### Testing Example

```python
# tests/unit/indexing/test_indexing_service.py
import pytest
from src.core.indexing import IndexingService
from tests.fixtures.database import create_test_db
from tests.fixtures.git import create_test_git_client

def test_index_repository_extracts_symbols():
    # Arrange - use real lightweight implementations
    db = create_test_db()  # PostgreSQL test database
    parser = TreeSitterParser()
    git_client = create_test_git_client(fixture_repo="simple-python")
    service = IndexingService(db, parser, git_client)

    # Act
    service.index_repository("test-repo")

    # Assert
    symbols = db.get_symbols(repo="test-repo")
    assert len(symbols) > 0
    assert any(s.name == "main" for s in symbols)
```

### Python Tools Configuration

**pyproject.toml:**
```toml
[tool.black]
line-length = 88
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 88

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = "--strict-markers --cov=src --cov-report=term-missing"

[tool.coverage.run]
source = ["src"]
omit = ["tests/*", "**/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

## TypeScript Frontend Standards

### Code Organization

```
frontend/
├── src/
│   ├── components/       # React components
│   │   ├── CodeViewer/
│   │   ├── Search/
│   │   └── Navigation/
│   ├── hooks/            # Custom React hooks
│   ├── services/         # API clients and business logic
│   ├── types/            # TypeScript type definitions
│   ├── utils/            # Shared utilities
│   └── __tests__/        # Co-located tests
└── public/
```

### TypeScript Standards

**Always use TypeScript, never any:**

```typescript
// Good - explicit types
interface Symbol {
  name: string;
  kind: SymbolKind;
  location: Location;
}

function searchSymbols(query: string): Promise<Symbol[]> {
  return apiClient.get<Symbol[]>(`/api/symbols?q=${query}`);
}

// Bad - using any
function searchSymbols(query: any): Promise<any> {
  return apiClient.get(`/api/symbols?q=${query}`);
}
```

**Use strict mode:**

```json
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "strictFunctionTypes": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true
  }
}
```

### React Component Standards

**Use functional components with TypeScript:**

```typescript
// Good
interface CodeViewerProps {
  filePath: string;
  content: string;
  onLineClick?: (lineNumber: number) => void;
}

export const CodeViewer: React.FC<CodeViewerProps> = ({
  filePath,
  content,
  onLineClick
}) => {
  const [selectedLine, setSelectedLine] = useState<number | null>(null);

  const handleLineClick = (lineNum: number) => {
    setSelectedLine(lineNum);
    onLineClick?.(lineNum);
  };

  return (
    <div className="code-viewer">
      {/* ... */}
    </div>
  );
};
```

### Testing Frontend Components

```typescript
// src/components/CodeViewer/__tests__/CodeViewer.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { CodeViewer } from '../CodeViewer';

describe('CodeViewer', () => {
  it('renders code content with line numbers', () => {
    const content = 'def main():\n    print("hello")';

    render(<CodeViewer filePath="test.py" content={content} />);

    expect(screen.getByText(/def main/)).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('calls onLineClick when line number is clicked', () => {
    const handleLineClick = jest.fn();

    render(
      <CodeViewer
        filePath="test.py"
        content="line 1\nline 2"
        onLineClick={handleLineClick}
      />
    );

    fireEvent.click(screen.getByText('1'));

    expect(handleLineClick).toHaveBeenCalledWith(1);
  });
});
```

### Frontend Tools Configuration

**package.json scripts:**
```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "test": "vitest",
    "test:coverage": "vitest --coverage",
    "lint": "eslint . --ext .ts,.tsx",
    "lint:fix": "eslint . --ext .ts,.tsx --fix",
    "format": "prettier --write \"src/**/*.{ts,tsx,css}\"",
    "format:check": "prettier --check \"src/**/*.{ts,tsx,css}\"",
    "type-check": "tsc --noEmit"
  }
}
```

**.prettierrc:**
```json
{
  "semi": true,
  "trailingComma": "es5",
  "singleQuote": true,
  "printWidth": 100,
  "tabWidth": 2,
  "useTabs": false
}
```

**.eslintrc.json:**
```json
{
  "extends": [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended",
    "prettier"
  ],
  "parser": "@typescript-eslint/parser",
  "plugins": ["@typescript-eslint", "react", "react-hooks"],
  "rules": {
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/explicit-function-return-type": "warn",
    "react/prop-types": "off",
    "react/react-in-jsx-scope": "off"
  }
}
```

## Git Commit Guidelines

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `perf`: Performance improvements
- `chore`: Build process, dependencies, tooling

**Examples:**
```
feat(indexing): add incremental indexing support

Implement git diff-based incremental indexing to avoid
re-parsing unchanged files. Reduces indexing time by 80%
for typical updates.

Closes #42

---

fix(search): handle special characters in symbol search

Escape regex special characters before executing search
to prevent query errors.

---

test(parser): add tests for C++ template parsing

Add comprehensive test coverage for tree-sitter C++
template extraction.
```

### Branch Naming

- `feature/short-description` - New features
- `fix/short-description` - Bug fixes
- `refactor/short-description` - Refactoring
- `test/short-description` - Test additions/improvements

## Code Review Guidelines

### For Authors

- Run full test suite before requesting review
- Ensure CI passes
- Keep PRs focused and reasonably sized
- Add tests for new functionality
- Update documentation if needed

### For Reviewers

- Check for test coverage
- Verify clean code principles
- Look for proper dependency injection
- Ensure type safety (no `any` in TypeScript, proper type hints in Python)
- Validate that tests actually test the intended behavior

## Continuous Integration

All PRs must pass:
- [ ] All tests (unit + integration)
- [ ] Code formatting checks (Black, Prettier)
- [ ] Linting (Ruff/Pylint, ESLint)
- [ ] Type checking (mypy, tsc)
- [ ] Minimum 80% code coverage
- [ ] No decrease in overall coverage

## Questions?

If you have questions about these guidelines or need clarification, please open an issue for discussion.

---

**Remember:** The goal is maintainable, testable, high-quality code. When in doubt, prioritize simplicity and clarity over cleverness.
