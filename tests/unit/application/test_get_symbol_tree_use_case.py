"""Tests for GetSymbolTreeUseCase using dependency injection."""

from datetime import datetime

import pytest

from inxr2.application.use_cases.symbols import (
    GetSymbolTreeFilesResponse,
    GetSymbolTreeRequest,
    GetSymbolTreeSymbolsResponse,
    GetSymbolTreeUseCase,
)
from inxr2.domain.entities import Commit, File, Reference, Repository, Symbol
from inxr2.domain.value_objects import CommitHash, ReferenceType, SymbolKind
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryReferenceRepository,
    InMemoryRepositoryRepository,
    InMemorySymbolRepository,
)


class TestGetSymbolTreeTier1:
    """Tier 1: list files with symbols."""

    @pytest.fixture
    def repo_adapter(self) -> InMemoryRepositoryRepository:
        adapter = InMemoryRepositoryRepository()
        adapter.add(Repository(id=1, name="test-repo", url="/repos/test-repo"))
        return adapter

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        repo = InMemoryCommitRepository()
        repo._commits[1] = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("abc123"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
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
                path="src/main.py",
                content_hash="h1",
                size_bytes=100,
                language="python",
            )
        )
        repo.add(
            File(
                id=2,
                repository_id=1,
                path="src/utils.py",
                content_hash="h2",
                size_bytes=200,
                language="python",
            )
        )
        repo.add(
            File(
                id=3,
                repository_id=1,
                path="src/empty.py",
                content_hash="h3",
                size_bytes=50,
                language="python",
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
                name="main",
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
                name="helper",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )
        # No symbols in file 3 (empty.py)
        return repo

    @pytest.fixture
    def reference_repo(self) -> InMemoryReferenceRepository:
        return InMemoryReferenceRepository()

    @pytest.fixture
    def use_case(
        self,
        repo_adapter: InMemoryRepositoryRepository,
        symbol_repo: InMemorySymbolRepository,
        file_repo: InMemoryFileRepository,
        reference_repo: InMemoryReferenceRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> GetSymbolTreeUseCase:
        return GetSymbolTreeUseCase(
            repository_repo=repo_adapter,
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            reference_repo=reference_repo,
            commit_repo=commit_repo,
        )

    @pytest.mark.asyncio
    async def test_tier1_returns_files_with_symbols(
        self, use_case: GetSymbolTreeUseCase
    ) -> None:
        """Tier 1 returns only files that contain symbols."""
        result = await use_case.execute(
            GetSymbolTreeRequest(repository_name="test-repo", branch="main")
        )

        assert isinstance(result, GetSymbolTreeFilesResponse)
        assert len(result.files) == 2
        paths = {f.path for f in result.files}
        assert paths == {"src/main.py", "src/utils.py"}
        # empty.py should not appear (no symbols)
        assert "src/empty.py" not in paths

    @pytest.mark.asyncio
    async def test_tier1_includes_symbol_counts(
        self, use_case: GetSymbolTreeUseCase
    ) -> None:
        """Tier 1 files include symbol counts."""
        result = await use_case.execute(
            GetSymbolTreeRequest(repository_name="test-repo", branch="main")
        )

        assert isinstance(result, GetSymbolTreeFilesResponse)
        counts = {f.path: f.symbol_count for f in result.files}
        assert counts["src/main.py"] == 1
        assert counts["src/utils.py"] == 1

    @pytest.mark.asyncio
    async def test_tier1_sorted_by_path(self, use_case: GetSymbolTreeUseCase) -> None:
        """Tier 1 files are sorted by path."""
        result = await use_case.execute(
            GetSymbolTreeRequest(repository_name="test-repo", branch="main")
        )

        assert isinstance(result, GetSymbolTreeFilesResponse)
        paths = [f.path for f in result.files]
        assert paths == sorted(paths)

    @pytest.mark.asyncio
    async def test_tier1_returns_available_kinds(
        self, use_case: GetSymbolTreeUseCase
    ) -> None:
        """Tier 1 response includes available top-level symbol kinds."""
        result = await use_case.execute(
            GetSymbolTreeRequest(repository_name="test-repo", branch="main")
        )

        assert isinstance(result, GetSymbolTreeFilesResponse)
        assert "function" in result.available_kinds

    @pytest.mark.asyncio
    async def test_tier1_kinds_filter_narrows_files(
        self,
        use_case: GetSymbolTreeUseCase,
        symbol_repo: InMemorySymbolRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> None:
        """Kinds filter returns only files with matching top-level symbols."""
        # Add a class symbol to file 1 (main.py already has a function)
        file_repo.add(
            File(
                id=4,
                repository_id=1,
                path="src/models.py",
                content_hash="h4",
                size_bytes=300,
                language="python",
            )
        )
        file_repo._commit_files.add((1, 4))
        commit_repo._branch_commits[(1, "main", 1)] = True
        symbol_repo.add(
            Symbol(
                id=10,
                repository_id=1,
                file_id=4,
                name="MyClass",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=20,
                end_column=0,
            )
        )

        # Filter to only class → should return only models.py
        result = await use_case.execute(
            GetSymbolTreeRequest(
                repository_name="test-repo", branch="main", kinds=["class"]
            )
        )

        assert isinstance(result, GetSymbolTreeFilesResponse)
        paths = {f.path for f in result.files}
        assert "src/models.py" in paths
        assert "src/main.py" not in paths
        assert "src/utils.py" not in paths

        # available_kinds should still show all kinds (not filtered)
        assert "class" in result.available_kinds
        assert "function" in result.available_kinds

    @pytest.mark.asyncio
    async def test_tier1_unknown_repo_raises(
        self, use_case: GetSymbolTreeUseCase
    ) -> None:
        """Unknown repository name raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await use_case.execute(GetSymbolTreeRequest(repository_name="nonexistent"))


class TestGetSymbolTreeTier2:
    """Tier 2: top-level symbols in a file."""

    @pytest.fixture
    def repo_adapter(self) -> InMemoryRepositoryRepository:
        adapter = InMemoryRepositoryRepository()
        adapter.add(Repository(id=1, name="test-repo", url="/repos/test-repo"))
        return adapter

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        repo = InMemoryCommitRepository()
        repo._commits[1] = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("abc123"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
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
                path="src/models.py",
                content_hash="h1",
                size_bytes=500,
                language="python",
            )
        )
        return repo

    @pytest.fixture
    def symbol_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemorySymbolRepository:
        repo = InMemorySymbolRepository(file_repo=file_repo)
        # Top-level class
        repo.add(
            Symbol(
                id=1,
                repository_id=1,
                file_id=1,
                name="UserModel",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=30,
                end_column=0,
                parent_symbol_id=None,
            )
        )
        # Top-level function
        repo.add(
            Symbol(
                id=2,
                repository_id=1,
                file_id=1,
                name="create_user",
                kind=SymbolKind.FUNCTION,
                start_line=32,
                start_column=0,
                end_line=40,
                end_column=0,
                parent_symbol_id=None,
            )
        )
        # Method (child of UserModel) — should NOT appear in tier 2
        repo.add(
            Symbol(
                id=3,
                repository_id=1,
                file_id=1,
                name="save",
                kind=SymbolKind.METHOD,
                start_line=10,
                start_column=4,
                end_line=15,
                end_column=0,
                parent_symbol_id=1,
            )
        )
        return repo

    @pytest.fixture
    def reference_repo(self) -> InMemoryReferenceRepository:
        return InMemoryReferenceRepository()

    @pytest.fixture
    def use_case(
        self,
        repo_adapter: InMemoryRepositoryRepository,
        symbol_repo: InMemorySymbolRepository,
        file_repo: InMemoryFileRepository,
        reference_repo: InMemoryReferenceRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> GetSymbolTreeUseCase:
        return GetSymbolTreeUseCase(
            repository_repo=repo_adapter,
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            reference_repo=reference_repo,
            commit_repo=commit_repo,
        )

    @pytest.mark.asyncio
    async def test_tier2_returns_top_level_symbols_only(
        self, use_case: GetSymbolTreeUseCase
    ) -> None:
        """Tier 2 returns only symbols with no parent."""
        result = await use_case.execute(
            GetSymbolTreeRequest(repository_name="test-repo", file_id=1)
        )

        assert isinstance(result, GetSymbolTreeSymbolsResponse)
        assert len(result.symbols) == 2
        names = {n.symbol.name for n in result.symbols}
        assert names == {"UserModel", "create_user"}
        # Method should not appear
        assert "save" not in names

    @pytest.mark.asyncio
    async def test_tier2_has_children_flag(
        self, use_case: GetSymbolTreeUseCase
    ) -> None:
        """has_children is True for symbols with child symbols."""
        result = await use_case.execute(
            GetSymbolTreeRequest(repository_name="test-repo", file_id=1)
        )

        assert isinstance(result, GetSymbolTreeSymbolsResponse)
        by_name = {n.symbol.name: n for n in result.symbols}
        assert by_name["UserModel"].has_children is True
        assert by_name["create_user"].has_children is False

    @pytest.mark.asyncio
    async def test_tier2_includes_file_path(
        self, use_case: GetSymbolTreeUseCase
    ) -> None:
        """Tier 2 symbols include their file path."""
        result = await use_case.execute(
            GetSymbolTreeRequest(repository_name="test-repo", file_id=1)
        )

        assert isinstance(result, GetSymbolTreeSymbolsResponse)
        for node in result.symbols:
            assert node.file_path == "src/models.py"

    @pytest.mark.asyncio
    async def test_tier2_filter_by_kind(self, use_case: GetSymbolTreeUseCase) -> None:
        """Kind filter narrows tier 2 results."""
        result = await use_case.execute(
            GetSymbolTreeRequest(repository_name="test-repo", file_id=1, kind="class")
        )

        assert isinstance(result, GetSymbolTreeSymbolsResponse)
        assert len(result.symbols) == 1
        assert result.symbols[0].symbol.name == "UserModel"


class TestGetSymbolTreeTier3:
    """Tier 3: children of a symbol."""

    @pytest.fixture
    def repo_adapter(self) -> InMemoryRepositoryRepository:
        adapter = InMemoryRepositoryRepository()
        adapter.add(Repository(id=1, name="test-repo", url="/repos/test-repo"))
        return adapter

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        repo = InMemoryCommitRepository()
        repo._commits[1] = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("abc123"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
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
                path="src/models.py",
                content_hash="h1",
                size_bytes=500,
                language="python",
            )
        )
        return repo

    @pytest.fixture
    def symbol_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemorySymbolRepository:
        repo = InMemorySymbolRepository(file_repo=file_repo)
        # Parent class
        repo.add(
            Symbol(
                id=1,
                repository_id=1,
                file_id=1,
                name="UserModel",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=30,
                end_column=0,
            )
        )
        # Child method
        repo.add(
            Symbol(
                id=2,
                repository_id=1,
                file_id=1,
                name="save",
                kind=SymbolKind.METHOD,
                start_line=10,
                start_column=4,
                end_line=15,
                end_column=0,
                parent_symbol_id=1,
            )
        )
        # Child field
        repo.add(
            Symbol(
                id=3,
                repository_id=1,
                file_id=1,
                name="username",
                kind=SymbolKind.FIELD,
                start_line=2,
                start_column=4,
                end_line=2,
                end_column=20,
                parent_symbol_id=1,
            )
        )
        # Another top-level (should NOT appear)
        repo.add(
            Symbol(
                id=4,
                repository_id=1,
                file_id=1,
                name="helper",
                kind=SymbolKind.FUNCTION,
                start_line=32,
                start_column=0,
                end_line=40,
                end_column=0,
            )
        )
        return repo

    @pytest.fixture
    def reference_repo(self) -> InMemoryReferenceRepository:
        return InMemoryReferenceRepository()

    @pytest.fixture
    def use_case(
        self,
        repo_adapter: InMemoryRepositoryRepository,
        symbol_repo: InMemorySymbolRepository,
        file_repo: InMemoryFileRepository,
        reference_repo: InMemoryReferenceRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> GetSymbolTreeUseCase:
        return GetSymbolTreeUseCase(
            repository_repo=repo_adapter,
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            reference_repo=reference_repo,
            commit_repo=commit_repo,
        )

    @pytest.mark.asyncio
    async def test_tier3_returns_children_only(
        self, use_case: GetSymbolTreeUseCase
    ) -> None:
        """Tier 3 returns only children of the specified parent."""
        result = await use_case.execute(
            GetSymbolTreeRequest(repository_name="test-repo", parent_symbol_id=1)
        )

        assert isinstance(result, GetSymbolTreeSymbolsResponse)
        assert len(result.symbols) == 2
        names = {n.symbol.name for n in result.symbols}
        assert names == {"save", "username"}

    @pytest.mark.asyncio
    async def test_tier3_unknown_parent_raises(
        self, use_case: GetSymbolTreeUseCase
    ) -> None:
        """Unknown parent symbol ID raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await use_case.execute(
                GetSymbolTreeRequest(repository_name="test-repo", parent_symbol_id=999)
            )


class TestGetSymbolTreeInheritance:
    """Inheritance references in the symbol tree."""

    @pytest.fixture
    def repo_adapter(self) -> InMemoryRepositoryRepository:
        adapter = InMemoryRepositoryRepository()
        adapter.add(Repository(id=1, name="test-repo", url="/repos/test-repo"))
        return adapter

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        repo = InMemoryCommitRepository()
        repo._commits[1] = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("abc123"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
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
                path="src/models.py",
                content_hash="h1",
                size_bytes=500,
                language="python",
            )
        )
        repo.add(
            File(
                id=2,
                repository_id=1,
                path="src/base.py",
                content_hash="h2",
                size_bytes=300,
                language="python",
            )
        )
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
                name="AdminUser",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=30,
                end_column=0,
            )
        )
        repo.add(
            Symbol(
                id=2,
                repository_id=1,
                file_id=1,
                name="helper",
                kind=SymbolKind.FUNCTION,
                start_line=32,
                start_column=0,
                end_line=40,
                end_column=0,
            )
        )
        # BaseUser class in a different file (target for inheritance resolution)
        repo.add(
            Symbol(
                id=3,
                repository_id=1,
                file_id=2,
                name="BaseUser",
                kind=SymbolKind.CLASS,
                start_line=5,
                start_column=0,
                end_line=50,
                end_column=0,
            )
        )
        return repo

    @pytest.fixture
    def reference_repo(self) -> InMemoryReferenceRepository:
        repo = InMemoryReferenceRepository()
        # Inheritance reference: AdminUser extends BaseUser
        repo.add(
            Reference(
                id=1,
                repository_id=1,
                source_file_id=1,
                source_line=1,  # Within AdminUser's line range
                source_column=20,
                source_end_column=28,
                reference_text="BaseUser",
                reference_type=ReferenceType.INHERITANCE,
            )
        )
        # Non-inheritance reference (should be excluded)
        repo.add(
            Reference(
                id=2,
                repository_id=1,
                source_file_id=1,
                source_line=5,
                source_column=0,
                source_end_column=10,
                reference_text="some_func",
                reference_type=ReferenceType.CALL,
            )
        )
        return repo

    @pytest.fixture
    def use_case(
        self,
        repo_adapter: InMemoryRepositoryRepository,
        symbol_repo: InMemorySymbolRepository,
        file_repo: InMemoryFileRepository,
        reference_repo: InMemoryReferenceRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> GetSymbolTreeUseCase:
        return GetSymbolTreeUseCase(
            repository_repo=repo_adapter,
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            reference_repo=reference_repo,
            commit_repo=commit_repo,
        )

    @pytest.mark.asyncio
    async def test_inheritance_refs_attached_to_class(
        self, use_case: GetSymbolTreeUseCase
    ) -> None:
        """Inheritance references are attached to the correct class symbol."""
        result = await use_case.execute(
            GetSymbolTreeRequest(repository_name="test-repo", file_id=1)
        )

        assert isinstance(result, GetSymbolTreeSymbolsResponse)
        by_name = {n.symbol.name: n for n in result.symbols}

        admin = by_name["AdminUser"]
        assert len(admin.inheritance) == 1
        inh = admin.inheritance[0]
        assert inh.reference_text == "BaseUser"
        assert inh.target_symbol_id == 3  # Resolved to BaseUser symbol
        assert inh.target_file_id == 2
        assert inh.target_file_path == "src/base.py"
        assert inh.target_line == 5

        # Function should have no inheritance
        helper = by_name["helper"]
        assert len(helper.inheritance) == 0


class TestGetSymbolTreeCommitScoped:
    """Symbol tree respects branch/commit scoping."""

    @pytest.fixture
    def repo_adapter(self) -> InMemoryRepositoryRepository:
        adapter = InMemoryRepositoryRepository()
        adapter.add(Repository(id=1, name="test-repo", url="/repos/test-repo"))
        return adapter

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        repo = InMemoryCommitRepository()
        repo._commits[1] = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("commit1aaa"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        repo._commits[2] = Commit(
            id=2,
            repository_id=1,
            commit_hash=CommitHash("commit2bbb"),
            author_date=datetime(2025, 1, 2),
            commit_date=datetime(2025, 1, 2),
        )
        repo._branch_commits[(1, "main", 1)] = True
        repo._branch_commits[(1, "main", 2)] = True
        return repo

    @pytest.fixture
    def file_repo(
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        repo = InMemoryFileRepository(commit_repo=commit_repo)
        # File v1 at commit 1
        repo.add(
            File(
                id=1,
                repository_id=1,
                path="src/app.py",
                content_hash="old",
                size_bytes=100,
                language="python",
            )
        )
        # File v2 at commit 2 (same path, new content)
        repo.add(
            File(
                id=2,
                repository_id=1,
                path="src/app.py",
                content_hash="new",
                size_bytes=150,
                language="python",
            )
        )
        # New file only at commit 2
        repo.add(
            File(
                id=3,
                repository_id=1,
                path="src/new_module.py",
                content_hash="nm",
                size_bytes=80,
                language="python",
            )
        )
        repo._commit_files.add((1, 1))
        repo._commit_files.add((2, 2))
        repo._commit_files.add((2, 3))
        return repo

    @pytest.fixture
    def symbol_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemorySymbolRepository:
        repo = InMemorySymbolRepository(file_repo=file_repo)
        # Symbol in file v1
        repo.add(
            Symbol(
                id=1,
                repository_id=1,
                file_id=1,
                name="old_func",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        # Symbol in file v2
        repo.add(
            Symbol(
                id=2,
                repository_id=1,
                file_id=2,
                name="new_func",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        # Symbol in new_module.py
        repo.add(
            Symbol(
                id=3,
                repository_id=1,
                file_id=3,
                name="extra",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )
        return repo

    @pytest.fixture
    def reference_repo(self) -> InMemoryReferenceRepository:
        return InMemoryReferenceRepository()

    @pytest.fixture
    def use_case(
        self,
        repo_adapter: InMemoryRepositoryRepository,
        symbol_repo: InMemorySymbolRepository,
        file_repo: InMemoryFileRepository,
        reference_repo: InMemoryReferenceRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> GetSymbolTreeUseCase:
        return GetSymbolTreeUseCase(
            repository_repo=repo_adapter,
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            reference_repo=reference_repo,
            commit_repo=commit_repo,
        )

    @pytest.mark.asyncio
    async def test_commit_scoped_tier1_shows_files_at_commit(
        self, use_case: GetSymbolTreeUseCase
    ) -> None:
        """Tier 1 at commit 1 shows only files from that commit."""
        result = await use_case.execute(
            GetSymbolTreeRequest(
                repository_name="test-repo",
                commit_hash="commit1aaa",
            )
        )

        assert isinstance(result, GetSymbolTreeFilesResponse)
        paths = {f.path for f in result.files}
        assert paths == {"src/app.py"}
        # new_module.py not at commit 1

    @pytest.mark.asyncio
    async def test_commit_scoped_tier1_latest_commit(
        self, use_case: GetSymbolTreeUseCase
    ) -> None:
        """Tier 1 at commit 2 shows files from that commit."""
        result = await use_case.execute(
            GetSymbolTreeRequest(
                repository_name="test-repo",
                commit_hash="commit2bbb",
            )
        )

        assert isinstance(result, GetSymbolTreeFilesResponse)
        paths = {f.path for f in result.files}
        assert paths == {"src/app.py", "src/new_module.py"}

    @pytest.mark.asyncio
    async def test_invalid_commit_hash_raises(
        self, use_case: GetSymbolTreeUseCase
    ) -> None:
        """Invalid commit hash raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await use_case.execute(
                GetSymbolTreeRequest(
                    repository_name="test-repo",
                    commit_hash="nonexistent",
                )
            )
