"""Tests for dependency injection providers."""

from typing import Any

import pytest

import inxr2.infrastructure.dependencies as deps_module
from inxr2.adapters.external.git_service import GitService
from inxr2.adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from inxr2.adapters.persistence.repositories.file_adapter import PostgresFileRepository
from inxr2.adapters.persistence.repositories.file_search_adapter import (
    PostgresFileSearchRepository,
)
from inxr2.adapters.persistence.repositories.file_version_adapter import (
    PostgresFileVersionRepository,
)
from inxr2.adapters.persistence.repositories.index_status_adapter import (
    PostgresIndexStatusRepository,
)
from inxr2.adapters.persistence.repositories.reference_adapter import (
    PostgresReferenceRepository,
)
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from inxr2.adapters.persistence.repositories.symbol_adapter import (
    PostgresSymbolRepository,
)
from inxr2.application.ports.repositories import FileSearchPort, FileVersionPort
from inxr2.application.use_cases.indexing.index_local_directory import (
    IndexLocalDirectoryUseCase,
)
from inxr2.application.use_cases.repositories.get_repository_files import (
    GetRepositoryFilesUseCase,
)
from inxr2.application.use_cases.repositories.get_repository_tree import (
    GetRepositoryTreeUseCase,
)
from inxr2.application.use_cases.repositories.list_repositories import (
    ListRepositoriesUseCase,
)
from inxr2.infrastructure.dependencies import (
    get_commit_adapter,
    get_file_adapter,
    get_file_search_adapter,
    get_file_version_adapter,
    get_filesystem,
    get_git_service,
    get_index_local_directory_use_case,
    get_index_status_adapter,
    get_list_repositories_use_case,
    get_reference_adapter,
    get_repository_adapter,
    get_repository_files_use_case,
    get_repository_tree_use_case,
    get_symbol_adapter,
)
from tests.fixtures.test_doubles import (
    FakeFileSystem,
    FakeGitService,
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryFileVersionRepository,
    InMemoryRepositoryRepository,
)


class TestRepositoryAdapterProviders:
    """Tests for repository adapter provider functions.

    These tests verify that DI provider functions create the correct adapter types.
    The session is stored by constructors but never used, so a stub suffices.
    """

    @pytest.fixture
    def stub_session(self) -> Any:
        """Stub standing in for AsyncSession in DI wiring tests."""
        return object()

    def test_get_repository_adapter(self, stub_session: Any) -> None:
        """get_repository_adapter should return PostgresRepositoryAdapter."""
        adapter = get_repository_adapter(stub_session)
        assert isinstance(adapter, PostgresRepositoryAdapter)

    def test_get_commit_adapter(self, stub_session: Any) -> None:
        """get_commit_adapter should return PostgresCommitRepository."""
        adapter = get_commit_adapter(stub_session)
        assert isinstance(adapter, PostgresCommitRepository)

    def test_get_file_adapter(self, stub_session: Any) -> None:
        """get_file_adapter should return PostgresFileRepository."""
        adapter = get_file_adapter(stub_session)
        assert isinstance(adapter, PostgresFileRepository)

    def test_get_file_search_adapter(self, stub_session: Any) -> None:
        """get_file_search_adapter should return PostgresFileSearchRepository."""
        adapter = get_file_search_adapter(stub_session)
        assert isinstance(adapter, PostgresFileSearchRepository)
        assert isinstance(adapter, FileSearchPort)

    def test_get_file_version_adapter(self, stub_session: Any) -> None:
        """get_file_version_adapter should return PostgresFileVersionRepository."""
        adapter = get_file_version_adapter(stub_session)
        assert isinstance(adapter, PostgresFileVersionRepository)
        assert isinstance(adapter, FileVersionPort)

    def test_get_symbol_adapter(self, stub_session: Any) -> None:
        """get_symbol_adapter should return PostgresSymbolRepository."""
        adapter = get_symbol_adapter(stub_session)
        assert isinstance(adapter, PostgresSymbolRepository)

    def test_get_reference_adapter(self, stub_session: Any) -> None:
        """get_reference_adapter should return PostgresReferenceRepository."""
        adapter = get_reference_adapter(stub_session)
        assert isinstance(adapter, PostgresReferenceRepository)

    def test_get_index_status_adapter(self, stub_session: Any) -> None:
        """get_index_status_adapter should return PostgresIndexStatusRepository."""
        adapter = get_index_status_adapter(stub_session)
        assert isinstance(adapter, PostgresIndexStatusRepository)


class TestGitServiceProvider:
    """Tests for GitService provider."""

    def test_get_git_service_returns_git_service(self) -> None:
        """get_git_service should return a GitService instance."""
        service = get_git_service()
        assert isinstance(service, GitService)

    def test_get_git_service_is_singleton(self) -> None:
        """get_git_service should return the same instance (singleton)."""
        # Reset singleton for clean test
        deps_module._git_service = None

        service1 = get_git_service()
        service2 = get_git_service()
        assert service1 is service2

    def test_get_git_service_creates_new_if_none(self) -> None:
        """get_git_service should create new instance if none exists."""
        deps_module._git_service = None

        service = get_git_service()
        assert service is not None
        assert isinstance(service, GitService)


class TestFileSystemProvider:
    """Tests for FileSystem provider."""

    def test_get_filesystem_returns_filesystem_port(self) -> None:
        """get_filesystem should return a FileSystemPort instance."""
        from inxr2.application.ports.services import FileSystemPort

        filesystem = get_filesystem()
        assert isinstance(filesystem, FileSystemPort)

    def test_get_filesystem_is_singleton(self) -> None:
        """get_filesystem should return the same instance (singleton)."""
        deps_module._local_filesystem = None

        fs1 = get_filesystem()
        fs2 = get_filesystem()
        assert fs1 is fs2

    def test_get_filesystem_creates_new_if_none(self) -> None:
        """get_filesystem should create new instance if none exists."""
        from inxr2.adapters.external.local_filesystem import LocalFileSystem

        deps_module._local_filesystem = None

        filesystem = get_filesystem()
        assert filesystem is not None
        assert isinstance(filesystem, LocalFileSystem)


class TestUseCaseProviders:
    """Tests for use case provider functions."""

    @pytest.fixture
    def fake_repository_adapter(self) -> InMemoryRepositoryRepository:
        """Create fake repository adapter."""
        return InMemoryRepositoryRepository()

    @pytest.fixture
    def fake_commit_adapter(self) -> InMemoryCommitRepository:
        """Create fake commit adapter."""
        return InMemoryCommitRepository()

    @pytest.fixture
    def fake_file_adapter(self) -> InMemoryFileRepository:
        """Create fake file adapter."""
        return InMemoryFileRepository()

    def test_get_list_repositories_use_case(
        self, fake_repository_adapter: InMemoryRepositoryRepository
    ) -> None:
        """get_list_repositories_use_case should return ListRepositoriesUseCase."""
        use_case = get_list_repositories_use_case(fake_repository_adapter)
        assert isinstance(use_case, ListRepositoriesUseCase)

    def test_get_repository_files_use_case(
        self,
        fake_repository_adapter: InMemoryRepositoryRepository,
        fake_file_adapter: InMemoryFileRepository,
    ) -> None:
        """get_repository_files_use_case should return GetRepositoryFilesUseCase."""
        use_case = get_repository_files_use_case(
            fake_repository_adapter, fake_file_adapter
        )
        assert isinstance(use_case, GetRepositoryFilesUseCase)

    def test_get_index_local_directory_use_case(
        self,
        fake_repository_adapter: InMemoryRepositoryRepository,
        fake_commit_adapter: InMemoryCommitRepository,
        fake_file_adapter: InMemoryFileRepository,
    ) -> None:
        """get_index_local_directory_use_case should return IndexLocalDirectoryUseCase."""
        fake_filesystem = FakeFileSystem()
        use_case = get_index_local_directory_use_case(
            fake_repository_adapter,
            fake_commit_adapter,
            fake_file_adapter,
            fake_filesystem,
        )
        assert isinstance(use_case, IndexLocalDirectoryUseCase)

    def test_get_repository_tree_use_case(
        self,
        fake_repository_adapter: InMemoryRepositoryRepository,
        fake_file_adapter: InMemoryFileRepository,
        fake_commit_adapter: InMemoryCommitRepository,
    ) -> None:
        """get_repository_tree_use_case should return GetRepositoryTreeUseCase."""
        fake_file_version_adapter = InMemoryFileVersionRepository(
            file_repo=fake_file_adapter
        )
        fake_git_service = FakeGitService()
        use_case = get_repository_tree_use_case(
            fake_repository_adapter,
            fake_file_adapter,
            fake_file_version_adapter,
            fake_commit_adapter,
            fake_git_service,
        )
        assert isinstance(use_case, GetRepositoryTreeUseCase)


class TestUseCaseDependencyWiring:
    """Tests that use cases receive correct dependencies."""

    def test_list_repositories_has_repository_repo(self) -> None:
        """ListRepositoriesUseCase should receive repository adapter."""
        fake_adapter = InMemoryRepositoryRepository()
        use_case = get_list_repositories_use_case(fake_adapter)
        assert use_case._repository_repo is fake_adapter

    def test_repository_files_has_both_repos(self) -> None:
        """GetRepositoryFilesUseCase should receive both adapters."""
        fake_repo_adapter = InMemoryRepositoryRepository()
        fake_file_adapter = InMemoryFileRepository()
        use_case = get_repository_files_use_case(fake_repo_adapter, fake_file_adapter)
        assert use_case._repository_repo is fake_repo_adapter
        assert use_case._file_repo is fake_file_adapter

    def test_index_local_directory_has_all_repos(self) -> None:
        """IndexLocalDirectoryUseCase should receive all adapters including filesystem."""
        fake_repo = InMemoryRepositoryRepository()
        fake_commit = InMemoryCommitRepository()
        fake_file = InMemoryFileRepository()
        fake_filesystem = FakeFileSystem()
        use_case = get_index_local_directory_use_case(
            fake_repo, fake_commit, fake_file, fake_filesystem
        )
        assert use_case._repository_repo is fake_repo
        assert use_case._commit_repo is fake_commit
        assert use_case._file_repo is fake_file
        assert use_case._filesystem is fake_filesystem

    def test_repository_tree_has_all_repos(self) -> None:
        """GetRepositoryTreeUseCase should receive all adapters and git service."""
        fake_repo = InMemoryRepositoryRepository()
        fake_file = InMemoryFileRepository()
        fake_file_version = InMemoryFileVersionRepository(file_repo=fake_file)
        fake_commit = InMemoryCommitRepository()
        fake_git = FakeGitService()
        use_case = get_repository_tree_use_case(
            fake_repo, fake_file, fake_file_version, fake_commit, fake_git
        )
        assert use_case._repository_repo is fake_repo
        assert use_case._file_repo is fake_file
        assert use_case._file_version_repo is fake_file_version
        assert use_case._commit_repo is fake_commit
        assert use_case._git_service is fake_git
