"""Tests for DefaultIndexingOrchestrator implementation."""

from datetime import UTC
from pathlib import Path

import pytest

from inxr2.application.ports.services import ChangedFiles, CommitInfo
from inxr2.application.use_cases.indexing.default_orchestrator import (
    DefaultIndexingOrchestrator,
)
from inxr2.application.use_cases.indexing.orchestrator import (
    IndexRepositoryRequest,
)
from tests.fixtures.test_doubles import (
    FakeGitService,
    FakePlaintextParser,
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryIndexStatusRepository,
    InMemoryReferenceRepository,
    InMemoryRepositoryRepository,
    InMemorySymbolRepository,
    InMemoryTextContentRepository,
)


class FakeParserService:
    """Fake parser service for testing without real parsing."""

    def __init__(self) -> None:
        """Initialize fake parser service."""
        self.comments_to_return: list[dict] = []

    def supports_language(self, language: str) -> bool:
        """Check if language is supported."""
        return language in ["python", "typescript", "java"]

    async def parse_file(
        self, content: str, language: str, file_path: str
    ) -> tuple[list[dict], list[dict]]:
        """
        Parse file and return symbols and references as dicts.

        Note: Signature matches TreeSitterService.parse_file() which returns
        dicts, not Symbol objects.
        """
        # Return fake symbols as dicts (matching real TreeSitterService)
        file_name = Path(file_path).name
        symbols = [
            {
                "name": f"function_in_{file_name}",
                "kind": "function",
                "start_line": 1,
                "start_column": 0,
                "end_line": 5,
                "end_column": 0,
                "parent_symbol_id": None,
                "signature": None,
                "metadata": {},
            }
        ]
        # Return fake references (using "text" and "type" like real parsers)
        references = [
            {
                "text": "print",
                "type": "call",
                "source_line": 2,
                "source_column": 0,
            }
        ]
        return symbols, references

    async def extract_comments(
        self, content: str, language: str, file_path: str
    ) -> list[dict]:
        """
        Extract comments and docstrings from a file.

        Returns list of dicts with keys:
        - content: The comment text
        - content_type: Type (single_line_comment, block_comment, docstring)
        - source_line: Starting line number
        - source_end_line: Ending line number (optional)
        """
        # Return predefined comments if set, otherwise return default
        if self.comments_to_return:
            return self.comments_to_return

        # Default: return one fake comment per file
        file_name = Path(file_path).name
        return [
            {
                "content": f"This is a comment in {file_name}",
                "content_type": "single_line_comment",
                "source_line": 1,
            }
        ]


@pytest.fixture
def repository_adapter() -> InMemoryRepositoryRepository:
    """Create in-memory repository adapter."""
    return InMemoryRepositoryRepository()


@pytest.fixture
def commit_repo() -> InMemoryCommitRepository:
    """Create in-memory commit repository."""
    return InMemoryCommitRepository()


@pytest.fixture
def file_repo() -> InMemoryFileRepository:
    """Create in-memory file repository."""
    return InMemoryFileRepository()


@pytest.fixture
def symbol_repo() -> InMemorySymbolRepository:
    """Create in-memory symbol repository."""
    return InMemorySymbolRepository()


@pytest.fixture
def reference_repo(
    symbol_repo: InMemorySymbolRepository,
) -> InMemoryReferenceRepository:
    """Create in-memory reference repository."""
    return InMemoryReferenceRepository(symbol_repo=symbol_repo)


@pytest.fixture
def index_status_repo() -> InMemoryIndexStatusRepository:
    """Create in-memory index status repository."""
    return InMemoryIndexStatusRepository()


@pytest.fixture
def text_content_repo() -> InMemoryTextContentRepository:
    """Create in-memory text content repository."""
    return InMemoryTextContentRepository()


@pytest.fixture
def git_service() -> FakeGitService:
    """Create fake git service."""
    return FakeGitService()


@pytest.fixture
def parser_service() -> FakeParserService:
    """Create fake parser service."""
    return FakeParserService()


@pytest.fixture
def orchestrator(
    repository_adapter: InMemoryRepositoryRepository,
    commit_repo: InMemoryCommitRepository,
    file_repo: InMemoryFileRepository,
    symbol_repo: InMemorySymbolRepository,
    reference_repo: InMemoryReferenceRepository,
    index_status_repo: InMemoryIndexStatusRepository,
    text_content_repo: InMemoryTextContentRepository,
    git_service: FakeGitService,
    parser_service: FakeParserService,
) -> DefaultIndexingOrchestrator:
    """Create orchestrator with all dependencies."""
    return DefaultIndexingOrchestrator(
        repository_repo=repository_adapter,
        commit_repo=commit_repo,
        file_repo=file_repo,
        symbol_repo=symbol_repo,
        reference_repo=reference_repo,
        index_status_repo=index_status_repo,
        text_content_repo=text_content_repo,
        git_service=git_service,
        parser_service=parser_service,
        plaintext_parser=FakePlaintextParser(),
    )


class TestDefaultIndexingOrchestrator:
    """Tests for DefaultIndexingOrchestrator."""

    @pytest.mark.asyncio
    async def test_index_repository_full_creates_repository(
        self,
        orchestrator: DefaultIndexingOrchestrator,
        repository_adapter: InMemoryRepositoryRepository,
    ) -> None:
        """Test that full indexing creates repository in database."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert
        assert response.repository_name == "test-repo"
        # Verify repository was created
        repos = await repository_adapter.list_all()
        assert len(repos) == 1
        assert repos[0].name == "test-repo"

    @pytest.mark.asyncio
    async def test_index_repository_full_indexes_commits(
        self,
        orchestrator: DefaultIndexingOrchestrator,
        commit_repo: InMemoryCommitRepository,
    ) -> None:
        """Test that full indexing creates commit records."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert
        assert response.commits_indexed == 2  # 2 commits in fake git service
        # Verify commits were saved
        commits = await commit_repo.list_by_repository(repository_id=1)
        assert len(commits) >= 2

    @pytest.mark.asyncio
    async def test_index_repository_full_processes_files(
        self,
        orchestrator: DefaultIndexingOrchestrator,
        file_repo: InMemoryFileRepository,
    ) -> None:
        """Test that full indexing processes files in commits."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert
        assert response.files_processed > 0
        # Verify files were saved
        all_files = list(file_repo._files.values())
        assert len(all_files) > 0

    @pytest.mark.asyncio
    async def test_index_repository_full_extracts_symbols(
        self,
        orchestrator: DefaultIndexingOrchestrator,
        symbol_repo: InMemorySymbolRepository,
    ) -> None:
        """Test that full indexing extracts symbols from files."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert
        assert response.symbols_found > 0
        # Verify symbols were saved
        all_symbols = list(symbol_repo._symbols.values())
        assert len(all_symbols) > 0

    @pytest.mark.asyncio
    async def test_index_repository_with_max_history_limit(
        self,
        orchestrator: DefaultIndexingOrchestrator,
        commit_repo: InMemoryCommitRepository,
    ) -> None:
        """Test that max_history limits number of commits indexed."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            max_history=1,  # Only index 1 commit
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert
        assert response.commits_indexed == 1  # Limited to 1

    @pytest.mark.asyncio
    async def test_second_index_only_processes_new_commits(
        self,
        orchestrator: DefaultIndexingOrchestrator,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
    ) -> None:
        """Test that second index call only processes new commits (incremental behavior)."""
        # Arrange - first do an initial index with limited history
        first_request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            max_history=1,  # Only index first commit
        )
        await orchestrator.index_repository(first_request)

        # Get repository ID
        repo = await repository_adapter.find_by_name("test-repo")
        assert repo is not None
        assert repo.id is not None

        # Now do another index - should automatically be incremental
        second_request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_repository(second_request)

        # Assert
        # Should only index the second commit (incremental behavior)
        assert response.commits_indexed == 1

    @pytest.mark.asyncio
    async def test_index_repository_calculates_statistics(
        self, orchestrator: DefaultIndexingOrchestrator
    ) -> None:
        """Test that response contains accurate statistics."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert - verify statistics are populated
        assert response.repository_id > 0
        assert response.commits_indexed > 0
        assert response.files_total > 0
        assert response.files_processed > 0
        assert response.files_skipped >= 0
        assert response.files_failed >= 0
        assert response.symbols_found > 0
        assert response.references_found > 0
        assert response.elapsed_seconds > 0
        assert isinstance(response.errors, list)

    @pytest.mark.asyncio
    async def test_index_repository_updates_index_status(
        self,
        orchestrator: DefaultIndexingOrchestrator,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
    ) -> None:
        """Test that indexing updates index status."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        await orchestrator.index_repository(request)

        # Assert - verify index status was created
        all_statuses = list(index_status_repo._statuses.values())
        assert len(all_statuses) > 0
        status = all_statuses[0]
        assert status.indexing_status == "completed"


class TestGitServiceIntegration:
    """Tests for git service integration - regression tests for API compatibility."""

    @pytest.mark.asyncio
    async def test_orchestrator_calls_list_commits_not_get_commits(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """
        Regression test: Orchestrator must call list_commits, not get_commits.

        This test verifies the fix for the bug where the orchestrator was
        calling git_service.get_commits() which doesn't exist - the correct
        method is git_service.list_commits().
        """

        # Arrange - create a spy git service that tracks method calls
        class SpyGitService(FakeGitService):
            def __init__(self) -> None:
                super().__init__()
                self.list_commits_called = False
                self.list_commits_args: dict = {}

            def list_commits(
                self,
                repo_path: Path,
                branch: str,
                max_count: int | None = None,
                since_days: int | None = None,
            ) -> list[CommitInfo]:
                self.list_commits_called = True
                self.list_commits_args = {
                    "repo_path": repo_path,
                    "branch": branch,
                    "max_count": max_count,
                    "since_days": since_days,
                }
                return super().list_commits(repo_path, branch, max_count, since_days)

        spy_git = SpyGitService()
        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=spy_git,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            max_history=100,
            since_days=15,
        )

        # Act
        await orchestrator.index_repository(request)

        # Assert - verify list_commits was called with correct arguments
        assert spy_git.list_commits_called, "list_commits should be called"
        assert spy_git.list_commits_args["branch"] == "main"
        assert spy_git.list_commits_args["max_count"] == 100
        assert spy_git.list_commits_args["since_days"] == 15

    @pytest.mark.asyncio
    async def test_orchestrator_passes_since_days_to_git_service(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """Test that since_days filter is passed to git service correctly."""

        class SpyGitService(FakeGitService):
            def __init__(self) -> None:
                super().__init__()
                self.since_days_received: int | None = None

            def list_commits(
                self,
                repo_path: Path,
                branch: str,
                max_count: int | None = None,
                since_days: int | None = None,
            ) -> list[CommitInfo]:
                self.since_days_received = since_days
                return super().list_commits(repo_path, branch, max_count, since_days)

        spy_git = SpyGitService()
        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=spy_git,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        # Test with since_days=30
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            since_days=30,
        )

        await orchestrator.index_repository(request)

        assert spy_git.since_days_received == 30

    @pytest.mark.asyncio
    async def test_orchestrator_indexes_head_when_no_commits_in_date_range(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """
        Regression test: When since_days filters out all commits, still index HEAD.

        Even if there are no commits in the last N days, we should still
        index the current HEAD state to capture the repository's contents.
        """
        from datetime import datetime

        class EmptyCommitsGitService(FakeGitService):
            """Git service that returns no commits for date filter."""

            def __init__(self) -> None:
                super().__init__()
                self.get_commit_info_called = False

            def list_commits(
                self,
                repo_path: Path,
                branch: str,
                max_count: int | None = None,
                since_days: int | None = None,
            ) -> list[CommitInfo]:
                # Return empty list to simulate no commits in date range
                if since_days is not None:
                    return []
                return super().list_commits(repo_path, branch, max_count, since_days)

            def get_commit_info(self, repo_path: Path, commit_hash: str) -> CommitInfo:
                self.get_commit_info_called = True
                return CommitInfo(
                    hash="def456",
                    short_hash="def456",
                    author_name="Test User",
                    author_email="test@example.com",
                    author_date=datetime(2024, 1, 2, 0, 0, 0),
                    committer_name="Test User",
                    committer_email="test@example.com",
                    commit_date=datetime(2024, 1, 2, 0, 0, 0),
                    message="HEAD commit",
                    parent_hashes=[],
                )

        empty_git = EmptyCommitsGitService()
        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=empty_git,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            since_days=15,  # No commits in last 15 days
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert - should still index HEAD commit
        assert (
            empty_git.get_commit_info_called
        ), "get_commit_info should be called for HEAD"
        assert response.commits_indexed == 1, "HEAD commit should be indexed"
        assert response.files_processed > 0, "HEAD files should be processed"

    @pytest.mark.asyncio
    async def test_orchestrator_calls_list_files_not_get_files_in_commit(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """
        Regression test: Orchestrator must call list_files, not get_files_in_commit.

        This test verifies the fix for the bug where the orchestrator was
        calling git_service.get_files_in_commit() which doesn't exist - the
        correct method is git_service.list_files().
        """

        class SpyGitService(FakeGitService):
            def __init__(self) -> None:
                super().__init__()
                self.list_files_called = False
                self.list_files_args: dict = {}

            def list_files(
                self,
                repo_path: Path,
                commit_hash: str,
                patterns: list[str] | None = None,
            ) -> list[str]:
                self.list_files_called = True
                self.list_files_args = {
                    "repo_path": repo_path,
                    "commit_hash": commit_hash,
                }
                return super().list_files(repo_path, commit_hash, patterns)

        spy_git = SpyGitService()
        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=spy_git,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        await orchestrator.index_repository(request)

        # Assert - verify list_files was called
        assert (
            spy_git.list_files_called
        ), "list_files should be called (not get_files_in_commit)"

    @pytest.mark.asyncio
    async def test_orchestrator_handles_timezone_aware_datetimes(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """
        Regression test: Orchestrator must handle timezone-aware datetimes from GitPython.

        GitPython returns timezone-aware datetime objects for author_date and
        commit_date. The orchestrator must convert these to naive UTC datetimes
        for database storage.
        """
        from datetime import datetime

        class TimezoneAwareGitService(FakeGitService):
            def __init__(self) -> None:
                super().__init__()
                # Override commits with timezone-aware datetimes (like GitPython returns)
                self.commits = [
                    CommitInfo(
                        hash="tz123",
                        short_hash="tz123",
                        author_name="Test User",
                        author_email="test@example.com",
                        author_date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
                        committer_name="Test User",
                        committer_email="test@example.com",
                        commit_date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
                        message="Commit with timezone",
                        parent_hashes=[],
                    ),
                ]
                self.files_in_commit = {
                    "tz123": ["src/main.py"],
                }

        tz_git = TimezoneAwareGitService()
        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=tz_git,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act - should not raise "can't subtract offset-naive and offset-aware datetimes"
        response = await orchestrator.index_repository(request)

        # Assert - indexing succeeded
        assert response.commits_indexed == 1
        # Verify commit was saved with naive datetime
        commits = await commit_repo.list_by_repository(repository_id=1)
        assert len(commits) >= 1
        saved_commit = commits[0]
        assert saved_commit.author_date.tzinfo is None, "author_date should be naive"
        assert saved_commit.commit_date.tzinfo is None, "commit_date should be naive"

    @pytest.mark.asyncio
    async def test_orchestrator_handles_dict_symbols_from_parser(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        git_service: FakeGitService,
    ) -> None:
        """
        Regression test: Orchestrator must handle dict symbols from TreeSitterService.

        The TreeSitterService.parse_file() returns tuple[list[dict], list[dict]],
        not tuple[list[Symbol], list[dict]]. The orchestrator must convert these
        dicts to Symbol objects.
        """

        class DictReturningParserService:
            """Parser that returns dicts (like real TreeSitterService)."""

            def supports_language(self, language: str) -> bool:
                return language == "python"

            async def parse_file(
                self, content: str, language: str, file_path: str
            ) -> tuple[list[dict], list[dict]]:
                # Return dicts, not Symbol objects
                symbols = [
                    {
                        "name": "test_function",
                        "kind": "function",
                        "start_line": 1,
                        "start_column": 0,
                        "end_line": 5,
                        "end_column": 0,
                    }
                ]
                references = [
                    {
                        "text": "print",
                        "type": "call",
                        "source_line": 2,
                        "source_column": 0,
                    }
                ]
                return symbols, references

        dict_parser = DictReturningParserService()
        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=git_service,
            parser_service=dict_parser,
            plaintext_parser=FakePlaintextParser(),
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act - should not raise "'dict' object has no attribute 'name'"
        response = await orchestrator.index_repository(request)

        # Assert - symbols were created from dicts
        assert response.symbols_found > 0, "Should have found symbols"
        all_symbols = list(symbol_repo._symbols.values())
        assert len(all_symbols) > 0, "Symbols should be saved"
        assert all_symbols[0].name == "test_function"

    @pytest.mark.asyncio
    async def test_orchestrator_calculates_source_end_column_if_missing(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        git_service: FakeGitService,
    ) -> None:
        """
        Regression test: Orchestrator must calculate source_end_column if not provided.

        Some parsers (like C parser) don't provide source_end_column in reference
        data. The orchestrator should calculate it from source_column + len(reference_text).
        """

        class ParserWithoutEndColumn:
            """Parser that doesn't provide source_end_column (like real C parser)."""

            def supports_language(self, language: str) -> bool:
                return language == "c"

            async def parse_file(
                self, content: str, language: str, file_path: str
            ) -> tuple[list[dict], list[dict]]:
                symbols = [
                    {
                        "name": "main",
                        "kind": "function",
                        "start_line": 1,
                        "start_column": 0,
                        "end_line": 5,
                        "end_column": 0,
                    }
                ]
                # References WITHOUT source_end_column
                # References WITHOUT source_end_column (like real C parser)
                references = [
                    {
                        "text": "printf",  # 6 chars
                        "type": "call",
                        "source_line": 3,
                        "source_column": 4,
                        # source_end_column is NOT provided
                    }
                ]
                return symbols, references

        no_end_parser = ParserWithoutEndColumn()
        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=git_service,
            parser_service=no_end_parser,
            plaintext_parser=FakePlaintextParser(),
        )

        # Update git service to return .c files
        git_service.files_in_commit = {
            "abc123": ["main.c"],
            "def456": ["main.c"],
        }
        # Also update changed_files_in_commit for delta indexing
        git_service.changed_files_in_commit = {
            "abc123": ChangedFiles(added=["main.c"], modified=[], deleted=[]),
            "def456": ChangedFiles(added=[], modified=[], deleted=[]),  # No changes
        }

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["c"],
        )

        # Act - should not raise "'source_end_column'" KeyError
        response = await orchestrator.index_repository(request)

        # Assert - references were created with calculated end column
        assert response.references_found > 0, "Should have found references"
        all_refs = list(reference_repo._references.values())
        assert len(all_refs) > 0, "References should be saved"
        ref = all_refs[0]
        # source_end_column should be calculated: 4 + len("printf") = 10
        assert ref.source_end_column == 10, "source_end_column should be calculated"

    @pytest.mark.asyncio
    async def test_orchestrator_converts_reference_type_string_to_enum(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        git_service: FakeGitService,
    ) -> None:
        """
        Regression test: Orchestrator must convert reference_type string to ReferenceType enum.

        Parsers return reference type as a string (e.g., "call", "usage", "import"),
        but the Reference entity expects a ReferenceType enum. Without conversion,
        the mapper will fail with "'str' object has no attribute 'value'".
        """
        from inxr2.domain.value_objects import ReferenceType

        class ParserWithStringReferenceType:
            """Parser that returns reference type as string (like all real parsers)."""

            def supports_language(self, language: str) -> bool:
                return language == "c"

            async def parse_file(
                self, content: str, language: str, file_path: str
            ) -> tuple[list[dict], list[dict]]:
                symbols = [
                    {
                        "name": "main",
                        "kind": "function",
                        "start_line": 1,
                        "start_column": 0,
                        "end_line": 5,
                        "end_column": 0,
                    }
                ]
                # References with string type (like all real parsers)
                references = [
                    {
                        "text": "printf",
                        "type": "call",  # String, not ReferenceType.CALL
                        "source_line": 3,
                        "source_column": 4,
                    },
                    {
                        "text": "count",
                        "type": "usage",  # String, not ReferenceType.USAGE
                        "source_line": 4,
                        "source_column": 0,
                    },
                ]
                return symbols, references

        string_type_parser = ParserWithStringReferenceType()
        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=git_service,
            parser_service=string_type_parser,
            plaintext_parser=FakePlaintextParser(),
        )

        # Update git service to return .c files
        git_service.files_in_commit = {
            "abc123": ["main.c"],
            "def456": ["main.c"],
        }
        # Also update changed_files_in_commit for delta indexing
        git_service.changed_files_in_commit = {
            "abc123": ChangedFiles(added=["main.c"], modified=[], deleted=[]),
            "def456": ChangedFiles(added=[], modified=[], deleted=[]),  # No changes
        }

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["c"],
        )

        # Act - should not raise "'str' object has no attribute 'value'"
        response = await orchestrator.index_repository(request)

        # Assert - references were created with proper ReferenceType enum
        assert response.references_found > 0, "Should have found references"
        all_refs = list(reference_repo._references.values())
        assert len(all_refs) > 0, "References should be saved"

        # Verify reference_type is ReferenceType enum, not string
        for ref in all_refs:
            assert isinstance(
                ref.reference_type, ReferenceType
            ), f"reference_type should be ReferenceType enum, got {type(ref.reference_type)}"

        # Check specific types were converted correctly
        ref_types = {ref.reference_type for ref in all_refs}
        assert ReferenceType.CALL in ref_types, "Should have CALL reference"
        assert ReferenceType.USAGE in ref_types, "Should have USAGE reference"

    @pytest.mark.asyncio
    async def test_orchestrator_skips_existing_commits_on_reindex(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        git_service: FakeGitService,
        parser_service: FakeParserService,
    ) -> None:
        """
        Regression test: Re-indexing should not fail on duplicate commits.

        When re-running indexing without resetting the database, commits that
        already exist should be skipped (reused) rather than causing a
        UniqueViolation error on the uq_repo_commit_hash constraint.
        """
        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=git_service,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # First indexing run
        response1 = await orchestrator.index_repository(request)
        assert response1.commits_indexed == 2

        # Count commits after first run
        commits_after_first = await commit_repo.list_by_repository(repository_id=1)
        first_commit_count = len(commits_after_first)

        # Second indexing run - should detect HEAD already indexed and return early
        response2 = await orchestrator.index_repository(request)

        # Should report 0 commits because HEAD hasn't changed (incremental detection)
        assert (
            response2.commits_indexed == 0
        ), "Second run should skip indexing when HEAD unchanged"

        # Commits should not be duplicated
        commits_after_second = await commit_repo.list_by_repository(repository_id=1)
        assert (
            len(commits_after_second) == first_commit_count
        ), "Commits should not be duplicated on re-index"


class TestHeadFirstIndexing:
    """Tests for HEAD-first indexing optimization.

    HEAD-first indexing ensures:
    1. HEAD (newest commit) is processed first with ALL files
    2. Older commits use delta indexing (only changed files)

    This guarantees complete file coverage at HEAD for time-travel queries.
    """

    @pytest.mark.asyncio
    async def test_head_first_processes_all_files_at_head(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """
        Test that HEAD commit processes ALL files, not just changed ones.

        With HEAD-first indexing:
        - HEAD (def456): Processes ALL files (main.py, utils.py, new_file.py)
        - Older (abc123): Only processes changed files (main.py, utils.py - added)

        Total: 5 files processed (3 at HEAD + 2 at older commit)
        """

        class TrackingGitService(FakeGitService):
            """Git service that tracks which files are processed."""

            def __init__(self) -> None:
                super().__init__()
                self.files_processed_per_commit: dict[str, list[str]] = {}

            def get_file_content(
                self, repo_path: Path, commit_hash: str, file_path: str
            ) -> str:
                # Track which files were actually processed
                if commit_hash not in self.files_processed_per_commit:
                    self.files_processed_per_commit[commit_hash] = []
                self.files_processed_per_commit[commit_hash].append(file_path)
                return super().get_file_content(repo_path, commit_hash, file_path)

        tracking_git = TrackingGitService()
        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=tracking_git,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert - HEAD (def456) processes ALL files
        assert sorted(tracking_git.files_processed_per_commit.get("def456", [])) == [
            "src/main.py",
            "src/new_file.py",
            "src/utils.py",
        ], "HEAD commit should process ALL files"

        # Older commit (abc123) processes only changed files (both added in initial)
        assert sorted(tracking_git.files_processed_per_commit.get("abc123", [])) == [
            "src/main.py",
            "src/utils.py",
        ], "Older commit should process only changed files"

        # Total: 3 at HEAD + 2 at older = 5 files
        assert response.files_processed == 5, "Should process 5 files total"

    @pytest.mark.asyncio
    async def test_head_first_delta_for_older_commits(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """Test that older commits use delta indexing (only changed files)."""
        from datetime import datetime

        # Create a git service with 3 commits
        three_commit_git = FakeGitService(
            commits=[
                CommitInfo(
                    hash="commit1",
                    short_hash="commit1",
                    author_name="Test User",
                    author_email="test@example.com",
                    author_date=datetime(2024, 1, 1, 0, 0, 0),
                    committer_name="Test User",
                    committer_email="test@example.com",
                    commit_date=datetime(2024, 1, 1, 0, 0, 0),
                    message="Initial",
                    parent_hashes=[],
                ),
                CommitInfo(
                    hash="commit2",
                    short_hash="commit2",
                    author_name="Test User",
                    author_email="test@example.com",
                    author_date=datetime(2024, 1, 2, 0, 0, 0),
                    committer_name="Test User",
                    committer_email="test@example.com",
                    commit_date=datetime(2024, 1, 2, 0, 0, 0),
                    message="Add file",
                    parent_hashes=["commit1"],
                ),
                CommitInfo(
                    hash="commit3",
                    short_hash="commit3",
                    author_name="Test User",
                    author_email="test@example.com",
                    author_date=datetime(2024, 1, 3, 0, 0, 0),
                    committer_name="Test User",
                    committer_email="test@example.com",
                    commit_date=datetime(2024, 1, 3, 0, 0, 0),
                    message="HEAD",
                    parent_hashes=["commit2"],
                ),
            ]
        )
        three_commit_git.files_in_commit = {
            "commit1": ["a.py"],
            "commit2": ["a.py", "b.py"],
            "commit3": ["a.py", "b.py", "c.py"],
        }
        three_commit_git.changed_files_in_commit = {
            "commit1": ChangedFiles(added=["a.py"], modified=[], deleted=[]),
            "commit2": ChangedFiles(added=["b.py"], modified=[], deleted=[]),
            "commit3": ChangedFiles(added=["c.py"], modified=[], deleted=[]),
        }

        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=three_commit_git,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert
        # HEAD (commit3): ALL files → 3 processed
        # commit2: only b.py (added) → 1 processed
        # commit1: only a.py (added) → 1 processed
        # Total: 5 files processed
        assert response.files_processed == 5, "Should process 5 files"

        # Unchanged files:
        # HEAD: 0 (we process all)
        # commit2: 1 unchanged (a.py)
        # commit1: 0 (all files are "added")
        assert response.files_unchanged == 1, "Should have 1 unchanged file"

    @pytest.mark.asyncio
    async def test_head_first_single_commit_processes_all(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """Test that a single commit (HEAD only) processes all files."""
        from datetime import datetime

        single_commit_git = FakeGitService(
            commits=[
                CommitInfo(
                    hash="only",
                    short_hash="only",
                    author_name="Test User",
                    author_email="test@example.com",
                    author_date=datetime(2024, 1, 1, 0, 0, 0),
                    committer_name="Test User",
                    committer_email="test@example.com",
                    commit_date=datetime(2024, 1, 1, 0, 0, 0),
                    message="Only commit",
                    parent_hashes=[],
                ),
            ]
        )
        single_commit_git.files_in_commit = {
            "only": ["a.py", "b.py", "c.py"],
        }
        single_commit_git.changed_files_in_commit = {
            "only": ChangedFiles(
                added=["a.py", "b.py", "c.py"], modified=[], deleted=[]
            ),
        }

        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=single_commit_git,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert - single commit processes all files
        assert response.files_processed == 3, "Should process all 3 files"
        assert response.files_unchanged == 0, "No unchanged files for single commit"


class TestBranchCommitsPopulation:
    """Tests for branch_commits table population during indexing."""

    @pytest.fixture
    def repository_adapter(self) -> InMemoryRepositoryRepository:
        return InMemoryRepositoryRepository()

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        return InMemoryCommitRepository()

    @pytest.fixture
    def file_repo(self) -> InMemoryFileRepository:
        return InMemoryFileRepository()

    @pytest.fixture
    def symbol_repo(self) -> InMemorySymbolRepository:
        return InMemorySymbolRepository()

    @pytest.fixture
    def reference_repo(self) -> InMemoryReferenceRepository:
        return InMemoryReferenceRepository()

    @pytest.fixture
    def index_status_repo(self) -> InMemoryIndexStatusRepository:
        return InMemoryIndexStatusRepository()

    @pytest.fixture
    def parser_service(self) -> FakeParserService:
        return FakeParserService()

    @pytest.mark.asyncio
    async def test_full_index_populates_branch_commits(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """Test that full indexing populates the branch_commits junction table."""
        git_service = FakeGitService()

        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=git_service,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert - branch_commits should be populated
        assert response.commits_indexed > 0

        # Check that commits are linked to the branch
        for commit in commit_repo._commits.values():
            if commit.id is not None:
                branches = await commit_repo.get_branches_for_commit(commit.id)
                assert (
                    "main" in branches
                ), f"Commit {commit.id} should be linked to main branch"

    @pytest.mark.asyncio
    async def test_second_index_populates_branch_commits(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """Test that second index call also populates branch_commits."""
        git_service = FakeGitService()

        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=git_service,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        # First index
        first_request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )
        await orchestrator.index_repository(first_request)

        # Second index (incremental behavior)
        second_request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )
        await orchestrator.index_repository(second_request)

        # Assert - all commits should be linked to the branch
        for commit in commit_repo._commits.values():
            if commit.id is not None:
                branches = await commit_repo.get_branches_for_commit(commit.id)
                assert "main" in branches

    @pytest.mark.asyncio
    async def test_indexing_different_branches_creates_separate_links(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """Test that indexing different branches creates correct branch links."""
        git_service = FakeGitService()

        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=git_service,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        # Index main branch
        main_request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )
        await orchestrator.index_repository(main_request)

        # Index feature branch (same commits, different branch name)
        feature_request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="feature",
            languages=["python"],
        )
        await orchestrator.index_repository(feature_request)

        # Assert - commits should be linked to both branches
        for commit in commit_repo._commits.values():
            if commit.id is not None:
                branches = await commit_repo.get_branches_for_commit(commit.id)
                assert "main" in branches, "Commit should be linked to main"
                assert "feature" in branches, "Commit should also be linked to feature"


class TestBranchIndexingOptimization:
    """Tests for branch indexing optimization using merge-base."""

    @pytest.mark.asyncio
    async def test_uses_list_branch_commits_when_base_branch_set(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """Test that list_branch_commits is called when base_branch is set and differs from branch."""
        git_service = FakeGitService()

        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=git_service,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        # Request with base_branch different from branch
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="feature",
            languages=["python"],
            base_branch="main",  # Different from branch
        )

        await orchestrator.index_repository(request)

        # Assert - list_branch_commits should have been called
        assert (
            git_service._list_branch_commits_called
        ), "list_branch_commits should be called when base_branch differs from branch"
        assert git_service._list_branch_commits_args["branch"] == "feature"
        assert git_service._list_branch_commits_args["base_branch"] == "main"

    @pytest.mark.asyncio
    async def test_uses_list_commits_when_base_branch_equals_branch(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """Test that list_commits (not list_branch_commits) is used when base_branch equals branch."""
        git_service = FakeGitService()

        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=git_service,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        # Request with base_branch same as branch (no optimization needed)
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            base_branch="main",  # Same as branch
        )

        await orchestrator.index_repository(request)

        # Assert - list_branch_commits should NOT have been called
        assert (
            not git_service._list_branch_commits_called
        ), "list_branch_commits should NOT be called when base_branch equals branch"

    @pytest.mark.asyncio
    async def test_uses_list_commits_when_no_base_branch(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """Test that list_commits (not list_branch_commits) is used when base_branch is None."""
        git_service = FakeGitService()

        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=git_service,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        # Request without base_branch
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="feature",
            languages=["python"],
            base_branch=None,  # No base branch
        )

        await orchestrator.index_repository(request)

        # Assert - list_branch_commits should NOT have been called
        assert (
            not git_service._list_branch_commits_called
        ), "list_branch_commits should NOT be called when base_branch is None"

    @pytest.mark.asyncio
    async def test_fewer_commits_indexed_with_optimization(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """Test that fewer commits are indexed when branch optimization is active."""
        git_service = FakeGitService()
        # FakeGitService has 2 commits by default
        # list_branch_commits returns only the last commit (simulating feature branch)

        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=git_service,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        # Index with optimization (base_branch set)
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="feature",
            languages=["python"],
            base_branch="main",
        )

        response = await orchestrator.index_repository(request)

        # Assert - only 1 commit should be indexed (the branch-specific one)
        # list_branch_commits returns only the last commit
        assert (
            response.commits_indexed == 1
        ), "Should index only 1 commit when using branch optimization"

    @pytest.mark.asyncio
    async def test_extracts_and_saves_comments(
        self,
        orchestrator: DefaultIndexingOrchestrator,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """Test that text search extracts and saves comments when enabled."""
        # Arrange: Set up fake comments to be extracted
        parser_service.comments_to_return = [
            {
                "content": "This is a docstring",
                "content_type": "docstring",
                "source_line": 1,
                "source_end_line": 3,
            },
            {
                "content": "This is an inline comment",
                "content_type": "single_line_comment",
                "source_line": 5,
            },
        ]

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert: Comments should be saved to text_content_repo
        all_text_contents = text_content_repo.get_all()
        assert len(all_text_contents) > 0, "Should have saved text contents"

        # Verify we have both comment types
        docstrings = [tc for tc in all_text_contents if tc.content_type == "docstring"]
        comments = [
            tc for tc in all_text_contents if tc.content_type == "single_line_comment"
        ]

        assert len(docstrings) > 0, "Should have extracted docstrings"
        assert len(comments) > 0, "Should have extracted comments"

        # Verify content matches
        assert any("docstring" in tc.content for tc in docstrings)
        assert any("inline comment" in tc.content for tc in comments)

        # Verify response contains text content counts
        assert response.comments_indexed == len(
            comments
        ), "Response should track comment count"
        assert response.docstrings_indexed == len(
            docstrings
        ), "Response should track docstring count"

    @pytest.mark.asyncio
    async def test_commit_messages_indexed(
        self,
        orchestrator: DefaultIndexingOrchestrator,
        text_content_repo: InMemoryTextContentRepository,
        git_service: FakeGitService,
    ) -> None:
        """Test that commit messages are indexed when text search is enabled."""
        # Arrange: Use default FakeGitService with 2 commits
        # Commit 1: "Initial commit"
        # Commit 2: "Add feature"

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert: Commit messages should be saved to text_content_repo
        all_text_contents = text_content_repo.get_all()

        # Filter for commit messages (source_type = "commit_message")
        commit_messages = [
            tc for tc in all_text_contents if tc.source_type == "commit_message"
        ]

        # Should have 2 commit messages (one per commit)
        assert (
            len(commit_messages) == 2
        ), f"Should have 2 commit messages, got {len(commit_messages)}"

        # Verify commit message content
        commit_texts = {tc.content for tc in commit_messages}
        assert "Initial commit" in commit_texts, "Should have first commit message"
        assert "Add feature" in commit_texts, "Should have second commit message"

        # Verify commit messages have correct metadata
        for tc in commit_messages:
            assert tc.source_type == "commit_message"
            assert tc.source_file_id is None, "Commit messages should not have file_id"
            assert tc.source_line is None, "Commit messages should not have line number"
            assert tc.content_type == "commit_message"

        # Verify response contains commit message count
        assert (
            response.commit_messages_indexed == 2
        ), "Response should track commit message count"

    @pytest.mark.asyncio
    async def test_existing_commit_message_not_duplicated(
        self,
        orchestrator: DefaultIndexingOrchestrator,
        text_content_repo: InMemoryTextContentRepository,
        git_service: FakeGitService,
    ) -> None:
        """Test that re-indexing does not duplicate commit messages.

        When a commit already exists in the database, its message should NOT
        be re-indexed. This prevents inflated search result counts.
        """
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act: Index once
        await orchestrator.index_repository(request)

        # Verify initial state: 2 commit messages (one per commit)
        all_text_contents = text_content_repo.get_all()
        commit_messages_after_first = [
            tc for tc in all_text_contents if tc.source_type == "commit_message"
        ]
        assert len(commit_messages_after_first) == 2

        # Act: Index again (same commits will be found as existing)
        await orchestrator.index_repository(request)

        # Assert: Still only 2 commit messages, NOT 4
        all_text_contents = text_content_repo.get_all()
        commit_messages_after_second = [
            tc for tc in all_text_contents if tc.source_type == "commit_message"
        ]
        assert len(commit_messages_after_second) == 2, (
            f"Expected 2 commit messages after re-indexing, "
            f"got {len(commit_messages_after_second)} (duplicates were created)"
        )

    @pytest.mark.asyncio
    async def test_non_code_files_indexed(
        self,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        text_content_repo: InMemoryTextContentRepository,
        parser_service: FakeParserService,
    ) -> None:
        """Test that non-code files are indexed when text search is enabled."""
        # Arrange: Create a git service with markdown and YAML files
        from datetime import datetime

        git_service = FakeGitService(
            commits=[
                CommitInfo(
                    hash="abc123",
                    short_hash="abc123",
                    author_name="Test User",
                    author_email="test@example.com",
                    author_date=datetime(2024, 1, 1, 0, 0, 0),
                    committer_name="Test User",
                    committer_email="test@example.com",
                    commit_date=datetime(2024, 1, 1, 0, 0, 0),
                    message="Add docs",
                    parent_hashes=[],
                )
            ]
        )
        # Add non-code files to the commit
        git_service.files_in_commit = {
            "abc123": ["README.md", "config.yaml", "Dockerfile"]
        }
        git_service.changed_files_in_commit = {
            "abc123": ChangedFiles(
                added=["README.md", "config.yaml", "Dockerfile"],
                modified=[],
                deleted=[],
            )
        }

        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            text_content_repo=text_content_repo,
            git_service=git_service,
            parser_service=parser_service,
            plaintext_parser=FakePlaintextParser(),
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert: Non-code files should be indexed
        all_text_contents = text_content_repo.get_all()

        # Filter for file content (source_type = "file_content")
        file_contents = [
            tc for tc in all_text_contents if tc.source_type == "file_content"
        ]

        # Should have content from non-code files
        assert len(file_contents) > 0, "Should have indexed non-code file content"

        # Verify content has correct metadata
        for tc in file_contents:
            assert tc.source_type == "file_content"
            assert tc.source_file_id is not None, "Should have file_id"
            assert tc.source_line is not None, "Should have line number"
            assert tc.content.strip(), "Content should not be empty"

        # Verify response contains non-code file count
        assert (
            response.non_code_files_indexed >= 3
        ), "Response should track non-code files indexed"
