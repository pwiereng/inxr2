"""Tests for GetFileContentUseCase using dependency injection."""

from datetime import datetime
from pathlib import Path

import pytest

from inxr2.application.use_cases.files import (
    BinaryFileError,
    GetFileContentRequest,
    GetFileContentUseCase,
    RepositoryPathNotFoundError,
    ResolveFileUseCase,
)
from inxr2.domain.entities import Commit, File, Repository
from inxr2.domain.exceptions import FileNotFound, RepositoryNotFound
from inxr2.domain.value_objects import CommitHash
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryFileVersionRepository,
    InMemoryRepositoryRepository,
)


class StubGitContentService:
    """Stub git service for testing content retrieval."""

    def __init__(self) -> None:
        """Initialize with empty content map."""
        self._contents: dict[tuple[str, str, str], str] = {}
        self._binary_files: set[tuple[str, str, str]] = set()
        self._missing_files: set[tuple[str, str, str]] = set()

    def set_content(
        self, repo_path: str, commit_hash: str, file_path: str, content: str
    ) -> None:
        """Set content to return for a file."""
        key = (repo_path, commit_hash, file_path)
        self._contents[key] = content

    def set_binary(self, repo_path: str, commit_hash: str, file_path: str) -> None:
        """Mark a file as binary (will raise UnicodeDecodeError)."""
        key = (repo_path, commit_hash, file_path)
        self._binary_files.add(key)

    def set_missing(self, repo_path: str, commit_hash: str, file_path: str) -> None:
        """Mark a file as missing (will raise FileNotFoundError)."""
        key = (repo_path, commit_hash, file_path)
        self._missing_files.add(key)

    def get_file_content(
        self, repo_path: Path, commit_hash: str, file_path: str
    ) -> str:
        """Return predefined content or raise errors."""
        key = (str(repo_path), commit_hash, file_path)

        if key in self._missing_files:
            raise FileNotFoundError(f"File not found: {file_path}")

        if key in self._binary_files:
            raise UnicodeDecodeError("utf-8", b"\x00", 0, 1, "binary file")

        return self._contents.get(key, "")


class TestGetFileContentUseCase:
    """Tests for GetFileContentUseCase."""

    @pytest.fixture
    def repository_repo(self, tmp_path: Path) -> InMemoryRepositoryRepository:
        """Create repository with test data."""
        # Create actual directory for the repository path
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()

        repo = InMemoryRepositoryRepository()
        repo.add(
            Repository(
                id=1,
                name="test-repo",
                url=str(repo_path),
                default_branch="main",
            )
        )
        return repo

    @pytest.fixture
    def commit_repo(self) -> InMemoryCommitRepository:
        """Create commit repository with test data."""
        repo = InMemoryCommitRepository()

        commit = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("abc123def456"),
            author_date=datetime(2025, 1, 1, 12, 0, 0),
            commit_date=datetime(2025, 1, 1, 12, 0, 0),
        )
        repo._commits[1] = commit
        repo._branch_commits[(1, "main", 1)] = True

        return repo

    @pytest.fixture
    def file_repo(
        self, commit_repo: InMemoryCommitRepository
    ) -> InMemoryFileRepository:
        """Create file repository with test data."""
        repo = InMemoryFileRepository(commit_repo=commit_repo)

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

        return repo

    @pytest.fixture
    def git_service(self, tmp_path: Path) -> StubGitContentService:
        """Create stub git service with test content."""
        repo_path = tmp_path / "test-repo"
        service = StubGitContentService()
        service.set_content(
            str(repo_path),
            "abc123def456",
            "src/main.py",
            "def main():\n    print('hello')\n",
        )
        return service

    @pytest.fixture
    def resolve_file_use_case(
        self,
        repository_repo: InMemoryRepositoryRepository,
        file_repo: InMemoryFileRepository,
        commit_repo: InMemoryCommitRepository,
    ) -> ResolveFileUseCase:
        """Create ResolveFileUseCase with test repositories."""
        return ResolveFileUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            file_version_repo=InMemoryFileVersionRepository(file_repo),
            commit_repo=commit_repo,
        )

    @pytest.fixture
    def use_case(
        self,
        resolve_file_use_case: ResolveFileUseCase,
        git_service: StubGitContentService,
    ) -> GetFileContentUseCase:
        """Create use case with test dependencies."""
        return GetFileContentUseCase(
            resolve_file_use_case=resolve_file_use_case,
            git_service=git_service,
        )

    # === Basic Content Retrieval Tests ===

    @pytest.mark.asyncio
    async def test_get_file_content_by_name_and_path(
        self, use_case: GetFileContentUseCase
    ) -> None:
        """Should get file content by repository name and path."""
        request = GetFileContentRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        result = await use_case.execute(request)

        assert result.content == "def main():\n    print('hello')\n"
        assert result.file.path == "src/main.py"
        assert result.repository.name == "test-repo"

    @pytest.mark.asyncio
    async def test_returns_correct_line_count(
        self, use_case: GetFileContentUseCase
    ) -> None:
        """Should calculate correct line count."""
        request = GetFileContentRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        result = await use_case.execute(request)

        # Content: "def main():\n    print('hello')\n" = 2 lines
        assert result.line_count == 2

    @pytest.mark.asyncio
    async def test_returns_correct_size_bytes(
        self, use_case: GetFileContentUseCase
    ) -> None:
        """Should calculate correct size in bytes."""
        request = GetFileContentRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        result = await use_case.execute(request)

        expected_size = len(b"def main():\n    print('hello')\n")
        assert result.size_bytes == expected_size

    @pytest.mark.asyncio
    async def test_includes_file_metadata(
        self, use_case: GetFileContentUseCase
    ) -> None:
        """Should include file, commit, and repository in response."""
        request = GetFileContentRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        result = await use_case.execute(request)

        assert result.file is not None
        assert result.file.language == "Python"
        assert result.commit is not None
        assert result.commit.commit_hash.value == "abc123def456"
        assert result.repository is not None
        assert result.repository.name == "test-repo"

    # === Error Handling Tests ===

    @pytest.mark.asyncio
    async def test_raises_repository_not_found(
        self, use_case: GetFileContentUseCase
    ) -> None:
        """Should raise RepositoryNotFound for unknown repository."""
        request = GetFileContentRequest(
            repository_name="unknown-repo",
            file_path="src/main.py",
        )

        with pytest.raises(RepositoryNotFound):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_raises_file_not_found(self, use_case: GetFileContentUseCase) -> None:
        """Should raise FileNotFound for unknown file path."""
        request = GetFileContentRequest(
            repository_name="test-repo",
            file_path="nonexistent/file.py",
        )

        with pytest.raises(FileNotFound):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_raises_binary_file_error(
        self,
        resolve_file_use_case: ResolveFileUseCase,
        tmp_path: Path,
    ) -> None:
        """Should raise BinaryFileError for binary files."""
        repo_path = tmp_path / "test-repo"
        git_service = StubGitContentService()
        git_service.set_binary(str(repo_path), "abc123def456", "src/main.py")

        use_case = GetFileContentUseCase(
            resolve_file_use_case=resolve_file_use_case,
            git_service=git_service,
        )

        request = GetFileContentRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        with pytest.raises(BinaryFileError) as exc_info:
            await use_case.execute(request)

        assert "src/main.py" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_repository_path_not_found(
        self,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
        git_service: StubGitContentService,
    ) -> None:
        """Should raise RepositoryPathNotFoundError if path doesn't exist."""
        # Create repository with non-existent path
        repository_repo = InMemoryRepositoryRepository()
        repository_repo.add(
            Repository(
                id=1,
                name="test-repo",
                url="/nonexistent/path",
                default_branch="main",
            )
        )

        resolve_use_case = ResolveFileUseCase(
            repository_repo=repository_repo,
            file_repo=file_repo,
            file_version_repo=InMemoryFileVersionRepository(file_repo),
            commit_repo=commit_repo,
        )

        use_case = GetFileContentUseCase(
            resolve_file_use_case=resolve_use_case,
            git_service=git_service,
        )

        request = GetFileContentRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        with pytest.raises(RepositoryPathNotFoundError) as exc_info:
            await use_case.execute(request)

        assert "/nonexistent/path" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_value_error_without_required_params(
        self, use_case: GetFileContentUseCase
    ) -> None:
        """Should raise ValueError when required params are missing."""
        request = GetFileContentRequest()

        with pytest.raises(ValueError) as exc_info:
            await use_case.execute(request)

        assert "repository_name" in str(exc_info.value)

    # === Line Counting Edge Cases ===

    @pytest.mark.asyncio
    async def test_line_count_empty_file(
        self,
        resolve_file_use_case: ResolveFileUseCase,
        tmp_path: Path,
    ) -> None:
        """Should return 0 lines for empty file."""
        repo_path = tmp_path / "test-repo"
        git_service = StubGitContentService()
        git_service.set_content(str(repo_path), "abc123def456", "src/main.py", "")

        use_case = GetFileContentUseCase(
            resolve_file_use_case=resolve_file_use_case,
            git_service=git_service,
        )

        request = GetFileContentRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        result = await use_case.execute(request)

        assert result.line_count == 0
        assert result.content == ""

    @pytest.mark.asyncio
    async def test_line_count_no_trailing_newline(
        self,
        resolve_file_use_case: ResolveFileUseCase,
        tmp_path: Path,
    ) -> None:
        """Should count lines correctly when file has no trailing newline."""
        repo_path = tmp_path / "test-repo"
        git_service = StubGitContentService()
        git_service.set_content(
            str(repo_path), "abc123def456", "src/main.py", "line1\nline2"
        )

        use_case = GetFileContentUseCase(
            resolve_file_use_case=resolve_file_use_case,
            git_service=git_service,
        )

        request = GetFileContentRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        result = await use_case.execute(request)

        # "line1\nline2" = 2 lines (no trailing newline)
        assert result.line_count == 2

    @pytest.mark.asyncio
    async def test_line_count_single_line_with_newline(
        self,
        resolve_file_use_case: ResolveFileUseCase,
        tmp_path: Path,
    ) -> None:
        """Should count single line with trailing newline correctly."""
        repo_path = tmp_path / "test-repo"
        git_service = StubGitContentService()
        git_service.set_content(
            str(repo_path), "abc123def456", "src/main.py", "single line\n"
        )

        use_case = GetFileContentUseCase(
            resolve_file_use_case=resolve_file_use_case,
            git_service=git_service,
        )

        request = GetFileContentRequest(
            repository_name="test-repo",
            file_path="src/main.py",
        )

        result = await use_case.execute(request)

        # "single line\n" = 1 line
        assert result.line_count == 1
