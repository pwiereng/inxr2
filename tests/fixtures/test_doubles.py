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

from inxr2.application.ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    RepositoryPort,
    SymbolRepositoryPort,
)
from inxr2.application.ports.services import GitServicePort, ParserServicePort
from inxr2.domain.entities import Commit, File, Repository, Symbol

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

    For time travel testing, pass a commit repository:
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository(commit_repo=commit_repo)
    """

    def __init__(self, commit_repo: "InMemoryCommitRepository | None" = None) -> None:
        """Initialize with empty storage.

        Args:
            commit_repo: Optional commit repository for commit hash lookups
                         (required for find_by_repository_path_and_commit_hash)
        """
        self._files: dict[int, File] = {}
        self._next_id = 1
        self._commit_repo = commit_repo

    async def save(self, file: File) -> File:
        """Save file to in-memory storage."""
        if file.id is None:
            file = File(
                id=self._next_id,
                repository_id=file.repository_id,
                commit_id=file.commit_id,
                path=file.path,
                content_hash=file.content_hash,
                size_bytes=file.size_bytes,
                language=file.language,
                encoding=file.encoding,
                is_binary=file.is_binary,
                line_count=file.line_count,
                indexed_at=file.indexed_at,
            )
            self._next_id += 1
        self._files[file.id] = file
        return file

    async def find_by_id(self, file_id: int) -> File | None:
        """Find file by ID."""
        return self._files.get(file_id)

    async def save_many(self, files: list[File]) -> list[File]:
        """Save multiple files."""
        for file in files:
            if file.id is None:
                file.id = len(self._files) + 1
            self._files[file.id] = file
        return files

    async def list_by_repository(self, repository_id: int) -> list[File]:
        """List all files for a repository."""
        return [f for f in self._files.values() if f.repository_id == repository_id]

    async def find_by_path(
        self, repository_id: int, commit_id: int, path: str
    ) -> File | None:
        """Find file by path."""
        for file in self._files.values():
            if (
                file.repository_id == repository_id
                and file.commit_id == commit_id
                and file.path == path
            ):
                return file
        return None

    async def list_by_commit(self, commit_id: int) -> list[File]:
        """List files for a commit."""
        return [f for f in self._files.values() if f.commit_id == commit_id]

    async def find_by_content_hash(self, content_hash: str) -> list[File]:
        """Find files by content hash."""
        return [f for f in self._files.values() if f.content_hash == content_hash]

    async def find_by_repository_and_path(
        self, repository_id: int, path: str
    ) -> File | None:
        """Find file by repository and path (latest version)."""
        for file in self._files.values():
            if file.repository_id == repository_id and file.path == path:
                return file
        return None

    async def list_versions_by_path(self, repository_id: int, path: str) -> list[File]:
        """List all versions of a file across commits (for time travel)."""
        return [
            f
            for f in self._files.values()
            if f.repository_id == repository_id and f.path == path
        ]

    async def find_by_repository_path_and_commit_hash(
        self, repository_id: int, path: str, commit_hash: str
    ) -> File | None:
        """Find file by repository, path, and commit hash (for time travel).

        Requires commit_repo to be set for proper commit hash lookups.
        """
        if self._commit_repo is None:
            # No commit repo - fall back to simple path matching (legacy behavior)
            for file in self._files.values():
                if file.repository_id == repository_id and file.path == path:
                    return file
            return None

        # Look up commit by hash
        commit = await self._commit_repo.find_by_hash(repository_id, commit_hash)
        if commit is None or commit.id is None:
            return None

        # Find file matching repository, path, and commit_id
        for file in self._files.values():
            if (
                file.repository_id == repository_id
                and file.path == path
                and file.commit_id == commit.id
            ):
                return file
        return None

    # Test helper methods
    def add(self, file: File) -> None:
        """Add a file for testing."""
        self._files[file.id] = file

    def clear(self) -> None:
        """Clear all files."""
        self._files.clear()


class InMemoryRepositoryRepository(RepositoryPort):
    """In-memory implementation of RepositoryPort for testing."""

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._repositories: dict[int, Repository] = {}
        self._next_id = 1

    async def save(self, repository: Repository) -> Repository:
        """Save repository to in-memory storage."""
        if repository.id is None:
            repository = Repository(
                id=self._next_id,
                name=repository.name,
                url=repository.url,
                description=repository.description,
                default_branch=repository.default_branch,
                config=repository.config,
                created_at=repository.created_at,
                updated_at=repository.updated_at,
            )
            self._next_id += 1
        self._repositories[repository.id] = repository
        return repository

    async def find_by_id(self, repository_id: int) -> Repository | None:
        """Find repository by ID."""
        return self._repositories.get(repository_id)

    async def find_by_name(self, name: str) -> Repository | None:
        """Find repository by name."""
        for repo in self._repositories.values():
            if repo.name == name:
                return repo
        return None

    async def list_all(self) -> list[Repository]:
        """List all repositories."""
        return list(self._repositories.values())

    async def update(self, repository: Repository) -> Repository:
        """Update repository."""
        if repository.id in self._repositories:
            self._repositories[repository.id] = repository
            return repository
        raise ValueError(f"Repository {repository.id} not found")

    async def delete(self, repository_id: int) -> bool:
        """Delete repository."""
        if repository_id in self._repositories:
            del self._repositories[repository_id]
            return True
        return False

    def clear(self) -> None:
        """Clear all repositories."""
        self._repositories.clear()


class InMemoryCommitRepository(CommitRepositoryPort):
    """In-memory implementation of CommitRepositoryPort for testing."""

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._commits: dict[int, Commit] = {}
        self._next_id = 1

    async def save(self, commit: Commit) -> Commit:
        """Save commit to in-memory storage."""
        if commit.id is None:
            from inxr2.domain.value_objects import CommitHash

            commit = Commit(
                id=self._next_id,
                repository_id=commit.repository_id,
                commit_hash=(
                    commit.commit_hash
                    if isinstance(commit.commit_hash, CommitHash)
                    else CommitHash(commit.commit_hash)
                ),
                short_hash=commit.short_hash,
                parent_hashes=commit.parent_hashes,
                branch=commit.branch,
                author_name=commit.author_name,
                author_email=commit.author_email,
                committer_name=commit.committer_name,
                committer_email=commit.committer_email,
                author_date=commit.author_date,
                commit_date=commit.commit_date,
                message=commit.message,
                indexed_at=commit.indexed_at,
            )
            self._next_id += 1
        self._commits[commit.id] = commit
        return commit

    async def save_many(self, commits: list[Commit]) -> list[Commit]:
        """Save multiple commits."""
        result = []
        for commit in commits:
            saved = await self.save(commit)
            result.append(saved)
        return result

    async def find_by_id(self, commit_id: int) -> Commit | None:
        """Find commit by ID."""
        return self._commits.get(commit_id)

    async def find_by_hash(self, repository_id: int, commit_hash: str) -> Commit | None:
        """Find commit by repository and hash."""
        for commit in self._commits.values():
            if (
                commit.repository_id == repository_id
                and commit.commit_hash.value == commit_hash
            ):
                return commit
        return None

    async def list_by_repository(
        self, repository_id: int, branch: str | None = None, limit: int = 100
    ) -> list[Commit]:
        """List commits for a repository."""
        commits = [
            c for c in self._commits.values() if c.repository_id == repository_id
        ]
        if branch:
            commits = [c for c in commits if c.branch == branch]
        # Sort by commit date descending
        commits.sort(key=lambda c: c.commit_date, reverse=True)
        return commits[:limit]

    def clear(self) -> None:
        """Clear all commits."""
        self._commits.clear()


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
    from inxr2.domain.value_objects import SymbolKind, SymbolLocation

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
