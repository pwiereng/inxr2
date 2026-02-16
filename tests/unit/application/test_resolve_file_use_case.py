"""Tests for ResolveFileUseCase using dependency injection."""

from datetime import datetime

import pytest

from inxr2.application.use_cases.files import (
    ResolveFileRequest,
    ResolveFileUseCase,
)
from inxr2.domain.entities import Commit, File, Repository
from inxr2.domain.exceptions import CommitNotFound, FileNotFound, RepositoryNotFound
from inxr2.domain.value_objects import CommitHash
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryRepositoryRepository,
)


class TestResolveFileUseCase:
    """Tests for ResolveFileUseCase."""

    @pytest.fixture
    def repository_repo(self) -> InMemoryRepositoryRepository:
        """Create repository with test data."""
        repo = InMemoryRepositoryRepository()
        repo.add(
            Repository(
                id=1,
                name="test-repo",
                url="/path/to/repo",
                default_branch="main",
            )
        )
        return repo

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        """Create commit repository with test data."""
        repo = InMemoryCommitRepository()

        # Commit on main branch
        commit1 = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("abc123def456"),
            author_date=datetime(2025, 1, 1, 12, 0, 0),
            commit_date=datetime(2025, 1, 1, 12, 0, 0),
        )
        repo._commits[1] = commit1
        repo._branch_commits[(1, "main", 1)] = True

        # Commit on feature branch
        commit2 = Commit(
            id=2,
            repository_id=1,
            commit_hash=CommitHash("def789ghi012"),
            author_date=datetime(2025, 1, 2, 12, 0, 0),
            commit_date=datetime(2025, 1, 2, 12, 0, 0),
        )
        repo._commits[2] = commit2
        repo._branch_commits[(1, "feature", 2)] = True

        return repo

    @pytest.fixture
    def file_repo(
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        """Create file repository with test data linked to commits."""
        repo = InMemoryFileRepository(commit_repo=commit_repo)

        # File on main branch (commit 1)
        repo.add(
            File(
                id=1,
                repository_id=1,
                path="src/main.py",
                content_hash="hash1",
                size_bytes=100,
                language="Python",
            )
        )
        repo._commit_files.add((1, 1))  # Link file 1 to commit 1

        # Same file on feature branch (commit 2) with different content
        repo.add(
            File(
                id=2,
                repository_id=1,
                path="src/main.py",
                content_hash="hash2",
                size_bytes=150,
                language="Python",
            )
        )
        repo._commit_files.add((2, 2))  # Link file 2 to commit 2

        # File only on feature branch
        repo.add(
            File(
                id=3,
                repository_id=1,
                path="src/feature.py",
                content_hash="hash3",
                size_bytes=200,
                language="Python",
            )
        )
        repo._commit_files.add((2, 3))  # Link file 3 to commit 2

        return repo

    @pytest.fixture
    def use_case(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> ResolveFileUseCase:
        """Create use case with test repositories."""
        return ResolveFileUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
        )

    # === Repository Resolution Tests ===

    @pytest.mark.asyncio
    async def test_raises_repository_not_found_for_unknown_repo(
        self, use_case: ResolveFileUseCase
    ) -> None:
        """Should raise RepositoryNotFound for unknown repository."""
        request = ResolveFileRequest(
            repository_name="unknown-repo",
            file_path="src/main.py",
        )

        with pytest.raises(RepositoryNotFound) as exc_info:
            await use_case.execute(request)

        assert "unknown-repo" in str(exc_info.value)

    # === Default Resolution (Latest) Tests ===

    @pytest.mark.asyncio
    async def test_resolves_file_by_default_to_latest(
        self, use_case: ResolveFileUseCase
    ) -> None:
        """Should resolve to latest file version when no commit/branch specified."""
        request = ResolveFileRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        response = await use_case.execute(request)

        assert response.file.path == "src/main.py"
        assert response.repository.name == "test-repo"
        assert response.commit is not None

    @pytest.mark.asyncio
    async def test_raises_file_not_found_for_unknown_path(
        self, use_case: ResolveFileUseCase
    ) -> None:
        """Should raise FileNotFound for unknown file path."""
        request = ResolveFileRequest(
            repository_name="test-repo",
            file_path="nonexistent/file.py",
        )

        with pytest.raises(FileNotFound) as exc_info:
            await use_case.execute(request)

        assert "nonexistent/file.py" in str(exc_info.value)

    # === Commit Resolution Tests ===

    @pytest.mark.asyncio
    async def test_resolves_file_at_specific_commit(
        self, use_case: ResolveFileUseCase
    ) -> None:
        """Should resolve file at specific commit hash."""
        request = ResolveFileRequest(
            repository_name="test-repo",
            file_path="src/main.py",
            commit_hash="abc123def456",
        )

        response = await use_case.execute(request)

        assert response.file.path == "src/main.py"
        assert response.file.content_hash == "hash1"
        assert response.commit.commit_hash.value == "abc123def456"

    @pytest.mark.asyncio
    async def test_resolves_different_file_version_at_different_commit(
        self, use_case: ResolveFileUseCase
    ) -> None:
        """Should return different file version for different commit."""
        # Get file at commit 1
        request1 = ResolveFileRequest(
            repository_name="test-repo",
            file_path="src/main.py",
            commit_hash="abc123def456",
        )
        response1 = await use_case.execute(request1)

        # Get file at commit 2
        request2 = ResolveFileRequest(
            repository_name="test-repo",
            file_path="src/main.py",
            commit_hash="def789ghi012",
        )
        response2 = await use_case.execute(request2)

        # Should be different file records
        assert response1.file.id != response2.file.id
        assert response1.file.content_hash != response2.file.content_hash

    @pytest.mark.asyncio
    async def test_raises_file_not_found_at_commit(
        self, use_case: ResolveFileUseCase
    ) -> None:
        """Should raise FileNotFound when file doesn't exist at commit."""
        request = ResolveFileRequest(
            repository_name="test-repo",
            file_path="src/feature.py",  # Only exists on feature branch (commit 2)
            commit_hash="abc123def456",  # Commit 1 (main)
        )

        with pytest.raises(FileNotFound) as exc_info:
            await use_case.execute(request)

        assert "abc123def456" in str(exc_info.value)

    # === Branch Resolution Tests ===

    @pytest.mark.asyncio
    async def test_resolves_file_on_specific_branch(
        self, use_case: ResolveFileUseCase
    ) -> None:
        """Should resolve latest file version on specified branch."""
        request = ResolveFileRequest(
            repository_name="test-repo",
            file_path="src/main.py",
            branch="feature",
        )

        response = await use_case.execute(request)

        assert response.file.path == "src/main.py"
        assert response.file.content_hash == "hash2"  # Feature branch version
        assert response.commit.commit_hash.value == "def789ghi012"

    @pytest.mark.asyncio
    async def test_resolves_branch_specific_file(
        self, use_case: ResolveFileUseCase
    ) -> None:
        """Should resolve file that only exists on specific branch."""
        request = ResolveFileRequest(
            repository_name="test-repo",
            file_path="src/feature.py",  # Only on feature branch
            branch="feature",
        )

        response = await use_case.execute(request)

        assert response.file.path == "src/feature.py"
        assert response.file.content_hash == "hash3"

    @pytest.mark.asyncio
    async def test_raises_file_not_found_on_branch(
        self, use_case: ResolveFileUseCase
    ) -> None:
        """Should raise FileNotFound when file doesn't exist on branch."""
        request = ResolveFileRequest(
            repository_name="test-repo",
            file_path="src/feature.py",  # Only exists on feature branch
            branch="main",
        )

        with pytest.raises(FileNotFound) as exc_info:
            await use_case.execute(request)

        assert "main" in str(exc_info.value)

    # === Priority Tests ===

    @pytest.mark.asyncio
    async def test_commit_takes_priority_over_branch(
        self, use_case: ResolveFileUseCase
    ) -> None:
        """Commit hash should take priority over branch when both specified."""
        request = ResolveFileRequest(
            repository_name="test-repo",
            file_path="src/main.py",
            commit_hash="abc123def456",  # Commit 1
            branch="feature",  # Should be ignored
        )

        response = await use_case.execute(request)

        # Should use commit, not branch
        assert response.file.content_hash == "hash1"
        assert response.commit.commit_hash.value == "abc123def456"

    # === Response Structure Tests ===

    @pytest.mark.asyncio
    async def test_response_includes_all_context(
        self, use_case: ResolveFileUseCase
    ) -> None:
        """Response should include file, commit, and repository."""
        request = ResolveFileRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        response = await use_case.execute(request)

        # File should be populated
        assert response.file is not None
        assert response.file.path == "src/main.py"

        # Commit should be populated
        assert response.commit is not None
        assert response.commit.id is not None

        # Repository should be populated
        assert response.repository is not None
        assert response.repository.name == "test-repo"


class TestResolveFileUseCaseEdgeCases:
    """Edge case tests for ResolveFileUseCase."""

    @pytest.mark.asyncio
    async def test_raises_commit_not_found_for_orphaned_file(self) -> None:
        """Should raise CommitNotFound if file references missing commit."""
        repository_repo = InMemoryRepositoryRepository()
        repository_repo.add(Repository(id=1, name="test-repo", url="/path"))

        commit_repo = InMemoryCommitRepository()
        # No commits added - file will reference missing commit

        file_repo = InMemoryFileRepository(commit_repo=commit_repo)
        file_repo.add(
            File(
                id=1,
                repository_id=1,
                path="orphan.py",
                content_hash="hash",
                size_bytes=100,
            )
        )

        use_case = ResolveFileUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
        )

        request = ResolveFileRequest(
            repository_name="test-repo",
            file_path="orphan.py",
        )

        with pytest.raises(CommitNotFound):
            await use_case.execute(request)
