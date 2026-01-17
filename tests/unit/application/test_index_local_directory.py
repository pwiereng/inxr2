"""Tests for IndexLocalDirectoryUseCase."""

from pathlib import Path

import pytest

from inxr2.application.use_cases.indexing.index_local_directory import (
    IndexLocalDirectoryRequest,
    IndexLocalDirectoryUseCase,
)
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryRepositoryRepository,
)


class TestIndexLocalDirectoryUseCase:
    """Tests for IndexLocalDirectoryUseCase."""

    @pytest.mark.asyncio
    async def test_index_empty_directory(self, tmp_path: Path) -> None:
        """Test indexing an empty directory."""
        # Arrange
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        repo_repo = InMemoryRepositoryRepository()
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository()

        use_case = IndexLocalDirectoryUseCase(
            repository_repo=repo_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )

        # Act
        result = await use_case.execute(
            IndexLocalDirectoryRequest(
                path=str(empty_dir),
                name="empty-repo",
                description="Empty test repository",
            )
        )

        # Assert
        assert result.total_files == 0
        assert result.indexed_files == 0
        assert result.skipped_files == 0

        # Verify repository was created
        repo = await repo_repo.find_by_id(result.repository_id)
        assert repo is not None
        assert repo.name == "empty-repo"
        assert repo.description == "Empty test repository"

    @pytest.mark.asyncio
    async def test_index_directory_with_text_files(self, tmp_path: Path) -> None:
        """Test indexing a directory with text files."""
        # Arrange - create test files
        test_dir = tmp_path / "test-repo"
        test_dir.mkdir()

        # Create some Python files
        (test_dir / "main.py").write_text("print('hello')\n")
        (test_dir / "utils.py").write_text("def helper():\n    pass\n")

        # Create a markdown file
        (test_dir / "README.md").write_text("# Test\n\nDescription\n")

        repo_repo = InMemoryRepositoryRepository()
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository()

        use_case = IndexLocalDirectoryUseCase(
            repository_repo=repo_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )

        # Act
        result = await use_case.execute(
            IndexLocalDirectoryRequest(path=str(test_dir), name="test-repo")
        )

        # Assert
        assert result.total_files == 3
        assert result.indexed_files == 3
        assert result.skipped_files == 0

        # Verify files were indexed
        files = await file_repo.list_by_repository(result.repository_id)
        assert len(files) == 3

        # Verify file details
        paths = {f.path for f in files}
        assert paths == {"main.py", "utils.py", "README.md"}

        # Verify languages detected
        languages = {f.path: f.language for f in files}
        assert languages["main.py"] == "python"
        assert languages["utils.py"] == "python"
        assert languages["README.md"] == "markdown"

        # Verify line counts
        line_counts = {f.path: f.line_count for f in files}
        assert line_counts["main.py"] == 1
        assert line_counts["utils.py"] == 2
        assert line_counts["README.md"] == 3

    @pytest.mark.asyncio
    async def test_index_skips_excluded_directories(self, tmp_path: Path) -> None:
        """Test that excluded directories are skipped."""
        # Arrange - create directory structure with excluded dirs
        test_dir = tmp_path / "project"
        test_dir.mkdir()

        # Create files in main directory
        (test_dir / "main.py").write_text("main")

        # Create excluded directories with files
        node_modules = test_dir / "node_modules"
        node_modules.mkdir()
        (node_modules / "package.js").write_text("// should skip")

        venv = test_dir / "venv"
        venv.mkdir()
        (venv / "activate").write_text("# should skip")

        git_dir = test_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("should skip")

        pycache = test_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "module.pyc").write_text("skip")

        # Create valid subdirectory
        src = test_dir / "src"
        src.mkdir()
        (src / "app.py").write_text("app")

        repo_repo = InMemoryRepositoryRepository()
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository()

        use_case = IndexLocalDirectoryUseCase(
            repository_repo=repo_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )

        # Act
        result = await use_case.execute(
            IndexLocalDirectoryRequest(path=str(test_dir), name="project")
        )

        # Assert - should only index files in main dir and src/
        files = await file_repo.list_by_repository(result.repository_id)
        paths = {f.path for f in files}

        # Should include main.py and src/app.py
        assert "main.py" in paths
        assert "src/app.py" in paths

        # Should NOT include files from excluded directories
        assert "node_modules/package.js" not in paths
        assert "venv/activate" not in paths
        assert ".git/config" not in paths
        assert "__pycache__/module.pyc" not in paths

        # Only 2 files should be indexed
        assert len(files) == 2

    @pytest.mark.asyncio
    async def test_index_skips_binary_files(self, tmp_path: Path) -> None:
        """Test that binary files are skipped."""
        # Arrange
        test_dir = tmp_path / "binary-test"
        test_dir.mkdir()

        # Create text files
        (test_dir / "script.py").write_text("print('hello')")
        (test_dir / "README.md").write_text("# Readme")

        # Create binary files (will be detected by extension)
        (test_dir / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (test_dir / "program.exe").write_bytes(b"MZ\x90\x00")
        (test_dir / "archive.zip").write_bytes(b"PK\x03\x04")

        repo_repo = InMemoryRepositoryRepository()
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository()

        use_case = IndexLocalDirectoryUseCase(
            repository_repo=repo_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )

        # Act
        result = await use_case.execute(
            IndexLocalDirectoryRequest(path=str(test_dir), name="binary-test")
        )

        # Assert
        assert result.total_files == 5
        assert result.indexed_files == 2  # Only text files
        assert result.skipped_files == 3  # Binary files skipped

        files = await file_repo.list_by_repository(result.repository_id)
        paths = {f.path for f in files}

        assert "script.py" in paths
        assert "README.md" in paths
        assert "image.png" not in paths
        assert "program.exe" not in paths
        assert "archive.zip" not in paths

    @pytest.mark.asyncio
    async def test_index_creates_commit(self, tmp_path: Path) -> None:
        """Test that a commit is created during indexing."""
        # Arrange
        test_dir = tmp_path / "commit-test"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")

        repo_repo = InMemoryRepositoryRepository()
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository()

        use_case = IndexLocalDirectoryUseCase(
            repository_repo=repo_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )

        # Act
        result = await use_case.execute(
            IndexLocalDirectoryRequest(path=str(test_dir), name="commit-test")
        )

        # Assert
        commits = await commit_repo.list_by_repository(result.repository_id)
        assert len(commits) == 1

        commit = commits[0]
        assert commit.repository_id == result.repository_id
        assert commit.branch == "local"
        assert commit.author_name == "local"
        assert commit.message == "Local directory index"
        assert commit.parent_hashes is None or commit.parent_hashes == []

    @pytest.mark.asyncio
    async def test_index_calculates_content_hash(self, tmp_path: Path) -> None:
        """Test that content hashes are calculated for files."""
        # Arrange
        test_dir = tmp_path / "hash-test"
        test_dir.mkdir()

        file_content = "print('test content')\n"
        (test_dir / "test.py").write_text(file_content)

        repo_repo = InMemoryRepositoryRepository()
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository()

        use_case = IndexLocalDirectoryUseCase(
            repository_repo=repo_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )

        # Act
        result = await use_case.execute(
            IndexLocalDirectoryRequest(path=str(test_dir), name="hash-test")
        )

        # Assert
        files = await file_repo.list_by_repository(result.repository_id)
        assert len(files) == 1

        file = files[0]
        assert file.content_hash is not None
        assert len(file.content_hash) == 40  # SHA1 hex digest length

    @pytest.mark.asyncio
    async def test_index_nested_directories(self, tmp_path: Path) -> None:
        """Test indexing deeply nested directory structures."""
        # Arrange
        test_dir = tmp_path / "nested"
        test_dir.mkdir()

        # Create nested structure
        (test_dir / "level1").mkdir()
        (test_dir / "level1" / "file1.py").write_text("level 1")

        (test_dir / "level1" / "level2").mkdir()
        (test_dir / "level1" / "level2" / "file2.py").write_text("level 2")

        (test_dir / "level1" / "level2" / "level3").mkdir()
        (test_dir / "level1" / "level2" / "level3" / "file3.py").write_text("level 3")

        repo_repo = InMemoryRepositoryRepository()
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository()

        use_case = IndexLocalDirectoryUseCase(
            repository_repo=repo_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )

        # Act
        result = await use_case.execute(
            IndexLocalDirectoryRequest(path=str(test_dir), name="nested")
        )

        # Assert
        assert result.indexed_files == 3

        files = await file_repo.list_by_repository(result.repository_id)
        paths = {f.path for f in files}

        assert "level1/file1.py" in paths
        assert "level1/level2/file2.py" in paths
        assert "level1/level2/level3/file3.py" in paths

    @pytest.mark.asyncio
    async def test_index_sets_file_sizes(self, tmp_path: Path) -> None:
        """Test that file sizes are correctly recorded."""
        # Arrange
        test_dir = tmp_path / "size-test"
        test_dir.mkdir()

        small_content = "x"
        (test_dir / "small.txt").write_text(small_content)

        large_content = "x" * 1000
        (test_dir / "large.txt").write_text(large_content)

        repo_repo = InMemoryRepositoryRepository()
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository()

        use_case = IndexLocalDirectoryUseCase(
            repository_repo=repo_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )

        # Act
        result = await use_case.execute(
            IndexLocalDirectoryRequest(path=str(test_dir), name="size-test")
        )

        # Assert
        files = await file_repo.list_by_repository(result.repository_id)
        sizes = {f.path: f.size_bytes for f in files}

        assert sizes["small.txt"] == len(small_content.encode("utf-8"))
        assert sizes["large.txt"] == len(large_content.encode("utf-8"))

    @pytest.mark.asyncio
    async def test_index_preserves_relative_paths(self, tmp_path: Path) -> None:
        """Test that file paths are stored relative to repository root."""
        # Arrange
        test_dir = tmp_path / "path-test"
        test_dir.mkdir()

        src = test_dir / "src"
        src.mkdir()
        (src / "main.py").write_text("main")

        tests = test_dir / "tests"
        tests.mkdir()
        (tests / "test_main.py").write_text("test")

        repo_repo = InMemoryRepositoryRepository()
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository()

        use_case = IndexLocalDirectoryUseCase(
            repository_repo=repo_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )

        # Act
        result = await use_case.execute(
            IndexLocalDirectoryRequest(path=str(test_dir), name="path-test")
        )

        # Assert
        files = await file_repo.list_by_repository(result.repository_id)
        paths = {f.path for f in files}

        # Paths should be relative, not absolute
        assert "src/main.py" in paths
        assert "tests/test_main.py" in paths

        # Should NOT contain absolute paths
        for path in paths:
            assert not path.startswith(str(test_dir))
            assert not path.startswith("/")
