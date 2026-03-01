"""Tests for SearchFilesUseCase using dependency injection."""

from datetime import UTC, datetime

import pytest

from inxr2.application.use_cases.search import SearchFilesRequest, SearchFilesUseCase
from inxr2.domain.entities import Commit, File, Repository
from inxr2.domain.exceptions import CommitNotFound, RepositoryNotFound
from inxr2.domain.value_objects import CommitHash
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryFileSearchRepository,
    InMemoryRepositoryRepository,
)


class TestSearchFilesUseCase:
    """Tests for SearchFilesUseCase."""

    @pytest.fixture
    def repository_repo(self) -> InMemoryRepositoryRepository:
        """Create a repository repository with test data."""
        repo = InMemoryRepositoryRepository()
        repo.add(
            Repository(
                id=1,
                name="test-repo",
                url="/repos/test-repo",
                description="Test repository",
            )
        )
        return repo

    @pytest.fixture
    async def commit_repo(self) -> InMemoryCommitRepository:
        """Create a commit repository with test data."""
        repo = InMemoryCommitRepository()
        commit = await repo.save(
            Commit(
                id=None,
                repository_id=1,
                commit_hash=CommitHash("abc123"),
                author_date=datetime(2024, 1, 1, tzinfo=UTC),
                commit_date=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        assert commit.id is not None
        await repo.link_commit_to_branch(1, commit.id, "main")
        return repo

    @pytest.fixture
    async def file_repo(
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        """Create a file repository with test data linked to commits."""
        repo = InMemoryFileRepository(commit_repo=commit_repo)
        f1 = await repo.save(
            File(
                repository_id=1,
                path="src/utils.py",
                content_hash="hash1",
                size_bytes=1000,
                language="python",
            )
        )
        f2 = await repo.save(
            File(
                repository_id=1,
                path="src/main.ts",
                content_hash="hash2",
                size_bytes=500,
                language="typescript",
            )
        )
        # Link files to the saved commit (abc123)
        assert f1.id is not None and f2.id is not None
        # Use the actual commit ID from the commit_repo fixture
        saved_commits = list(commit_repo._commits.values())
        assert len(saved_commits) == 1
        commit_id = saved_commits[0].id
        assert commit_id is not None
        await repo.link_file_to_commit(f1.id, commit_id=commit_id)
        await repo.link_file_to_commit(f2.id, commit_id=commit_id)
        return repo

    @pytest.fixture
    def use_case(
        self,
        file_repo: InMemoryFileRepository,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> SearchFilesUseCase:
        """Create the use case with all dependencies."""
        file_search_repo = InMemoryFileSearchRepository(file_repo)
        return SearchFilesUseCase(
            file_search_repo=file_search_repo,
            repository_repo=repository_repo,
            commit_repo=commit_repo,
        )

    @pytest.mark.asyncio
    async def test_search_finds_matching_files(
        self, use_case: SearchFilesUseCase
    ) -> None:
        """Test basic search returns results with hydrated names."""
        request = SearchFilesRequest(query="utils")
        response = await use_case.execute(request)

        assert response.total_count == 1
        assert len(response.files) == 1
        assert response.files[0].path == "src/utils.py"
        assert response.files[0].repository_name == "test-repo"
        # No commit context when searching without branch/commit_hash
        assert response.files[0].commit_id is None
        assert response.files[0].commit_hash is None

    @pytest.mark.asyncio
    async def test_search_with_repository_filter(
        self, use_case: SearchFilesUseCase
    ) -> None:
        """Test filtering by repository name."""
        request = SearchFilesRequest(query="src", repository_name="test-repo")
        response = await use_case.execute(request)

        assert response.total_count == 2
        for file in response.files:
            assert file.repository_name == "test-repo"

    @pytest.mark.asyncio
    async def test_search_with_nonexistent_repository_raises(
        self, use_case: SearchFilesUseCase
    ) -> None:
        """Test that searching with a nonexistent repository raises RepositoryNotFound."""
        request = SearchFilesRequest(query="utils", repository_name="no-such-repo")

        with pytest.raises(RepositoryNotFound):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_search_with_branch_resolves_latest_commit(
        self, use_case: SearchFilesUseCase
    ) -> None:
        """Test that branch resolves to latest commit on that branch."""
        request = SearchFilesRequest(
            query="utils", repository_name="test-repo", branch="main"
        )
        response = await use_case.execute(request)

        assert response.total_count == 1
        assert response.files[0].path == "src/utils.py"

    @pytest.mark.asyncio
    async def test_search_with_commit_hash(self, use_case: SearchFilesUseCase) -> None:
        """Test that commit hash resolves to commit ID."""
        request = SearchFilesRequest(
            query="utils", repository_name="test-repo", commit_hash="abc123"
        )
        response = await use_case.execute(request)

        assert response.total_count == 1
        assert response.files[0].commit_hash == "abc123"

    @pytest.mark.asyncio
    async def test_search_with_nonexistent_commit_raises(
        self, use_case: SearchFilesUseCase
    ) -> None:
        """Test that searching with a nonexistent commit hash raises CommitNotFound."""
        request = SearchFilesRequest(
            query="utils", repository_name="test-repo", commit_hash="deadbeef"
        )

        with pytest.raises(CommitNotFound):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_branch_without_repository_raises_error(
        self, use_case: SearchFilesUseCase
    ) -> None:
        """Test that specifying branch without repository raises ValueError."""
        request = SearchFilesRequest(query="utils", branch="main")

        with pytest.raises(
            ValueError,
            match="repository parameter is required when using branch or commit_hash",
        ):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_search_with_language_filter(
        self, use_case: SearchFilesUseCase
    ) -> None:
        """Test that language filter is passed through correctly."""
        request = SearchFilesRequest(query="src", language="typescript")
        response = await use_case.execute(request)

        assert response.total_count == 1
        assert response.files[0].path == "src/main.ts"
        assert response.files[0].language == "typescript"

    @pytest.mark.asyncio
    async def test_search_no_results(self, use_case: SearchFilesUseCase) -> None:
        """Test that no results are handled correctly."""
        request = SearchFilesRequest(query="nonexistent_file_xyz")
        response = await use_case.execute(request)

        assert response.total_count == 0
        assert response.files == []

    @pytest.mark.asyncio
    async def test_result_includes_filename(self, use_case: SearchFilesUseCase) -> None:
        """Test that filename is correctly extracted from path."""
        request = SearchFilesRequest(query="utils")
        response = await use_case.execute(request)

        assert response.files[0].name == "utils.py"
        assert response.files[0].path == "src/utils.py"


class TestSearchFilesGlobalScope:
    """Tests for global file search (scope=latest, no repository)."""

    @pytest.fixture
    def repository_repo(self) -> InMemoryRepositoryRepository:
        repo = InMemoryRepositoryRepository()
        repo.add(
            Repository(
                id=1,
                name="repo-a",
                url="/repos/repo-a",
                default_branch="main",
            )
        )
        repo.add(
            Repository(
                id=2,
                name="repo-b",
                url="/repos/repo-b",
                default_branch="main",
            )
        )
        return repo

    @pytest.fixture
    async def commit_repo(self) -> InMemoryCommitRepository:
        repo = InMemoryCommitRepository()
        c1 = await repo.save(
            Commit(
                id=None,
                repository_id=1,
                commit_hash=CommitHash("aaa111"),
                author_date=datetime(2024, 1, 1, tzinfo=UTC),
                commit_date=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        assert c1.id is not None
        await repo.link_commit_to_branch(1, c1.id, "main")

        c2 = await repo.save(
            Commit(
                id=None,
                repository_id=2,
                commit_hash=CommitHash("bbb222"),
                author_date=datetime(2024, 1, 2, tzinfo=UTC),
                commit_date=datetime(2024, 1, 2, tzinfo=UTC),
            )
        )
        assert c2.id is not None
        await repo.link_commit_to_branch(2, c2.id, "main")
        return repo

    @pytest.fixture
    async def file_repo(
        self,
        commit_repo: InMemoryCommitRepository,
        repository_repo: InMemoryRepositoryRepository,
    ) -> InMemoryFileRepository:
        repo = InMemoryFileRepository(commit_repo=commit_repo)
        repo._repository_repo = repository_repo  # type: ignore[attr-defined]
        f1 = await repo.save(
            File(
                repository_id=1,
                path="src/utils.py",
                content_hash="h1",
                size_bytes=100,
                language="python",
            )
        )
        f2 = await repo.save(
            File(
                repository_id=2,
                path="src/helpers.rs",
                content_hash="h2",
                size_bytes=200,
                language="rust",
            )
        )
        assert f1.id is not None and f2.id is not None
        # Use actual commit IDs from the commit_repo fixture
        commits_by_repo: dict[int, int] = {}
        for c in commit_repo._commits.values():
            assert c.id is not None
            commits_by_repo[c.repository_id] = c.id
        await repo.link_file_to_commit(f1.id, commit_id=commits_by_repo[1])
        await repo.link_file_to_commit(f2.id, commit_id=commits_by_repo[2])
        return repo

    @pytest.fixture
    def use_case(
        self,
        file_repo: InMemoryFileRepository,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> SearchFilesUseCase:
        file_search_repo = InMemoryFileSearchRepository(file_repo)
        return SearchFilesUseCase(
            file_search_repo=file_search_repo,
            repository_repo=repository_repo,
            commit_repo=commit_repo,
        )

    @pytest.mark.asyncio
    async def test_global_file_search_returns_multiple_repos(
        self, use_case: SearchFilesUseCase
    ) -> None:
        """Global file search returns files from multiple repos."""
        request = SearchFilesRequest(query="src", scope="latest")
        response = await use_case.execute(request)

        assert response.total_count == 2
        repo_names = {f.repository_name for f in response.files}
        assert repo_names == {"repo-a", "repo-b"}

    @pytest.mark.asyncio
    async def test_branch_without_repo_still_raises_in_non_global_mode(
        self, use_case: SearchFilesUseCase
    ) -> None:
        """branch without repository_name still raises when specified."""
        request = SearchFilesRequest(query="src", branch="main")

        with pytest.raises(
            ValueError,
            match="repository parameter is required when using branch or commit_hash",
        ):
            await use_case.execute(request)


class TestSearchFilesExtensionFilter:
    """Tests for file search with extension filtering."""

    @pytest.fixture
    def repository_repo(self) -> InMemoryRepositoryRepository:
        repo = InMemoryRepositoryRepository()
        repo.add(
            Repository(
                id=1,
                name="test-repo",
                url="/repos/test-repo",
                default_branch="main",
            )
        )
        return repo

    @pytest.fixture
    async def commit_repo(self) -> InMemoryCommitRepository:
        repo = InMemoryCommitRepository()
        c = await repo.save(
            Commit(
                id=None,
                repository_id=1,
                commit_hash=CommitHash("ext111"),
                author_date=datetime(2024, 1, 1, tzinfo=UTC),
                commit_date=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        assert c.id is not None
        await repo.link_commit_to_branch(1, c.id, "main")
        return repo

    @pytest.fixture
    async def file_repo(
        self,
        commit_repo: InMemoryCommitRepository,
        repository_repo: InMemoryRepositoryRepository,
    ) -> InMemoryFileRepository:
        repo = InMemoryFileRepository(commit_repo=commit_repo)
        repo._repository_repo = repository_repo  # type: ignore[attr-defined]
        f1 = await repo.save(
            File(
                repository_id=1,
                path="src/utils.py",
                content_hash="h1",
                size_bytes=100,
                language="python",
                extension=".py",
            )
        )
        f2 = await repo.save(
            File(
                repository_id=1,
                path="src/main.ts",
                content_hash="h2",
                size_bytes=200,
                language="typescript",
                extension=".ts",
            )
        )
        f3 = await repo.save(
            File(
                repository_id=1,
                path="src/app.tsx",
                content_hash="h3",
                size_bytes=300,
                language="typescript",
                extension=".tsx",
            )
        )
        assert f1.id is not None and f2.id is not None and f3.id is not None
        commit_id = list(commit_repo._commits.values())[0].id
        assert commit_id is not None
        await repo.link_file_to_commit(f1.id, commit_id=commit_id)
        await repo.link_file_to_commit(f2.id, commit_id=commit_id)
        await repo.link_file_to_commit(f3.id, commit_id=commit_id)
        return repo

    @pytest.fixture
    def use_case(
        self,
        file_repo: InMemoryFileRepository,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> SearchFilesUseCase:
        file_search_repo = InMemoryFileSearchRepository(file_repo)
        return SearchFilesUseCase(
            file_search_repo=file_search_repo,
            repository_repo=repository_repo,
            commit_repo=commit_repo,
        )

    @pytest.mark.asyncio
    async def test_extension_filter_single(self, use_case: SearchFilesUseCase) -> None:
        """Extension filter returns only matching files."""
        request = SearchFilesRequest(query="src", extensions=[".py"])
        response = await use_case.execute(request)

        assert response.total_count == 1
        assert response.files[0].path == "src/utils.py"

    @pytest.mark.asyncio
    async def test_extension_filter_multiple(
        self, use_case: SearchFilesUseCase
    ) -> None:
        """Multiple extensions returns union of matches."""
        request = SearchFilesRequest(query="src", extensions=[".ts", ".tsx"])
        response = await use_case.execute(request)

        assert response.total_count == 2
        paths = {f.path for f in response.files}
        assert paths == {"src/main.ts", "src/app.tsx"}

    @pytest.mark.asyncio
    async def test_extension_filter_with_no_match(
        self, use_case: SearchFilesUseCase
    ) -> None:
        """Extension filter with no match returns empty."""
        request = SearchFilesRequest(query="src", extensions=[".rs"])
        response = await use_case.execute(request)

        assert response.total_count == 0

    @pytest.mark.asyncio
    async def test_no_extension_filter_returns_all(
        self, use_case: SearchFilesUseCase
    ) -> None:
        """No extension filter returns all matching files."""
        request = SearchFilesRequest(query="src")
        response = await use_case.execute(request)

        assert response.total_count == 3

    @pytest.mark.asyncio
    async def test_get_distinct_extensions(
        self, file_repo: InMemoryFileRepository
    ) -> None:
        """get_distinct_extensions returns sorted unique extensions."""
        search_repo = InMemoryFileSearchRepository(file_repo)
        extensions = await search_repo.get_distinct_extensions(repository_id=1)

        assert extensions == [".py", ".ts", ".tsx"]

    @pytest.mark.asyncio
    async def test_get_distinct_extensions_empty(self) -> None:
        """get_distinct_extensions returns empty list when no files exist."""
        file_repo = InMemoryFileRepository()
        search_repo = InMemoryFileSearchRepository(file_repo)
        extensions = await search_repo.get_distinct_extensions()

        assert extensions == []


class TestExtensionlessFileFilter:
    """Tests for extensionless file support via (none) sentinel."""

    @pytest.fixture
    def repository_repo(self) -> InMemoryRepositoryRepository:
        repo = InMemoryRepositoryRepository()
        repo.add(
            Repository(
                id=1,
                name="test-repo",
                url="/repos/test-repo",
                default_branch="main",
            )
        )
        return repo

    @pytest.fixture
    async def commit_repo(self) -> InMemoryCommitRepository:
        repo = InMemoryCommitRepository()
        c = await repo.save(
            Commit(
                id=None,
                repository_id=1,
                commit_hash=CommitHash("none111"),
                author_date=datetime(2024, 1, 1, tzinfo=UTC),
                commit_date=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        assert c.id is not None
        await repo.link_commit_to_branch(1, c.id, "main")
        return repo

    @pytest.fixture
    async def file_repo(
        self,
        commit_repo: InMemoryCommitRepository,
        repository_repo: InMemoryRepositoryRepository,
    ) -> InMemoryFileRepository:
        repo = InMemoryFileRepository(commit_repo=commit_repo)
        repo._repository_repo = repository_repo  # type: ignore[attr-defined]
        f1 = await repo.save(
            File(
                repository_id=1,
                path="src/utils.py",
                content_hash="h1",
                size_bytes=100,
                language="python",
                extension=".py",
            )
        )
        f2 = await repo.save(
            File(
                repository_id=1,
                path="Dockerfile",
                content_hash="h2",
                size_bytes=200,
                language=None,
                extension=None,
            )
        )
        f3 = await repo.save(
            File(
                repository_id=1,
                path="Makefile",
                content_hash="h3",
                size_bytes=150,
                language=None,
                extension=None,
            )
        )
        assert f1.id is not None and f2.id is not None and f3.id is not None
        commit_id = list(commit_repo._commits.values())[0].id
        assert commit_id is not None
        await repo.link_file_to_commit(f1.id, commit_id=commit_id)
        await repo.link_file_to_commit(f2.id, commit_id=commit_id)
        await repo.link_file_to_commit(f3.id, commit_id=commit_id)
        return repo

    @pytest.fixture
    def search_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemoryFileSearchRepository:
        return InMemoryFileSearchRepository(file_repo)

    @pytest.fixture
    def use_case(
        self,
        file_repo: InMemoryFileRepository,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> SearchFilesUseCase:
        file_search_repo = InMemoryFileSearchRepository(file_repo)
        return SearchFilesUseCase(
            file_search_repo=file_search_repo,
            repository_repo=repository_repo,
            commit_repo=commit_repo,
        )

    @pytest.mark.asyncio
    async def test_get_distinct_extensions_includes_none_sentinel(
        self, search_repo: InMemoryFileSearchRepository
    ) -> None:
        """get_distinct_extensions includes (none) when extensionless files exist."""
        extensions = await search_repo.get_distinct_extensions(repository_id=1)
        assert "(none)" in extensions
        assert extensions[0] == "(none)"
        assert ".py" in extensions

    @pytest.mark.asyncio
    async def test_get_distinct_extensions_no_sentinel_without_extensionless(
        self,
    ) -> None:
        """get_distinct_extensions omits (none) when all files have extensions."""
        file_repo = InMemoryFileRepository()
        await file_repo.save(
            File(
                repository_id=1,
                path="src/main.py",
                content_hash="h1",
                size_bytes=100,
                language="python",
                extension=".py",
            )
        )
        search_repo = InMemoryFileSearchRepository(file_repo)
        extensions = await search_repo.get_distinct_extensions()
        assert "(none)" not in extensions
        assert extensions == [".py"]

    @pytest.mark.asyncio
    async def test_search_by_name_with_none_sentinel(
        self, search_repo: InMemoryFileSearchRepository
    ) -> None:
        """Search with (none) extension returns only extensionless files."""
        results = await search_repo.search_by_name(query="file", extensions=["(none)"])
        paths = {f.path for f in results}
        assert paths == {"Dockerfile", "Makefile"}

    @pytest.mark.asyncio
    async def test_search_by_name_with_mixed_extensions(
        self, search_repo: InMemoryFileSearchRepository
    ) -> None:
        """Search with (none) and real extensions returns both."""
        results = await search_repo.search_by_name(
            query="", extensions=[".py", "(none)"]
        )
        paths = {f.path for f in results}
        assert "src/utils.py" in paths
        assert "Dockerfile" in paths
        assert "Makefile" in paths

    @pytest.mark.asyncio
    async def test_search_files_use_case_with_none_sentinel(
        self, use_case: SearchFilesUseCase
    ) -> None:
        """Use case passes (none) sentinel through to search."""
        request = SearchFilesRequest(query="file", extensions=["(none)"])
        response = await use_case.execute(request)
        paths = {f.path for f in response.files}
        assert paths == {"Dockerfile", "Makefile"}


class TestValidateExtensions:
    """Tests for _validate_extensions in search API routes."""

    def test_allows_none_sentinel(self) -> None:
        """(none) sentinel passes validation."""
        from inxr2.adapters.api.routes.search import _validate_extensions

        result = _validate_extensions(["(none)"])
        assert result == ["(none)"]

    def test_allows_none_with_real_extensions(self) -> None:
        """(none) alongside real extensions passes validation."""
        from inxr2.adapters.api.routes.search import _validate_extensions

        result = _validate_extensions(["(none)", ".py", ".TS"])
        assert result == ["(none)", ".py", ".ts"]

    def test_rejects_invalid_extension(self) -> None:
        """Invalid extensions raise HTTPException 422."""
        from fastapi import HTTPException

        from inxr2.adapters.api.routes.search import _validate_extensions

        with pytest.raises(HTTPException) as exc_info:
            _validate_extensions(["invalid"])
        assert exc_info.value.status_code == 422

    def test_none_input_returns_none(self) -> None:
        """None input returns None."""
        from inxr2.adapters.api.routes.search import _validate_extensions

        assert _validate_extensions(None) is None
