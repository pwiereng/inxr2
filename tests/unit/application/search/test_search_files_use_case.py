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
        # Link files to commit 1 (abc123)
        assert f1.id is not None and f2.id is not None
        await repo.link_file_to_commit(f1.id, commit_id=1)
        await repo.link_file_to_commit(f2.id, commit_id=1)
        return repo

    @pytest.fixture
    def use_case(
        self,
        file_repo: InMemoryFileRepository,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> SearchFilesUseCase:
        """Create the use case with all dependencies."""
        return SearchFilesUseCase(
            file_repo=file_repo,
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
