"""Index local directory use case."""

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ....domain.entities import Commit, File, Repository
from ....domain.services.language_detector import LanguageDetector
from ....domain.value_objects import CommitHash
from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    RepositoryPort,
)


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
    ) -> None:
        """
        Initialize use case.

        Args:
            repository_repo: Repository for accessing repositories
            commit_repo: Repository for accessing commits
            file_repo: Repository for accessing files
        """
        self._repository_repo = repository_repo
        self._commit_repo = commit_repo
        self._file_repo = file_repo
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
        repository = Repository(
            name=request.name,
            url=f"file://{request.path}",
            description=request.description or f"Local directory: {request.path}",
            default_branch="local",
        )
        saved_repo = await self._repository_repo.save(repository)
        assert saved_repo.id is not None, "Repository ID must be set after save"

        # 2. Create dummy commit (for local indexing)
        commit_hash = self._generate_local_commit_hash(request.path)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash(commit_hash),
            author_name="local",
            author_email="local@localhost",
            committer_name="local",
            committer_email="local@localhost",
            author_date=datetime.utcnow(),
            commit_date=datetime.utcnow(),
            message="Local directory index",
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

        for file_path in self._walk_directory(request.path):
            total_files += 1

            # Skip non-text files
            if not self._language_detector.is_text_file(file_path):
                skipped_files += 1
                continue

            try:
                # Get file metadata
                stats = os.stat(file_path)
                relative_path = os.path.relpath(file_path, request.path)

                # Detect language
                language = self._language_detector.detect(file_path)

                # Calculate content hash
                content_hash = self._calculate_file_hash(file_path)

                # Create file entity
                file_entity = File(
                    repository_id=saved_repo.id,
                    commit_id=saved_commit.id,
                    path=relative_path,
                    content_hash=content_hash,
                    size_bytes=stats.st_size,
                    language=language,
                    line_count=self._count_lines(file_path),
                )

                await self._file_repo.save(file_entity)
                indexed_files += 1

            except Exception as e:
                # Skip files that can't be read
                print(f"Warning: Skipping {file_path}: {e}")
                skipped_files += 1
                continue

        return IndexLocalDirectoryResponse(
            repository_id=saved_repo.id,
            total_files=total_files,
            indexed_files=indexed_files,
            skipped_files=skipped_files,
        )

    def _walk_directory(self, path: str) -> list[Path]:
        """
        Walk directory and return all file paths.

        Args:
            path: Directory path to walk

        Returns:
            List of file paths
        """
        files = []
        for root, dirs, filenames in os.walk(path):
            # Filter out directories to skip
            dirs[:] = [
                d for d in dirs if not d.startswith(".") and d not in self.SKIP_DIRS
            ]

            for filename in filenames:
                # Skip hidden files
                if not filename.startswith("."):
                    files.append(Path(root) / filename)

        return files

    def _generate_local_commit_hash(self, path: str) -> str:
        """
        Generate a deterministic hash for a local directory.

        Args:
            path: Directory path

        Returns:
            40-character hex hash
        """
        # Use timestamp + path for uniqueness
        timestamp = datetime.utcnow().isoformat()
        data = f"local:{path}:{timestamp}".encode()
        return hashlib.sha1(data).hexdigest()

    def _calculate_file_hash(self, file_path: str | Path) -> str:
        """
        Calculate SHA-1 hash of file content.

        Args:
            file_path: Path to file

        Returns:
            40-character hex hash
        """
        sha1 = hashlib.sha1()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha1.update(chunk)
        return sha1.hexdigest()

    def _count_lines(self, file_path: str | Path) -> int | None:
        """
        Count lines in a text file.

        Args:
            file_path: Path to file

        Returns:
            Number of lines or None if can't be read
        """
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f)
        except Exception:
            return None
