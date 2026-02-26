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


class TestSearchSymbolsGlobalScope:
    """Tests for global symbol search (scope=latest, no repository_id)."""

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        repo = InMemoryCommitRepository()
        # Repo 1 commit on main
        c1 = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("aaa111"),
            author_date=datetime(2025, 1, 1, 12, 0, 0),
            commit_date=datetime(2025, 1, 1, 12, 0, 0),
        )
        repo._commits[1] = c1
        repo._branch_commits[(1, "main", 1)] = True

        # Repo 2 commit on main
        c2 = Commit(
            id=2,
            repository_id=2,
            commit_hash=CommitHash("bbb222"),
            author_date=datetime(2025, 1, 2, 12, 0, 0),
            commit_date=datetime(2025, 1, 2, 12, 0, 0),
        )
        repo._commits[2] = c2
        repo._branch_commits[(2, "main", 2)] = True
        return repo

    @pytest.fixture
    def file_repo(
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        repo = InMemoryFileRepository(commit_repo=commit_repo)
        repo.add(
            File(
                id=1,
                repository_id=1,
                path="src/app.py",
                content_hash="h1",
                size_bytes=100,
                language="python",
            )
        )
        repo.add(
            File(
                id=2,
                repository_id=2,
                path="src/lib.rs",
                content_hash="h2",
                size_bytes=200,
                language="rust",
            )
        )
        # Link files to commits
        repo._commit_files.add((1, 1))
        repo._commit_files.add((2, 2))
        return repo

    @pytest.fixture
    def symbol_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemorySymbolRepository:
        repo = InMemorySymbolRepository(file_repo=file_repo)
        repo.add(
            Symbol(
                id=1,
                repository_id=1,
                file_id=1,
                name="parse",
                qualified_name="parse",
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
                repository_id=2,
                file_id=2,
                name="parse_input",
                qualified_name="parse_input",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=10,
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
        return SearchSymbolsUseCase(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
        )

    @pytest.mark.asyncio
    async def test_global_symbol_search_returns_multiple_repos(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """Global symbol search returns symbols from multiple repos."""
        request = SearchSymbolsRequest(query="parse", scope="latest")
        result = await use_case.execute(request)

        assert result.total == 2
        repo_ids = {s.symbol.repository_id for s in result.symbols}
        assert repo_ids == {1, 2}

    @pytest.mark.asyncio
    async def test_global_search_scope_ignored_with_repo_id(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """scope is ignored when repository_id is set."""
        request = SearchSymbolsRequest(query="parse", repository_id=1, scope="latest")
        result = await use_case.execute(request)

        assert result.total == 1
        assert result.symbols[0].symbol.repository_id == 1


class TestGlobalSearchIncludesOlderCommitFiles:
    """Regression test for issue #135.

    Global search (scope=latest, no repository_id) must include symbols
    from files that were NOT modified in the HEAD commit. The bug was
    that head_file_ids_subquery() only returned files linked to the HEAD
    commit, missing files last modified in older commits.
    """

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        repo = InMemoryCommitRepository()
        # Commit 1 (older) on main
        c1 = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("aaa111"),
            author_date=datetime(2025, 1, 1, 12, 0, 0),
            commit_date=datetime(2025, 1, 1, 12, 0, 0),
        )
        repo._commits[1] = c1
        repo._branch_commits[(1, "main", 1)] = True

        # Commit 2 (HEAD, newer) on main
        c2 = Commit(
            id=2,
            repository_id=1,
            commit_hash=CommitHash("bbb222"),
            author_date=datetime(2025, 1, 2, 12, 0, 0),
            commit_date=datetime(2025, 1, 2, 12, 0, 0),
        )
        repo._commits[2] = c2
        repo._branch_commits[(1, "main", 2)] = True
        return repo

    @pytest.fixture
    def file_repo(
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        repo = InMemoryFileRepository(commit_repo=commit_repo)
        # File A: modified only in commit 1 (NOT in HEAD commit 2)
        repo.add(
            File(
                id=1,
                repository_id=1,
                path="src/old_module.py",
                content_hash="h1",
                size_bytes=100,
                language="python",
            )
        )
        repo._commit_files.add((1, 1))  # linked to commit 1 only

        # File B: modified in commit 2 (HEAD)
        repo.add(
            File(
                id=2,
                repository_id=1,
                path="src/new_module.py",
                content_hash="h2",
                size_bytes=200,
                language="python",
            )
        )
        repo._commit_files.add((2, 2))  # linked to commit 2 only
        return repo

    @pytest.fixture
    def symbol_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemorySymbolRepository:
        repo = InMemorySymbolRepository(file_repo=file_repo)
        # Symbol X in file A (older commit)
        repo.add(
            Symbol(
                id=1,
                repository_id=1,
                file_id=1,
                name="old_function",
                qualified_name="old_module.old_function",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        # Symbol Y in file B (HEAD commit)
        repo.add(
            Symbol(
                id=2,
                repository_id=1,
                file_id=2,
                name="new_function",
                qualified_name="new_module.new_function",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=10,
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
        return SearchSymbolsUseCase(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
        )

    @pytest.mark.asyncio
    async def test_global_search_finds_symbols_from_older_commits(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """Global search must find symbols from files not in HEAD commit."""
        request = SearchSymbolsRequest(query="function", scope="latest")
        result = await use_case.execute(request)

        names = {s.symbol.name for s in result.symbols}
        assert (
            "old_function" in names
        ), "Symbol from file modified in older commit should be found"
        assert (
            "new_function" in names
        ), "Symbol from file modified in HEAD commit should be found"
        assert result.total == 2


class TestSearchSymbolsExtensionFilter:
    """Tests for symbol search with extension filtering."""

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        repo = InMemoryCommitRepository()
        c = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("ext111"),
            author_date=datetime(2025, 1, 1, 12, 0, 0),
            commit_date=datetime(2025, 1, 1, 12, 0, 0),
        )
        repo._commits[1] = c
        repo._branch_commits[(1, "main", 1)] = True
        return repo

    @pytest.fixture
    def file_repo(
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        repo = InMemoryFileRepository(commit_repo=commit_repo)
        repo.add(
            File(
                id=1,
                repository_id=1,
                path="src/app.py",
                content_hash="h1",
                size_bytes=100,
                language="python",
                extension=".py",
            )
        )
        repo.add(
            File(
                id=2,
                repository_id=1,
                path="src/main.ts",
                content_hash="h2",
                size_bytes=200,
                language="typescript",
                extension=".ts",
            )
        )
        repo.add(
            File(
                id=3,
                repository_id=1,
                path="src/app.tsx",
                content_hash="h3",
                size_bytes=300,
                language="typescript",
                extension=".tsx",
            )
        )
        repo._commit_files.add((1, 1))
        repo._commit_files.add((1, 2))
        repo._commit_files.add((1, 3))
        return repo

    @pytest.fixture
    def symbol_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemorySymbolRepository:
        repo = InMemorySymbolRepository(file_repo=file_repo)
        repo.add(
            Symbol(
                id=1,
                repository_id=1,
                file_id=1,
                name="run",
                qualified_name="run",
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
                file_id=2,
                name="render",
                qualified_name="render",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        repo.add(
            Symbol(
                id=3,
                repository_id=1,
                file_id=3,
                name="App",
                qualified_name="App",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=20,
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
        return SearchSymbolsUseCase(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
        )

    @pytest.mark.asyncio
    async def test_extension_filter_single(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """Extension filter returns only symbols from matching files."""
        request = SearchSymbolsRequest(query="", extensions=[".py"], limit=10)
        result = await use_case.execute(request)

        assert result.total == 1
        assert result.symbols[0].symbol.name == "run"

    @pytest.mark.asyncio
    async def test_extension_filter_multiple(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """Multiple extensions returns union of matches."""
        request = SearchSymbolsRequest(query="", extensions=[".ts", ".tsx"], limit=10)
        result = await use_case.execute(request)

        assert result.total == 2
        names = {s.symbol.name for s in result.symbols}
        assert names == {"render", "App"}

    @pytest.mark.asyncio
    async def test_extension_filter_no_match(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """Extension filter with no match returns empty."""
        request = SearchSymbolsRequest(query="", extensions=[".rs"], limit=10)
        result = await use_case.execute(request)

        assert result.total == 0

    @pytest.mark.asyncio
    async def test_no_extension_filter_returns_all(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """No extension filter returns all symbols."""
        request = SearchSymbolsRequest(query="", limit=10)
        result = await use_case.execute(request)

        assert result.total == 3
