"""Tests for repository use cases."""

from datetime import datetime

import pytest

from inxr2.application.use_cases.repositories.get_repository_files import (
    GetRepositoryFilesRequest,
    GetRepositoryFilesUseCase,
)
from inxr2.application.use_cases.repositories.list_repositories import (
    ListRepositoriesUseCase,
)
from inxr2.domain.entities import Commit, File, Repository
from inxr2.domain.value_objects import CommitHash
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryRepositoryRepository,
)


class TestListRepositoriesUseCase:
    """Tests for ListRepositoriesUseCase."""

    @pytest.mark.asyncio
    async def test_list_empty_repositories(self) -> None:
        """Test listing repositories when none exist."""
        # Arrange
        repo_repository = InMemoryRepositoryRepository()
        use_case = ListRepositoriesUseCase(repository_repo=repo_repository)

        # Act
        result = await use_case.execute()

        # Assert
        assert result.repositories == []
        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_list_multiple_repositories(self) -> None:
        """Test listing multiple repositories."""
        # Arrange
        repo_repository = InMemoryRepositoryRepository()

        # Add test repositories
        repo1 = Repository(
            name="repo1",
            url="https://github.com/user/repo1.git",
            description="First repository",
        )
        repo2 = Repository(
            name="repo2",
            url="https://github.com/user/repo2.git",
            description="Second repository",
        )
        repo3 = Repository(
            name="repo3",
            url="https://github.com/user/repo3.git",
        )

        await repo_repository.save(repo1)
        await repo_repository.save(repo2)
        await repo_repository.save(repo3)

        use_case = ListRepositoriesUseCase(repository_repo=repo_repository)

        # Act
        result = await use_case.execute()

        # Assert
        assert result.total_count == 3
        assert len(result.repositories) == 3
        assert all(isinstance(r, Repository) for r in result.repositories)

        # Verify repository data
        names = {r.name for r in result.repositories}
        assert names == {"repo1", "repo2", "repo3"}


class TestGetRepositoryFilesUseCase:
    """Tests for GetRepositoryFilesUseCase."""

    @pytest.mark.asyncio
    async def test_get_files_for_nonexistent_repository(self) -> None:
        """Test getting files for a repository that doesn't exist."""
        # Arrange
        repo_repository = InMemoryRepositoryRepository()
        file_repository = InMemoryFileRepository()
        use_case = GetRepositoryFilesUseCase(
            repository_repo=repo_repository,
            file_repo=file_repository,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Repository 999 not found"):
            await use_case.execute(GetRepositoryFilesRequest(repository_id=999))

    @pytest.mark.asyncio
    async def test_get_files_for_empty_repository(self) -> None:
        """Test getting files for a repository with no files."""
        # Arrange
        repo_repository = InMemoryRepositoryRepository()
        file_repository = InMemoryFileRepository()

        # Create a repository
        repo = await repo_repository.save(
            Repository(name="test-repo", url="https://example.com/repo.git")
        )

        use_case = GetRepositoryFilesUseCase(
            repository_repo=repo_repository,
            file_repo=file_repository,
        )

        # Act
        result = await use_case.execute(
            GetRepositoryFilesRequest(repository_id=repo.id)
        )

        # Assert
        assert result.files == []
        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_get_files_for_repository(self) -> None:
        """Test getting files for a repository with multiple files."""
        # Arrange
        repo_repository = InMemoryRepositoryRepository()
        file_repository = InMemoryFileRepository()
        commit_repository = InMemoryCommitRepository()

        # Create repository
        repo = await repo_repository.save(
            Repository(name="test-repo", url="https://example.com/repo.git")
        )

        # Create commit
        commit = await commit_repository.save(
            Commit(
                repository_id=repo.id,
                commit_hash=CommitHash("abc123" + "0" * 34),
                short_hash="abc123",
                parent_hashes=[],
                branch="main",
                author_name="Test Author",
                author_email="test@example.com",
                committer_name="Test Author",
                committer_email="test@example.com",
                author_date=datetime(2025, 1, 1, 12, 0, 0),
                commit_date=datetime(2025, 1, 1, 12, 0, 0),
                message="Test commit",
            )
        )

        # Create files
        await file_repository.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/main.py",
                content_hash="hash1",
                size_bytes=1024,
                language="python",
                line_count=50,
            )
        )
        await file_repository.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="README.md",
                content_hash="hash2",
                size_bytes=512,
                language="markdown",
                line_count=20,
            )
        )
        await file_repository.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="tests/test_main.py",
                content_hash="hash3",
                size_bytes=2048,
                language="python",
                line_count=100,
            )
        )

        use_case = GetRepositoryFilesUseCase(
            repository_repo=repo_repository,
            file_repo=file_repository,
        )

        # Act
        result = await use_case.execute(
            GetRepositoryFilesRequest(repository_id=repo.id)
        )

        # Assert
        assert result.total_count == 3
        assert len(result.files) == 3
        assert all(isinstance(f, File) for f in result.files)
        assert all(f.repository_id == repo.id for f in result.files)

        # Verify file paths
        paths = {f.path for f in result.files}
        assert paths == {"src/main.py", "README.md", "tests/test_main.py"}

    @pytest.mark.asyncio
    async def test_get_files_only_for_specified_repository(self) -> None:
        """Test that files are filtered by repository ID."""
        # Arrange
        repo_repository = InMemoryRepositoryRepository()
        file_repository = InMemoryFileRepository()
        commit_repository = InMemoryCommitRepository()

        # Create two repositories
        repo1 = await repo_repository.save(
            Repository(name="repo1", url="https://example.com/repo1.git")
        )
        repo2 = await repo_repository.save(
            Repository(name="repo2", url="https://example.com/repo2.git")
        )

        # Create commits
        commit1 = await commit_repository.save(
            Commit(
                repository_id=repo1.id,
                commit_hash=CommitHash("abc123" + "0" * 34),
                short_hash="abc123",
                parent_hashes=[],
                branch="main",
                author_name="Test Author",
                author_email="test@example.com",
                committer_name="Test Author",
                committer_email="test@example.com",
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
                message="Commit 1",
            )
        )
        commit2 = await commit_repository.save(
            Commit(
                repository_id=repo2.id,
                commit_hash=CommitHash("def456" + "0" * 34),
                short_hash="def456",
                parent_hashes=[],
                branch="main",
                author_name="Test Author",
                author_email="test@example.com",
                committer_name="Test Author",
                committer_email="test@example.com",
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
                message="Commit 2",
            )
        )

        # Add files to both repositories
        await file_repository.save(
            File(
                repository_id=repo1.id,
                commit_id=commit1.id,
                path="file1.py",
                content_hash="hash1",
                size_bytes=100,
            )
        )
        await file_repository.save(
            File(
                repository_id=repo1.id,
                commit_id=commit1.id,
                path="file2.py",
                content_hash="hash2",
                size_bytes=200,
            )
        )
        await file_repository.save(
            File(
                repository_id=repo2.id,
                commit_id=commit2.id,
                path="file3.py",
                content_hash="hash3",
                size_bytes=300,
            )
        )

        use_case = GetRepositoryFilesUseCase(
            repository_repo=repo_repository,
            file_repo=file_repository,
        )

        # Act
        result = await use_case.execute(
            GetRepositoryFilesRequest(repository_id=repo1.id)
        )

        # Assert
        assert result.total_count == 2
        assert all(f.repository_id == repo1.id for f in result.files)
        paths = {f.path for f in result.files}
        assert paths == {"file1.py", "file2.py"}
