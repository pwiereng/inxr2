"""Tests for DefaultIndexingOrchestrator implementation."""

from datetime import UTC
from pathlib import Path

import pytest

from inxr2.application.use_cases.indexing.default_orchestrator import (
    DefaultIndexingOrchestrator,
)
from inxr2.application.use_cases.indexing.orchestrator import (
    IncrementalIndexRequest,
    IndexingStrategy,
    IndexRepositoryRequest,
)
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryIndexStatusRepository,
    InMemoryReferenceRepository,
    InMemoryRepositoryRepository,
    InMemorySymbolRepository,
)


class FakeGitService:
    """Fake git service for testing without real git operations."""

    def __init__(self, commits: list[dict] | None = None):
        """
        Initialize with test commits.

        Args:
            commits: List of dicts matching GitService.list_commits() output
        """
        from datetime import datetime

        self.commits = commits or [
            {
                "hash": "abc123",
                "short_hash": "abc123",
                "author_name": "Test User",
                "author_email": "test@example.com",
                "author_date": datetime(2024, 1, 1, 0, 0, 0),
                "committer_name": "Test User",
                "committer_email": "test@example.com",
                "commit_date": datetime(2024, 1, 1, 0, 0, 0),
                "message": "Initial commit",
                "parent_hashes": [],
            },
            {
                "hash": "def456",
                "short_hash": "def456",
                "author_name": "Test User",
                "author_email": "test@example.com",
                "author_date": datetime(2024, 1, 2, 0, 0, 0),
                "committer_name": "Test User",
                "committer_email": "test@example.com",
                "commit_date": datetime(2024, 1, 2, 0, 0, 0),
                "message": "Add feature",
                "parent_hashes": ["abc123"],
            },
        ]
        self.files_in_commit: dict[str, list[str]] = {
            "abc123": ["src/main.py", "src/utils.py"],
            "def456": ["src/main.py", "src/utils.py", "src/new_file.py"],
        }

    def get_repository_info(self, repo_path: Path) -> dict:
        """Get repository information."""
        return {
            "current_branch": "main",
            "default_branch": "main",
            "remote_url": str(repo_path),
        }

    def get_current_commit(self, repo_path: Path, branch: str | None = None) -> str:
        """Get current commit hash."""
        commit_hash: str = self.commits[-1]["hash"]
        return commit_hash

    def get_commit_info(self, repo_path: Path, commit_hash: str) -> dict:
        """Get detailed information about a commit."""
        for commit in self.commits:
            if commit["hash"] == commit_hash:
                return commit
        # Return the last commit if not found
        return self.commits[-1]

    def list_commits(
        self,
        repo_path: Path,
        branch: str,
        max_count: int | None = None,
        since_days: int | None = None,
    ) -> list[dict]:
        """Get commit history (oldest to newest)."""
        commits = self.commits.copy()
        if max_count:
            commits = commits[:max_count]
        return commits

    def list_files(
        self, repo_path: Path, commit_hash: str, patterns: list[str] | None = None
    ) -> list[str]:
        """Get list of files in a commit."""
        return self.files_in_commit.get(commit_hash, [])

    def get_file_content(
        self, repo_path: Path, commit_hash: str, file_path: str
    ) -> str:
        """Get file content at specific commit."""
        return f"# Content of {file_path} at {commit_hash}\nprint('hello')"


class FakeParserService:
    """Fake parser service for testing without real parsing."""

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
        git_service=git_service,
        parser_service=parser_service,
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
            strategy=IndexingStrategy.FULL,
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
            strategy=IndexingStrategy.FULL,
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
            strategy=IndexingStrategy.FULL,
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
            strategy=IndexingStrategy.FULL,
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
            strategy=IndexingStrategy.FULL,
            max_history=1,  # Only index 1 commit
        )

        # Act
        response = await orchestrator.index_repository(request)

        # Assert
        assert response.commits_indexed == 1  # Limited to 1

    @pytest.mark.asyncio
    async def test_index_incremental_only_processes_new_commits(
        self,
        orchestrator: DefaultIndexingOrchestrator,
        repository_adapter: InMemoryRepositoryRepository,
        commit_repo: InMemoryCommitRepository,
        index_status_repo: InMemoryIndexStatusRepository,
    ) -> None:
        """Test that incremental indexing only processes new commits."""
        # Arrange - first do a partial full index
        full_request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            strategy=IndexingStrategy.FULL,
            max_history=1,  # Only index first commit
        )
        await orchestrator.index_repository(full_request)

        # Get repository ID
        repo = await repository_adapter.find_by_name("test-repo")
        assert repo is not None
        assert repo.id is not None

        # Now do incremental index
        incremental_request = IncrementalIndexRequest(
            repository_id=repo.id,
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
        )

        # Act
        response = await orchestrator.index_incremental(incremental_request)

        # Assert
        # Should only index the second commit
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
            strategy=IndexingStrategy.FULL,
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
    ) -> None:
        """Test that indexing updates index status."""
        # Arrange
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            strategy=IndexingStrategy.FULL,
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
            ) -> list[dict]:
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
            git_service=spy_git,
            parser_service=parser_service,
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            strategy=IndexingStrategy.FULL,
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
            ) -> list[dict]:
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
            git_service=spy_git,
            parser_service=parser_service,
        )

        # Test with since_days=30
        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            strategy=IndexingStrategy.FULL,
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
            ) -> list[dict]:
                # Return empty list to simulate no commits in date range
                if since_days is not None:
                    return []
                return super().list_commits(repo_path, branch, max_count, since_days)

            def get_commit_info(self, repo_path: Path, commit_hash: str) -> dict:
                self.get_commit_info_called = True
                return {
                    "hash": "def456",
                    "short_hash": "def456",
                    "author_name": "Test User",
                    "author_email": "test@example.com",
                    "author_date": datetime(2024, 1, 2, 0, 0, 0),
                    "committer_name": "Test User",
                    "committer_email": "test@example.com",
                    "commit_date": datetime(2024, 1, 2, 0, 0, 0),
                    "message": "HEAD commit",
                    "parent_hashes": [],
                }

        empty_git = EmptyCommitsGitService()
        orchestrator = DefaultIndexingOrchestrator(
            repository_repo=repository_adapter,
            commit_repo=commit_repo,
            file_repo=file_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            index_status_repo=index_status_repo,
            git_service=empty_git,
            parser_service=parser_service,
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            strategy=IndexingStrategy.FULL,
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
            git_service=spy_git,
            parser_service=parser_service,
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            strategy=IndexingStrategy.FULL,
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
                    {
                        "hash": "tz123",
                        "short_hash": "tz123",
                        "author_name": "Test User",
                        "author_email": "test@example.com",
                        "author_date": datetime(
                            2024, 1, 1, 12, 0, 0, tzinfo=UTC
                        ),
                        "committer_name": "Test User",
                        "committer_email": "test@example.com",
                        "commit_date": datetime(
                            2024, 1, 1, 12, 0, 0, tzinfo=UTC
                        ),
                        "message": "Commit with timezone",
                        "parent_hashes": [],
                    },
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
            git_service=tz_git,
            parser_service=parser_service,
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            strategy=IndexingStrategy.FULL,
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
            git_service=git_service,
            parser_service=dict_parser,
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            strategy=IndexingStrategy.FULL,
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
            git_service=git_service,
            parser_service=no_end_parser,
        )

        # Update git service to return .c files
        git_service.files_in_commit = {
            "abc123": ["main.c"],
            "def456": ["main.c"],
        }

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["c"],
            strategy=IndexingStrategy.FULL,
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
            git_service=git_service,
            parser_service=string_type_parser,
        )

        # Update git service to return .c files
        git_service.files_in_commit = {
            "abc123": ["main.c"],
            "def456": ["main.c"],
        }

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["c"],
            strategy=IndexingStrategy.FULL,
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
            git_service=git_service,
            parser_service=parser_service,
        )

        request = IndexRepositoryRequest(
            repository_path=Path("/repos/test-repo"),
            branch="main",
            languages=["python"],
            strategy=IndexingStrategy.FULL,
        )

        # First indexing run
        response1 = await orchestrator.index_repository(request)
        assert response1.commits_indexed == 2

        # Count commits after first run
        commits_after_first = await commit_repo.list_by_repository(repository_id=1)
        first_commit_count = len(commits_after_first)

        # Second indexing run - should NOT raise UniqueViolation
        response2 = await orchestrator.index_repository(request)

        # Should still report commits processed (even if skipped)
        assert response2.commits_indexed == 2

        # Commits should not be duplicated
        commits_after_second = await commit_repo.list_by_repository(repository_id=1)
        assert (
            len(commits_after_second) == first_commit_count
        ), "Commits should not be duplicated on re-index"
