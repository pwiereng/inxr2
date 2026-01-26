"""Tests for GetSymbolReferencesUseCase using dependency injection."""

from datetime import datetime

import pytest

from inxr2.application.use_cases.symbols import (
    GetSymbolReferencesRequest,
    GetSymbolReferencesUseCase,
)
from inxr2.domain.entities import Commit, File, Reference, Symbol
from inxr2.domain.exceptions import SymbolNotFound
from inxr2.domain.value_objects import CommitHash, ReferenceType, SymbolKind
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryReferenceRepository,
    InMemorySymbolRepository,
)


class TestGetSymbolReferencesUseCase:
    """Tests for GetSymbolReferencesUseCase."""

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        """Create commit repository with test data."""
        repo = InMemoryCommitRepository()
        commit = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("abc123def456"),
            author_date=datetime(2025, 1, 1, 12, 0, 0),
            commit_date=datetime(2025, 1, 1, 12, 0, 0),
        )
        repo._commits[1] = commit
        return repo

    @pytest.fixture
    def file_repo(
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        """Create file repository with test data."""
        repo = InMemoryFileRepository(commit_repo=commit_repo)
        repo.add(
            File(
                id=1,
                repository_id=1,
                commit_id=1,
                path="src/main.py",
                content_hash="hash1",
                size_bytes=100,
                language="Python",
            )
        )
        repo.add(
            File(
                id=2,
                repository_id=1,
                commit_id=1,
                path="src/utils.py",
                content_hash="hash2",
                size_bytes=200,
                language="Python",
            )
        )
        return repo

    @pytest.fixture
    def symbol_repo(self) -> InMemorySymbolRepository:
        """Create symbol repository with test data."""
        repo = InMemorySymbolRepository()
        repo.add(
            Symbol(
                id=1,
                repository_id=1,
                file_id=1,
                commit_id=1,
                name="save",
                qualified_name="Repository.save",
                kind=SymbolKind.METHOD,
                start_line=10,
                start_column=4,
                end_line=20,
                end_column=0,
            )
        )
        repo.add(
            Symbol(
                id=2,
                repository_id=1,
                file_id=2,
                commit_id=1,
                name="save",  # Same name, different class
                qualified_name="Service.save",
                kind=SymbolKind.METHOD,
                start_line=15,
                start_column=4,
                end_line=25,
                end_column=0,
            )
        )
        return repo

    @pytest.fixture
    def reference_repo(self) -> InMemoryReferenceRepository:
        """Create reference repository with test data."""
        repo = InMemoryReferenceRepository()
        # References to "save" by text (could be either symbol)
        repo.add(
            Reference(
                id=1,
                repository_id=1,
                source_file_id=2,
                target_symbol_id=1,
                reference_text="save",
                reference_type=ReferenceType.CALL,
                source_line=30,
                source_column=8,
                source_end_column=12,
                commit_id=1,
            )
        )
        repo.add(
            Reference(
                id=2,
                repository_id=1,
                source_file_id=1,
                target_symbol_id=2,
                reference_text="save",
                reference_type=ReferenceType.CALL,
                source_line=50,
                source_column=12,
                source_end_column=16,
                commit_id=1,
            )
        )
        repo.add(
            Reference(
                id=3,
                repository_id=1,
                source_file_id=2,
                target_symbol_id=1,
                reference_text="save",
                reference_type=ReferenceType.CALL,
                source_line=35,
                source_column=4,
                source_end_column=8,
                commit_id=1,
            )
        )
        return repo

    @pytest.fixture
    def use_case(
        self,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> GetSymbolReferencesUseCase:
        """Create use case with test dependencies."""
        return GetSymbolReferencesUseCase(
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
        )

    # === Basic Reference Lookup Tests ===

    @pytest.mark.asyncio
    async def test_get_references_by_name(
        self, use_case: GetSymbolReferencesUseCase
    ) -> None:
        """Should find all references matching symbol name when by_name=True."""
        request = GetSymbolReferencesRequest(symbol_id=1, by_name=True)

        result = await use_case.execute(request)

        # Should find all 3 references to "save"
        assert result.total == 3
        assert result.symbol_name == "save"

    @pytest.mark.asyncio
    async def test_get_references_by_id(
        self, use_case: GetSymbolReferencesUseCase
    ) -> None:
        """Should find only references to specific symbol when by_name=False."""
        request = GetSymbolReferencesRequest(symbol_id=1, by_name=False)

        result = await use_case.execute(request)

        # Should find only 2 references with target_symbol_id=1
        assert result.total == 2
        for ref in result.references:
            assert ref.reference.target_symbol_id == 1

    @pytest.mark.asyncio
    async def test_enriches_with_file_paths(
        self, use_case: GetSymbolReferencesUseCase
    ) -> None:
        """Should include source file paths for each reference."""
        request = GetSymbolReferencesRequest(symbol_id=1, by_name=True)

        result = await use_case.execute(request)

        paths = {r.source_file_path for r in result.references}
        assert "src/main.py" in paths
        assert "src/utils.py" in paths

    # === Error Handling Tests ===

    @pytest.mark.asyncio
    async def test_raises_symbol_not_found(
        self, use_case: GetSymbolReferencesUseCase
    ) -> None:
        """Should raise SymbolNotFound for unknown symbol."""
        request = GetSymbolReferencesRequest(symbol_id=999)

        with pytest.raises(SymbolNotFound):
            await use_case.execute(request)

    # === Limit Tests ===

    @pytest.mark.asyncio
    async def test_respects_limit(self, use_case: GetSymbolReferencesUseCase) -> None:
        """Should respect limit parameter."""
        request = GetSymbolReferencesRequest(symbol_id=1, by_name=True, limit=2)

        result = await use_case.execute(request)

        assert result.total == 2

    # === Batch File Fetching Tests ===

    @pytest.mark.asyncio
    async def test_batch_fetches_file_paths(
        self, use_case: GetSymbolReferencesUseCase
    ) -> None:
        """Should batch fetch file paths for multiple references."""
        request = GetSymbolReferencesRequest(symbol_id=1, by_name=True)

        result = await use_case.execute(request)

        # All references should have source file paths
        for ref in result.references:
            assert ref.source_file_path is not None
