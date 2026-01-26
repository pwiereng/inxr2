"""Tests for dependency injection providers."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import inxr2.infrastructure.dependencies as deps_module
from inxr2.adapters.external.git_service import GitService
from inxr2.adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from inxr2.adapters.persistence.repositories.file_adapter import PostgresFileRepository
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


class TestRepositoryAdapterProviders:
    """Tests for repository adapter provider functions."""

    @pytest.fixture
    def mock_session(self) -> AsyncSession:
        """Create a mock AsyncSession."""
        session = MagicMock(spec=AsyncSession)
        return session

    def test_get_repository_adapter(self, mock_session: AsyncSession) -> None:
        """get_repository_adapter should return PostgresRepositoryAdapter."""
        adapter = get_repository_adapter(mock_session)
        assert isinstance(adapter, PostgresRepositoryAdapter)

    def test_get_commit_adapter(self, mock_session: AsyncSession) -> None:
        """get_commit_adapter should return PostgresCommitRepository."""
        adapter = get_commit_adapter(mock_session)
        assert isinstance(adapter, PostgresCommitRepository)

    def test_get_file_adapter(self, mock_session: AsyncSession) -> None:
        """get_file_adapter should return PostgresFileRepository."""
        adapter = get_file_adapter(mock_session)
        assert isinstance(adapter, PostgresFileRepository)

    def test_get_symbol_adapter(self, mock_session: AsyncSession) -> None:
        """get_symbol_adapter should return PostgresSymbolRepository."""
        adapter = get_symbol_adapter(mock_session)
        assert isinstance(adapter, PostgresSymbolRepository)

    def test_get_reference_adapter(self, mock_session: AsyncSession) -> None:
        """get_reference_adapter should return PostgresReferenceRepository."""
        adapter = get_reference_adapter(mock_session)
        assert isinstance(adapter, PostgresReferenceRepository)

    def test_get_index_status_adapter(self, mock_session: AsyncSession) -> None:
        """get_index_status_adapter should return PostgresIndexStatusRepository."""
        adapter = get_index_status_adapter(mock_session)
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
    def mock_repository_adapter(self) -> MagicMock:
        """Create mock repository adapter."""
        return MagicMock()

    @pytest.fixture
    def mock_commit_adapter(self) -> MagicMock:
        """Create mock commit adapter."""
        return MagicMock()

    @pytest.fixture
    def mock_file_adapter(self) -> MagicMock:
        """Create mock file adapter."""
        return MagicMock()

    def test_get_list_repositories_use_case(
        self, mock_repository_adapter: MagicMock
    ) -> None:
        """get_list_repositories_use_case should return ListRepositoriesUseCase."""
        use_case = get_list_repositories_use_case(mock_repository_adapter)
        assert isinstance(use_case, ListRepositoriesUseCase)

    def test_get_repository_files_use_case(
        self,
        mock_repository_adapter: MagicMock,
        mock_file_adapter: MagicMock,
    ) -> None:
        """get_repository_files_use_case should return GetRepositoryFilesUseCase."""
        use_case = get_repository_files_use_case(
            mock_repository_adapter, mock_file_adapter
        )
        assert isinstance(use_case, GetRepositoryFilesUseCase)

    def test_get_index_local_directory_use_case(
        self,
        mock_repository_adapter: MagicMock,
        mock_commit_adapter: MagicMock,
        mock_file_adapter: MagicMock,
    ) -> None:
        """get_index_local_directory_use_case should return IndexLocalDirectoryUseCase."""
        mock_filesystem = MagicMock()
        use_case = get_index_local_directory_use_case(
            mock_repository_adapter,
            mock_commit_adapter,
            mock_file_adapter,
            mock_filesystem,
        )
        assert isinstance(use_case, IndexLocalDirectoryUseCase)

    def test_get_repository_tree_use_case(
        self,
        mock_repository_adapter: MagicMock,
        mock_file_adapter: MagicMock,
        mock_commit_adapter: MagicMock,
    ) -> None:
        """get_repository_tree_use_case should return GetRepositoryTreeUseCase."""
        use_case = get_repository_tree_use_case(
            mock_repository_adapter, mock_file_adapter, mock_commit_adapter
        )
        assert isinstance(use_case, GetRepositoryTreeUseCase)


class TestUseCaseDependencyWiring:
    """Tests that use cases receive correct dependencies."""

    def test_list_repositories_has_repository_repo(self) -> None:
        """ListRepositoriesUseCase should receive repository adapter."""
        mock_adapter = MagicMock()
        use_case = get_list_repositories_use_case(mock_adapter)
        # Access internal attribute to verify wiring
        assert use_case._repository_repo is mock_adapter

    def test_repository_files_has_both_repos(self) -> None:
        """GetRepositoryFilesUseCase should receive both adapters."""
        mock_repo_adapter = MagicMock()
        mock_file_adapter = MagicMock()
        use_case = get_repository_files_use_case(mock_repo_adapter, mock_file_adapter)
        assert use_case._repository_repo is mock_repo_adapter
        assert use_case._file_repo is mock_file_adapter

    def test_index_local_directory_has_all_repos(self) -> None:
        """IndexLocalDirectoryUseCase should receive all adapters including filesystem."""
        mock_repo = MagicMock()
        mock_commit = MagicMock()
        mock_file = MagicMock()
        mock_filesystem = MagicMock()
        use_case = get_index_local_directory_use_case(
            mock_repo, mock_commit, mock_file, mock_filesystem
        )
        assert use_case._repository_repo is mock_repo
        assert use_case._commit_repo is mock_commit
        assert use_case._file_repo is mock_file
        assert use_case._filesystem is mock_filesystem

    def test_repository_tree_has_all_repos(self) -> None:
        """GetRepositoryTreeUseCase should receive all three adapters."""
        mock_repo = MagicMock()
        mock_file = MagicMock()
        mock_commit = MagicMock()
        use_case = get_repository_tree_use_case(mock_repo, mock_file, mock_commit)
        assert use_case._repository_repo is mock_repo
        assert use_case._file_repo is mock_file
        assert use_case._commit_repo is mock_commit
