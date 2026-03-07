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
    InMemoryFileVersionRepository,
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
        file_version_repo = InMemoryFileVersionRepository(file_repo)
        use_case = GetRepositoryTreeUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            file_version_repo=file_version_repo,
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
        file_version_repo = InMemoryFileVersionRepository(file_repo)
        use_case = GetRepositoryTreeUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            file_version_repo=file_version_repo,
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
        file_version_repo = InMemoryFileVersionRepository(file_repo)
        use_case = GetRepositoryTreeUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            file_version_repo=file_version_repo,
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
        file_version_repo = InMemoryFileVersionRepository(file_repo)
        use_case = GetRepositoryTreeUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            file_version_repo=file_version_repo,
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


class TestGetRepositoryTreeUseCaseGhostFiles:
    """Tests for ghost file filtering in GetRepositoryTreeUseCase.

    Ghost files appear when a file is renamed or deleted between commits.
    The indexed commit_files table may contain stale paths that no longer
    exist at the target commit. The use case should filter these out using
    git ls-tree as the source of truth.
    """

    @pytest.fixture
    def repository_repo(self) -> InMemoryRepositoryRepository:
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
        """Create two commits: before and after a file rename."""
        repo = InMemoryCommitRepository()
        repo.add(
            Commit(
                id=1,
                repository_id=1,
                commit_hash=CommitHash("a" * 40),
                author_date=datetime(2026, 1, 1, 10, 0, 0),
                commit_date=datetime(2026, 1, 1, 10, 0, 0),
            )
        )
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
        """Create files simulating a rename with ghost entries.

        At commit1: old_name.py, utils.py
        At commit2: new_name.py, utils.py
          BUT commit_files also incorrectly contains old_name.py (ghost)
        """
        repo = InMemoryFileRepository(commit_repo=commit_repo)

        # Files at commit1
        repo.add(
            File(
                id=1,
                repository_id=1,
                path="old_name.py",
                content_hash="hash_old",
                size_bytes=100,
                language="python",
            )
        )
        repo.add(
            File(
                id=2,
                repository_id=1,
                path="utils.py",
                content_hash="hash_utils",
                size_bytes=100,
                language="python",
            )
        )
        repo._commit_files.update({(1, 1), (1, 2)})

        # Files at commit2 - includes ghost: old_name.py still linked
        repo.add(
            File(
                id=3,
                repository_id=1,
                path="new_name.py",
                content_hash="hash_new",
                size_bytes=100,
                language="python",
            )
        )
        repo.add(
            File(
                id=4,
                repository_id=1,
                path="utils.py",
                content_hash="hash_utils",
                size_bytes=100,
                language="python",
            )
        )
        # Ghost: old_name.py (id=1) is still linked to commit2
        repo._commit_files.update({(2, 1), (2, 3), (2, 4)})

        return repo

    @pytest.fixture
    def git_service(self) -> FakeGitService:
        """Git service that knows the real file list at each commit."""
        service = FakeGitService()
        # commit2 only has new_name.py and utils.py (old_name.py was renamed)
        service.files_in_commit["b" * 40] = ["new_name.py", "utils.py"]
        service.files_in_commit["a" * 40] = ["old_name.py", "utils.py"]
        return service

    @pytest.mark.asyncio
    async def test_ghost_files_filtered_from_tree(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
        git_service: FakeGitService,
    ) -> None:
        """Ghost files from renamed/deleted paths should not appear in tree."""
        file_version_repo = InMemoryFileVersionRepository(file_repo)
        use_case = GetRepositoryTreeUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            file_version_repo=file_version_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

        request = GetRepositoryTreeRequest(
            repository_id=1,
            commit_hash="b" * 40,
        )

        result = await use_case.execute(request)

        file_paths = self._extract_file_paths(result.root)
        assert "new_name.py" in file_paths
        assert "utils.py" in file_paths
        assert "old_name.py" not in file_paths, (
            "Ghost file old_name.py should be filtered out — "
            "it was renamed to new_name.py and does not exist at this commit"
        )
        assert result.total_files == 2

    @pytest.mark.asyncio
    async def test_ghost_files_filtered_with_changed_only(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
        git_service: FakeGitService,
    ) -> None:
        """Ghost files should also be filtered when using changed_only mode."""
        file_version_repo = InMemoryFileVersionRepository(file_repo)

        # Set up changed_files for commit2
        git_service.changed_files_in_commit["b" * 40] = ChangedFiles(
            added=["new_name.py"],
            modified=[],
            deleted=["old_name.py"],
        )

        use_case = GetRepositoryTreeUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            file_version_repo=file_version_repo,
            commit_repo=commit_repo,
            git_service=git_service,
        )

        request = GetRepositoryTreeRequest(
            repository_id=1,
            commit_hash="b" * 40,
            changed_only=True,
        )

        result = await use_case.execute(request)

        file_paths = self._extract_file_paths(result.root)
        assert "new_name.py" in file_paths
        assert "old_name.py" not in file_paths

    @pytest.mark.asyncio
    async def test_tree_without_git_service_returns_unfiltered(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> None:
        """Without git_service, tree returns all indexed files (no filtering)."""
        file_version_repo = InMemoryFileVersionRepository(file_repo)
        use_case = GetRepositoryTreeUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            file_version_repo=file_version_repo,
            commit_repo=commit_repo,
            # No git_service - can't filter
        )

        request = GetRepositoryTreeRequest(
            repository_id=1,
            commit_hash="b" * 40,
        )

        result = await use_case.execute(request)

        # Without git_service, ghost files remain (graceful degradation)
        file_paths = self._extract_file_paths(result.root)
        assert "old_name.py" in file_paths
        assert "new_name.py" in file_paths
        assert result.total_files == 3

    def _extract_file_paths(self, nodes: list) -> set[str]:
        """Recursively extract all file paths from tree nodes."""
        paths: set[str] = set()
        for node in nodes:
            if node.node_type == "file":
                paths.add(node.path)
            if node.children:
                paths.update(self._extract_file_paths(node.children))
        return paths
