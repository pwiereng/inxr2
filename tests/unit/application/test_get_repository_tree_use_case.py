"""Tests for GetRepositoryTreeUseCase - especially changed_only filtering."""

from datetime import datetime

import pytest

from inxr2.application.ports.services import ChangedFiles
from inxr2.application.use_cases.repositories.get_repository_tree import (
    GetRepositoryTreeRequest,
    GetRepositoryTreeUseCase,
)
from inxr2.domain.entities import Commit, File, Repository
from inxr2.domain.value_objects import CommitHash
from tests.fixtures.test_doubles import (
    FakeGitService,
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryRepositoryRepository,
)


class TestGetRepositoryTreeUseCaseChangedOnly:
    """Tests for changed_only filtering in GetRepositoryTreeUseCase.

    The changed_only=True parameter uses git to determine which files were
    actually changed at a commit (comparing against first parent), then
    filters the indexed tree to only show those files.
    """

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
        """Create commits for testing.

        Creates two commits:
        - commit1 (older): initial version of files
        - commit2 (newer): some files changed, some unchanged
        """
        repo = InMemoryCommitRepository()
        # Older commit
        repo.add(
            Commit(
                id=1,
                repository_id=1,
                commit_hash=CommitHash("a" * 40),
                author_date=datetime(2026, 1, 1, 10, 0, 0),
                commit_date=datetime(2026, 1, 1, 10, 0, 0),
            )
        )
        # Newer commit
        repo.add(
            Commit(
                id=2,
                repository_id=1,
                commit_hash=CommitHash("b" * 40),
                author_date=datetime(2026, 1, 2, 10, 0, 0),
                commit_date=datetime(2026, 1, 2, 10, 0, 0),
            )
        )
        return repo

    @pytest.fixture
    def file_repo(
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        """Create files across two commits.

        At commit1 (older):
        - file_a.py, file_b.py, file_c.py

        At commit2 (newer):
        - file_a.py (CHANGED), file_b.py (unchanged), file_c.py (unchanged),
          file_d.py (NEW)

        Git will report file_a.py as modified and file_d.py as added.
        """
        repo = InMemoryFileRepository(commit_repo=commit_repo)

        # Files at commit1 (older)
        repo.add(
            File(
                id=1,
                repository_id=1,
                path="file_a.py",
                content_hash="hash_a_v1",
                size_bytes=100,
                language="python",
            )
        )
        repo.add(
            File(
                id=2,
                repository_id=1,
                path="file_b.py",
                content_hash="hash_b_v1",
                size_bytes=100,
                language="python",
            )
        )
        repo.add(
            File(
                id=3,
                repository_id=1,
                path="file_c.py",
                content_hash="hash_c_v1",
                size_bytes=100,
                language="python",
            )
        )
        # Link commit 1 files
        repo._commit_files.update({(1, 1), (1, 2), (1, 3)})

        # Files at commit2 (newer) - full tree snapshot
        repo.add(
            File(
                id=4,
                repository_id=1,
                path="file_a.py",
                content_hash="hash_a_v2",  # CHANGED
                size_bytes=150,
                language="python",
            )
        )
        repo.add(
            File(
                id=5,
                repository_id=1,
                path="file_b.py",
                content_hash="hash_b_v1",  # UNCHANGED
                size_bytes=100,
                language="python",
            )
        )
        repo.add(
            File(
                id=6,
                repository_id=1,
                path="file_c.py",
                content_hash="hash_c_v1",  # UNCHANGED
                size_bytes=100,
                language="python",
            )
        )
        repo.add(
            File(
                id=7,
                repository_id=1,
                path="file_d.py",
                content_hash="hash_d_v1",  # NEW FILE
                size_bytes=200,
                language="python",
            )
        )
        # Link commit 2 files (full snapshot)
        repo._commit_files.update({(2, 4), (2, 5), (2, 6), (2, 7)})

        return repo

    @pytest.fixture
    def git_service(self) -> FakeGitService:
        """Create git service with changed files data."""
        service = FakeGitService()
        # commit2: file_a.py modified, file_d.py added
        service.changed_files_in_commit["b" * 40] = ChangedFiles(
            added=["file_d.py"],
            modified=["file_a.py"],
            deleted=[],
        )
        # commit1 (initial): all files are new
        service.changed_files_in_commit["a" * 40] = ChangedFiles(
            added=["file_a.py", "file_b.py", "file_c.py"],
            modified=[],
            deleted=[],
        )
        return service

    @pytest.mark.asyncio
    async def test_changed_only_returns_only_changed_files(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
        git_service: FakeGitService,
    ) -> None:
        """Test that changed_only=True returns only files git reports as changed."""
        use_case = GetRepositoryTreeUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

        request = GetRepositoryTreeRequest(
            repository_id=1,
            commit_hash="b" * 40,
            changed_only=True,
        )

        result = await use_case.execute(request)

        # Should only return 2 files: file_a.py (modified) and file_d.py (added)
        assert result.total_files == 2, (
            f"Expected 2 changed files, got {result.total_files}. "
            "The changed_only filter should use git to determine changed files."
        )

        file_paths = self._extract_file_paths(result.root)
        assert "file_a.py" in file_paths, "file_a.py should be included (modified)"
        assert "file_d.py" in file_paths, "file_d.py should be included (added)"
        assert "file_b.py" not in file_paths, "file_b.py should NOT be included"
        assert "file_c.py" not in file_paths, "file_c.py should NOT be included"

    @pytest.mark.asyncio
    async def test_changed_only_false_returns_all_files(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
        git_service: FakeGitService,
    ) -> None:
        """Test that changed_only=False returns all files at the commit."""
        use_case = GetRepositoryTreeUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

        request = GetRepositoryTreeRequest(
            repository_id=1,
            commit_hash="b" * 40,
            changed_only=False,
        )

        result = await use_case.execute(request)

        # Should return all 4 files at commit2
        assert (
            result.total_files == 4
        ), f"Expected 4 files (full tree), got {result.total_files}"

    @pytest.mark.asyncio
    async def test_changed_only_first_commit_returns_all_files(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
        git_service: FakeGitService,
    ) -> None:
        """Test that changed_only on first commit returns all files (all are new)."""
        use_case = GetRepositoryTreeUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

        request = GetRepositoryTreeRequest(
            repository_id=1,
            commit_hash="a" * 40,
            changed_only=True,
        )

        result = await use_case.execute(request)

        # First commit - git reports all files as added
        assert (
            result.total_files == 3
        ), f"Expected 3 files (all new at first commit), got {result.total_files}"

    @pytest.mark.asyncio
    async def test_changed_only_without_git_service_raises(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> None:
        """Test that changed_only=True without git_service raises ValueError."""
        use_case = GetRepositoryTreeUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
            # No git_service
        )

        request = GetRepositoryTreeRequest(
            repository_id=1,
            commit_hash="b" * 40,
            changed_only=True,
        )

        with pytest.raises(ValueError, match="git_service"):
            await use_case.execute(request)

    def _extract_file_paths(self, nodes: list) -> set[str]:
        """Recursively extract all file paths from tree nodes."""
        paths: set[str] = set()
        for node in nodes:
            if node.node_type == "file":
                paths.add(node.path)
            if node.children:
                paths.update(self._extract_file_paths(node.children))
        return paths
