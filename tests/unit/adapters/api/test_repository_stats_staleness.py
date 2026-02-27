"""Tests for repository stats staleness detection."""

from datetime import datetime
from pathlib import Path

import pytest

from inxr2.application.use_cases.repositories import GetRepositoryStatsRequest
from inxr2.application.use_cases.repositories.get_repository_stats import (
    GetRepositoryStatsUseCase,
)
from inxr2.domain.entities import IndexStatus, Repository
from inxr2.domain.exceptions import InvalidRepositoryPath
from tests.fixtures.test_doubles import (
    FakeGitService,
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryFileVersionRepository,
    InMemoryIndexStatusRepository,
    InMemoryReferenceRepository,
    InMemoryRepositoryRepository,
    InMemorySymbolRepository,
)


class TestRepositoryStatsStaleness:
    """Tests for staleness fields in GetRepositoryStatsUseCase."""

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
    def file_repo(self) -> InMemoryFileRepository:
        return InMemoryFileRepository()

    @pytest.fixture
    def file_version_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemoryFileVersionRepository:
        return InMemoryFileVersionRepository(file_repo=file_repo)

    @pytest.fixture
    def symbol_repo(self) -> InMemorySymbolRepository:
        return InMemorySymbolRepository()

    @pytest.fixture
    def reference_repo(self) -> InMemoryReferenceRepository:
        return InMemoryReferenceRepository()

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        return InMemoryCommitRepository()

    @pytest.fixture
    def index_status_repo(self) -> InMemoryIndexStatusRepository:
        return InMemoryIndexStatusRepository()

    @pytest.fixture
    def git_service(self) -> FakeGitService:
        return FakeGitService()

    @pytest.mark.asyncio
    async def test_stale_when_git_head_differs_from_indexed(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        file_version_repo: InMemoryFileVersionRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        commit_repo: InMemoryCommitRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        git_service: FakeGitService,
    ) -> None:
        """Stats should show is_stale=True when git HEAD differs from last indexed commit."""
        # Set up: index status says "abc123" but git HEAD is "def456"
        await index_status_repo.save(
            IndexStatus(
                repository_id=1,
                branch="main",
                indexing_status="completed",
                last_indexed_commit="abc123",
                last_indexed_at=datetime(2024, 1, 1),
            )
        )
        # FakeGitService.get_current_commit returns the last commit hash ("def456" by default)

        use_case = GetRepositoryStatsUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            file_version_repo=file_version_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            commit_repo=commit_repo,
            index_status_repo=index_status_repo,
            git_service=git_service,
        )

        result = await use_case.execute(GetRepositoryStatsRequest(repository_id=1))

        assert result.is_stale is True
        assert result.last_indexed_commit == "abc123"
        assert result.git_head_commit == "def456"
        assert result.last_indexed_at == datetime(2024, 1, 1)

    @pytest.mark.asyncio
    async def test_not_stale_when_commits_match(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        file_version_repo: InMemoryFileVersionRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        commit_repo: InMemoryCommitRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        git_service: FakeGitService,
    ) -> None:
        """Stats should show is_stale=False when indexed commit matches git HEAD."""
        # FakeGitService returns "def456" as current commit
        await index_status_repo.save(
            IndexStatus(
                repository_id=1,
                branch="main",
                indexing_status="completed",
                last_indexed_commit="def456",
                last_indexed_at=datetime(2024, 1, 2),
            )
        )

        use_case = GetRepositoryStatsUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            file_version_repo=file_version_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            commit_repo=commit_repo,
            index_status_repo=index_status_repo,
            git_service=git_service,
        )

        result = await use_case.execute(GetRepositoryStatsRequest(repository_id=1))

        assert result.is_stale is False
        assert result.last_indexed_commit == "def456"
        assert result.git_head_commit == "def456"

    @pytest.mark.asyncio
    async def test_not_stale_when_never_indexed(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        file_version_repo: InMemoryFileVersionRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        commit_repo: InMemoryCommitRepository,
        index_status_repo: InMemoryIndexStatusRepository,
        git_service: FakeGitService,
    ) -> None:
        """Stats should show is_stale=False when repo has never been indexed."""
        # No index status saved — never indexed

        use_case = GetRepositoryStatsUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            file_version_repo=file_version_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            commit_repo=commit_repo,
            index_status_repo=index_status_repo,
            git_service=git_service,
        )

        result = await use_case.execute(GetRepositoryStatsRequest(repository_id=1))

        assert result.is_stale is False
        assert result.last_indexed_commit is None
        assert result.git_head_commit == "def456"

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_git_failure(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        file_version_repo: InMemoryFileVersionRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        commit_repo: InMemoryCommitRepository,
        index_status_repo: InMemoryIndexStatusRepository,
    ) -> None:
        """Stats should show is_stale=False when git service raises."""

        class FailingGitService(FakeGitService):
            def get_current_commit(
                self, repo_path: Path, branch: str | None = None
            ) -> str:
                raise InvalidRepositoryPath(str(repo_path))

        await index_status_repo.save(
            IndexStatus(
                repository_id=1,
                branch="main",
                indexing_status="completed",
                last_indexed_commit="abc123",
                last_indexed_at=datetime(2024, 1, 1),
            )
        )

        use_case = GetRepositoryStatsUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            file_version_repo=file_version_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            commit_repo=commit_repo,
            index_status_repo=index_status_repo,
            git_service=FailingGitService(),
        )

        result = await use_case.execute(GetRepositoryStatsRequest(repository_id=1))

        assert result.is_stale is False
        assert result.git_head_commit is None
        assert result.last_indexed_commit == "abc123"

    @pytest.mark.asyncio
    async def test_no_staleness_without_dependencies(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        file_version_repo: InMemoryFileVersionRepository,
        symbol_repo: InMemorySymbolRepository,
        reference_repo: InMemoryReferenceRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> None:
        """Stats should default to is_stale=False when deps are not injected."""
        use_case = GetRepositoryStatsUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            file_version_repo=file_version_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            commit_repo=commit_repo,
            # No index_status_repo or git_service
        )

        result = await use_case.execute(GetRepositoryStatsRequest(repository_id=1))

        assert result.is_stale is False
        assert result.last_indexed_commit is None
        assert result.git_head_commit is None
