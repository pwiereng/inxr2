"""Tests for application use cases using dependency injection (NOT mocking)."""

import pytest

from inxr2.application.ports.repositories import SymbolRepositoryPort
from inxr2.application.use_cases.search_symbols import (
    SearchSymbolsRequest,
    SearchSymbolsUseCase,
)
from inxr2.domain.entities import Symbol
from inxr2.domain.value_objects import SymbolKind

# ============================================================================
# Fake Repository (Test Double) - Implements Port Interface
# ============================================================================
# This is BETTER than mocking because:
# 1. It's a real implementation that follows the interface contract
# 2. Tests are decoupled from implementation details
# 3. More maintainable - refactoring doesn't break tests
# 4. Clearer test intent - you can see exactly what data is returned
# ============================================================================


class FakeSymbolRepository(SymbolRepositoryPort):
    """
    Fake symbol repository for testing.

    Uses dependency injection pattern - implements the port interface
    with in-memory storage instead of database.

    This is PREFERRED over mocking frameworks because:
    - Tests remain valid even if implementation changes
    - Clear, explicit test data setup
    - No brittle mock expectations
    - Follows the Dependency Inversion Principle
    """

    def __init__(self) -> None:
        """Initialize with empty in-memory storage."""
        self._symbols: dict[int, Symbol] = {}
        self._next_id = 1

    async def save(self, symbol: Symbol) -> Symbol:
        """Save symbol to in-memory storage."""
        if symbol.id is None:
            # Assign new ID
            new_symbol = Symbol(
                id=self._next_id,
                file_id=symbol.file_id,
                repository_id=symbol.repository_id,
                commit_id=symbol.commit_id,
                name=symbol.name,
                kind=symbol.kind,
                start_line=symbol.start_line,
                start_column=symbol.start_column,
                end_line=symbol.end_line,
                end_column=symbol.end_column,
                qualified_name=symbol.qualified_name,
                parent_symbol_id=symbol.parent_symbol_id,
                scope=symbol.scope,
                signature=symbol.signature,
                docstring=symbol.docstring,
                metadata=symbol.metadata,
            )
            self._symbols[self._next_id] = new_symbol
            self._next_id += 1
            return new_symbol
        else:
            self._symbols[symbol.id] = symbol
            return symbol

    async def save_many(self, symbols: list[Symbol]) -> list[Symbol]:
        """Bulk save symbols."""
        return [await self.save(symbol) for symbol in symbols]

    async def find_by_id(self, symbol_id: int) -> Symbol | None:
        """Find symbol by ID from in-memory storage."""
        return self._symbols.get(symbol_id)

    async def search_by_name(
        self,
        name: str,
        repository_id: int | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> list[Symbol]:
        """Search symbols by name from in-memory storage."""
        results = [
            symbol
            for symbol in self._symbols.values()
            if name.lower() in symbol.name.lower()
            and (repository_id is None or symbol.repository_id == repository_id)
            and (kind is None or symbol.kind.value == kind)
        ]
        return results[:limit]

    async def find_by_qualified_name(
        self, repository_id: int, qualified_name: str
    ) -> list[Symbol]:
        """Find symbols by qualified name."""
        return [
            symbol
            for symbol in self._symbols.values()
            if symbol.repository_id == repository_id
            and symbol.qualified_name == qualified_name
        ]

    async def list_by_file(self, file_id: int) -> list[Symbol]:
        """List all symbols in a file."""
        return [
            symbol for symbol in self._symbols.values() if symbol.file_id == file_id
        ]

    async def delete_by_file(self, file_id: int) -> int:
        """Delete all symbols for a file."""
        to_delete = [
            sid for sid, symbol in self._symbols.items() if symbol.file_id == file_id
        ]
        for sid in to_delete:
            del self._symbols[sid]
        return len(to_delete)

    async def find_by_exact_name(
        self,
        name: str,
        repository_id: int | None = None,
        commit_id: int | None = None,
    ) -> list[Symbol]:
        """Find all symbols with exact name match."""
        return [
            symbol
            for symbol in self._symbols.values()
            if symbol.name == name
            and (repository_id is None or symbol.repository_id == repository_id)
            and (commit_id is None or symbol.commit_id == commit_id)
        ]

    async def count_by_repository(self, repository_id: int) -> int:
        """Count total symbols in a repository."""
        return len(
            [s for s in self._symbols.values() if s.repository_id == repository_id]
        )

    async def copy_symbols_to_file(
        self,
        source_file_id: int,
        target_file_id: int,
        target_commit_id: int,
        target_repository_id: int,
    ) -> int:
        """Copy all symbols from source file to target file."""
        source_symbols = [
            s for s in self._symbols.values() if s.file_id == source_file_id
        ]
        if not source_symbols:
            return 0

        # Map old symbol IDs to new ones for parent_symbol_id remapping
        old_to_new_id: dict[int, int] = {}

        for source in source_symbols:
            new_symbol = Symbol(
                id=self._next_id,
                file_id=target_file_id,
                repository_id=target_repository_id,
                commit_id=target_commit_id,
                name=source.name,
                kind=source.kind,
                start_line=source.start_line,
                start_column=source.start_column,
                end_line=source.end_line,
                end_column=source.end_column,
                qualified_name=source.qualified_name,
                scope=source.scope,
                signature=source.signature,
                docstring=source.docstring,
                metadata=source.metadata,
                parent_symbol_id=None,  # Will be remapped below
            )
            self._symbols[self._next_id] = new_symbol
            if source.id is not None:
                old_to_new_id[source.id] = self._next_id
            self._next_id += 1

        # Remap parent_symbol_id references
        for source in source_symbols:
            if source.parent_symbol_id is not None and source.id is not None:
                new_id = old_to_new_id.get(source.id)
                new_parent_id = old_to_new_id.get(source.parent_symbol_id)
                if new_id is not None and new_parent_id is not None:
                    old_symbol = self._symbols[new_id]
                    self._symbols[new_id] = Symbol(
                        id=old_symbol.id,
                        file_id=old_symbol.file_id,
                        repository_id=old_symbol.repository_id,
                        commit_id=old_symbol.commit_id,
                        name=old_symbol.name,
                        kind=old_symbol.kind,
                        start_line=old_symbol.start_line,
                        start_column=old_symbol.start_column,
                        end_line=old_symbol.end_line,
                        end_column=old_symbol.end_column,
                        qualified_name=old_symbol.qualified_name,
                        scope=old_symbol.scope,
                        signature=old_symbol.signature,
                        docstring=old_symbol.docstring,
                        metadata=old_symbol.metadata,
                        parent_symbol_id=new_parent_id,
                    )

        return len(source_symbols)

    def add_test_symbol(self, symbol: Symbol) -> None:
        """Helper method to add test data."""
        if symbol.id is not None:
            self._symbols[symbol.id] = symbol
        else:
            # Assign ID if not provided
            symbol_with_id = Symbol(
                id=self._next_id,
                file_id=symbol.file_id,
                repository_id=symbol.repository_id,
                commit_id=symbol.commit_id,
                name=symbol.name,
                kind=symbol.kind,
                start_line=symbol.start_line,
                start_column=symbol.start_column,
                end_line=symbol.end_line,
                end_column=symbol.end_column,
            )
            self._symbols[self._next_id] = symbol_with_id
            self._next_id += 1


# ============================================================================
# Use Case Tests with Dependency Injection
# ============================================================================


class TestSearchSymbolsUseCase:
    """
    Tests for SearchSymbolsUseCase using dependency injection.

    ARCHITECTURE NOTE:
    We inject a FakeSymbolRepository (test double) instead of using
    mocking frameworks. This follows Clean Architecture principles:
    - Use cases depend on ports (interfaces)
    - Tests inject fake implementations
    - No coupling to infrastructure details
    """

    @pytest.fixture
    def fake_repository(self) -> FakeSymbolRepository:
        """Provide a fake repository with test data."""
        repo = FakeSymbolRepository()

        # Add test symbols
        repo.add_test_symbol(
            Symbol(
                id=1,
                file_id=1,
                repository_id=1,
                commit_id=1,
                name="calculate_total",
                kind=SymbolKind.FUNCTION,
                start_line=10,
                start_column=0,
                end_line=15,
                end_column=0,
            )
        )
        repo.add_test_symbol(
            Symbol(
                id=2,
                file_id=1,
                repository_id=1,
                commit_id=1,
                name="Calculator",
                kind=SymbolKind.CLASS,
                start_line=20,
                start_column=0,
                end_line=30,
                end_column=0,
            )
        )
        repo.add_test_symbol(
            Symbol(
                id=3,
                file_id=2,
                repository_id=1,
                commit_id=1,
                name="calculate_tax",
                kind=SymbolKind.FUNCTION,
                start_line=30,
                start_column=0,
                end_line=35,
                end_column=0,
            )
        )

        return repo

    @pytest.fixture
    def use_case(self, fake_repository: FakeSymbolRepository) -> SearchSymbolsUseCase:
        """Provide use case with fake repository injected."""
        # Dependency injection: inject fake instead of real repository
        return SearchSymbolsUseCase(symbol_repository=fake_repository)

    @pytest.mark.asyncio
    async def test_search_finds_matching_symbols(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """Test that search finds symbols matching the query."""
        # Arrange
        request = SearchSymbolsRequest(query="calculate")

        # Act
        response = await use_case.execute(request)

        # Assert
        assert len(response.symbols) == 2  # calculate_total and calculate_tax
        assert response.total_count == 2
        assert all("calculate" in s.name.lower() for s in response.symbols)

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, use_case: SearchSymbolsUseCase) -> None:
        """Test that search respects the limit parameter."""
        # Arrange
        request = SearchSymbolsRequest(query="calculate", limit=1)

        # Act
        response = await use_case.execute(request)

        # Assert
        assert len(response.symbols) == 1
        assert response.total_count == 2  # Total found, but limited to 1

    @pytest.mark.asyncio
    async def test_search_with_no_matches(self, use_case: SearchSymbolsUseCase) -> None:
        """Test search when no symbols match."""
        # Arrange
        request = SearchSymbolsRequest(query="nonexistent")

        # Act
        response = await use_case.execute(request)

        # Assert
        assert len(response.symbols) == 0
        assert response.total_count == 0

    @pytest.mark.asyncio
    async def test_search_is_case_insensitive(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """Test that search is case-insensitive."""
        # Arrange
        request = SearchSymbolsRequest(query="CALCULATOR")

        # Act
        response = await use_case.execute(request)

        # Assert
        assert len(response.symbols) >= 1
        assert any(s.name == "Calculator" for s in response.symbols)


# ============================================================================
# Why This Approach is Better Than Mocking
# ============================================================================
#
# ❌ DON'T DO THIS (using mocks):
# ```python
# from unittest.mock import Mock
#
# def test_with_mock():
#     mock_repo = Mock(spec=SymbolRepositoryPort)
#     mock_repo.find_by_name.return_value = [...]  # Brittle!
#     use_case = SearchSymbolsUseCase(mock_repo)
#     # Test breaks if implementation details change
# ```
#
# ✅ DO THIS (using fakes/test doubles):
# ```python
# def test_with_fake():
#     fake_repo = FakeSymbolRepository()  # Real implementation
#     fake_repo.add_test_symbol(...)      # Clear test data
#     use_case = SearchSymbolsUseCase(fake_repo)
#     # Test remains valid even if implementation changes
# ```
#
# Benefits of Dependency Injection over Mocking:
# 1. **Resilient**: Tests survive refactoring
# 2. **Clear**: Explicit test data, no magic mock setup
# 3. **Fast**: No framework overhead
# 4. **Reliable**: Fake follows the real interface contract
# 5. **Maintainable**: One fake serves many tests
# ============================================================================
