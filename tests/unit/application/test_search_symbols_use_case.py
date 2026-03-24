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


class TestSearchSymbolsCommitScoped:
    """Tests for commit-scoped symbol search (time travel)."""

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        repo = InMemoryCommitRepository()
        # Two commits on the same branch
        c1 = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("commit1aaa"),
            author_date=datetime(2025, 1, 1, 12, 0, 0),
            commit_date=datetime(2025, 1, 1, 12, 0, 0),
        )
        c2 = Commit(
            id=2,
            repository_id=1,
            commit_hash=CommitHash("commit2bbb"),
            author_date=datetime(2025, 1, 2, 12, 0, 0),
            commit_date=datetime(2025, 1, 2, 12, 0, 0),
        )
        repo._commits[1] = c1
        repo._commits[2] = c2
        repo._branch_commits[(1, "main", 1)] = True
        repo._branch_commits[(1, "main", 2)] = True
        return repo

    @pytest.fixture
    def file_repo(
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        repo = InMemoryFileRepository(commit_repo=commit_repo)
        # File version at commit 1
        repo.add(
            File(
                id=1,
                repository_id=1,
                path="src/app.py",
                content_hash="h1_old",
                size_bytes=100,
                language="python",
            )
        )
        # File version at commit 2 (same path, different content)
        repo.add(
            File(
                id=2,
                repository_id=1,
                path="src/app.py",
                content_hash="h1_new",
                size_bytes=150,
                language="python",
            )
        )
        # Link file versions to commits
        repo._commit_files.add((1, 1))  # commit 1 -> file version 1
        repo._commit_files.add((2, 2))  # commit 2 -> file version 2
        return repo

    @pytest.fixture
    def symbol_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemorySymbolRepository:
        repo = InMemorySymbolRepository(file_repo=file_repo)
        # Symbol in file version 1 (commit 1) — at line 10
        repo.add(
            Symbol(
                id=1,
                repository_id=1,
                file_id=1,
                name="sync",
                qualified_name="sync",
                kind=SymbolKind.FUNCTION,
                start_line=10,
                start_column=0,
                end_line=20,
                end_column=0,
            )
        )
        # Symbol in file version 2 (commit 2) — moved to line 50
        repo.add(
            Symbol(
                id=2,
                repository_id=1,
                file_id=2,
                name="sync",
                qualified_name="sync",
                kind=SymbolKind.FUNCTION,
                start_line=50,
                start_column=0,
                end_line=60,
                end_column=0,
            )
        )
        # Symbol only in commit 2
        repo.add(
            Symbol(
                id=3,
                repository_id=1,
                file_id=2,
                name="new_helper",
                qualified_name="new_helper",
                kind=SymbolKind.FUNCTION,
                start_line=70,
                start_column=0,
                end_line=80,
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
    async def test_commit_scoped_search_returns_symbols_at_commit(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """Partial search with commit_hash returns symbols from that commit only."""
        request = SearchSymbolsRequest(
            query="sync",
            repository_id=1,
            commit_hash="commit1aaa",
        )
        result = await use_case.execute(request)

        assert result.total == 1
        # Should find sync at line 10 (commit 1), not line 50 (commit 2)
        assert result.symbols[0].symbol.start_line == 10

    @pytest.mark.asyncio
    async def test_commit_scoped_search_excludes_symbols_not_at_commit(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """Symbols added in later commits should not appear in earlier commit search."""
        request = SearchSymbolsRequest(
            query="new_helper",
            repository_id=1,
            commit_hash="commit1aaa",
        )
        result = await use_case.execute(request)

        assert result.total == 0

    @pytest.mark.asyncio
    async def test_commit_scoped_search_latest_commit(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """Search at latest commit returns symbols from that commit."""
        request = SearchSymbolsRequest(
            query="sync",
            repository_id=1,
            commit_hash="commit2bbb",
        )
        result = await use_case.execute(request)

        assert result.total == 1
        # Should find sync at line 50 (commit 2)
        assert result.symbols[0].symbol.start_line == 50

    @pytest.mark.asyncio
    async def test_commit_scoped_search_requires_repository_id(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """commit_hash without repository_id should raise ValueError."""
        request = SearchSymbolsRequest(
            query="sync",
            commit_hash="commit1aaa",
        )
        with pytest.raises(ValueError, match="requires repository_id"):
            await use_case.execute(request)


class TestSearchSymbolsTopLevelOnly:
    """Tests for top_level_only filter in SearchSymbolsUseCase."""

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        return InMemoryCommitRepository()

    @pytest.fixture
    def file_repo(
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
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
        return repo

    @pytest.fixture
    def symbol_repo(self) -> InMemorySymbolRepository:
        repo = InMemorySymbolRepository()
        # Top-level function
        repo.add(
            Symbol(
                id=1,
                repository_id=1,
                file_id=1,
                name="top_func",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )
        # Top-level class
        repo.add(
            Symbol(
                id=2,
                repository_id=1,
                file_id=1,
                name="MyClass",
                kind=SymbolKind.CLASS,
                start_line=10,
                start_column=0,
                end_line=30,
                end_column=0,
            )
        )
        # Method nested inside MyClass
        repo.add(
            Symbol(
                id=3,
                repository_id=1,
                file_id=1,
                name="nested_method",
                kind=SymbolKind.METHOD,
                start_line=12,
                start_column=4,
                end_line=20,
                end_column=0,
                parent_symbol_id=2,
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
    async def test_top_level_only_excludes_nested(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """top_level_only=True should exclude symbols with non-namespace parents."""
        request = SearchSymbolsRequest(query="", top_level_only=True, limit=50)

        result = await use_case.execute(request)

        names = {s.symbol.name for s in result.symbols}
        assert "top_func" in names
        assert "MyClass" in names
        assert "nested_method" not in names

    @pytest.mark.asyncio
    async def test_top_level_only_false_returns_all(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """top_level_only=False should return all symbols including nested."""
        request = SearchSymbolsRequest(query="", top_level_only=False, limit=50)

        result = await use_case.execute(request)

        names = {s.symbol.name for s in result.symbols}
        assert "top_func" in names
        assert "MyClass" in names
        assert "nested_method" in names


# ============================================================
# Bug #384 — search_symbols wildcard (*) returns no results
# ============================================================


class TestSearchSymbolsWildcard:
    """Tests for wildcard (*) query in search_symbols (bug #384).

    Query `*` should return all symbols, not be treated as a literal string.
    """

    @pytest.fixture
    def symbol_repo(self) -> InMemorySymbolRepository:
        repo = InMemorySymbolRepository()
        for idx, name in enumerate(["alpha", "beta", "gamma"], start=1):
            repo.add(
                Symbol(
                    id=idx,
                    repository_id=1,
                    file_id=1,
                    name=name,
                    qualified_name=name,
                    kind=SymbolKind.FUNCTION,
                    start_line=idx,
                    start_column=0,
                    end_line=idx + 1,
                    end_column=0,
                )
            )
        return repo

    @pytest.fixture
    def use_case(self, symbol_repo: InMemorySymbolRepository) -> SearchSymbolsUseCase:
        return SearchSymbolsUseCase(
            symbol_repo=symbol_repo,
            file_repo=InMemoryFileRepository(commit_repo=InMemoryCommitRepository()),
            commit_repo=InMemoryCommitRepository(),
        )

    @pytest.mark.asyncio
    async def test_wildcard_star_returns_all_symbols(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """query='*' should return all symbols, not treat * as a literal."""
        request = SearchSymbolsRequest(query="*", limit=50)

        result = await use_case.execute(request)

        # Bug: currently returns 0 because '*' is treated as a literal substring
        assert result.total == 3

    @pytest.mark.asyncio
    async def test_wildcard_star_with_kind_filter(
        self, symbol_repo: InMemorySymbolRepository
    ) -> None:
        """query='*' with kind filter should return all symbols of that kind."""
        symbol_repo.add(
            Symbol(
                id=10,
                repository_id=1,
                file_id=1,
                name="MyClass",
                qualified_name="MyClass",
                kind=SymbolKind.CLASS,
                start_line=100,
                start_column=0,
                end_line=110,
                end_column=0,
            )
        )
        use_case = SearchSymbolsUseCase(
            symbol_repo=symbol_repo,
            file_repo=InMemoryFileRepository(commit_repo=InMemoryCommitRepository()),
            commit_repo=InMemoryCommitRepository(),
        )
        request = SearchSymbolsRequest(query="*", kind="function", limit=50)

        result = await use_case.execute(request)

        assert result.total == 3
        assert all(s.symbol.kind == "function" for s in result.symbols)


# ============================================================
# Bug #385 — kind:interface doesn't match Swift protocol symbols
# ============================================================


class TestSearchSymbolsKindInterface:
    """Tests for kind='interface' matching Swift protocols (bug #385).

    Swift protocols are stored with kind='protocol'; querying kind='interface'
    should also return them.
    """

    @pytest.fixture
    def symbol_repo(self) -> InMemorySymbolRepository:
        repo = InMemorySymbolRepository()
        repo.add(
            Symbol(
                id=1,
                repository_id=1,
                file_id=1,
                name="Drawable",
                qualified_name="Drawable",
                kind=SymbolKind.INTERFACE,
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
                name="Codable",
                qualified_name="Codable",
                kind=SymbolKind.PROTOCOL,
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
                file_id=1,
                name="helper",
                qualified_name="helper",
                kind=SymbolKind.FUNCTION,
                start_line=20,
                start_column=0,
                end_line=30,
                end_column=0,
            )
        )
        return repo

    @pytest.fixture
    def use_case(self, symbol_repo: InMemorySymbolRepository) -> SearchSymbolsUseCase:
        return SearchSymbolsUseCase(
            symbol_repo=symbol_repo,
            file_repo=InMemoryFileRepository(commit_repo=InMemoryCommitRepository()),
            commit_repo=InMemoryCommitRepository(),
        )

    @pytest.mark.asyncio
    async def test_kind_interface_matches_protocol_symbols(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """kind='interface' should return Swift protocol symbols (kind='protocol')."""
        request = SearchSymbolsRequest(query="", kind="interface", limit=50)

        result = await use_case.execute(request)

        names = {s.symbol.name for s in result.symbols}
        # Bug: currently only returns 'Drawable' (interface), not 'Codable' (protocol)
        assert "Codable" in names

    @pytest.mark.asyncio
    async def test_kind_interface_still_matches_interface_symbols(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """kind='interface' should still return native interface symbols."""
        request = SearchSymbolsRequest(query="", kind="interface", limit=50)

        result = await use_case.execute(request)

        names = {s.symbol.name for s in result.symbols}
        assert "Drawable" in names

    @pytest.mark.asyncio
    async def test_kind_interface_excludes_functions(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """kind='interface' should not return functions."""
        request = SearchSymbolsRequest(query="", kind="interface", limit=50)

        result = await use_case.execute(request)

        names = {s.symbol.name for s in result.symbols}
        assert "helper" not in names

    @pytest.mark.asyncio
    async def test_kind_interface_returns_both_interface_and_protocol(
        self, use_case: SearchSymbolsUseCase
    ) -> None:
        """kind='interface' should return both interface and protocol symbols."""
        request = SearchSymbolsRequest(query="", kind="interface", limit=50)

        result = await use_case.execute(request)

        # Bug: currently returns total=1; after fix should be 2
        assert result.total == 2
