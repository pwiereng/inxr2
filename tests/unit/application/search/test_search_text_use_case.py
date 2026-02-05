"""Tests for SearchTextUseCase using dependency injection."""

from datetime import datetime, timezone

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
                author_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                commit_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
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
                id=None,
                repository_id=1,
                commit_id=1,
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
                content_type="inline_comment",
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
    async def test_search_finds_matching_text(self, use_case: SearchTextUseCase) -> None:
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
