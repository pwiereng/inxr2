"""Tests for SearchTextUseCase using dependency injection."""

from datetime import UTC, datetime

import pytest

from inxr2.application.use_cases.search import SearchTextRequest, SearchTextUseCase
from inxr2.domain.entities import Commit, File, Repository, TextContent
from inxr2.domain.value_objects import CommitHash
from tests.fixtures.test_doubles import (
    FakeTextSearch,
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryRepositoryRepository,
    InMemoryTextContentRepository,
)


class TestSearchTextUseCase:
    """Tests for SearchTextUseCase."""

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
        commit1 = await repo.save(
            Commit(
                id=None,
                repository_id=1,
                commit_hash=CommitHash("abc123"),
                author_date=datetime(2024, 1, 1, tzinfo=UTC),
                commit_date=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        assert commit1.id is not None
        await repo.link_commit_to_branch(1, commit1.id, "main")
        return repo

    @pytest.fixture
    async def file_repo(self) -> InMemoryFileRepository:
        """Create a file repository with test data."""
        repo = InMemoryFileRepository()
        await repo.save(
            File(
                repository_id=1,
                path="src/parser.py",
                content_hash="hash1",
                size_bytes=1000,
                language="python",
            )
        )
        return repo

    @pytest.fixture
    async def text_content_repo(self) -> InMemoryTextContentRepository:
        """Create a text content repository with test data."""
        repo = InMemoryTextContentRepository()
        await repo.save(
            TextContent(
                id=None,
                repository_id=1,
                commit_id=1,
                source_type="comment",
                source_file_id=1,
                source_line=42,
                source_end_line=42,
                content="TODO: refactor this function",
                language="python",
                content_type="single_line_comment",
            )
        )
        return repo

    @pytest.fixture
    def text_search(
        self, text_content_repo: InMemoryTextContentRepository
    ) -> FakeTextSearch:
        """Create a fake text search service."""
        return FakeTextSearch(text_content_repo)

    @pytest.fixture
    def use_case(
        self,
        text_search: FakeTextSearch,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
    ) -> SearchTextUseCase:
        """Create the use case with all dependencies."""
        return SearchTextUseCase(
            text_search=text_search,
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )

    @pytest.mark.asyncio
    async def test_search_finds_matching_text(
        self, use_case: SearchTextUseCase
    ) -> None:
        """Test basic text search finds matching content."""
        request = SearchTextRequest(query="TODO")
        response = await use_case.execute(request)

        assert response.total == 1
        assert len(response.results) == 1
        assert response.query == "TODO"
        assert response.mode == "keyword"

    @pytest.mark.asyncio
    async def test_search_with_empty_query_raises_error(
        self, use_case: SearchTextUseCase
    ) -> None:
        """Test that empty query raises ValueError."""
        request = SearchTextRequest(query="")

        with pytest.raises(ValueError, match="Search query cannot be empty"):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_search_enriches_results_with_file_path(
        self, use_case: SearchTextUseCase
    ) -> None:
        """Test that results are enriched with file paths."""
        request = SearchTextRequest(query="TODO")
        response = await use_case.execute(request)

        assert response.results[0].file_path == "src/parser.py"
        assert response.results[0].source_line == 42
        assert response.results[0].repository_name == "test-repo"
        assert response.results[0].commit_hash == "abc123"


class TestSearchTextGlobalScope:
    """Tests for global search (scope=latest, no repository_id)."""

    @pytest.fixture
    def repository_repo(self) -> InMemoryRepositoryRepository:
        """Create repos with default branches."""
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
        """Create commits on default branches for two repos."""
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
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        """Create files linked to commits for two repos."""
        repo = InMemoryFileRepository(commit_repo=commit_repo)
        f1 = await repo.save(
            File(
                repository_id=1,
                path="src/app.py",
                content_hash="h1",
                size_bytes=100,
                language="python",
            )
        )
        f2 = await repo.save(
            File(
                repository_id=2,
                path="src/main.rs",
                content_hash="h2",
                size_bytes=200,
                language="rust",
            )
        )
        assert f1.id is not None and f2.id is not None
        await repo.link_file_to_commit(f1.id, commit_id=1)
        await repo.link_file_to_commit(f2.id, commit_id=2)
        return repo

    @pytest.fixture
    async def text_content_repo(self) -> InMemoryTextContentRepository:
        """Create text content across two repos."""
        repo = InMemoryTextContentRepository()
        await repo.save(
            TextContent(
                repository_id=1,
                commit_id=None,
                source_type="comment",
                content="TODO: fix parsing logic",
                source_file_id=1,
                source_line=10,
                source_end_line=10,
                language="python",
                content_type="single_line_comment",
            )
        )
        await repo.save(
            TextContent(
                repository_id=2,
                commit_id=None,
                source_type="comment",
                content="TODO: implement handler",
                source_file_id=2,
                source_line=20,
                source_end_line=20,
                language="rust",
                content_type="single_line_comment",
            )
        )
        return repo

    @pytest.fixture
    def text_search(
        self,
        text_content_repo: InMemoryTextContentRepository,
        file_repo: InMemoryFileRepository,
    ) -> FakeTextSearch:
        """Create fake text search with file_repo for scope filtering."""
        return FakeTextSearch(text_content_repo, file_repo=file_repo)

    @pytest.fixture
    def use_case(
        self,
        text_search: FakeTextSearch,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
    ) -> SearchTextUseCase:
        return SearchTextUseCase(
            text_search=text_search,
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )

    @pytest.mark.asyncio
    async def test_global_search_returns_results_from_multiple_repos(
        self, use_case: SearchTextUseCase
    ) -> None:
        """Global search (no repo_id, scope=latest) returns results from all repos."""
        request = SearchTextRequest(query="TODO", scope="latest")
        response = await use_case.execute(request)

        assert response.total == 2
        repo_names = {r.repository_name for r in response.results}
        assert repo_names == {"repo-a", "repo-b"}

    @pytest.mark.asyncio
    async def test_scope_ignored_when_repository_id_set(
        self, use_case: SearchTextUseCase
    ) -> None:
        """When repository_id is set, scope is ignored - only that repo's results."""
        request = SearchTextRequest(query="TODO", repository_id=1, scope="latest")
        response = await use_case.execute(request)

        assert response.total == 1
        assert response.results[0].repository_name == "repo-a"

    @pytest.mark.asyncio
    async def test_scope_defaults_to_latest(self, use_case: SearchTextUseCase) -> None:
        """scope defaults to 'latest' when not specified."""
        request = SearchTextRequest(query="TODO")
        response = await use_case.execute(request)

        # Should still find results (default scope=latest is applied)
        assert response.total == 2
