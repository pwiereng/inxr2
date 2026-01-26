"""Local file system adapter implementation."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from ...application.ports.services import FileStat, FileSystemPort


class LocalFileSystem(FileSystemPort):
    """
    File system adapter that uses the local file system.

    This is the production implementation of FileSystemPort that
    performs actual I/O operations on the local file system.
    """

    def walk_directory(
        self,
        path: str | Path,
        skip_dirs: set[str] | None = None,
        skip_hidden: bool = True,
    ) -> list[Path]:
        """Walk directory tree and return all file paths."""
        skip_dirs = skip_dirs or set()
        files: list[Path] = []

        for root, dirs, filenames in os.walk(path):
            # Filter directories in-place to prevent descending into them
            dirs[:] = [
                d
                for d in dirs
                if d not in skip_dirs and (not skip_hidden or not d.startswith("."))
            ]

            for filename in filenames:
                # Skip hidden files if requested
                if skip_hidden and filename.startswith("."):
                    continue
                files.append(Path(root) / filename)

        return files

    def stat(self, path: str | Path) -> FileStat:
        """Get file statistics."""
        stats = os.stat(path)
        path_obj = Path(path)
        return FileStat(
            size_bytes=stats.st_size,
            is_file=path_obj.is_file(),
            is_dir=path_obj.is_dir(),
        )

    def read_bytes(self, path: str | Path) -> bytes:
        """Read file content as bytes."""
        with open(path, "rb") as f:
            return f.read()

    def read_text(
        self, path: str | Path, encoding: str = "utf-8", errors: str = "strict"
    ) -> str:
        """Read file content as text."""
        with open(path, encoding=encoding, errors=errors) as f:
            return f.read()

    def relative_path(self, path: str | Path, base: str | Path) -> str:
        """Get path relative to base directory."""
        return os.path.relpath(path, base)

    def exists(self, path: str | Path) -> bool:
        """Check if path exists."""
        return Path(path).exists()

    @contextmanager
    def open_binary(self, path: str | Path) -> Iterator[BinaryIO]:
        """Open file for binary reading as a context manager."""
        f = open(path, "rb")
        try:
            yield f
        finally:
            f.close()
