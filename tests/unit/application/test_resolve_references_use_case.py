"""Tests for ResolveReferencesUseCase using dependency injection."""

import pytest

from inxr2.application.use_cases.indexing import (
    ResolveReferencesRequest,
    ResolveReferencesUseCase,
)
from inxr2.domain.entities import Reference, Symbol
from inxr2.domain.value_objects import ReferenceType, SymbolKind
from tests.fixtures.test_doubles import InMemoryReferenceRepository


class FakeSymbolRepository:
    """Minimal fake symbol repository for resolve references testing.

    This is a simplified version that provides just what InMemoryReferenceRepository
    needs to resolve references.
    """

    def __init__(self) -> None:
        self._symbols: dict[int, Symbol] = {}
        self._next_id = 1

    def add(self, symbol: Symbol) -> Symbol:
        """Add a symbol for testing."""
        if symbol.id is None:
            symbol = Symbol(
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
            self._next_id += 1
        self._symbols[symbol.id] = symbol
        return symbol


class TestResolveReferencesUseCase:
    """Tests for ResolveReferencesUseCase."""

    @pytest.fixture
    def symbol_repo(self) -> FakeSymbolRepository:
        """Create a symbol repository with test symbols."""
        repo = FakeSymbolRepository()

        # Add test symbols
        repo.add(
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
        repo.add(
            Symbol(
                id=2,
                file_id=1,
                repository_id=1,
                commit_id=1,
                name="Calculator",
                kind=SymbolKind.CLASS,
                start_line=20,
                start_column=0,
                end_line=50,
                end_column=0,
            )
        )
        # Symbol in a different commit (for commit-aware testing)
        repo.add(
            Symbol(
                id=3,
                file_id=2,
                repository_id=1,
                commit_id=2,
                name="calculate_total",
                kind=SymbolKind.FUNCTION,
                start_line=10,
                start_column=0,
                end_line=15,
                end_column=0,
            )
        )

        return repo

    @pytest.fixture
    def reference_repo(
        self, symbol_repo: FakeSymbolRepository
    ) -> InMemoryReferenceRepository:
        """Create a reference repository with test references."""
        repo = InMemoryReferenceRepository(symbol_repo=symbol_repo)

        # Unresolved reference to calculate_total in commit 1
        repo.add(
            Reference(
                id=1,
                repository_id=1,
                commit_id=1,
                source_file_id=2,
                source_line=5,
                source_column=10,
                source_end_column=25,
                reference_text="calculate_total",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,  # Unresolved
            )
        )
        # Unresolved reference to Calculator in commit 1
        repo.add(
            Reference(
                id=2,
                repository_id=1,
                commit_id=1,
                source_file_id=2,
                source_line=8,
                source_column=5,
                source_end_column=15,
                reference_text="Calculator",
                reference_type=ReferenceType.INSTANTIATION,
                target_symbol_id=None,  # Unresolved
            )
        )
        # Already resolved reference (should be skipped)
        repo.add(
            Reference(
                id=3,
                repository_id=1,
                commit_id=1,
                source_file_id=2,
                source_line=10,
                source_column=0,
                source_end_column=15,
                reference_text="calculate_total",
                reference_type=ReferenceType.CALL,
                target_symbol_id=1,  # Already resolved
            )
        )
        # Unresolved reference to nonexistent symbol
        repo.add(
            Reference(
                id=4,
                repository_id=1,
                commit_id=1,
                source_file_id=2,
                source_line=15,
                source_column=0,
                source_end_column=20,
                reference_text="nonexistent_func",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,  # Unresolved, no matching symbol
            )
        )
        # Reference in commit 2 (for commit-aware testing)
        repo.add(
            Reference(
                id=5,
                repository_id=1,
                commit_id=2,
                source_file_id=3,
                source_line=5,
                source_column=10,
                source_end_column=25,
                reference_text="calculate_total",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,  # Unresolved
            )
        )

        return repo

    @pytest.fixture
    def use_case(
        self, reference_repo: InMemoryReferenceRepository
    ) -> ResolveReferencesUseCase:
        """Create the use case with the fake repository."""
        return ResolveReferencesUseCase(reference_repository=reference_repo)

    @pytest.mark.asyncio
    async def test_resolve_references_without_commit_awareness(
        self,
        use_case: ResolveReferencesUseCase,
        reference_repo: InMemoryReferenceRepository,
    ) -> None:
        """Test resolving references across all commits."""
        # Arrange
        request = ResolveReferencesRequest(repository_id=1, commit_aware=False)

        # Act
        response = await use_case.execute(request)

        # Assert
        # Should resolve 3 references:
        # - ref 1: calculate_total -> symbol 1 (cross-commit match OK)
        # - ref 2: Calculator -> symbol 2
        # - ref 5: calculate_total -> symbol 1 or 3 (cross-commit match OK)
        # Should NOT resolve ref 4 (no matching symbol)
        # Should skip ref 3 (already resolved)
        assert response.resolved_count == 3

        # Verify ref 1 is now resolved
        ref1 = await reference_repo.find_by_id(1)
        assert ref1 is not None
        assert ref1.target_symbol_id == 1

        # Verify ref 2 is now resolved
        ref2 = await reference_repo.find_by_id(2)
        assert ref2 is not None
        assert ref2.target_symbol_id == 2

        # Verify ref 4 is still unresolved
        ref4 = await reference_repo.find_by_id(4)
        assert ref4 is not None
        assert ref4.target_symbol_id is None

    @pytest.mark.asyncio
    async def test_resolve_references_with_commit_awareness(
        self,
        use_case: ResolveReferencesUseCase,
        reference_repo: InMemoryReferenceRepository,
    ) -> None:
        """Test resolving references within same commit only."""
        # Arrange
        request = ResolveReferencesRequest(repository_id=1, commit_aware=True)

        # Act
        response = await use_case.execute(request)

        # Assert
        # Should resolve:
        # - ref 1: calculate_total in commit 1 -> symbol 1 in commit 1
        # - ref 2: Calculator in commit 1 -> symbol 2 in commit 1
        # - ref 5: calculate_total in commit 2 -> symbol 3 in commit 2
        # Should NOT resolve ref 4 (no matching symbol)
        # Should skip ref 3 (already resolved)
        assert response.resolved_count == 3

        # Verify ref 5 is resolved to symbol in same commit (commit 2)
        ref5 = await reference_repo.find_by_id(5)
        assert ref5 is not None
        assert ref5.target_symbol_id == 3  # Symbol 3 is in commit 2

    @pytest.mark.asyncio
    async def test_resolve_references_for_different_repository(
        self,
        use_case: ResolveReferencesUseCase,
        reference_repo: InMemoryReferenceRepository,
    ) -> None:
        """Test that only references in specified repository are resolved."""
        # Arrange - request for repository that doesn't exist
        request = ResolveReferencesRequest(repository_id=999, commit_aware=False)

        # Act
        response = await use_case.execute(request)

        # Assert - no references should be resolved
        assert response.resolved_count == 0

    @pytest.mark.asyncio
    async def test_resolve_references_skips_already_resolved(
        self,
        use_case: ResolveReferencesUseCase,
        reference_repo: InMemoryReferenceRepository,
    ) -> None:
        """Test that already resolved references are not counted again."""
        # Arrange
        request = ResolveReferencesRequest(repository_id=1, commit_aware=False)

        # Act - resolve twice
        response1 = await use_case.execute(request)
        response2 = await use_case.execute(request)

        # Assert
        assert response1.resolved_count == 3
        assert response2.resolved_count == 0  # All already resolved

    @pytest.mark.asyncio
    async def test_resolve_references_empty_repository(
        self, symbol_repo: FakeSymbolRepository
    ) -> None:
        """Test resolving references when there are no references."""
        # Arrange
        empty_ref_repo = InMemoryReferenceRepository(symbol_repo=symbol_repo)
        use_case = ResolveReferencesUseCase(reference_repository=empty_ref_repo)
        request = ResolveReferencesRequest(repository_id=1, commit_aware=False)

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.resolved_count == 0
