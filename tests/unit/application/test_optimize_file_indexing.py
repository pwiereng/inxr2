"""Tests for OptimizeFileIndexingUseCase using dependency injection."""

import pytest

from inxr2.application.use_cases.indexing.optimize_file_indexing import (
    OptimizationResult,
    OptimizeFileIndexingRequest,
    OptimizeFileIndexingUseCase,
)
from inxr2.domain.entities import File, Reference, Symbol
from inxr2.domain.value_objects import ReferenceType, SymbolKind
from tests.fixtures.test_doubles import (
    InMemoryFileRepository,
    InMemoryReferenceRepository,
    InMemorySymbolRepository,
)


class TestOptimizeFileIndexingUseCase:
    """Tests for OptimizeFileIndexingUseCase."""

    @pytest.fixture
    def symbol_repo(self) -> InMemorySymbolRepository:
        """Create a symbol repository with test symbols."""
        repo = InMemorySymbolRepository()

        # Donor file (file_id=1) with symbols
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

        return repo

    @pytest.fixture
    def reference_repo(
        self, symbol_repo: InMemorySymbolRepository
    ) -> InMemoryReferenceRepository:
        """Create a reference repository with test references."""
        repo = InMemoryReferenceRepository(symbol_repo=symbol_repo)

        # References in donor file (file_id=1)
        repo.add(
            Reference(
                id=1,
                repository_id=1,
                commit_id=1,
                source_file_id=1,
                source_line=5,
                source_column=10,
                source_end_column=25,
                reference_text="print",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )
        repo.add(
            Reference(
                id=2,
                repository_id=1,
                commit_id=1,
                source_file_id=1,
                source_line=8,
                source_column=5,
                source_end_column=15,
                reference_text="sum",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )

        return repo

    @pytest.fixture
    def file_repo(self) -> InMemoryFileRepository:
        """Create a file repository with test files."""
        repo = InMemoryFileRepository()

        # Donor file with content hash "abc123"
        repo.add(
            File(
                id=1,
                repository_id=1,
                commit_id=1,
                path="src/calculator.py",
                content_hash="abc123",
                size_bytes=1024,
                language="python",
                line_count=50,
            )
        )

        # Another file with different content hash
        repo.add(
            File(
                id=2,
                repository_id=1,
                commit_id=1,
                path="src/utils.py",
                content_hash="def456",
                size_bytes=512,
                language="python",
                line_count=25,
            )
        )

        return repo

    @pytest.fixture
    def use_case(
        self,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
    ) -> OptimizeFileIndexingUseCase:
        """Create the use case with fake repositories."""
        return OptimizeFileIndexingUseCase(
            file_repository=file_repo,
            symbol_repository=symbol_repo,
            reference_repository=reference_repo,
        )

    @pytest.mark.asyncio
    async def test_optimization_finds_matching_content_hash(
        self,
        use_case: OptimizeFileIndexingUseCase,
        file_repo: InMemoryFileRepository,
    ) -> None:
        """Test that optimization finds donor file with matching content hash."""
        # Arrange - create target file with same content hash as donor
        target_file = File(
            id=3,
            repository_id=1,
            commit_id=2,
            path="src/calculator.py",  # Same file, different commit
            content_hash="abc123",  # Same content hash
            size_bytes=1024,
            language="python",
            line_count=50,
        )
        await file_repo.save(target_file)

        # Build cache (simulates what CLI does)
        cache = await file_repo.get_content_hash_to_file_id_map(repository_id=1)

        request = OptimizeFileIndexingRequest(
            target_file_id=3,
            target_commit_id=2,
            target_repository_id=1,
            content_hash="abc123",
            content_hash_cache=cache,
        )

        # Act
        result = await use_case.execute(request)

        # Assert
        assert result is not None
        assert result.optimization_applied is True
        assert result.donor_file_id == 1
        assert result.symbols_copied == 2  # 2 symbols from donor
        assert result.references_copied == 2  # 2 references from donor

    @pytest.mark.asyncio
    async def test_optimization_skipped_when_no_match(
        self,
        use_case: OptimizeFileIndexingUseCase,
        file_repo: InMemoryFileRepository,
    ) -> None:
        """Test that optimization is skipped when no matching content hash exists."""
        # Arrange - build cache BEFORE creating target file
        # This simulates the real scenario where we check the cache before saving
        cache = await file_repo.get_content_hash_to_file_id_map(repository_id=1)

        # Create target file with unique content hash
        target_file = File(
            id=3,
            repository_id=1,
            commit_id=2,
            path="src/new_file.py",
            content_hash="xyz789",  # No match in cache
            size_bytes=256,
            language="python",
            line_count=10,
        )
        await file_repo.save(target_file)

        request = OptimizeFileIndexingRequest(
            target_file_id=3,
            target_commit_id=2,
            target_repository_id=1,
            content_hash="xyz789",
            content_hash_cache=cache,  # Cache built before target was saved
        )

        # Act
        result = await use_case.execute(request)

        # Assert
        assert result is not None
        assert result.optimization_applied is False
        assert result.donor_file_id is None
        assert result.symbols_copied == 0
        assert result.references_copied == 0

    @pytest.mark.asyncio
    async def test_optimization_copies_symbols_correctly(
        self,
        use_case: OptimizeFileIndexingUseCase,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
    ) -> None:
        """Test that symbols are copied with correct file_id and commit_id."""
        # Arrange
        target_file = File(
            id=3,
            repository_id=1,
            commit_id=2,
            path="src/calculator.py",
            content_hash="abc123",
            size_bytes=1024,
            language="python",
            line_count=50,
        )
        await file_repo.save(target_file)

        cache = await file_repo.get_content_hash_to_file_id_map(repository_id=1)

        request = OptimizeFileIndexingRequest(
            target_file_id=3,
            target_commit_id=2,
            target_repository_id=1,
            content_hash="abc123",
            content_hash_cache=cache,
        )

        # Act
        result = await use_case.execute(request)

        # Assert - verify symbols were copied
        assert result.symbols_copied == 2

        # Check that new symbols exist for target file
        target_symbols = [s for s in symbol_repo._symbols.values() if s.file_id == 3]
        assert len(target_symbols) == 2

        # Verify copied symbols have correct attributes
        for symbol in target_symbols:
            assert symbol.file_id == 3  # Target file ID
            assert symbol.commit_id == 2  # Target commit ID
            assert symbol.repository_id == 1
            # Symbol names should match original
            assert symbol.name in ["calculate_total", "Calculator"]

    @pytest.mark.asyncio
    async def test_optimization_copies_references_correctly(
        self,
        use_case: OptimizeFileIndexingUseCase,
        file_repo: InMemoryFileRepository,
        reference_repo: InMemoryReferenceRepository,
    ) -> None:
        """Test that references are copied with correct file_id and commit_id."""
        # Arrange
        target_file = File(
            id=3,
            repository_id=1,
            commit_id=2,
            path="src/calculator.py",
            content_hash="abc123",
            size_bytes=1024,
            language="python",
            line_count=50,
        )
        await file_repo.save(target_file)

        cache = await file_repo.get_content_hash_to_file_id_map(repository_id=1)

        request = OptimizeFileIndexingRequest(
            target_file_id=3,
            target_commit_id=2,
            target_repository_id=1,
            content_hash="abc123",
            content_hash_cache=cache,
        )

        # Act
        result = await use_case.execute(request)

        # Assert - verify references were copied
        assert result.references_copied == 2

        # Check that new references exist for target file
        target_refs = [
            r for r in reference_repo._references.values() if r.source_file_id == 3
        ]
        assert len(target_refs) == 2

        # Verify copied references have correct attributes
        for ref in target_refs:
            assert ref.source_file_id == 3  # Target file ID
            assert ref.commit_id == 2  # Target commit ID
            assert ref.repository_id == 1
            # Reference text should match original
            assert ref.reference_text in ["print", "sum"]

    @pytest.mark.asyncio
    async def test_optimization_with_empty_cache(
        self,
        use_case: OptimizeFileIndexingUseCase,
        file_repo: InMemoryFileRepository,
    ) -> None:
        """Test optimization when cache is empty."""
        # Arrange
        target_file = File(
            id=3,
            repository_id=1,
            commit_id=2,
            path="src/new_file.py",
            content_hash="abc123",
            size_bytes=256,
            language="python",
            line_count=10,
        )
        await file_repo.save(target_file)

        # Empty cache
        request = OptimizeFileIndexingRequest(
            target_file_id=3,
            target_commit_id=2,
            target_repository_id=1,
            content_hash="abc123",
            content_hash_cache={},  # Empty cache
        )

        # Act
        result = await use_case.execute(request)

        # Assert
        assert result is not None
        assert result.optimization_applied is False
        assert result.donor_file_id is None

    @pytest.mark.asyncio
    async def test_optimization_result_properties(
        self,
        use_case: OptimizeFileIndexingUseCase,
        file_repo: InMemoryFileRepository,
    ) -> None:
        """Test OptimizationResult properties and methods."""
        # Arrange
        target_file = File(
            id=3,
            repository_id=1,
            commit_id=2,
            path="src/calculator.py",
            content_hash="abc123",
            size_bytes=1024,
            language="python",
            line_count=50,
        )
        await file_repo.save(target_file)

        cache = await file_repo.get_content_hash_to_file_id_map(repository_id=1)

        request = OptimizeFileIndexingRequest(
            target_file_id=3,
            target_commit_id=2,
            target_repository_id=1,
            content_hash="abc123",
            content_hash_cache=cache,
        )

        # Act
        result = await use_case.execute(request)

        # Assert - verify all properties
        assert isinstance(result, OptimizationResult)
        assert isinstance(result.optimization_applied, bool)
        assert isinstance(result.donor_file_id, (int, type(None)))
        assert isinstance(result.symbols_copied, int)
        assert isinstance(result.references_copied, int)
        assert result.symbols_copied >= 0
        assert result.references_copied >= 0

    @pytest.mark.asyncio
    async def test_optimization_across_different_commits(
        self,
        use_case: OptimizeFileIndexingUseCase,
        file_repo: InMemoryFileRepository,
    ) -> None:
        """Test that optimization works when donor is from a different commit."""
        # Arrange - donor in commit 1, target in commit 10
        target_file = File(
            id=3,
            repository_id=1,
            commit_id=10,  # Much later commit
            path="src/calculator.py",
            content_hash="abc123",  # Same content
            size_bytes=1024,
            language="python",
            line_count=50,
        )
        await file_repo.save(target_file)

        cache = await file_repo.get_content_hash_to_file_id_map(repository_id=1)

        request = OptimizeFileIndexingRequest(
            target_file_id=3,
            target_commit_id=10,
            target_repository_id=1,
            content_hash="abc123",
            content_hash_cache=cache,
        )

        # Act
        result = await use_case.execute(request)

        # Assert - optimization should work across commits
        assert result.optimization_applied is True
        assert result.donor_file_id == 1
        assert result.symbols_copied == 2
        assert result.references_copied == 2
