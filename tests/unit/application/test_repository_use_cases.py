"""Tests for repository use cases."""

from datetime import datetime

import pytest

from inxr2.application.ports.services import ChangedFiles
from inxr2.application.use_cases.repositories.get_repository_files import (
    GetRepositoryFilesRequest,
    GetRepositoryFilesUseCase,
)
from inxr2.application.use_cases.repositories.get_repository_tree import (
    GetRepositoryTreeRequest,
    GetRepositoryTreeUseCase,
)
from inxr2.application.use_cases.repositories.list_repositories import (
    ListRepositoriesUseCase,
)
from inxr2.domain.entities import Commit, File, Repository
from inxr2.domain.value_objects import CommitHash
from tests.fixtures.test_doubles import (
    FakeGitService,
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
        assert repo.id is not None

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
        assert repo.id is not None

        # Create commit
        commit = await commit_repository.save(
            Commit(
                repository_id=repo.id,
                commit_hash=CommitHash("abc123" + "0" * 34),
                author_date=datetime(2025, 1, 1, 12, 0, 0),
                commit_date=datetime(2025, 1, 1, 12, 0, 0),
            )
        )
        assert commit.id is not None

        # Create files
        await file_repository.save(
            File(
                repository_id=repo.id,
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
        assert repo1.id is not None
        repo2 = await repo_repository.save(
            Repository(name="repo2", url="https://example.com/repo2.git")
        )
        assert repo2.id is not None

        # Create commits
        commit1 = await commit_repository.save(
            Commit(
                repository_id=repo1.id,
                commit_hash=CommitHash("abc123" + "0" * 34),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        assert commit1.id is not None
        commit2 = await commit_repository.save(
            Commit(
                repository_id=repo2.id,
                commit_hash=CommitHash("def456" + "0" * 34),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        assert commit2.id is not None

        # Add files to both repositories
        await file_repository.save(
            File(
                repository_id=repo1.id,
                path="file1.py",
                content_hash="hash1",
                size_bytes=100,
            )
        )
        await file_repository.save(
            File(
                repository_id=repo1.id,
                path="file2.py",
                content_hash="hash2",
                size_bytes=200,
            )
        )
        await file_repository.save(
            File(
                repository_id=repo2.id,
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


class TestGetRepositoryTreeUseCase:
    """Tests for GetRepositoryTreeUseCase."""

    @pytest.mark.asyncio
    async def test_get_tree_for_nonexistent_repository_by_id(self) -> None:
        """Test getting tree for a repository that doesn't exist by ID."""
        repo_repository = InMemoryRepositoryRepository()
        file_repository = InMemoryFileRepository()
        use_case = GetRepositoryTreeUseCase(
            repository_repo=repo_repository,
            file_repo=file_repository,
        )

        with pytest.raises(ValueError, match="Repository not found"):
            await use_case.execute(GetRepositoryTreeRequest(repository_id=999))

    @pytest.mark.asyncio
    async def test_get_tree_for_nonexistent_repository_by_name(self) -> None:
        """Test getting tree for a repository that doesn't exist by name."""
        repo_repository = InMemoryRepositoryRepository()
        file_repository = InMemoryFileRepository()
        use_case = GetRepositoryTreeUseCase(
            repository_repo=repo_repository,
            file_repo=file_repository,
        )

        with pytest.raises(ValueError, match="Repository not found"):
            await use_case.execute(
                GetRepositoryTreeRequest(repository_name="nonexistent")
            )

    @pytest.mark.asyncio
    async def test_get_tree_for_empty_repository(self) -> None:
        """Test getting tree for a repository with no files."""
        repo_repository = InMemoryRepositoryRepository()
        file_repository = InMemoryFileRepository()

        repo = await repo_repository.save(
            Repository(name="test-repo", url="https://example.com/repo.git")
        )

        use_case = GetRepositoryTreeUseCase(
            repository_repo=repo_repository,
            file_repo=file_repository,
        )

        result = await use_case.execute(GetRepositoryTreeRequest(repository_id=repo.id))

        assert result.repository_id == repo.id
        assert result.repository_name == "test-repo"
        assert result.root == []
        assert result.total_files == 0
        assert result.total_directories == 0

    @pytest.mark.asyncio
    async def test_get_tree_builds_hierarchy(self) -> None:
        """Test that tree structure is built correctly from flat file paths."""
        repo_repository = InMemoryRepositoryRepository()
        file_repository = InMemoryFileRepository()
        commit_repository = InMemoryCommitRepository()

        repo = await repo_repository.save(
            Repository(name="test-repo", url="https://example.com/repo.git")
        )
        assert repo.id is not None

        commit = await commit_repository.save(
            Commit(
                repository_id=repo.id,
                commit_hash=CommitHash("abc123" + "0" * 34),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        assert commit.id is not None

        # Create files in nested structure
        await file_repository.save(
            File(
                repository_id=repo.id,
                path="src/main.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            )
        )
        await file_repository.save(
            File(
                repository_id=repo.id,
                path="src/utils/helper.py",
                content_hash="hash2",
                size_bytes=200,
                language="python",
            )
        )
        await file_repository.save(
            File(
                repository_id=repo.id,
                path="README.md",
                content_hash="hash3",
                size_bytes=50,
                language="markdown",
            )
        )

        use_case = GetRepositoryTreeUseCase(
            repository_repo=repo_repository,
            file_repo=file_repository,
        )

        result = await use_case.execute(GetRepositoryTreeRequest(repository_id=repo.id))

        assert result.total_files == 3
        assert result.total_directories == 2  # src, src/utils

        # Check root level: should have src directory and README.md file
        root_names = {node.name for node in result.root}
        assert root_names == {"src", "README.md"}

        # Find src directory
        src_node = next(n for n in result.root if n.name == "src")
        assert src_node.node_type == "directory"
        assert len(src_node.children) == 2  # main.py and utils

        # Find README
        readme_node = next(n for n in result.root if n.name == "README.md")
        assert readme_node.node_type == "file"
        assert readme_node.language == "markdown"

    @pytest.mark.asyncio
    async def test_get_tree_sorts_directories_first(self) -> None:
        """Test that directories are sorted before files."""
        repo_repository = InMemoryRepositoryRepository()
        file_repository = InMemoryFileRepository()
        commit_repository = InMemoryCommitRepository()

        repo = await repo_repository.save(
            Repository(name="test-repo", url="https://example.com/repo.git")
        )
        assert repo.id is not None

        commit = await commit_repository.save(
            Commit(
                repository_id=repo.id,
                commit_hash=CommitHash("abc123" + "0" * 34),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        assert commit.id is not None

        # Create files: alphabetically "app.py" comes before "src"
        # but directories should be listed first
        await file_repository.save(
            File(
                repository_id=repo.id,
                path="app.py",
                content_hash="hash1",
                size_bytes=100,
            )
        )
        await file_repository.save(
            File(
                repository_id=repo.id,
                path="src/main.py",
                content_hash="hash2",
                size_bytes=100,
            )
        )
        await file_repository.save(
            File(
                repository_id=repo.id,
                path="zebra.txt",
                content_hash="hash3",
                size_bytes=100,
            )
        )

        use_case = GetRepositoryTreeUseCase(
            repository_repo=repo_repository,
            file_repo=file_repository,
        )

        result = await use_case.execute(GetRepositoryTreeRequest(repository_id=repo.id))

        # Directories first, then files (alphabetically within each group)
        assert result.root[0].name == "src"
        assert result.root[0].node_type == "directory"
        assert result.root[1].name == "app.py"
        assert result.root[1].node_type == "file"
        assert result.root[2].name == "zebra.txt"
        assert result.root[2].node_type == "file"

    @pytest.mark.asyncio
    async def test_get_tree_by_name(self) -> None:
        """Test getting tree using repository name instead of ID."""
        repo_repository = InMemoryRepositoryRepository()
        file_repository = InMemoryFileRepository()
        commit_repository = InMemoryCommitRepository()

        repo = await repo_repository.save(
            Repository(name="my-repo", url="https://example.com/repo.git")
        )
        assert repo.id is not None

        commit = await commit_repository.save(
            Commit(
                repository_id=repo.id,
                commit_hash=CommitHash("abc123" + "0" * 34),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        assert commit.id is not None

        await file_repository.save(
            File(
                repository_id=repo.id,
                path="index.js",
                content_hash="hash1",
                size_bytes=100,
            )
        )

        use_case = GetRepositoryTreeUseCase(
            repository_repo=repo_repository,
            file_repo=file_repository,
        )

        # Use repository_name instead of repository_id
        result = await use_case.execute(
            GetRepositoryTreeRequest(repository_name="my-repo")
        )

        assert result.repository_id == repo.id
        assert result.repository_name == "my-repo"
        assert result.total_files == 1

    @pytest.mark.asyncio
    async def test_request_requires_id_or_name(self) -> None:
        """Test that request requires either repository_id or repository_name."""
        with pytest.raises(ValueError, match="Either repository_id or repository_name"):
            GetRepositoryTreeRequest()

    @pytest.mark.asyncio
    async def test_get_tree_at_specific_commit(self) -> None:
        """Test getting tree at a specific commit (time travel)."""
        repo_repository = InMemoryRepositoryRepository()
        commit_repository = InMemoryCommitRepository()
        file_repository = InMemoryFileRepository(commit_repo=commit_repository)

        repo = await repo_repository.save(
            Repository(name="test-repo", url="https://example.com/repo.git")
        )
        assert repo.id is not None

        # Create two commits
        commit1 = await commit_repository.save(
            Commit(
                repository_id=repo.id,
                commit_hash=CommitHash("aaa111" + "0" * 34),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        assert commit1.id is not None
        commit2 = await commit_repository.save(
            Commit(
                repository_id=repo.id,
                commit_hash=CommitHash("bbb222" + "0" * 34),
                author_date=datetime(2025, 1, 2),
                commit_date=datetime(2025, 1, 2),
            )
        )
        assert commit2.id is not None

        # Files at commit 1: only app.py exists
        f1 = await file_repository.save(
            File(
                repository_id=repo.id,
                path="app.py",
                content_hash="hash1",
                size_bytes=100,
            )
        )
        assert f1.id is not None
        await file_repository.link_file_to_commit(f1.id, commit1.id)

        # Files at commit 2: app.py (updated) and new_feature.py exist
        f2 = await file_repository.save(
            File(
                repository_id=repo.id,
                path="app.py",
                content_hash="hash1_v2",
                size_bytes=150,
            )
        )
        f3 = await file_repository.save(
            File(
                repository_id=repo.id,
                path="new_feature.py",
                content_hash="hash2",
                size_bytes=200,
            )
        )
        assert f2.id is not None and f3.id is not None
        await file_repository.link_files_to_commit([f2.id, f3.id], commit2.id)

        use_case = GetRepositoryTreeUseCase(
            repository_repo=repo_repository,
            file_repo=file_repository,
            commit_repo=commit_repository,
        )

        # Get tree at commit 1 - should only have app.py
        result1 = await use_case.execute(
            GetRepositoryTreeRequest(
                repository_id=repo.id,
                commit_hash="aaa111" + "0" * 34,
            )
        )
        assert result1.total_files == 1
        assert result1.root[0].name == "app.py"

        # Get tree at commit 2 - should have both files
        result2 = await use_case.execute(
            GetRepositoryTreeRequest(
                repository_id=repo.id,
                commit_hash="bbb222" + "0" * 34,
            )
        )
        assert result2.total_files == 2
        file_names = {node.name for node in result2.root}
        assert file_names == {"app.py", "new_feature.py"}

    @pytest.mark.asyncio
    async def test_get_tree_with_invalid_commit(self) -> None:
        """Test that getting tree with invalid commit raises error."""
        repo_repository = InMemoryRepositoryRepository()
        file_repository = InMemoryFileRepository()
        commit_repository = InMemoryCommitRepository()

        repo = await repo_repository.save(
            Repository(name="test-repo", url="https://example.com/repo.git")
        )

        use_case = GetRepositoryTreeUseCase(
            repository_repo=repo_repository,
            file_repo=file_repository,
            commit_repo=commit_repository,
        )

        with pytest.raises(ValueError, match="Commit not found"):
            await use_case.execute(
                GetRepositoryTreeRequest(
                    repository_id=repo.id,
                    commit_hash="nonexistent" + "0" * 30,
                )
            )

    @pytest.mark.asyncio
    async def test_get_tree_with_commit_hash_but_no_commit_repo(self) -> None:
        """Test that commit_hash without commit_repo raises informative error."""
        repo_repository = InMemoryRepositoryRepository()
        file_repository = InMemoryFileRepository()

        repo = await repo_repository.save(
            Repository(name="test-repo", url="https://example.com/repo.git")
        )

        # Create use case WITHOUT commit_repo
        use_case = GetRepositoryTreeUseCase(
            repository_repo=repo_repository,
            file_repo=file_repository,
            commit_repo=None,  # No commit repo provided
        )

        with pytest.raises(ValueError, match="Time travel requires commit repository"):
            await use_case.execute(
                GetRepositoryTreeRequest(
                    repository_id=repo.id,
                    commit_hash="abc123" + "0" * 34,  # commit_hash provided
                )
            )

    @pytest.mark.asyncio
    async def test_get_tree_changed_only_shows_files_at_commit(self) -> None:
        """Test changed_only=True shows only files changed at that commit."""
        repo_repository = InMemoryRepositoryRepository()
        commit_repository = InMemoryCommitRepository()
        file_repository = InMemoryFileRepository(commit_repo=commit_repository)

        repo = await repo_repository.save(
            Repository(name="test-repo", url="https://example.com/repo.git")
        )
        assert repo.id is not None

        # Create two commits
        commit1 = await commit_repository.save(
            Commit(
                repository_id=repo.id,
                commit_hash=CommitHash("aaa111" + "0" * 34),
                commit_date=datetime(2024, 1, 1, 12, 0, 0),
                author_date=datetime(2024, 1, 1, 12, 0, 0),
            )
        )
        commit2 = await commit_repository.save(
            Commit(
                repository_id=repo.id,
                commit_hash=CommitHash("bbb222" + "0" * 34),
                commit_date=datetime(2024, 1, 2, 12, 0, 0),
                author_date=datetime(2024, 1, 2, 12, 0, 0),
            )
        )
        assert commit1.id is not None
        assert commit2.id is not None

        # Commit 1: adds app.py
        file_repository.add(
            File(
                id=1,
                repository_id=repo.id,
                path="app.py",
                content_hash="hash1",
                size_bytes=100,
            )
        )
        file_repository._commit_files.add((commit1.id, 1))

        # Commit 2: adds utils.py, app.py still present (full snapshot)
        file_repository._commit_files.add((commit2.id, 1))  # app.py at commit 2
        file_repository.add(
            File(
                id=2,
                repository_id=repo.id,
                path="utils.py",
                content_hash="hash2",
                size_bytes=200,
            )
        )
        file_repository._commit_files.add((commit2.id, 2))  # utils.py at commit 2

        # Git service reports utils.py as added at commit2
        git_service = FakeGitService()
        git_service.changed_files_in_commit["bbb222" + "0" * 34] = ChangedFiles(
            added=["utils.py"],
            modified=[],
            deleted=[],
        )

        use_case = GetRepositoryTreeUseCase(
            repository_repo=repo_repository,
            file_repo=file_repository,
            commit_repo=commit_repository,
            git_service=git_service,
        )

        # changed_only=True at commit2: should only show utils.py (changed at commit2)
        result_changed = await use_case.execute(
            GetRepositoryTreeRequest(
                repository_id=repo.id,
                commit_hash="bbb222" + "0" * 34,
                changed_only=True,
            )
        )
        assert result_changed.total_files == 1
        assert result_changed.root[0].name == "utils.py"

        # changed_only=False at commit2: should show full tree (both files)
        result_full = await use_case.execute(
            GetRepositoryTreeRequest(
                repository_id=repo.id,
                commit_hash="bbb222" + "0" * 34,
                changed_only=False,
            )
        )
        assert result_full.total_files == 2
        paths = {node.name for node in result_full.root}
        assert paths == {"app.py", "utils.py"}

    @pytest.mark.asyncio
    async def test_get_tree_changed_only_requires_commit_hash(self) -> None:
        """Test that changed_only without commit_hash uses default behavior."""
        repo_repository = InMemoryRepositoryRepository()
        file_repository = InMemoryFileRepository()

        repo = await repo_repository.save(
            Repository(name="test-repo", url="https://example.com/repo.git")
        )
        assert repo.id is not None

        file_repository.add(
            File(
                id=1,
                repository_id=repo.id,
                path="app.py",
                content_hash="hash1",
                size_bytes=100,
            )
        )

        use_case = GetRepositoryTreeUseCase(
            repository_repo=repo_repository,
            file_repo=file_repository,
        )

        # changed_only=True but no commit_hash: should use default behavior (list all)
        result = await use_case.execute(
            GetRepositoryTreeRequest(
                repository_id=repo.id,
                changed_only=True,  # This is ignored without commit_hash
            )
        )
        assert result.total_files == 1
