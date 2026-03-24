"""Tests for SearchTextUseCase using dependency injection."""

from datetime import UTC, datetime

import pytest

from inxr2.application.use_cases.search import SearchTextRequest, SearchTextUseCase
from inxr2.domain.entities import Commit, File, Reference, Repository, TextContent
from inxr2.domain.value_objects import CommitHash
from inxr2.domain.value_objects.reference_type import ReferenceType
from tests.fixtures.test_doubles import (
    FakeTextSearch,
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryReferenceRepository,
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
        # Use actual commit IDs from the commit_repo fixture
        commits_by_repo: dict[int, int] = {}
        for c in commit_repo._commits.values():
            assert c.id is not None
            commits_by_repo[c.repository_id] = c.id
        await repo.link_file_to_commit(f1.id, commit_id=commits_by_repo[1])
        await repo.link_file_to_commit(f2.id, commit_id=commits_by_repo[2])
        # Store file IDs for text_content_repo to reference
        repo._test_file_ids = (f1.id, f2.id)  # type: ignore[attr-defined]
        return repo

    @pytest.fixture
    async def text_content_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemoryTextContentRepository:
        """Create text content across two repos."""
        f1_id, f2_id = file_repo._test_file_ids  # type: ignore[attr-defined]
        repo = InMemoryTextContentRepository()
        await repo.save(
            TextContent(
                repository_id=1,
                commit_id=None,
                source_type="comment",
                content="TODO: fix parsing logic",
                source_file_id=f1_id,
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
                source_file_id=f2_id,
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


class TestSearchTextWithReferences:
    """Tests for reference search integration in SearchTextUseCase."""

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
    async def file_repo(
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        """Create a file repository with test data."""
        repo = InMemoryFileRepository(commit_repo=commit_repo)
        f1 = await repo.save(
            File(
                repository_id=1,
                path="src/parser.py",
                content_hash="hash1",
                size_bytes=1000,
                language="python",
            )
        )
        f2 = await repo.save(
            File(
                repository_id=1,
                path="src/utils.py",
                content_hash="hash2",
                size_bytes=500,
                language="python",
            )
        )
        assert f1.id is not None and f2.id is not None
        commits_by_repo: dict[int, int] = {}
        for c in commit_repo._commits.values():
            assert c.id is not None
            commits_by_repo[c.repository_id] = c.id
        await repo.link_file_to_commit(f1.id, commit_id=commits_by_repo[1])
        await repo.link_file_to_commit(f2.id, commit_id=commits_by_repo[1])
        repo._test_file_ids = (f1.id, f2.id)  # type: ignore[attr-defined]
        return repo

    @pytest.fixture
    async def reference_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemoryReferenceRepository:
        """Create a reference repository with test data."""
        f1_id, f2_id = file_repo._test_file_ids  # type: ignore[attr-defined]
        repo = InMemoryReferenceRepository(file_repo=file_repo)
        await repo.save(
            Reference(
                repository_id=1,
                source_file_id=f1_id,
                source_line=10,
                source_column=4,
                source_end_column=15,
                reference_text="processFile",
                reference_type=ReferenceType.CALL,
            )
        )
        await repo.save(
            Reference(
                repository_id=1,
                source_file_id=f2_id,
                source_line=25,
                source_column=0,
                source_end_column=11,
                reference_text="processFile",
                reference_type=ReferenceType.IMPORT,
            )
        )
        await repo.save(
            Reference(
                repository_id=1,
                source_file_id=f1_id,
                source_line=15,
                source_column=8,
                source_end_column=19,
                reference_text="parseConfig",
                reference_type=ReferenceType.CALL,
            )
        )
        return repo

    @pytest.fixture
    async def text_content_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemoryTextContentRepository:
        """Create a text content repository with test data."""
        f1_id, _f2_id = file_repo._test_file_ids  # type: ignore[attr-defined]
        repo = InMemoryTextContentRepository()
        await repo.save(
            TextContent(
                id=None,
                repository_id=1,
                commit_id=1,
                source_type="comment",
                source_file_id=f1_id,
                source_line=42,
                source_end_line=42,
                content="TODO: refactor processFile function",
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
        reference_repo: InMemoryReferenceRepository,
    ) -> SearchTextUseCase:
        """Create the use case with reference repo."""
        return SearchTextUseCase(
            text_search=text_search,
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
            reference_repo=reference_repo,
        )

    @pytest.mark.asyncio
    async def test_reference_only_search_finds_matching_references(
        self, use_case: SearchTextUseCase
    ) -> None:
        """Searching with source_types=['reference'] only returns references."""
        request = SearchTextRequest(
            query="processFile", source_types=["reference"], repository_id=1
        )
        response = await use_case.execute(request)

        assert response.total == 2
        assert len(response.results) == 2
        assert all(r.source_type == "reference" for r in response.results)
        assert all(r.content == "processFile" for r in response.results)

    @pytest.mark.asyncio
    async def test_reference_results_have_correct_metadata(
        self, use_case: SearchTextUseCase
    ) -> None:
        """Reference results include correct file paths and repo names."""
        request = SearchTextRequest(
            query="processFile", source_types=["reference"], repository_id=1
        )
        response = await use_case.execute(request)

        file_paths = {r.file_path for r in response.results}
        assert file_paths == {"src/parser.py", "src/utils.py"}
        assert all(r.repository_name == "test-repo" for r in response.results)
        assert all(r.language == "python" for r in response.results)

    @pytest.mark.asyncio
    async def test_reference_results_include_reference_type_as_content_type(
        self, use_case: SearchTextUseCase
    ) -> None:
        """Reference results have reference_type in content_type field."""
        request = SearchTextRequest(
            query="processFile", source_types=["reference"], repository_id=1
        )
        response = await use_case.execute(request)

        content_types = {r.content_type for r in response.results}
        assert content_types == {"call", "import"}

    @pytest.mark.asyncio
    async def test_mixed_search_returns_both_text_and_references(
        self, use_case: SearchTextUseCase
    ) -> None:
        """Searching with reference + comment returns both types."""
        request = SearchTextRequest(
            query="processFile",
            source_types=["comment", "reference"],
            repository_id=1,
        )
        response = await use_case.execute(request)

        source_types = {r.source_type for r in response.results}
        assert "reference" in source_types
        assert "comment" in source_types

    @pytest.mark.asyncio
    async def test_mixed_search_pagination_driven_by_text_total(
        self, use_case: SearchTextUseCase
    ) -> None:
        """In mixed mode, total count is from text search (not references)."""
        request = SearchTextRequest(
            query="processFile",
            source_types=["comment", "reference"],
            repository_id=1,
        )
        response = await use_case.execute(request)

        # Total should be text total (1 comment), not ref total
        assert response.total == 1

    @pytest.mark.asyncio
    async def test_backward_compatibility_without_reference_repo(
        self,
        text_search: FakeTextSearch,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
    ) -> None:
        """Use case works without reference_repo (backward compatible)."""
        use_case = SearchTextUseCase(
            text_search=text_search,
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )
        request = SearchTextRequest(
            query="processFile",
            source_types=["reference"],
        )
        response = await use_case.execute(request)

        # No reference repo means no results (reference-only search)
        assert response.total == 0
        assert len(response.results) == 0

    @pytest.mark.asyncio
    async def test_reference_search_substring_matching(
        self, use_case: SearchTextUseCase
    ) -> None:
        """Reference search uses substring matching (like ILIKE)."""
        request = SearchTextRequest(
            query="process", source_types=["reference"], repository_id=1
        )
        response = await use_case.execute(request)

        # Should match "processFile" via substring
        assert response.total == 2
        assert all(r.content == "processFile" for r in response.results)

    @pytest.mark.asyncio
    async def test_commit_hash_scopes_reference_results(
        self,
        use_case: SearchTextUseCase,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> None:
        """Regression: references from files not at the specified commit are excluded.

        Before the fix, commit_id was never passed to reference_repo.search_by_text,
        so reference results ignored the commit filter entirely.
        """
        # Add a second commit and a file only present at that commit
        commit2 = await commit_repo.save(
            Commit(
                id=None,
                repository_id=1,
                commit_hash=CommitHash("def456" + "0" * 34),
                author_date=datetime(2024, 2, 1, tzinfo=UTC),
                commit_date=datetime(2024, 2, 1, tzinfo=UTC),
            )
        )
        assert commit2.id is not None
        future_file = await file_repo.save(
            File(
                repository_id=1,
                path="mcp-server/src/server.py",
                content_hash="future_hash",
                size_bytes=200,
                language="python",
            )
        )
        assert future_file.id is not None
        await file_repo.link_file_to_commit(future_file.id, commit_id=commit2.id)

        # Add a reference in the future file
        ref_repo: InMemoryReferenceRepository = use_case._reference_repo  # type: ignore[assignment]
        await ref_repo.save(
            Reference(
                repository_id=1,
                source_file_id=future_file.id,
                source_line=1,
                source_column=0,
                source_end_column=3,
                reference_text="mcp",
                reference_type=ReferenceType.IMPORT,
            )
        )

        # Search at commit1 ("abc123") — the future file should be excluded
        request = SearchTextRequest(
            query="mcp",
            source_types=["reference"],
            repository_id=1,
            commit_hash="abc123",
        )
        response = await use_case.execute(request)

        assert response.total == 0
        assert len(response.results) == 0


class TestSearchTextExtensionFilter:
    """Tests for text search with extension filtering."""

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
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        repo = InMemoryFileRepository(commit_repo=commit_repo)
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
        assert f1.id is not None and f2.id is not None
        commit_id = list(commit_repo._commits.values())[0].id
        assert commit_id is not None
        await repo.link_file_to_commit(f1.id, commit_id=commit_id)
        await repo.link_file_to_commit(f2.id, commit_id=commit_id)
        repo._test_file_ids = (f1.id, f2.id)  # type: ignore[attr-defined]
        return repo

    @pytest.fixture
    async def text_content_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemoryTextContentRepository:
        f1_id, f2_id = file_repo._test_file_ids  # type: ignore[attr-defined]
        repo = InMemoryTextContentRepository()
        await repo.save(
            TextContent(
                repository_id=1,
                commit_id=None,
                source_type="comment",
                content="TODO: fix python logic",
                source_file_id=f1_id,
                source_line=10,
                source_end_line=10,
                language="python",
                content_type="single_line_comment",
            )
        )
        await repo.save(
            TextContent(
                repository_id=1,
                commit_id=None,
                source_type="comment",
                content="TODO: fix typescript handler",
                source_file_id=f2_id,
                source_line=20,
                source_end_line=20,
                language="typescript",
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
    async def test_extension_filter_single(self, use_case: SearchTextUseCase) -> None:
        """Extension filter returns only text from matching file extensions."""
        request = SearchTextRequest(query="TODO", extensions=[".py"])
        response = await use_case.execute(request)

        assert response.total == 1
        assert "python" in response.results[0].content

    @pytest.mark.asyncio
    async def test_extension_filter_multiple(self, use_case: SearchTextUseCase) -> None:
        """Multiple extensions returns union of matches."""
        request = SearchTextRequest(query="TODO", extensions=[".py", ".ts"])
        response = await use_case.execute(request)

        assert response.total == 2

    @pytest.mark.asyncio
    async def test_extension_filter_no_match(self, use_case: SearchTextUseCase) -> None:
        """Extension filter with no match returns empty."""
        request = SearchTextRequest(query="TODO", extensions=[".rs"])
        response = await use_case.execute(request)

        assert response.total == 0

    @pytest.mark.asyncio
    async def test_no_extension_filter_returns_all(
        self, use_case: SearchTextUseCase
    ) -> None:
        """No extension filter returns all matching text."""
        request = SearchTextRequest(query="TODO")
        response = await use_case.execute(request)

        assert response.total == 2


class TestSearchTextReferenceExtensionFilter:
    """Tests for extension filtering on reference results."""

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
                commit_hash=CommitHash("ref111"),
                author_date=datetime(2024, 1, 1, tzinfo=UTC),
                commit_date=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        assert c.id is not None
        await repo.link_commit_to_branch(1, c.id, "main")
        return repo

    @pytest.fixture
    async def file_repo(
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        repo = InMemoryFileRepository(commit_repo=commit_repo)
        f1 = await repo.save(
            File(
                repository_id=1,
                path="src/parser.py",
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
        assert f1.id is not None and f2.id is not None
        commit_id = list(commit_repo._commits.values())[0].id
        assert commit_id is not None
        await repo.link_file_to_commit(f1.id, commit_id=commit_id)
        await repo.link_file_to_commit(f2.id, commit_id=commit_id)
        repo._test_file_ids = (f1.id, f2.id)  # type: ignore[attr-defined]
        return repo

    @pytest.fixture
    async def reference_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemoryReferenceRepository:
        f1_id, f2_id = file_repo._test_file_ids  # type: ignore[attr-defined]
        repo = InMemoryReferenceRepository(file_repo=file_repo)
        await repo.save(
            Reference(
                repository_id=1,
                source_file_id=f1_id,
                source_line=10,
                source_column=4,
                source_end_column=15,
                reference_text="Console",
                reference_type=ReferenceType.CALL,
            )
        )
        await repo.save(
            Reference(
                repository_id=1,
                source_file_id=f2_id,
                source_line=25,
                source_column=0,
                source_end_column=7,
                reference_text="Console",
                reference_type=ReferenceType.USAGE,
            )
        )
        return repo

    @pytest.fixture
    def use_case(
        self,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        reference_repo: InMemoryReferenceRepository,
    ) -> SearchTextUseCase:
        text_search = FakeTextSearch(
            InMemoryTextContentRepository(), file_repo=file_repo
        )
        return SearchTextUseCase(
            text_search=text_search,
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
            reference_repo=reference_repo,
        )

    @pytest.mark.asyncio
    async def test_reference_extension_filter(
        self, use_case: SearchTextUseCase
    ) -> None:
        """Extension filter applies to reference results."""
        request = SearchTextRequest(
            query="Console",
            source_types=["reference"],
            extensions=[".ts"],
        )
        response = await use_case.execute(request)

        assert len(response.results) == 1
        assert response.results[0].source_type == "reference"
        assert response.results[0].file_path == "src/main.ts"

    @pytest.mark.asyncio
    async def test_reference_no_extension_filter_returns_all(
        self, use_case: SearchTextUseCase
    ) -> None:
        """No extension filter returns all reference results."""
        request = SearchTextRequest(
            query="Console",
            source_types=["reference"],
        )
        response = await use_case.execute(request)

        assert len(response.results) == 2

    @pytest.mark.asyncio
    async def test_reference_extension_filter_excludes_py(
        self, use_case: SearchTextUseCase
    ) -> None:
        """Extension filter excluding .py returns only non-.py references."""
        request = SearchTextRequest(
            query="Console",
            source_types=["reference"],
            extensions=[".ts"],
        )
        response = await use_case.execute(request)

        for r in response.results:
            assert r.file_path is not None
            assert r.file_path.endswith(".ts")


class TestSearchTextDeduplication:
    """Regression tests for search result deduplication (#400).

    Code file body indexing (#395) creates plain_text rows covering all
    lines of a file, including lines already stored as comment/docstring
    rows. Two rows for the same file+line both match the same search term,
    producing duplicate results.

    Two dedup passes are required:
    1. DB layer (postgres_text_search.py): catches rows with the same raw
       source_line (e.g. comment at line 4 and plain_text chunk at line 4).
    2. Use case layer (search_text_use_case.py): catches rows where a
       multi-line plain_text chunk starting at line N refines to the same
       line as a shorter row at line N+k (e.g. docstring at line 8 and a
       plain_text chunk starting at line 7 that contains the match at line 8).
    """

    @pytest.fixture
    def repository_repo(self) -> InMemoryRepositoryRepository:
        repo = InMemoryRepositoryRepository()
        repo.add(
            Repository(
                id=1,
                name="travelbuddy",
                url="/repos/travelbuddy",
                description="Travel app",
            )
        )
        return repo

    @pytest.fixture
    async def commit_repo(self) -> InMemoryCommitRepository:
        from datetime import UTC, datetime

        from inxr2.domain.value_objects import CommitHash

        repo = InMemoryCommitRepository()
        commit = await repo.save(
            Commit(
                id=None,
                repository_id=1,
                commit_hash=CommitHash("a" * 40),
                author_date=datetime(2024, 1, 1, tzinfo=UTC),
                commit_date=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        assert commit.id is not None
        await repo.link_commit_to_branch(1, commit.id, "main")
        return repo

    @pytest.fixture
    async def file_repo(self) -> InMemoryFileRepository:
        repo = InMemoryFileRepository()
        await repo.save(
            File(
                repository_id=1,
                path="src/Logger.swift",
                content_hash="b" * 40,
                size_bytes=500,
                language="swift",
            )
        )
        return repo

    @pytest.mark.asyncio
    async def test_dedup_same_raw_source_line(
        self,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
    ) -> None:
        """Regression test for GH #400 (DB-layer case): a comment row and a
        plain_text row both at source_line=4 must produce only one result."""
        text_repo = InMemoryTextContentRepository()
        await text_repo.save(
            TextContent(
                repository_id=1,
                commit_id=None,
                source_type="comment",
                source_file_id=1,
                source_line=4,
                source_end_line=4,
                content="MARK: - TraceLogger",
                language="swift",
                content_type="single_line_comment",
            )
        )
        await text_repo.save(
            TextContent(
                repository_id=1,
                commit_id=None,
                source_type="file_content",
                source_file_id=1,
                source_line=4,
                source_end_line=4,
                content="// MARK: - TraceLogger",
                language=None,
                content_type="plain_text",
            )
        )
        use_case = SearchTextUseCase(
            text_search=FakeTextSearch(text_repo, file_repo=file_repo),
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )

        response = await use_case.execute(
            SearchTextRequest(query="TraceLogger", repository_id=1)
        )

        assert response.total == 1, (
            "Expected 1 deduplicated result for same file+line, "
            f"got {response.total}"
        )
        assert len(response.results) == 1

    @pytest.mark.asyncio
    async def test_dedup_multiline_chunk_refines_to_same_line(
        self,
        repository_repo: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
    ) -> None:
        """Regression test for GH #400 (use-case-layer case): a docstring at
        line 8 and a multi-line plain_text chunk starting at line 7 (where the
        match term appears at line 8, i.e. offset 1) both refine to source_line=8
        and must produce only one result after use-case dedup."""
        text_repo = InMemoryTextContentRepository()
        # Docstring at line 8 (single line)
        await text_repo.save(
            TextContent(
                repository_id=1,
                commit_id=None,
                source_type="docstring",
                source_file_id=1,
                source_line=8,
                source_end_line=8,
                content="Accepts the ModelContainer created by TravelBuddyApp",
                language="swift",
                content_type="docstring",
            )
        )
        # Multi-line plain_text chunk starting at line 7, containing the
        # match term at line 8 (offset 1 within the chunk).
        await text_repo.save(
            TextContent(
                repository_id=1,
                commit_id=None,
                source_type="file_content",
                source_file_id=1,
                source_line=7,
                source_end_line=13,
                content=(
                    "/// Persists UserProfile to the shared store.\n"
                    "/// Accepts the ModelContainer created by TravelBuddyApp\n"
                    "final class SwiftDataAdapter {}"
                ),
                language=None,
                content_type="plain_text",
            )
        )
        use_case = SearchTextUseCase(
            text_search=FakeTextSearch(text_repo, file_repo=file_repo),
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )

        response = await use_case.execute(
            SearchTextRequest(query="TravelBuddyApp", repository_id=1)
        )

        assert response.total == 1, (
            "Expected 1 deduplicated result after multi-line chunk refinement, "
            f"got {response.total}"
        )
        assert len(response.results) == 1
        assert response.results[0].source_line == 8

    @pytest.mark.asyncio
    async def test_dedup_does_not_collapse_same_path_different_repos(
        self,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
    ) -> None:
        """Cross-repo dedup key includes repository_id. Two repos that both
        have a match at the same file path and line must each produce a result."""
        repository_repo = InMemoryRepositoryRepository()
        repository_repo.add(
            Repository(id=1, name="repo-a", url="/repos/a", description="")
        )
        repository_repo.add(
            Repository(id=2, name="repo-b", url="/repos/b", description="")
        )
        # Add a second file in repo 2 at the same path
        await file_repo.save(
            File(
                repository_id=2,
                path="src/Logger.swift",  # same path as file_id=1 in repo 1
                content_hash="c" * 40,
                size_bytes=500,
                language="swift",
            )
        )

        text_repo = InMemoryTextContentRepository()
        await text_repo.save(
            TextContent(
                repository_id=1,
                commit_id=None,
                source_type="comment",
                source_file_id=1,
                source_line=4,
                source_end_line=4,
                content="// MARK: - TraceLogger",
                language="swift",
                content_type="single_line_comment",
            )
        )
        await text_repo.save(
            TextContent(
                repository_id=2,
                commit_id=None,
                source_type="comment",
                source_file_id=2,
                source_line=4,
                source_end_line=4,
                content="// MARK: - TraceLogger",
                language="swift",
                content_type="single_line_comment",
            )
        )
        use_case = SearchTextUseCase(
            text_search=FakeTextSearch(text_repo, file_repo=file_repo),
            repository_repo=repository_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )

        response = await use_case.execute(
            SearchTextRequest(query="TraceLogger")  # global search, no repository_id
        )

        assert len(response.results) == 2, (
            "Expected 2 results (one per repo), dedup must not collapse "
            f"cross-repo matches at the same path:line, got {len(response.results)}"
        )
        repo_ids = {r.repository_id for r in response.results}
        assert repo_ids == {1, 2}
