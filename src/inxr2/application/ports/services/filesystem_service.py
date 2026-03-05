"""Filesystem service port interface."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


@dataclass(frozen=True)
class FileStat:
    """File statistics returned by FileSystemPort.stat()."""

    size_bytes: int
    is_file: bool
    is_dir: bool


class FileSystemPort(ABC):
    """
    Port for file system operations.

    Abstracts file system access to enable testing without real I/O
    and to follow Clean Architecture principles (no I/O in use cases).
    """

    @abstractmethod
    def walk_directory(
        self,
        path: str | Path,
        skip_dirs: set[str] | None = None,
        skip_hidden: bool = True,
    ) -> list[Path]:
        """
        Walk directory tree and return all file paths.

        Args:
            path: Root directory to walk
            skip_dirs: Directory names to skip (e.g., {'__pycache__', 'node_modules'})
            skip_hidden: Whether to skip hidden files/directories (starting with '.')

        Returns:
            List of file paths found
        """
        pass

    @abstractmethod
    def stat(self, path: str | Path) -> FileStat:
        """
        Get file statistics.

        Args:
            path: Path to file

        Returns:
            FileStat with size and type information

        Raises:
            FileNotFoundError: If path doesn't exist
        """
        pass

    @abstractmethod
    def read_bytes(self, path: str | Path) -> bytes:
        """
        Read file content as bytes.

        Args:
            path: Path to file

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file can't be read
        """
        pass

    @abstractmethod
    def read_text(
        self, path: str | Path, encoding: str = "utf-8", errors: str = "strict"
    ) -> str:
        """
        Read file content as text.

        Args:
            path: Path to file
            encoding: Text encoding (default: utf-8)
            errors: Error handling ('strict', 'ignore', 'replace')

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If file doesn't exist
            UnicodeDecodeError: If decoding fails (with errors='strict')
        """
        pass

    @abstractmethod
    def relative_path(self, path: str | Path, base: str | Path) -> str:
        """
        Get path relative to base directory.

        Args:
            path: Absolute path
            base: Base directory path

        Returns:
            Relative path string
        """
        pass

    @abstractmethod
    def exists(self, path: str | Path) -> bool:
        """
        Check if path exists.

        Args:
            path: Path to check

        Returns:
            True if path exists
        """
        pass

    @abstractmethod
    @contextmanager
    def open_binary(self, path: str | Path) -> Iterator[BinaryIO]:
        """
        Open file for binary reading as a context manager.

        Enables streaming reads without loading entire file into memory.

        Args:
            path: Path to file

        Yields:
            Binary file handle

        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file can't be read

        Example:
            with filesystem.open_binary(path) as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    process(chunk)
        """
        pass
