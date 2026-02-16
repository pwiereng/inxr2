"""Index local directory use case."""

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ....domain.entities import Commit, File, Repository
from ....domain.services.language_detector import LanguageDetector
from ....domain.value_objects import CommitHash
from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    RepositoryPort,
)
from ...ports.services import FileSystemPort

logger = logging.getLogger(__name__)


@dataclass
class IndexLocalDirectoryRequest:
    """Request to index a local directory."""

    path: str
    name: str
    description: str | None = None


@dataclass
class IndexLocalDirectoryResponse:
    """Response from indexing a local directory."""

    repository_id: int
    total_files: int
    indexed_files: int
    skipped_files: int


class IndexLocalDirectoryUseCase:
    """
    Use case for indexing a local directory.

    This creates a repository, a dummy commit, and file entries
    for all text files in the directory.

    This is a simplified version for the vertical slice - no real
    git integration yet.
    """

    # Directories to skip
    SKIP_DIRS = {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        "node_modules",
        "venv",
        ".venv",
        "env",
        ".env",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "target",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "coverage",
        ".coverage",
    }

    def __init__(
        self,
        repository_repo: RepositoryPort,
        commit_repo: CommitRepositoryPort,
        file_repo: FileRepositoryPort,
        filesystem: FileSystemPort,
    ) -> None:
        """
        Initialize use case.

        Args:
            repository_repo: Repository for accessing repositories
            commit_repo: Repository for accessing commits
            file_repo: Repository for accessing files
            filesystem: File system port for I/O operations
        """
        self._repository_repo = repository_repo
        self._commit_repo = commit_repo
        self._file_repo = file_repo
        self._filesystem = filesystem
        self._language_detector = LanguageDetector()

    async def execute(
        self, request: IndexLocalDirectoryRequest
    ) -> IndexLocalDirectoryResponse:
        """
        Execute directory indexing.

        Args:
            request: Indexing request

        Returns:
            Indexing response with statistics
        """
        # 1. Create repository
        # Normalize to absolute path to avoid working directory dependency
        absolute_path = str(Path(request.path).resolve())
        repository = Repository(
            name=request.name,
            url=absolute_path,
            description=request.description or f"Local directory: {absolute_path}",
            default_branch="local",
        )
        saved_repo = await self._repository_repo.save(repository)
        assert saved_repo.id is not None, "Repository ID must be set after save"

        # 2. Create dummy commit (for local indexing)
        # Note: Author info and message are NOT stored - queried from git on-demand.
        # For local directories without git, this info is not available anyway.
        commit_hash = self._generate_local_commit_hash(absolute_path)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash(commit_hash),
            author_date=datetime.now(UTC).replace(tzinfo=None),
            commit_date=datetime.now(UTC).replace(tzinfo=None),
        )
        saved_commit = await self._commit_repo.save(commit)
        assert saved_commit.id is not None, "Commit ID must be set after save"

        # Link commit to the "local" branch
        await self._commit_repo.link_commit_to_branch(
            saved_repo.id, saved_commit.id, "local"
        )

        # 3. Walk directory and index files
        total_files = 0
        indexed_files = 0
        skipped_files = 0

        file_paths = self._filesystem.walk_directory(
            absolute_path, skip_dirs=self.SKIP_DIRS, skip_hidden=True
        )

        for file_path in file_paths:
            total_files += 1

            # Skip non-text files
            if not self._language_detector.is_text_file(file_path):
                skipped_files += 1
                continue

            try:
                # Get file metadata
                file_stat = self._filesystem.stat(file_path)
                relative_path = self._filesystem.relative_path(file_path, absolute_path)

                # Detect language
                language = self._language_detector.detect(file_path)

                # Calculate content hash
                content_hash = self._calculate_file_hash(file_path)

                # Create file entity
                file_entity = File(
                    repository_id=saved_repo.id,
                    path=relative_path,
                    content_hash=content_hash,
                    size_bytes=file_stat.size_bytes,
                    language=language,
                    line_count=self._count_lines(file_path),
                )

                saved_file = await self._file_repo.save(file_entity)
                # Link file to commit via junction table
                if saved_file.id is not None and saved_commit.id is not None:
                    await self._file_repo.link_file_to_commit(
                        saved_file.id, saved_commit.id
                    )
                indexed_files += 1

            except Exception as e:
                # Skip files that can't be read
                logger.warning("Skipping %s: %s", file_path, e)
                skipped_files += 1
                continue

        return IndexLocalDirectoryResponse(
            repository_id=saved_repo.id,
            total_files=total_files,
            indexed_files=indexed_files,
            skipped_files=skipped_files,
        )

    def _generate_local_commit_hash(self, path: str) -> str:
        """
        Generate a deterministic hash for a local directory.

        Args:
            path: Directory path

        Returns:
            40-character hex hash
        """
        # Use timestamp + path for uniqueness
        timestamp = datetime.now(UTC).replace(tzinfo=None).isoformat()
        data = f"local:{path}:{timestamp}".encode()
        return hashlib.sha1(data).hexdigest()

    def _calculate_file_hash(self, file_path: str | Path) -> str:
        """
        Calculate SHA-1 hash of file content using streaming.

        Reads file in chunks to avoid loading entire content into memory,
        which is important for large files.

        Args:
            file_path: Path to file

        Returns:
            40-character hex hash
        """
        sha1 = hashlib.sha1()
        with self._filesystem.open_binary(file_path) as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha1.update(chunk)
        return sha1.hexdigest()

    def _count_lines(self, file_path: str | Path) -> int | None:
        """
        Count lines in a file using streaming.

        Reads file in chunks to avoid loading entire content into memory,
        which is important for large files.

        Args:
            file_path: Path to file

        Returns:
            Number of lines or None if can't be read
        """
        try:
            line_count = 0
            last_byte: int | None = None
            with self._filesystem.open_binary(file_path) as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    line_count += chunk.count(b"\n")
                    last_byte = chunk[-1] if chunk else last_byte
            # Add 1 if file has content but doesn't end with newline
            if last_byte is not None and last_byte != ord(b"\n"):
                line_count += 1
            return line_count
        except Exception:
            return None
