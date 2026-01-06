"""Integration tests for repository adapters.

These tests verify that the PostgreSQL adapters work correctly
with a real database (SQLite in test mode).
"""

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from inxr2.adapters.persistence.repositories.file_adapter import PostgresFileRepository
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from inxr2.domain.entities import Commit, File, Repository
from inxr2.domain.value_objects import CommitHash


@pytest.mark.asyncio
class TestPostgresRepositoryAdapter:
    """Tests for PostgresRepositoryAdapter adapter."""

    async def test_save_and_find_repository(self, db_session: AsyncSession) -> None:
        """Test saving and retrieving a repository."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="test-repo",
            url="https://github.com/test/repo.git",
            description="Test repository",
        )

        # Act
        saved_repo = await repo_adapter.save(repository)
        found_repo = await repo_adapter.find_by_id(saved_repo.id)

        # Assert
        assert found_repo is not None
        assert found_repo.id == saved_repo.id
        assert found_repo.name == "test-repo"
        assert found_repo.url == "https://github.com/test/repo.git"
        assert found_repo.description == "Test repository"

    async def test_find_by_name(self, db_session: AsyncSession) -> None:
        """Test finding repository by name."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="unique-repo",
            url="https://github.com/test/unique.git",
        )
        await repo_adapter.save(repository)

        # Act
        found_repo = await repo_adapter.find_by_name("unique-repo")

        # Assert
        assert found_repo is not None
        assert found_repo.name == "unique-repo"

    async def test_list_all_repositories(self, db_session: AsyncSession) -> None:
        """Test listing all repositories."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo1 = Repository(name="repo1", url="https://example.com/1.git")
        repo2 = Repository(name="repo2", url="https://example.com/2.git")
        repo3 = Repository(name="repo3", url="https://example.com/3.git")

        await repo_adapter.save(repo1)
        await repo_adapter.save(repo2)
        await repo_adapter.save(repo3)

        # Act
        all_repos = await repo_adapter.list_all()

        # Assert
        assert len(all_repos) >= 3
        names = {r.name for r in all_repos}
        assert "repo1" in names
        assert "repo2" in names
        assert "repo3" in names

    async def test_delete_repository(self, db_session: AsyncSession) -> None:
        """Test deleting a repository."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="to-delete",
            url="https://example.com/delete.git",
        )
        saved_repo = await repo_adapter.save(repository)

        # Act
        deleted = await repo_adapter.delete(saved_repo.id)

        # Assert
        assert deleted is True

        # Verify deletion
        found = await repo_adapter.find_by_id(saved_repo.id)
        assert found is None


@pytest.mark.asyncio
class TestPostgresCommitRepository:
    """Tests for PostgresCommitRepository adapter."""

    async def test_save_and_find_commit(self, db_session: AsyncSession) -> None:
        """Test saving and retrieving a commit."""
        # Arrange - create repository first
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(name="test-repo", url="https://example.com/repo.git")
        saved_repo = await repo_adapter.save(repository)

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("abc123" + "0" * 34),
            short_hash="abc123",
            parent_hashes=None,
            branch="main",
            author_name="Test Author",
            author_email="test@example.com",
            committer_name="Test Author",
            committer_email="test@example.com",
            author_date=datetime(2025, 1, 1, 12, 0, 0),
            commit_date=datetime(2025, 1, 1, 12, 0, 0),
            message="Test commit",
        )

        # Act
        saved_commit = await commit_adapter.save(commit)
        found_commit = await commit_adapter.find_by_id(saved_commit.id)

        # Assert
        assert found_commit is not None
        assert found_commit.id == saved_commit.id
        assert found_commit.commit_hash.value == "abc123" + "0" * 34
        assert found_commit.message == "Test commit"

    async def test_save_many_commits(self, db_session: AsyncSession) -> None:
        """Test bulk saving commits."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(name="test-repo", url="https://example.com/repo.git")
        saved_repo = await repo_adapter.save(repository)

        commit_adapter = PostgresCommitRepository(db_session)
        commits = [
            Commit(
                repository_id=saved_repo.id,
                commit_hash=CommitHash(f"commit{i}" + "0" * 33),
                short_hash=f"commit{i}",
                author_name="Author",
                author_email="author@example.com",
                committer_name="Author",
                committer_email="author@example.com",
                author_date=datetime(2025, 1, i + 1),
                commit_date=datetime(2025, 1, i + 1),
                message=f"Commit {i}",
            )
            for i in range(3)
        ]

        # Act
        saved_commits = await commit_adapter.save_many(commits)

        # Assert
        assert len(saved_commits) == 3
        for commit in saved_commits:
            assert commit.id is not None

    async def test_find_by_hash(self, db_session: AsyncSession) -> None:
        """Test finding commit by hash."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(name="test-repo", url="https://example.com/repo.git")
        saved_repo = await repo_adapter.save(repository)

        commit_adapter = PostgresCommitRepository(db_session)
        commit_hash = "unique123" + "0" * 31
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash(commit_hash),
            author_name="Author",
            author_email="author@example.com",
            committer_name="Author",
            committer_email="author@example.com",
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
            message="Test",
        )
        await commit_adapter.save(commit)

        # Act
        found = await commit_adapter.find_by_hash(saved_repo.id, commit_hash)

        # Assert
        assert found is not None
        assert found.commit_hash.value == commit_hash

    async def test_list_by_repository(self, db_session: AsyncSession) -> None:
        """Test listing commits for a repository."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(name="test-repo", url="https://example.com/repo.git")
        saved_repo = await repo_adapter.save(repository)

        commit_adapter = PostgresCommitRepository(db_session)
        commits = [
            Commit(
                repository_id=saved_repo.id,
                commit_hash=CommitHash(f"hash{i}" + "0" * 35),
                author_name="Author",
                author_email="author@example.com",
                committer_name="Author",
                committer_email="author@example.com",
                author_date=datetime(2025, 1, i + 1),
                commit_date=datetime(2025, 1, i + 1),
                message=f"Commit {i}",
                branch="main",
            )
            for i in range(5)
        ]
        await commit_adapter.save_many(commits)

        # Act
        found_commits = await commit_adapter.list_by_repository(
            saved_repo.id, branch="main"
        )

        # Assert
        assert len(found_commits) >= 5


@pytest.mark.asyncio
class TestPostgresFileRepository:
    """Tests for PostgresFileRepository adapter."""

    async def test_save_and_find_file(self, db_session: AsyncSession) -> None:
        """Test saving and retrieving a file."""
        # Arrange - create repository and commit first
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(name="test-repo", url="https://example.com/repo.git")
        saved_repo = await repo_adapter.save(repository)

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("abc123" + "0" * 34),
            author_name="Author",
            author_email="author@example.com",
            committer_name="Author",
            committer_email="author@example.com",
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
            message="Test",
        )
        saved_commit = await commit_adapter.save(commit)

        file_adapter = PostgresFileRepository(db_session)
        file = File(
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            path="src/main.py",
            content_hash="hash123",
            size_bytes=1024,
            language="python",
            line_count=50,
        )

        # Act
        saved_file = await file_adapter.save(file)
        found_file = await file_adapter.find_by_id(saved_file.id)

        # Assert
        assert found_file is not None
        assert found_file.id == saved_file.id
        assert found_file.path == "src/main.py"
        assert found_file.language == "python"
        assert found_file.line_count == 50

    async def test_save_many_files(self, db_session: AsyncSession) -> None:
        """Test bulk saving files."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(name="test-repo", url="https://example.com/repo.git")
        saved_repo = await repo_adapter.save(repository)

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("abc123" + "0" * 34),
            author_name="Author",
            author_email="author@example.com",
            committer_name="Author",
            committer_email="author@example.com",
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
            message="Test",
        )
        saved_commit = await commit_adapter.save(commit)

        file_adapter = PostgresFileRepository(db_session)
        files = [
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                path=f"file{i}.py",
                content_hash=f"hash{i}",
                size_bytes=100 * i,
                language="python",
                line_count=10 * i,
            )
            for i in range(3)
        ]

        # Act
        saved_files = await file_adapter.save_many(files)

        # Assert
        assert len(saved_files) == 3
        for file in saved_files:
            assert file.id is not None

    async def test_list_by_repository(self, db_session: AsyncSession) -> None:
        """Test listing files for a repository."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(name="test-repo", url="https://example.com/repo.git")
        saved_repo = await repo_adapter.save(repository)

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("abc123" + "0" * 34),
            author_name="Author",
            author_email="author@example.com",
            committer_name="Author",
            committer_email="author@example.com",
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
            message="Test",
        )
        saved_commit = await commit_adapter.save(commit)

        file_adapter = PostgresFileRepository(db_session)
        files = [
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                path=f"src/file{i}.py",
                content_hash=f"hash{i}",
                size_bytes=100,
            )
            for i in range(5)
        ]
        await file_adapter.save_many(files)

        # Act
        found_files = await file_adapter.list_by_repository(saved_repo.id)

        # Assert
        assert len(found_files) >= 5
        paths = {f.path for f in found_files}
        assert "src/file0.py" in paths
        assert "src/file4.py" in paths

    async def test_find_by_path(self, db_session: AsyncSession) -> None:
        """Test finding file by path."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(name="test-repo", url="https://example.com/repo.git")
        saved_repo = await repo_adapter.save(repository)

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("abc123" + "0" * 34),
            author_name="Author",
            author_email="author@example.com",
            committer_name="Author",
            committer_email="author@example.com",
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
            message="Test",
        )
        saved_commit = await commit_adapter.save(commit)

        file_adapter = PostgresFileRepository(db_session)
        file = File(
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            path="unique/path.py",
            content_hash="hash",
            size_bytes=100,
        )
        await file_adapter.save(file)

        # Act
        found = await file_adapter.find_by_path(
            saved_repo.id, saved_commit.id, "unique/path.py"
        )

        # Assert
        assert found is not None
        assert found.path == "unique/path.py"

    async def test_list_by_commit(self, db_session: AsyncSession) -> None:
        """Test listing files by commit."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(name="test-repo", url="https://example.com/repo.git")
        saved_repo = await repo_adapter.save(repository)

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("abc123" + "0" * 34),
            author_name="Author",
            author_email="author@example.com",
            committer_name="Author",
            committer_email="author@example.com",
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
            message="Test",
        )
        saved_commit = await commit_adapter.save(commit)

        file_adapter = PostgresFileRepository(db_session)
        files = [
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                path=f"file{i}.py",
                content_hash=f"hash{i}",
                size_bytes=100,
            )
            for i in range(3)
        ]
        await file_adapter.save_many(files)

        # Act
        found_files = await file_adapter.list_by_commit(saved_commit.id)

        # Assert
        assert len(found_files) >= 3

    async def test_find_by_content_hash(self, db_session: AsyncSession) -> None:
        """Test finding files by content hash."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(name="test-repo", url="https://example.com/repo.git")
        saved_repo = await repo_adapter.save(repository)

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("abc123" + "0" * 34),
            author_name="Author",
            author_email="author@example.com",
            committer_name="Author",
            committer_email="author@example.com",
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
            message="Test",
        )
        saved_commit = await commit_adapter.save(commit)

        file_adapter = PostgresFileRepository(db_session)

        # Create files with same content hash
        files = [
            File(
                repository_id=saved_repo.id,
                commit_id=saved_commit.id,
                path=f"duplicate{i}.py",
                content_hash="same_content_hash",
                size_bytes=100,
            )
            for i in range(2)
        ]
        await file_adapter.save_many(files)

        # Act
        found_files = await file_adapter.find_by_content_hash("same_content_hash")

        # Assert
        assert len(found_files) >= 2
