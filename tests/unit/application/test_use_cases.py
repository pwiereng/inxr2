"""Tests for application use cases using dependency injection (NOT mocking)."""

import pytest

from inxr2.application.ports.repositories import SymbolRepositoryPort
from inxr2.application.use_cases.search_symbols import (
    SearchSymbolsRequest,
    SearchSymbolsUseCase,
)
from inxr2.domain.entities import Symbol
from inxr2.domain.value_objects import SymbolKind, SymbolLocation

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
        self._symbols: dict[str, Symbol] = {}

    async def save(self, symbol: Symbol) -> Symbol:
        """Save symbol to in-memory storage."""
        self._symbols[symbol.id] = symbol
        return symbol

    async def find_by_id(self, symbol_id: str) -> Symbol | None:
        """Find symbol by ID from in-memory storage."""
        return self._symbols.get(symbol_id)

    async def find_by_name(
        self, name: str, repository_id: str | None = None
    ) -> list[Symbol]:
        """Find symbols by name from in-memory storage."""
        results = [
            symbol
            for symbol in self._symbols.values()
            if name.lower() in symbol.name.lower()
            and (repository_id is None or symbol.file_id.startswith(repository_id))
        ]
        return results

    def add_test_symbol(self, symbol: Symbol) -> None:
        """Helper method to add test data."""
        self._symbols[symbol.id] = symbol


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
                id="sym-1",
                name="calculate_total",
                kind=SymbolKind.FUNCTION,
                location=SymbolLocation(line=10, column=0),
                file_id="file-1",
            )
        )
        repo.add_test_symbol(
            Symbol(
                id="sym-2",
                name="Calculator",
                kind=SymbolKind.CLASS,
                location=SymbolLocation(line=20, column=0),
                file_id="file-1",
            )
        )
        repo.add_test_symbol(
            Symbol(
                id="sym-3",
                name="calculate_tax",
                kind=SymbolKind.FUNCTION,
                location=SymbolLocation(line=30, column=0),
                file_id="file-2",
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
