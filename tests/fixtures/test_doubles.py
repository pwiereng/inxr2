"""
Test doubles (fakes) for testing - implements ports for testing.

ARCHITECTURE PATTERN: Dependency Injection over Mocking
========================================================

This module provides fake implementations of ports (interfaces) for testing.
These are REAL implementations that follow the interface contract, not mocks.

Why use test doubles instead of mocking frameworks?
---------------------------------------------------
✅ More maintainable - tests don't break when implementation changes
✅ Clearer intent - explicit test data setup
✅ Faster - no mocking framework overhead
✅ Follows port/adapter pattern - respects the architecture
✅ Type-safe - real implementations catch interface changes

Example Usage:
--------------
```python
# DON'T: Use mocking framework
from unittest.mock import Mock
mock_repo = Mock(spec=SymbolRepositoryPort)
mock_repo.find_by_name.return_value = [...]

# DO: Use test double (fake)
from tests.fixtures.test_doubles import FakeSymbolRepository
fake_repo = FakeSymbolRepository()
fake_repo.add_test_symbol(Symbol(...))
```
"""

from pathlib import Path

from inxr2.domain.entities import Symbol, File
from inxr2.application.ports.repositories import SymbolRepositoryPort, FileRepositoryPort
from inxr2.application.ports.services import ParserServicePort, GitServicePort


# ============================================================================
# Repository Test Doubles
# ============================================================================


class InMemorySymbolRepository(SymbolRepositoryPort):
    """
    In-memory implementation of SymbolRepositoryPort for testing.

    This is a test double (fake) that implements the port interface
    using in-memory storage instead of a database.

    Usage:
        repo = InMemorySymbolRepository()
        repo.add(Symbol(...))  # Add test data
        result = await repo.find_by_name("foo")  # Test
    """

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._symbols: dict[str, Symbol] = {}

    async def save(self, symbol: Symbol) -> Symbol:
        """Save symbol to in-memory storage."""
        self._symbols[symbol.id] = symbol
        return symbol

    async def find_by_id(self, symbol_id: str) -> Symbol | None:
        """Find symbol by ID."""
        return self._symbols.get(symbol_id)

    async def find_by_name(
        self, name: str, repository_id: str | None = None
    ) -> list[Symbol]:
        """Find symbols by name (case-insensitive)."""
        results = []
        for symbol in self._symbols.values():
            if name.lower() in symbol.name.lower():
                # Filter by repository if specified
                if repository_id is None or symbol.file_id.startswith(repository_id):
                    results.append(symbol)
        return results

    # Test helper methods
    def add(self, symbol: Symbol) -> None:
        """Add a symbol for testing (convenience method)."""
        self._symbols[symbol.id] = symbol

    def clear(self) -> None:
        """Clear all symbols (for test isolation)."""
        self._symbols.clear()

    def count(self) -> int:
        """Get total symbol count (for assertions)."""
        return len(self._symbols)


class InMemoryFileRepository(FileRepositoryPort):
    """
    In-memory implementation of FileRepositoryPort for testing.

    Example:
        repo = InMemoryFileRepository()
        repo.add(File(...))
        file = await repo.find_by_id("file-1")
    """

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._files: dict[str, File] = {}

    async def save(self, file: File) -> File:
        """Save file to in-memory storage."""
        self._files[file.id] = file
        return file

    async def find_by_id(self, file_id: str) -> File | None:
        """Find file by ID."""
        return self._files.get(file_id)

    # Test helper methods
    def add(self, file: File) -> None:
        """Add a file for testing."""
        self._files[file.id] = file

    def clear(self) -> None:
        """Clear all files."""
        self._files.clear()


# ============================================================================
# Service Test Doubles
# ============================================================================


class StubParserService(ParserServicePort):
    """
    Stub implementation of ParserServicePort for testing.

    A stub returns predefined responses. Useful when you need to
    control exactly what the parser returns in tests.

    Example:
        parser = StubParserService()
        parser.set_symbols_for_file("main.py", [Symbol(...), Symbol(...)])
        symbols = await parser.parse_file(Path("main.py"), "python")
    """

    def __init__(self) -> None:
        """Initialize with empty responses."""
        self._responses: dict[str, list[Symbol]] = {}

    async def parse_file(self, file_path: Path, language: str) -> list[Symbol]:
        """Return predefined symbols for the file."""
        key = str(file_path)
        return self._responses.get(key, [])

    # Test helper methods
    def set_symbols_for_file(self, file_path: str, symbols: list[Symbol]) -> None:
        """Set what symbols should be returned for a file."""
        self._responses[file_path] = symbols

    def clear(self) -> None:
        """Clear all predefined responses."""
        self._responses.clear()


class StubGitService(GitServicePort):
    """
    Stub implementation of GitServicePort for testing.

    Example:
        git = StubGitService()
        git.set_file_content("repo/path", "abc123", "main.py", "print('hello')")
        content = await git.get_file_content(Path("repo/path"), "abc123", Path("main.py"))
    """

    def __init__(self) -> None:
        """Initialize with empty responses."""
        self._file_contents: dict[tuple[str, str, str], str] = {}

    async def clone_repository(self, url: str, destination: Path) -> None:
        """Stub - does nothing in tests."""
        pass

    async def get_file_content(
        self, repo_path: Path, commit_hash: str, file_path: Path
    ) -> str:
        """Return predefined file content."""
        key = (str(repo_path), commit_hash, str(file_path))
        return self._file_contents.get(key, "")

    # Test helper methods
    def set_file_content(
        self, repo_path: str, commit_hash: str, file_path: str, content: str
    ) -> None:
        """Set what content should be returned for a file."""
        key = (repo_path, commit_hash, file_path)
        self._file_contents[key] = content

    def clear(self) -> None:
        """Clear all predefined responses."""
        self._file_contents.clear()


# ============================================================================
# Factory Functions for Common Test Scenarios
# ============================================================================


def create_populated_symbol_repository() -> InMemorySymbolRepository:
    """
    Create a symbol repository with common test data.

    Useful for tests that need realistic symbol data without
    setting it up manually each time.
    """
    from inxr2.domain.value_objects import SymbolLocation, SymbolKind

    repo = InMemorySymbolRepository()

    # Add some common test symbols
    repo.add(
        Symbol(
            id="sym-func-1",
            name="calculate_total",
            kind=SymbolKind.FUNCTION,
            location=SymbolLocation(line=10, column=0),
            file_id="file-1",
            scope="module",
        )
    )
    repo.add(
        Symbol(
            id="sym-class-1",
            name="Calculator",
            kind=SymbolKind.CLASS,
            location=SymbolLocation(line=20, column=0),
            file_id="file-1",
            scope="module",
        )
    )
    repo.add(
        Symbol(
            id="sym-method-1",
            name="add",
            kind=SymbolKind.METHOD,
            location=SymbolLocation(line=25, column=4),
            file_id="file-1",
            scope="module.Calculator",
        )
    )

    return repo


# ============================================================================
# Documentation: When to Use Which Pattern
# ============================================================================
#
# Test Double Patterns (from "Test Double" by Gerard Meszaros):
#
# 1. **Dummy**: Passed but never used (e.g., fill parameter lists)
#    - Use when: Interface requires parameter you don't care about
#
# 2. **Stub**: Returns predefined responses
#    - Use when: Need to control what dependencies return
#    - Example: StubParserService, StubGitService
#
# 3. **Fake**: Real working implementation (simpler than production)
#    - Use when: Need realistic behavior without infrastructure
#    - Example: InMemorySymbolRepository
#
# 4. **Spy**: Records how it was called (for verification)
#    - Use when: Need to verify interactions happened
#    - Prefer real assertions over spy when possible
#
# 5. **Mock** (framework): Pre-programmed with expectations
#    - Use when: ...actually, try to avoid these!
#    - Prefer fakes/stubs for cleaner, more maintainable tests
#
# In this codebase, we PREFER:
# - Fakes (InMemoryRepository) for repositories
# - Stubs (StubService) for external services
# - Real implementations whenever possible
# - Avoid mocking frameworks (unittest.mock, pytest-mock)
# ============================================================================
