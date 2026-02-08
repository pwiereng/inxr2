"""Tests for ResolveReferencesUseCase using dependency injection."""

import pytest

from inxr2.application.use_cases.indexing import (
    ResolveReferencesRequest,
    ResolveReferencesUseCase,
)
from inxr2.domain.entities import File, Reference, Symbol
from inxr2.domain.value_objects import ReferenceType, SymbolKind
from tests.fixtures.test_doubles import (
    InMemoryFileRepository,
    InMemoryReferenceRepository,
    InMemorySymbolRepository,
)


class TestResolveReferencesUseCase:
    """Tests for ResolveReferencesUseCase."""

    @pytest.fixture
    def symbol_repo(self) -> InMemorySymbolRepository:
        """Create a symbol repository with test symbols."""
        repo = InMemorySymbolRepository()

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
        self, symbol_repo: InMemorySymbolRepository
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
        # - ref 1: calculate_total -> symbol 3 (same file priority: ref is from file 2, symbol 3 is in file 2)
        # - ref 2: Calculator -> symbol 2
        # - ref 5: calculate_total -> symbol 1 (file 3 has no calculate_total, so picks by ID)
        # Should NOT resolve ref 4 (no matching symbol)
        # Should skip ref 3 (already resolved)
        assert response.resolved_count == 3

        # Verify ref 1 is now resolved to symbol 3 (same file as reference)
        ref1 = await reference_repo.find_by_id(1)
        assert ref1 is not None
        assert (
            ref1.target_symbol_id == 3
        )  # Same file priority: symbol 3 is in file 2, like ref 1

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
        self, symbol_repo: InMemorySymbolRepository
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


class TestDeterministicResolution:
    """Tests for deterministic resolution with same-file, same-language priority."""

    @pytest.fixture
    def file_repo(self) -> "InMemoryFileRepository":
        """Create a file repository with test files."""
        from tests.fixtures.test_doubles import InMemoryFileRepository

        repo = InMemoryFileRepository()

        # File 1: Python file
        repo.add(
            File(
                id=1,
                repository_id=1,
                commit_id=1,
                path="src/main.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            )
        )
        # File 2: Another Python file
        repo.add(
            File(
                id=2,
                repository_id=1,
                commit_id=1,
                path="src/utils.py",
                content_hash="hash2",
                size_bytes=100,
                language="python",
            )
        )
        # File 3: TypeScript file
        repo.add(
            File(
                id=3,
                repository_id=1,
                commit_id=1,
                path="src/app.ts",
                content_hash="hash3",
                size_bytes=100,
                language="typescript",
            )
        )
        return repo

    @pytest.fixture
    def symbol_repo_with_duplicates(self) -> InMemorySymbolRepository:
        """Create a symbol repository with multiple symbols having the same name."""
        repo = InMemorySymbolRepository()

        # Three symbols all named "Config" in different files
        repo.add(
            Symbol(
                id=1,
                file_id=1,  # Python file (main.py)
                repository_id=1,
                commit_id=1,
                name="Config",
                kind=SymbolKind.CLASS,
                start_line=10,
                start_column=0,
                end_line=20,
                end_column=0,
            )
        )
        repo.add(
            Symbol(
                id=2,
                file_id=2,  # Python file (utils.py)
                repository_id=1,
                commit_id=1,
                name="Config",
                kind=SymbolKind.CLASS,
                start_line=5,
                start_column=0,
                end_line=15,
                end_column=0,
            )
        )
        repo.add(
            Symbol(
                id=3,
                file_id=3,  # TypeScript file (app.ts)
                repository_id=1,
                commit_id=1,
                name="Config",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        return repo

    @pytest.mark.asyncio
    async def test_same_file_priority(
        self,
        symbol_repo_with_duplicates: InMemorySymbolRepository,
        file_repo: "InMemoryFileRepository",
    ) -> None:
        """Test that references resolve to symbols in the same file first."""
        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo_with_duplicates,
            file_repo=file_repo,
        )

        # Reference to "Config" from main.py (file_id=1)
        ref_repo.add(
            Reference(
                id=1,
                repository_id=1,
                commit_id=1,
                source_file_id=1,  # From main.py
                source_line=25,
                source_column=0,
                source_end_column=6,
                reference_text="Config",
                reference_type=ReferenceType.TYPE_ANNOTATION,
                target_symbol_id=None,
            )
        )

        use_case = ResolveReferencesUseCase(reference_repository=ref_repo)
        request = ResolveReferencesRequest(repository_id=1, commit_aware=False)

        await use_case.execute(request)

        # Should resolve to symbol 1 (in same file: main.py)
        ref = await ref_repo.find_by_id(1)
        assert ref is not None
        assert ref.target_symbol_id == 1  # Same file priority

    @pytest.mark.asyncio
    async def test_cross_file_falls_back_to_lowest_id(
        self,
        file_repo: "InMemoryFileRepository",
    ) -> None:
        """Test that without same-file match, references resolve to lowest symbol ID."""
        # Create symbol repo with Config in main.py (Python) and app.ts (TypeScript)
        # No Config in utils.py, so reference from utils.py tests cross-file fallback
        symbol_repo = InMemorySymbolRepository()
        symbol_repo.add(
            Symbol(
                id=1,
                file_id=1,  # Python file (main.py)
                repository_id=1,
                commit_id=1,
                name="Config",
                kind=SymbolKind.CLASS,
                start_line=10,
                start_column=0,
                end_line=20,
                end_column=0,
            )
        )
        symbol_repo.add(
            Symbol(
                id=3,
                file_id=3,  # TypeScript file (app.ts)
                repository_id=1,
                commit_id=1,
                name="Config",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )

        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
        )

        # Reference to "Config" from utils.py (file_id=2)
        # No Config symbol in utils.py, so should pick lowest ID (symbol 1)
        ref_repo.add(
            Reference(
                id=1,
                repository_id=1,
                commit_id=1,
                source_file_id=2,  # From utils.py
                source_line=20,
                source_column=0,
                source_end_column=6,
                reference_text="Config",
                reference_type=ReferenceType.TYPE_ANNOTATION,
                target_symbol_id=None,
            )
        )

        use_case = ResolveReferencesUseCase(reference_repository=ref_repo)
        request = ResolveReferencesRequest(repository_id=1, commit_aware=False)

        await use_case.execute(request)

        # Should resolve to symbol 1 (lowest ID, deterministic tiebreaker)
        ref = await ref_repo.find_by_id(1)
        assert ref is not None
        assert ref.target_symbol_id == 1  # Lowest ID wins

    @pytest.mark.asyncio
    async def test_cross_language_falls_back_to_id(
        self,
        file_repo: "InMemoryFileRepository",
    ) -> None:
        """Test resolution falls back to symbol ID when no same-language match."""
        symbol_repo = InMemorySymbolRepository()

        # Only TypeScript symbols, but reference from Python
        symbol_repo.add(
            Symbol(
                id=10,
                file_id=3,  # TypeScript
                repository_id=1,
                commit_id=1,
                name="Helper",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        symbol_repo.add(
            Symbol(
                id=5,  # Lower ID
                file_id=3,  # TypeScript
                repository_id=1,
                commit_id=1,
                name="Helper",
                kind=SymbolKind.CLASS,
                start_line=20,
                start_column=0,
                end_line=30,
                end_column=0,
            )
        )

        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
        )

        # Reference from Python file to TypeScript symbol
        ref_repo.add(
            Reference(
                id=1,
                repository_id=1,
                commit_id=1,
                source_file_id=1,  # From main.py (Python)
                source_line=5,
                source_column=0,
                source_end_column=6,
                reference_text="Helper",
                reference_type=ReferenceType.TYPE_ANNOTATION,
                target_symbol_id=None,
            )
        )

        use_case = ResolveReferencesUseCase(reference_repository=ref_repo)
        request = ResolveReferencesRequest(repository_id=1, commit_aware=False)

        await use_case.execute(request)

        # Should resolve to symbol 5 (lower ID = deterministic tiebreaker)
        ref = await ref_repo.find_by_id(1)
        assert ref is not None
        assert ref.target_symbol_id == 5

    @pytest.mark.asyncio
    async def test_resolution_is_deterministic(
        self,
        symbol_repo_with_duplicates: InMemorySymbolRepository,
        file_repo: "InMemoryFileRepository",
    ) -> None:
        """Test that resolution produces the same result every time."""
        results = []

        for _ in range(5):
            ref_repo = InMemoryReferenceRepository(
                symbol_repo=symbol_repo_with_duplicates,
                file_repo=file_repo,
            )

            ref_repo.add(
                Reference(
                    id=1,
                    repository_id=1,
                    commit_id=1,
                    source_file_id=1,
                    source_line=25,
                    source_column=0,
                    source_end_column=6,
                    reference_text="Config",
                    reference_type=ReferenceType.TYPE_ANNOTATION,
                    target_symbol_id=None,
                )
            )

            use_case = ResolveReferencesUseCase(reference_repository=ref_repo)
            request = ResolveReferencesRequest(repository_id=1, commit_aware=False)

            await use_case.execute(request)

            ref = await ref_repo.find_by_id(1)
            assert ref is not None
            results.append(ref.target_symbol_id)

        # All results should be the same
        assert len(set(results)) == 1, f"Resolution was not deterministic: {results}"
