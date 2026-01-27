"""Tests for SearchSymbolsUseCase using dependency injection."""

from datetime import datetime

import pytest

from inxr2.application.use_cases.symbols import (
    SearchSymbolsRequest,
    SearchSymbolsUseCase,
)
from inxr2.domain.entities import Commit, File, Symbol
from inxr2.domain.value_objects import CommitHash, SymbolKind
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemorySymbolRepository,
)


class TestSearchSymbolsUseCase:
    """Tests for SearchSymbolsUseCase."""

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
                name="main",
                qualified_name="main",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        repo.add(
            Symbol(
                id=2,
                repository_id=1,
                file_id=1,
                commit_id=1,
                name="setup",
                qualified_name="setup",
                kind=SymbolKind.FUNCTION,
                start_line=12,
                start_column=0,
                end_line=20,
                end_column=0,
            )
        )
        repo.add(
            Symbol(
                id=3,
                repository_id=1,
                file_id=2,
                commit_id=1,
                name="helper",
                qualified_name="helper",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )
        repo.add(
            Symbol(
                id=4,
                repository_id=1,
                file_id=2,
                commit_id=1,
                name="MyClass",
                qualified_name="MyClass",
                kind=SymbolKind.CLASS,
                start_line=10,
                start_column=0,
                end_line=30,
                end_column=0,
            )
        )
        return repo

    @pytest.fixture
    def use_case(
        self,
        symbol_repo: InMemorySymbolRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> SearchSymbolsUseCase:
        """Create use case with test dependencies."""
        return SearchSymbolsUseCase(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
        )

    # === Basic Search Tests ===

    @pytest.mark.asyncio
    async def test_search_returns_matching_symbols(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """Should return symbols matching the query."""
        request = SearchSymbolsRequest(query="main")

        result = await use_case.execute(request)

        assert result.total == 1
        assert len(result.symbols) == 1
        assert result.symbols[0].symbol.name == "main"

    @pytest.mark.asyncio
    async def test_search_enriches_with_file_paths(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """Should include file paths for each symbol."""
        request = SearchSymbolsRequest(query="main")

        result = await use_case.execute(request)

        assert result.symbols[0].file_path == "src/main.py"

    @pytest.mark.asyncio
    async def test_search_with_empty_query_returns_all(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """Should return all symbols when query is empty."""
        request = SearchSymbolsRequest(query="", limit=10)

        result = await use_case.execute(request)

        assert result.total == 4

    # === Filter Tests ===

    @pytest.mark.asyncio
    async def test_filter_by_kind(self, use_case: SearchSymbolsUseCase) -> None:
        """Should filter symbols by kind."""
        request = SearchSymbolsRequest(query="", kind="class", limit=10)

        result = await use_case.execute(request)

        assert result.total == 1
        assert result.symbols[0].symbol.kind == "class"

    @pytest.mark.asyncio
    async def test_filter_by_repository(
        self,
        symbol_repo: InMemorySymbolRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> None:
        """Should filter symbols by repository_id."""
        # Add symbol in different repository
        symbol_repo.add(
            Symbol(
                id=5,
                repository_id=2,
                file_id=1,
                commit_id=1,
                name="other_func",
                qualified_name="other_func",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )

        use_case = SearchSymbolsUseCase(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
        )

        request = SearchSymbolsRequest(query="", repository_id=1, limit=10)
        result = await use_case.execute(request)

        assert result.total == 4
        for s in result.symbols:
            assert s.symbol.repository_id == 1

    # === Pagination Tests ===

    @pytest.mark.asyncio
    async def test_pagination_with_limit(self, use_case: SearchSymbolsUseCase) -> None:
        """Should respect limit parameter."""
        request = SearchSymbolsRequest(query="", limit=2)

        result = await use_case.execute(request)

        assert len(result.symbols) == 2
        assert result.limit == 2

    @pytest.mark.asyncio
    async def test_pagination_with_offset(self, use_case: SearchSymbolsUseCase) -> None:
        """Should respect offset parameter."""
        request = SearchSymbolsRequest(query="", limit=10, offset=2)

        result = await use_case.execute(request)

        assert len(result.symbols) == 2  # 4 total - 2 offset = 2 remaining
        assert result.offset == 2

    # === Exact Match Tests ===

    @pytest.mark.asyncio
    async def test_exact_match(self, use_case: SearchSymbolsUseCase) -> None:
        """Should find exact name match when exact_match=True."""
        request = SearchSymbolsRequest(query="main", exact_match=True)

        result = await use_case.execute(request)

        assert result.total == 1
        assert result.symbols[0].symbol.name == "main"

    # === Batch File Fetching Tests ===

    @pytest.mark.asyncio
    async def test_batch_fetches_file_paths(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """Should batch fetch file paths for multiple symbols."""
        request = SearchSymbolsRequest(query="", limit=10)

        result = await use_case.execute(request)

        # All symbols should have file paths
        paths = {s.file_path for s in result.symbols}
        assert "src/main.py" in paths
        assert "src/utils.py" in paths
