# Contributing to INXR2

This document outlines the coding standards, development practices, and guidelines for contributing to the INXR2 cross-reference code browser.

## Table of Contents

- [Development Philosophy](#development-philosophy)
- [Code Style](#code-style)
- [Testing Requirements](#testing-requirements)
- [Development Workflow](#development-workflow)
- [Python Backend Standards](#python-backend-standards)
- [TypeScript Frontend Standards](#typescript-frontend-standards)
- [Git Commit Guidelines](#git-commit-guidelines)

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

All code must pass formatting and linting checks before being committed.

**Python:**
- **Black** for code formatting (line length: 100)
- **isort** for import sorting
- **Ruff** or **Pylint** for linting
- **mypy** for type checking

**TypeScript:**
- **Prettier** for code formatting
- **ESLint** for linting
- **TypeScript strict mode** enabled

### Running Formatters

```bash
# Python
black .
isort .
ruff check .
mypy .

# TypeScript
npm run format    # Prettier
npm run lint      # ESLint
npm run type-check  # TypeScript compiler
```

## Testing Requirements

### Test Coverage

- **Minimum coverage**: 80% overall
- **Target coverage**: 90%+
- All new features must include tests
- All bug fixes must include regression tests

### Test Philosophy

**Avoid Mocking - Use Real Dependencies:**
- Prefer dependency injection and real implementations over mocks
- Use in-memory databases (e.g., SQLite in-memory) instead of mocking database calls
- Create lightweight test fixtures and factories
- Only mock external services that can't be controlled (third-party APIs, network calls)

**Test Structure:**
- Use Arrange-Act-Assert pattern
- One logical assertion per test (multiple assertions on same object are fine)
- Tests should be independent and isolated
- Tests should be deterministic (no flaky tests)

### Running Tests

**CRITICAL: Always run tests before and after making changes**

```bash
# Python backend tests
pytest                          # Run all tests
pytest --cov=src --cov-report=html  # With coverage report
pytest -v                       # Verbose output
pytest tests/unit              # Only unit tests
pytest tests/integration       # Only integration tests

# TypeScript frontend tests
npm test                       # Run all tests
npm test -- --coverage        # With coverage
npm test -- --watch           # Watch mode during development
```

### Test Organization

```
tests/
├── unit/              # Fast, isolated unit tests
│   ├── backend/
│   │   ├── parsers/
│   │   ├── indexing/
│   │   └── api/
│   └── frontend/
│       ├── components/
│       └── utils/
├── integration/       # Tests with real dependencies (DB, file system)
│   ├── indexing/
│   ├── api/
│   └── database/
└── fixtures/          # Shared test data and factories
    ├── repositories/
    └── data/
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

**Pre-commit Checklist:**
- [ ] All tests pass
- [ ] Code is formatted (Black, Prettier)
- [ ] No linting errors
- [ ] Type checks pass (mypy, tsc)
- [ ] New code has tests
- [ ] Test coverage hasn't decreased

### Automated Checks

Use pre-commit hooks to automate these checks:

```bash
# Install pre-commit hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Python Backend Standards

### Code Organization

```
backend/
├── src/
│   ├── api/              # FastAPI routes and endpoints
│   ├── core/             # Core business logic
│   │   ├── indexing/     # Indexing engine
│   │   ├── parsing/      # Tree-sitter parsers
│   │   └── search/       # Search functionality
│   ├── db/               # Database models and queries
│   │   ├── models.py
│   │   └── repositories.py
│   ├── config/           # Configuration management
│   └── utils/            # Shared utilities
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
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
    db = create_test_db()  # In-memory SQLite
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
line-length = 100
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 100

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
