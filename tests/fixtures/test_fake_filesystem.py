"""Tests for FakeFileSystem test double."""

import pytest

from tests.fixtures.test_doubles import FakeFileSystem


class TestFakeFileSystem:
    """Tests for FakeFileSystem test double."""

    @pytest.fixture
    def filesystem(self) -> FakeFileSystem:
        """Create FakeFileSystem instance."""
        return FakeFileSystem()


class TestAddFile(TestFakeFileSystem):
    """Tests for add_file method."""

    def test_add_file_with_string_content(self, filesystem: FakeFileSystem) -> None:
        """add_file should accept string content."""
        filesystem.add_file("/project/main.py", "print('hello')")
        content = filesystem.read_text("/project/main.py")
        assert content == "print('hello')"

    def test_add_file_with_bytes_content(self, filesystem: FakeFileSystem) -> None:
        """add_file should accept bytes content."""
        filesystem.add_file("/project/data.bin", b"\x00\x01\x02")
        content = filesystem.read_bytes("/project/data.bin")
        assert content == b"\x00\x01\x02"


class TestWalkDirectory(TestFakeFileSystem):
    """Tests for walk_directory method."""

    def test_walks_virtual_directory(self, filesystem: FakeFileSystem) -> None:
        """walk_directory should find virtual files."""
        filesystem.add_file("/project/main.py", "main")
        filesystem.add_file("/project/utils.py", "utils")
        filesystem.add_file("/project/src/app.py", "app")

        files = filesystem.walk_directory("/project")
        paths = {str(f) for f in files}

        assert "/project/main.py" in paths
        assert "/project/utils.py" in paths
        assert "/project/src/app.py" in paths

    def test_skips_hidden_files(self, filesystem: FakeFileSystem) -> None:
        """walk_directory should skip hidden files by default."""
        filesystem.add_file("/project/main.py", "main")
        filesystem.add_file("/project/.hidden", "hidden")
        filesystem.add_file("/project/.git/config", "config")

        files = filesystem.walk_directory("/project")
        paths = {str(f) for f in files}

        assert "/project/main.py" in paths
        assert "/project/.hidden" not in paths
        assert "/project/.git/config" not in paths

    def test_includes_hidden_when_requested(self, filesystem: FakeFileSystem) -> None:
        """walk_directory should include hidden files when skip_hidden=False."""
        filesystem.add_file("/project/main.py", "main")
        filesystem.add_file("/project/.hidden", "hidden")

        files = filesystem.walk_directory("/project", skip_hidden=False)
        paths = {str(f) for f in files}

        assert "/project/main.py" in paths
        assert "/project/.hidden" in paths

    def test_skips_excluded_directories(self, filesystem: FakeFileSystem) -> None:
        """walk_directory should skip directories in skip_dirs."""
        filesystem.add_file("/project/main.py", "main")
        filesystem.add_file("/project/node_modules/pkg.js", "pkg")
        filesystem.add_file("/project/__pycache__/mod.pyc", "mod")

        files = filesystem.walk_directory(
            "/project", skip_dirs={"node_modules", "__pycache__"}
        )
        paths = {str(f) for f in files}

        assert "/project/main.py" in paths
        assert "/project/node_modules/pkg.js" not in paths
        assert "/project/__pycache__/mod.pyc" not in paths

    def test_returns_empty_for_nonexistent(self, filesystem: FakeFileSystem) -> None:
        """walk_directory should return empty for nonexistent path."""
        files = filesystem.walk_directory("/nonexistent")
        assert files == []


class TestStat(TestFakeFileSystem):
    """Tests for stat method."""

    def test_stat_returns_file_info(self, filesystem: FakeFileSystem) -> None:
        """stat should return correct info for virtual file."""
        content = "hello world"
        filesystem.add_file("/project/file.txt", content)

        stat = filesystem.stat("/project/file.txt")

        assert stat.size_bytes == len(content.encode("utf-8"))
        assert stat.is_file is True
        assert stat.is_dir is False

    def test_stat_returns_dir_info(self, filesystem: FakeFileSystem) -> None:
        """stat should return correct info for virtual directory."""
        filesystem.add_directory("/project/subdir")

        stat = filesystem.stat("/project/subdir")

        assert stat.is_file is False
        assert stat.is_dir is True

    def test_stat_raises_for_nonexistent(self, filesystem: FakeFileSystem) -> None:
        """stat should raise FileNotFoundError for nonexistent path."""
        with pytest.raises(FileNotFoundError):
            filesystem.stat("/nonexistent.txt")


class TestReadBytes(TestFakeFileSystem):
    """Tests for read_bytes method."""

    def test_reads_string_content_as_bytes(self, filesystem: FakeFileSystem) -> None:
        """read_bytes should return string content encoded as UTF-8."""
        filesystem.add_file("/file.txt", "hello")
        content = filesystem.read_bytes("/file.txt")
        assert content == b"hello"

    def test_reads_bytes_content(self, filesystem: FakeFileSystem) -> None:
        """read_bytes should return bytes content as-is."""
        filesystem.add_file("/file.bin", b"\x00\xff")
        content = filesystem.read_bytes("/file.bin")
        assert content == b"\x00\xff"

    def test_raises_for_nonexistent(self, filesystem: FakeFileSystem) -> None:
        """read_bytes should raise FileNotFoundError for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            filesystem.read_bytes("/nonexistent.txt")


class TestReadText(TestFakeFileSystem):
    """Tests for read_text method."""

    def test_reads_string_content(self, filesystem: FakeFileSystem) -> None:
        """read_text should return string content."""
        filesystem.add_file("/file.txt", "hello world")
        content = filesystem.read_text("/file.txt")
        assert content == "hello world"

    def test_decodes_bytes_content(self, filesystem: FakeFileSystem) -> None:
        """read_text should decode bytes content."""
        filesystem.add_file("/file.txt", "héllo".encode())
        content = filesystem.read_text("/file.txt")
        assert content == "héllo"


class TestRelativePath(TestFakeFileSystem):
    """Tests for relative_path method."""

    def test_returns_relative_path(self, filesystem: FakeFileSystem) -> None:
        """relative_path should return path relative to base."""
        rel = filesystem.relative_path("/project/src/main.py", "/project")
        assert rel == "src/main.py"

    def test_handles_root_files(self, filesystem: FakeFileSystem) -> None:
        """relative_path should handle files at root level."""
        rel = filesystem.relative_path("/project/main.py", "/project")
        assert rel == "main.py"

    def test_handles_trailing_slash(self, filesystem: FakeFileSystem) -> None:
        """relative_path should handle base with trailing slash."""
        rel = filesystem.relative_path("/project/main.py", "/project/")
        assert rel == "main.py"


class TestExists(TestFakeFileSystem):
    """Tests for exists method."""

    def test_exists_returns_true_for_file(self, filesystem: FakeFileSystem) -> None:
        """exists should return True for existing virtual file."""
        filesystem.add_file("/file.txt", "content")
        assert filesystem.exists("/file.txt") is True

    def test_exists_returns_true_for_directory(
        self, filesystem: FakeFileSystem
    ) -> None:
        """exists should return True for existing virtual directory."""
        filesystem.add_directory("/project")
        assert filesystem.exists("/project") is True

    def test_exists_returns_false_for_nonexistent(
        self, filesystem: FakeFileSystem
    ) -> None:
        """exists should return False for nonexistent path."""
        assert filesystem.exists("/nonexistent") is False


class TestClear(TestFakeFileSystem):
    """Tests for clear method."""

    def test_clear_removes_all_files(self, filesystem: FakeFileSystem) -> None:
        """clear should remove all virtual files."""
        filesystem.add_file("/file1.txt", "1")
        filesystem.add_file("/file2.txt", "2")
        filesystem.add_directory("/dir")

        filesystem.clear()

        assert filesystem.exists("/file1.txt") is False
        assert filesystem.exists("/file2.txt") is False
        assert filesystem.exists("/dir") is False
