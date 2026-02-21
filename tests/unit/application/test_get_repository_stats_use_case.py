"""Tests for GetRepositoryStatsUseCase using dependency injection."""

from datetime import datetime

import pytest

from inxr2.application.use_cases.repositories import (
    GetRepositoryStatsRequest,
    GetRepositoryStatsUseCase,
)
from inxr2.domain.entities import Commit, File, Reference, Repository, Symbol
from inxr2.domain.exceptions import RepositoryNotFound
from inxr2.domain.value_objects import CommitHash, ReferenceType, SymbolKind
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryReferenceRepository,
    InMemoryRepositoryRepository,
    InMemorySymbolRepository,
)


class TestGetRepositoryStatsUseCase:
    """Tests for GetRepositoryStatsUseCase."""

    @pytest.fixture
    def repository_repo(self) -> InMemoryRepositoryRepository:
        """Create repository with test data."""
        repo = InMemoryRepositoryRepository()
        repo.add(
            Repository(
                id=1,
                name="test-repo",
                url="/path/to/repo",
                default_branch="main",
            )
        )
        repo.add(
            Repository(
                id=2,
                name="other-repo",
                url="/path/to/other",
                default_branch="main",
            )
        )
        return repo

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        """Create commit repository with test data."""
        repo = InMemoryCommitRepository()
        # Commits for repo 1
        c1 = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("a" * 40),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        repo.add(c1)
        repo._branch_commits[(1, "main", 1)] = True

        c2 = Commit(
            id=2,
            repository_id=1,
            commit_hash=CommitHash("b" * 40),
            author_date=datetime(2025, 6, 15),
            commit_date=datetime(2025, 6, 15),
        )
        repo.add(c2)
        repo._branch_commits[(1, "main", 2)] = True

        # Commit for repo 2
        c3 = Commit(
            id=3,
            repository_id=2,
            commit_hash=CommitHash("c" * 40),
            author_date=datetime(2025, 3, 10),
            commit_date=datetime(2025, 3, 10),
        )
        repo.add(c3)
        repo._branch_commits[(2, "main", 3)] = True
        return repo

    @pytest.fixture
    def file_repo(
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        """Create file repository with test data."""
        repo = InMemoryFileRepository(commit_repo=commit_repo)
        # Files for repo 1 (linked to latest commit id=2)
        # _commit_files tuples are (commit_id, file_id)
        repo.add(
            File(
                id=1,
                repository_id=1,
                path="src/main.py",
                content_hash="hash1",
                size_bytes=100,
                language="Python",
                line_count=50,
            )
        )
        repo._commit_files.add((2, 1))
        repo.add(
            File(
                id=2,
                repository_id=1,
                path="src/utils.py",
                content_hash="hash2",
                size_bytes=200,
                language="Python",
                line_count=80,
            )
        )
        repo._commit_files.add((2, 2))
        repo.add(
            File(
                id=3,
                repository_id=1,
                path="src/app.ts",
                content_hash="hash3",
                size_bytes=300,
                language="TypeScript",
                line_count=120,
            )
        )
        repo._commit_files.add((2, 3))
        repo.add(
            File(
                id=4,
                repository_id=1,
                path="README.md",
                content_hash="hash4",
                size_bytes=50,
                language=None,  # Unknown language
                line_count=None,  # No line count
            )
        )
        repo._commit_files.add((2, 4))
        # Files for repo 2 (linked to commit id=3)
        repo.add(
            File(
                id=5,
                repository_id=2,
                path="index.js",
                content_hash="hash5",
                size_bytes=150,
                language="JavaScript",
                line_count=40,
            )
        )
        repo._commit_files.add((3, 5))
        return repo

    @pytest.fixture
    def symbol_repo(self) -> InMemorySymbolRepository:
        """Create symbol repository with test data."""
        repo = InMemorySymbolRepository()
        # Symbols for repo 1
        repo.add(
            Symbol(
                id=1,
                file_id=1,
                repository_id=1,
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
                file_id=1,
                repository_id=1,
                name="Helper",
                kind=SymbolKind.CLASS,
                start_line=12,
                start_column=0,
                end_line=30,
                end_column=0,
            )
        )
        repo.add(
            Symbol(
                id=3,
                file_id=2,
                repository_id=1,
                name="utility",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )
        # Symbol for repo 2
        repo.add(
            Symbol(
                id=4,
                file_id=5,
                repository_id=2,
                name="init",
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
        """Create reference repository with test data."""
        repo = InMemoryReferenceRepository()
        # References for repo 1
        repo.add(
            Reference(
                id=1,
                repository_id=1,
                source_file_id=1,
                source_line=5,
                source_column=10,
                source_end_column=17,
                reference_text="utility",
                reference_type=ReferenceType.CALL,
                target_symbol_id=3,  # Resolved
            )
        )
        repo.add(
            Reference(
                id=2,
                repository_id=1,
                source_file_id=1,
                source_line=8,
                source_column=4,
                source_end_column=10,
                reference_text="Helper",
                reference_type=ReferenceType.INSTANTIATION,
                target_symbol_id=None,  # Unresolved
            )
        )
        # Reference for repo 2
        repo.add(
            Reference(
                id=3,
                repository_id=2,
                source_file_id=5,
                source_line=3,
                source_column=0,
                source_end_column=7,
                reference_text="console",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,  # Unresolved
            )
        )
        return repo

    @pytest.fixture
    def use_case(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> GetRepositoryStatsUseCase:
        """Create use case with test repositories."""
        return GetRepositoryStatsUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            commit_repo=commit_repo,
        )

    # === Repository Resolution Tests ===

    @pytest.mark.asyncio
    async def test_get_stats_by_repository_id(
        self, use_case: GetRepositoryStatsUseCase
    ) -> None:
        """Should get stats when repository ID is provided."""
        request = GetRepositoryStatsRequest(repository_id=1)

        stats = await use_case.execute(request)

        assert stats.repository_id == 1
        assert stats.name == "test-repo"

    @pytest.mark.asyncio
    async def test_get_stats_by_repository_name(
        self, use_case: GetRepositoryStatsUseCase
    ) -> None:
        """Should get stats when repository name is provided."""
        request = GetRepositoryStatsRequest(repository_name="test-repo")

        stats = await use_case.execute(request)

        assert stats.repository_id == 1
        assert stats.name == "test-repo"

    @pytest.mark.asyncio
    async def test_raises_repository_not_found_for_unknown_id(
        self, use_case: GetRepositoryStatsUseCase
    ) -> None:
        """Should raise RepositoryNotFound for unknown repository ID."""
        request = GetRepositoryStatsRequest(repository_id=999)

        with pytest.raises(RepositoryNotFound) as exc_info:
            await use_case.execute(request)

        assert "999" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_repository_not_found_for_unknown_name(
        self, use_case: GetRepositoryStatsUseCase
    ) -> None:
        """Should raise RepositoryNotFound for unknown repository name."""
        request = GetRepositoryStatsRequest(repository_name="unknown-repo")

        with pytest.raises(RepositoryNotFound) as exc_info:
            await use_case.execute(request)

        assert "unknown-repo" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_value_error_when_no_identifier_provided(
        self, use_case: GetRepositoryStatsUseCase
    ) -> None:
        """Should raise ValueError when neither ID nor name is provided."""
        request = GetRepositoryStatsRequest()

        with pytest.raises(ValueError) as exc_info:
            await use_case.execute(request)

        assert "repository_id or repository_name" in str(exc_info.value)

    # === Statistics Aggregation Tests ===

    @pytest.mark.asyncio
    async def test_returns_correct_file_count(
        self, use_case: GetRepositoryStatsUseCase
    ) -> None:
        """Should return correct total file count."""
        request = GetRepositoryStatsRequest(repository_id=1)

        stats = await use_case.execute(request)

        assert stats.total_files == 4

    @pytest.mark.asyncio
    async def test_returns_correct_symbol_count(
        self, use_case: GetRepositoryStatsUseCase
    ) -> None:
        """Should return correct total symbol count."""
        request = GetRepositoryStatsRequest(repository_id=1)

        stats = await use_case.execute(request)

        assert stats.total_symbols == 3

    @pytest.mark.asyncio
    async def test_returns_correct_reference_count(
        self, use_case: GetRepositoryStatsUseCase
    ) -> None:
        """Should return correct total reference count."""
        request = GetRepositoryStatsRequest(repository_id=1)

        stats = await use_case.execute(request)

        assert stats.total_references == 2

    @pytest.mark.asyncio
    async def test_returns_correct_language_distribution(
        self, use_case: GetRepositoryStatsUseCase
    ) -> None:
        """Should return correct language distribution."""
        request = GetRepositoryStatsRequest(repository_id=1)

        stats = await use_case.execute(request)

        assert stats.language_distribution == {
            "Python": 2,
            "TypeScript": 1,
            "unknown": 1,  # README.md has no language
        }

    @pytest.mark.asyncio
    async def test_returns_correct_total_lines(
        self, use_case: GetRepositoryStatsUseCase
    ) -> None:
        """Should return total lines summed from all files."""
        request = GetRepositoryStatsRequest(repository_id=1)

        stats = await use_case.execute(request)

        # 50 + 80 + 120 + 0 (None) = 250
        assert stats.total_lines == 250

    @pytest.mark.asyncio
    async def test_returns_correct_resolved_unresolved_counts(
        self, use_case: GetRepositoryStatsUseCase
    ) -> None:
        """Should return resolved and unresolved reference counts."""
        request = GetRepositoryStatsRequest(repository_id=1)

        stats = await use_case.execute(request)

        # 2 total refs, 1 unresolved (no target_symbol_id)
        assert stats.total_references_unresolved == 1
        assert stats.total_references_resolved == 1

    @pytest.mark.asyncio
    async def test_returns_commit_date_range(
        self, use_case: GetRepositoryStatsUseCase
    ) -> None:
        """Should return the earliest and latest commit dates."""
        request = GetRepositoryStatsRequest(repository_id=1)

        stats = await use_case.execute(request)

        assert stats.commit_date_earliest == datetime(2025, 1, 1)
        assert stats.commit_date_latest == datetime(2025, 6, 15)

    # === Repository Isolation Tests ===

    @pytest.mark.asyncio
    async def test_stats_are_repository_specific(
        self, use_case: GetRepositoryStatsUseCase
    ) -> None:
        """Should only include data from the requested repository."""
        request = GetRepositoryStatsRequest(repository_id=2)

        stats = await use_case.execute(request)

        assert stats.repository_id == 2
        assert stats.name == "other-repo"
        assert stats.total_files == 1
        assert stats.total_symbols == 1
        assert stats.total_references == 1
        assert stats.language_distribution == {"JavaScript": 1}
        assert stats.total_lines == 40
        assert stats.total_references_unresolved == 1
        assert stats.total_references_resolved == 0
        assert stats.commit_date_earliest == datetime(2025, 3, 10)
        assert stats.commit_date_latest == datetime(2025, 3, 10)


class TestGetRepositoryStatsUseCaseEdgeCases:
    """Edge case tests for GetRepositoryStatsUseCase."""

    @pytest.mark.asyncio
    async def test_empty_repository_returns_zero_counts(self) -> None:
        """Should return zero counts for repository with no indexed data."""
        repository_repo = InMemoryRepositoryRepository()
        repository_repo.add(
            Repository(id=1, name="empty-repo", url="/path", default_branch="main")
        )

        file_repo = InMemoryFileRepository()
        symbol_repo = InMemorySymbolRepository()
        reference_repo = InMemoryReferenceRepository()
        commit_repo = InMemoryCommitRepository()

        use_case = GetRepositoryStatsUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            commit_repo=commit_repo,
        )

        request = GetRepositoryStatsRequest(repository_id=1)
        stats = await use_case.execute(request)

        assert stats.total_files == 0
        assert stats.total_symbols == 0
        assert stats.total_references == 0
        assert stats.language_distribution == {}
        assert stats.total_lines == 0
        assert stats.total_references_resolved == 0
        assert stats.total_references_unresolved == 0
        assert stats.commit_date_earliest is None
        assert stats.commit_date_latest is None

    @pytest.mark.asyncio
    async def test_all_files_same_language(self) -> None:
        """Should handle repository with all files in same language."""
        repository_repo = InMemoryRepositoryRepository()
        repository_repo.add(
            Repository(id=1, name="python-only", url="/path", default_branch="main")
        )

        file_repo = InMemoryFileRepository()
        file_repo.add(
            File(
                id=1,
                repository_id=1,
                path="a.py",
                content_hash="h1",
                size_bytes=100,
                language="Python",
            )
        )
        file_repo.add(
            File(
                id=2,
                repository_id=1,
                path="b.py",
                content_hash="h2",
                size_bytes=100,
                language="Python",
            )
        )
        file_repo.add(
            File(
                id=3,
                repository_id=1,
                path="c.py",
                content_hash="h3",
                size_bytes=100,
                language="Python",
            )
        )

        use_case = GetRepositoryStatsUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            symbol_repo=InMemorySymbolRepository(),
            reference_repo=InMemoryReferenceRepository(),
        )

        request = GetRepositoryStatsRequest(repository_id=1)
        stats = await use_case.execute(request)

        assert stats.language_distribution == {"Python": 3}

    @pytest.mark.asyncio
    async def test_uses_head_commit_files_when_commit_repo_provided(self) -> None:
        """Should use list_by_commit for HEAD instead of deduplication.

        Regression test: with HEAD-first indexing, the HEAD commit may have
        a lower auto-increment ID than older commits. Using file.id for
        deduplication would pick the wrong version. Using list_by_commit
        on the HEAD commit gives the correct file set.
        """
        repository_repo = InMemoryRepositoryRepository()
        repository_repo.add(
            Repository(id=1, name="test-repo", url="/path", default_branch="main")
        )

        commit_repo = InMemoryCommitRepository()
        # HEAD commit (indexed first, gets lower ID)
        head_commit = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("aaaa"),
            author_date=datetime(2025, 1, 10),
            commit_date=datetime(2025, 1, 10),
        )
        commit_repo.add(head_commit)
        commit_repo._branch_commits[(1, "main", 1)] = True

        # Older commit (indexed second, gets higher ID)
        old_commit = Commit(
            id=2,
            repository_id=1,
            commit_hash=CommitHash("bbbb"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        commit_repo.add(old_commit)
        commit_repo._branch_commits[(1, "main", 2)] = True

        file_repo = InMemoryFileRepository(commit_repo=commit_repo)
        # HEAD version of file (lower ID)
        file_repo.add(
            File(
                id=1,
                repository_id=1,
                path="src/main.py",
                content_hash="head_hash",
                size_bytes=100,
                language="Python",
            )
        )
        file_repo._commit_files.add((1, 1))  # linked to HEAD

        # Old version of file (higher ID)
        file_repo.add(
            File(
                id=2,
                repository_id=1,
                path="src/main.py",
                content_hash="old_hash",
                size_bytes=80,
                language="Python",
            )
        )
        file_repo._commit_files.add((2, 2))  # linked to old commit

        use_case = GetRepositoryStatsUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            symbol_repo=InMemorySymbolRepository(),
            reference_repo=InMemoryReferenceRepository(),
            commit_repo=commit_repo,
        )

        request = GetRepositoryStatsRequest(repository_id=1)
        stats = await use_case.execute(request)

        # Should count 1 file (from HEAD commit), not 2
        assert stats.total_files == 1
