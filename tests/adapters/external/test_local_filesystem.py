"""Tests for LocalFileSystem adapter."""

import os
from pathlib import Path

import pytest

from inxr2.adapters.external.local_filesystem import LocalFileSystem
from inxr2.application.ports.services import FileStat


class TestLocalFileSystem:
    """Tests for LocalFileSystem adapter."""

    @pytest.fixture
    def filesystem(self) -> LocalFileSystem:
        """Create LocalFileSystem instance."""
        return LocalFileSystem()

    @pytest.fixture
    def test_dir(self, tmp_path: Path) -> Path:
        """Create a test directory with some files."""
        # Create directory structure
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.py").write_text("print('hello')")

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_text("nested content")

        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "secret.txt").write_text("secret")

        (tmp_path / ".dotfile").write_text("hidden file")

        return tmp_path


class TestWalkDirectory(TestLocalFileSystem):
    """Tests for walk_directory method."""

    def test_finds_all_files(self, filesystem: LocalFileSystem, test_dir: Path) -> None:
        """walk_directory should find all non-hidden files."""
        files = filesystem.walk_directory(test_dir)
        paths = {str(f.relative_to(test_dir)) for f in files}

        assert "file1.txt" in paths
        assert "file2.py" in paths
        assert "subdir/file3.txt" in paths

    def test_skips_hidden_by_default(
        self, filesystem: LocalFileSystem, test_dir: Path
    ) -> None:
        """walk_directory should skip hidden files by default."""
        files = filesystem.walk_directory(test_dir)
        paths = {str(f.relative_to(test_dir)) for f in files}

        assert ".dotfile" not in paths
        assert ".hidden/secret.txt" not in paths

    def test_includes_hidden_when_requested(
        self, filesystem: LocalFileSystem, test_dir: Path
    ) -> None:
        """walk_directory should include hidden files when skip_hidden=False."""
        files = filesystem.walk_directory(test_dir, skip_hidden=False)
        paths = {str(f.relative_to(test_dir)) for f in files}

        assert ".dotfile" in paths
        assert ".hidden/secret.txt" in paths

    def test_skips_specified_directories(
        self, filesystem: LocalFileSystem, test_dir: Path
    ) -> None:
        """walk_directory should skip directories in skip_dirs set."""
        files = filesystem.walk_directory(test_dir, skip_dirs={"subdir"})
        paths = {str(f.relative_to(test_dir)) for f in files}

        assert "file1.txt" in paths
        assert "subdir/file3.txt" not in paths

    def test_returns_empty_for_empty_directory(
        self, filesystem: LocalFileSystem, tmp_path: Path
    ) -> None:
        """walk_directory should return empty list for empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        files = filesystem.walk_directory(empty_dir)
        assert files == []


class TestStat(TestLocalFileSystem):
    """Tests for stat method."""

    def test_returns_file_stat(
        self, filesystem: LocalFileSystem, test_dir: Path
    ) -> None:
        """stat should return FileStat for a file."""
        file_path = test_dir / "file1.txt"
        stat = filesystem.stat(file_path)

        assert isinstance(stat, FileStat)
        assert stat.size_bytes == len("content1")
        assert stat.is_file is True
        assert stat.is_dir is False

    def test_returns_dir_stat(
        self, filesystem: LocalFileSystem, test_dir: Path
    ) -> None:
        """stat should return FileStat for a directory."""
        stat = filesystem.stat(test_dir / "subdir")

        assert stat.is_file is False
        assert stat.is_dir is True

    def test_raises_for_nonexistent(
        self, filesystem: LocalFileSystem, test_dir: Path
    ) -> None:
        """stat should raise FileNotFoundError for nonexistent path."""
        with pytest.raises(FileNotFoundError):
            filesystem.stat(test_dir / "nonexistent.txt")


class TestReadBytes(TestLocalFileSystem):
    """Tests for read_bytes method."""

    def test_reads_file_content(
        self, filesystem: LocalFileSystem, test_dir: Path
    ) -> None:
        """read_bytes should return file content as bytes."""
        content = filesystem.read_bytes(test_dir / "file1.txt")
        assert content == b"content1"

    def test_reads_binary_content(
        self, filesystem: LocalFileSystem, tmp_path: Path
    ) -> None:
        """read_bytes should correctly read binary content."""
        binary_content = b"\x00\x01\x02\xff"
        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(binary_content)

        content = filesystem.read_bytes(binary_file)
        assert content == binary_content

    def test_raises_for_nonexistent(
        self, filesystem: LocalFileSystem, test_dir: Path
    ) -> None:
        """read_bytes should raise FileNotFoundError for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            filesystem.read_bytes(test_dir / "nonexistent.txt")


class TestReadText(TestLocalFileSystem):
    """Tests for read_text method."""

    def test_reads_text_content(
        self, filesystem: LocalFileSystem, test_dir: Path
    ) -> None:
        """read_text should return file content as string."""
        content = filesystem.read_text(test_dir / "file1.txt")
        assert content == "content1"

    def test_respects_encoding(
        self, filesystem: LocalFileSystem, tmp_path: Path
    ) -> None:
        """read_text should use specified encoding."""
        # Write UTF-16 encoded file
        utf16_file = tmp_path / "utf16.txt"
        utf16_file.write_bytes("hello".encode("utf-16"))

        content = filesystem.read_text(utf16_file, encoding="utf-16")
        assert content == "hello"

    def test_handles_errors_parameter(
        self, filesystem: LocalFileSystem, tmp_path: Path
    ) -> None:
        """read_text should respect errors parameter."""
        # Write invalid UTF-8 bytes
        invalid_file = tmp_path / "invalid.txt"
        invalid_file.write_bytes(b"\xff\xfe")

        # Should not raise with errors='ignore'
        content = filesystem.read_text(invalid_file, errors="ignore")
        assert isinstance(content, str)


class TestRelativePath(TestLocalFileSystem):
    """Tests for relative_path method."""

    def test_returns_relative_path(
        self, filesystem: LocalFileSystem, test_dir: Path
    ) -> None:
        """relative_path should return path relative to base."""
        file_path = test_dir / "subdir" / "file3.txt"
        rel = filesystem.relative_path(file_path, test_dir)
        assert rel == os.path.join("subdir", "file3.txt")

    def test_handles_same_directory(
        self, filesystem: LocalFileSystem, test_dir: Path
    ) -> None:
        """relative_path should handle file in same directory."""
        file_path = test_dir / "file1.txt"
        rel = filesystem.relative_path(file_path, test_dir)
        assert rel == "file1.txt"


class TestExists(TestLocalFileSystem):
    """Tests for exists method."""

    def test_returns_true_for_existing_file(
        self, filesystem: LocalFileSystem, test_dir: Path
    ) -> None:
        """exists should return True for existing file."""
        assert filesystem.exists(test_dir / "file1.txt") is True

    def test_returns_true_for_existing_directory(
        self, filesystem: LocalFileSystem, test_dir: Path
    ) -> None:
        """exists should return True for existing directory."""
        assert filesystem.exists(test_dir / "subdir") is True

    def test_returns_false_for_nonexistent(
        self, filesystem: LocalFileSystem, test_dir: Path
    ) -> None:
        """exists should return False for nonexistent path."""
        assert filesystem.exists(test_dir / "nonexistent.txt") is False
