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
from inxr2.adapters.persistence.repositories.reference_adapter import (
    PostgresReferenceRepository,
)
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from inxr2.adapters.persistence.repositories.symbol_adapter import (
    PostgresSymbolRepository,
)
from inxr2.domain.entities import Commit, File, Reference, Repository, Symbol
from inxr2.domain.value_objects import CommitHash, ReferenceType, SymbolKind


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
            )
            for i in range(5)
        ]
        saved_commits = await commit_adapter.save_many(commits)

        # Link all commits to main branch
        for c in saved_commits:
            await commit_adapter.link_commit_to_branch(saved_repo.id, c.id, "main")

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

    async def test_find_by_repository_and_path(self, db_session: AsyncSession) -> None:
        """Test finding file by repository and path."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="find-by-path-repo", url="https://example.com/repo.git"
        )
        saved_repo = await repo_adapter.save(repository)

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("findpath" + "0" * 32),
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
            path="src/utils/helper.py",
            content_hash="unique_hash",
            size_bytes=200,
            language="python",
        )
        await file_adapter.save(file)

        # Act
        found = await file_adapter.find_by_repository_and_path(
            saved_repo.id, "src/utils/helper.py"
        )

        # Assert
        assert found is not None
        assert found.path == "src/utils/helper.py"
        assert found.repository_id == saved_repo.id

    async def test_find_by_repository_and_path_not_found(
        self, db_session: AsyncSession
    ) -> None:
        """Test finding file by repository and path when it doesn't exist."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(name="empty-repo", url="https://example.com/empty.git")
        saved_repo = await repo_adapter.save(repository)

        file_adapter = PostgresFileRepository(db_session)

        # Act
        found = await file_adapter.find_by_repository_and_path(
            saved_repo.id, "nonexistent/file.py"
        )

        # Assert
        assert found is None

    async def test_find_by_repository_and_path_returns_latest_version(
        self, db_session: AsyncSession
    ) -> None:
        """Test that find_by_repository_and_path returns the latest file version.

        When multiple versions of the same file exist (from different commits),
        the method should return the one with the highest commit_id.
        """
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="multi-version-repo", url="https://example.com/repo.git"
        )
        saved_repo = await repo_adapter.save(repository)

        commit_adapter = PostgresCommitRepository(db_session)

        # Create an older commit
        old_commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("oldcommit" + "0" * 31),
            author_name="Author",
            author_email="author@example.com",
            committer_name="Author",
            committer_email="author@example.com",
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
            message="Old commit",
        )
        saved_old_commit = await commit_adapter.save(old_commit)

        # Create a newer commit
        new_commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("newcommit" + "0" * 31),
            author_name="Author",
            author_email="author@example.com",
            committer_name="Author",
            committer_email="author@example.com",
            author_date=datetime(2025, 1, 2),
            commit_date=datetime(2025, 1, 2),
            message="New commit",
        )
        saved_new_commit = await commit_adapter.save(new_commit)

        file_adapter = PostgresFileRepository(db_session)

        # Create old version of file (smaller size to distinguish)
        old_file = File(
            repository_id=saved_repo.id,
            commit_id=saved_old_commit.id,
            path="src/app.py",
            content_hash="old_hash",
            size_bytes=100,
            language="python",
        )
        await file_adapter.save(old_file)

        # Create new version of same file (larger size)
        new_file = File(
            repository_id=saved_repo.id,
            commit_id=saved_new_commit.id,
            path="src/app.py",
            content_hash="new_hash",
            size_bytes=200,
            language="python",
        )
        saved_new_file = await file_adapter.save(new_file)

        # Act
        found = await file_adapter.find_by_repository_and_path(
            saved_repo.id, "src/app.py"
        )

        # Assert - should return the latest version (from new_commit)
        assert found is not None
        assert found.id == saved_new_file.id
        assert found.commit_id == saved_new_commit.id
        assert found.content_hash == "new_hash"
        assert found.size_bytes == 200


@pytest.mark.asyncio
class TestPostgresSymbolRepository:
    """Tests for PostgresSymbolRepository adapter."""

    async def _create_test_data(self, db_session: AsyncSession):
        """Create test repository, commit, and file."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(name="symbol-test", url="https://example.com/repo.git")
        saved_repo = await repo_adapter.save(repository)

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("symtest" + "0" * 33),
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
        file1 = File(
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            path="src/repo1.py",
            content_hash="hash1",
            size_bytes=100,
        )
        file2 = File(
            repository_id=saved_repo.id,
            commit_id=saved_commit.id,
            path="src/repo2.py",
            content_hash="hash2",
            size_bytes=100,
        )
        saved_file1 = await file_adapter.save(file1)
        saved_file2 = await file_adapter.save(file2)

        return saved_repo, saved_commit, saved_file1, saved_file2

    async def test_find_by_exact_name_multiple_symbols(
        self, db_session: AsyncSession
    ) -> None:
        """Test finding all symbols with the exact same name."""
        # Arrange
        repo, commit, file1, file2 = await self._create_test_data(db_session)
        symbol_adapter = PostgresSymbolRepository(db_session)

        # Create multiple symbols with same name in different classes
        symbols = [
            Symbol(
                file_id=file1.id,
                repository_id=repo.id,
                commit_id=commit.id,
                name="save",
                qualified_name="FileRepository.save",
                kind=SymbolKind.METHOD,
                start_line=10,
                start_column=4,
                end_line=20,
                end_column=0,
            ),
            Symbol(
                file_id=file2.id,
                repository_id=repo.id,
                commit_id=commit.id,
                name="save",
                qualified_name="CommitRepository.save",
                kind=SymbolKind.METHOD,
                start_line=15,
                start_column=4,
                end_line=25,
                end_column=0,
            ),
            Symbol(
                file_id=file1.id,
                repository_id=repo.id,
                commit_id=commit.id,
                name="delete",  # Different name
                qualified_name="FileRepository.delete",
                kind=SymbolKind.METHOD,
                start_line=30,
                start_column=4,
                end_line=40,
                end_column=0,
            ),
        ]
        await symbol_adapter.save_many(symbols)

        # Act - find all symbols named "save"
        found = await symbol_adapter.find_by_exact_name("save", repo.id)

        # Assert
        assert len(found) == 2
        qualified_names = {s.qualified_name for s in found}
        assert "FileRepository.save" in qualified_names
        assert "CommitRepository.save" in qualified_names

    async def test_find_by_exact_name_no_match(self, db_session: AsyncSession) -> None:
        """Test finding symbols with a name that doesn't exist."""
        # Arrange
        repo, commit, file1, _ = await self._create_test_data(db_session)
        symbol_adapter = PostgresSymbolRepository(db_session)

        symbol = Symbol(
            file_id=file1.id,
            repository_id=repo.id,
            commit_id=commit.id,
            name="existing",
            kind=SymbolKind.FUNCTION,
            start_line=1,
            start_column=0,
            end_line=5,
            end_column=0,
        )
        await symbol_adapter.save(symbol)

        # Act
        found = await symbol_adapter.find_by_exact_name("nonexistent", repo.id)

        # Assert
        assert len(found) == 0


@pytest.mark.asyncio
class TestPostgresReferenceRepository:
    """Tests for PostgresReferenceRepository adapter."""

    async def _create_test_data(self, db_session: AsyncSession):
        """Create test repository, commit, file, and symbols."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(name="ref-test", url="https://example.com/repo.git")
        saved_repo = await repo_adapter.save(repository)

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("reftest" + "0" * 33),
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
            path="src/caller.py",
            content_hash="hash1",
            size_bytes=100,
        )
        saved_file = await file_adapter.save(file)

        return saved_repo, saved_commit, saved_file

    async def test_find_references_by_text(self, db_session: AsyncSession) -> None:
        """Test finding all references matching a text string."""
        # Arrange
        repo, commit, file = await self._create_test_data(db_session)
        reference_adapter = PostgresReferenceRepository(db_session)

        # Create references with same text but potentially different targets
        references = [
            Reference(
                source_file_id=file.id,
                repository_id=repo.id,
                commit_id=commit.id,
                source_line=10,
                source_column=4,
                source_end_column=8,
                reference_text="save",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,  # Unresolved
            ),
            Reference(
                source_file_id=file.id,
                repository_id=repo.id,
                commit_id=commit.id,
                source_line=20,
                source_column=4,
                source_end_column=8,
                reference_text="save",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            ),
            Reference(
                source_file_id=file.id,
                repository_id=repo.id,
                commit_id=commit.id,
                source_line=30,
                source_column=4,
                source_end_column=10,
                reference_text="delete",  # Different text
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            ),
        ]
        await reference_adapter.save_many(references)

        # Act - find all references with text "save"
        found = await reference_adapter.find_references_by_text("save", repo.id)

        # Assert
        assert len(found) == 2
        for ref in found:
            assert ref.reference_text == "save"

    async def test_find_references_by_text_no_match(
        self, db_session: AsyncSession
    ) -> None:
        """Test finding references with text that doesn't exist."""
        # Arrange
        repo, commit, file = await self._create_test_data(db_session)
        reference_adapter = PostgresReferenceRepository(db_session)

        reference = Reference(
            source_file_id=file.id,
            repository_id=repo.id,
            commit_id=commit.id,
            source_line=10,
            source_column=4,
            source_end_column=8,
            reference_text="existing",
            reference_type=ReferenceType.CALL,
        )
        await reference_adapter.save(reference)

        # Act
        found = await reference_adapter.find_references_by_text("nonexistent", repo.id)

        # Assert
        assert len(found) == 0

    async def test_find_references_by_text_only_returns_latest_file_version(
        self, db_session: AsyncSession
    ) -> None:
        """Test that find_references_by_text only returns references from latest files.

        When the same file is indexed multiple times (different commits),
        only references from the latest version should be returned to avoid
        duplicate results.
        """
        # Arrange - create repository
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="multi-commit-ref-test", url="https://example.com/repo.git"
        )
        saved_repo = await repo_adapter.save(repository)

        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        reference_adapter = PostgresReferenceRepository(db_session)

        # Create first (older) commit
        old_commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("oldref00" + "0" * 32),
            author_name="Author",
            author_email="author@example.com",
            committer_name="Author",
            committer_email="author@example.com",
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
            message="Old commit",
        )
        saved_old_commit = await commit_adapter.save(old_commit)

        # Create file in old commit
        old_file = File(
            repository_id=saved_repo.id,
            commit_id=saved_old_commit.id,
            path="src/caller.py",
            content_hash="old_hash",
            size_bytes=100,
        )
        saved_old_file = await file_adapter.save(old_file)

        # Create reference in old file
        old_ref = Reference(
            source_file_id=saved_old_file.id,
            repository_id=saved_repo.id,
            commit_id=saved_old_commit.id,
            source_line=10,
            source_column=4,
            source_end_column=14,
            reference_text="my_function",
            reference_type=ReferenceType.CALL,
        )
        await reference_adapter.save(old_ref)

        # Create second (newer) commit
        new_commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("newref00" + "0" * 32),
            author_name="Author",
            author_email="author@example.com",
            committer_name="Author",
            committer_email="author@example.com",
            author_date=datetime(2025, 1, 2),
            commit_date=datetime(2025, 1, 2),
            message="New commit",
        )
        saved_new_commit = await commit_adapter.save(new_commit)

        # Create file in new commit (same path, newer version)
        new_file = File(
            repository_id=saved_repo.id,
            commit_id=saved_new_commit.id,
            path="src/caller.py",  # Same path as old file
            content_hash="new_hash",
            size_bytes=150,
        )
        saved_new_file = await file_adapter.save(new_file)

        # Create reference in new file (same text, different line)
        new_ref = Reference(
            source_file_id=saved_new_file.id,
            repository_id=saved_repo.id,
            commit_id=saved_new_commit.id,
            source_line=15,  # Different line in new version
            source_column=4,
            source_end_column=14,
            reference_text="my_function",
            reference_type=ReferenceType.CALL,
        )
        await reference_adapter.save(new_ref)

        # Act - find references by text
        found = await reference_adapter.find_references_by_text(
            "my_function", saved_repo.id
        )

        # Assert - should only return the reference from the latest file version
        assert len(found) == 1
        assert found[0].source_file_id == saved_new_file.id
        assert found[0].source_line == 15  # From new version
