"""Get file content use case.

Retrieves file content from git at a specific commit, composing with
ResolveFileUseCase for file resolution.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ....domain.entities import Commit, File, Repository
from ....domain.exceptions import FileNotFound
from .resolve_file import ResolveFileRequest, ResolveFileUseCase


class GitContentServiceProtocol(Protocol):
    """Protocol for git content operations.

    This protocol defines the minimal interface needed by this use case.
    The concrete GitService class implements these methods.
    """

    def get_file_content(
        self, repo_path: Path, commit_hash: str, file_path: str
    ) -> str:
        """Get file content at a specific commit."""
        ...


class BinaryFileError(Exception):
    """Raised when attempting to read a binary file as text."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"File is binary and cannot be displayed as text: {path}")


class RepositoryPathNotFoundError(Exception):
    """Raised when the repository path doesn't exist on disk."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Repository path not found: {path}")


@dataclass
class FileContent:
    """File content with metadata.

    Contains the file content along with computed metadata
    like line count and size.
    """

    file: File
    commit: Commit
    repository: Repository
    content: str
    line_count: int
    size_bytes: int


@dataclass
class GetFileContentRequest:
    """Request to get file content.

    Can resolve by repository name + path, or by file ID directly.
    """

    # Resolution by name + path
    repository_name: str | None = None
    file_path: str | None = None
    commit_hash: str | None = None
    branch: str | None = None

    # Resolution by file ID (for direct file access)
    file_id: int | None = None


class GetFileContentUseCase:
    """Use case for getting file content from git.

    Composes with ResolveFileUseCase for file resolution, then
    fetches content from git and computes metadata.

    Handles:
    - File resolution (by name+path or by ID)
    - Git content fetching with error handling
    - Binary file detection
    - Line counting and size calculation
    """

    def __init__(
        self,
        resolve_file_use_case: ResolveFileUseCase,
        git_service: GitContentServiceProtocol,
    ) -> None:
        """Initialize use case with dependencies.

        Args:
            resolve_file_use_case: Use case for resolving files
            git_service: Git service for fetching content
        """
        self._resolve_file_use_case = resolve_file_use_case
        self._git_service = git_service

    async def execute(self, request: GetFileContentRequest) -> FileContent:
        """Execute file content retrieval.

        Args:
            request: Request with file resolution parameters

        Returns:
            FileContent with content and metadata

        Raises:
            RepositoryNotFound: If repository doesn't exist
            FileNotFound: If file doesn't exist
            CommitNotFound: If commit doesn't exist
            RepositoryPathNotFoundError: If repository path doesn't exist on disk
            BinaryFileError: If file is binary
            ValueError: If request parameters are invalid
        """
        # Resolve file using the composed use case
        if request.repository_name and request.file_path:
            resolved = await self._resolve_file_use_case.execute(
                ResolveFileRequest(
                    repository_name=request.repository_name,
                    file_path=request.file_path,
                    commit_hash=request.commit_hash,
                    branch=request.branch,
                )
            )
        elif request.file_id is not None:
            # For file_id resolution, we need to resolve differently
            # This requires accessing the repositories directly
            # For now, raise an error - the caller should use repository_name + file_path
            raise ValueError(
                "file_id resolution not yet supported. "
                "Use repository_name and file_path instead."
            )
        else:
            raise ValueError(
                "Either (repository_name and file_path) or file_id must be provided"
            )

        file = resolved.file
        commit = resolved.commit
        repository = resolved.repository

        # Verify repository path exists
        repo_path = Path(repository.url)
        if not repo_path.exists():
            raise RepositoryPathNotFoundError(repository.url)

        # Fetch content from git
        try:
            content = self._git_service.get_file_content(
                repo_path=repo_path,
                commit_hash=commit.commit_hash.value,
                file_path=file.path,
            )
        except FileNotFoundError as e:
            raise FileNotFound(
                path=file.path,
                repository_name=repository.name,
                commit_hash=commit.commit_hash.value,
            ) from e
        except UnicodeDecodeError as e:
            raise BinaryFileError(file.path) from e

        # Compute metadata
        line_count = self._count_lines(content)
        size_bytes = len(content.encode("utf-8"))

        return FileContent(
            file=file,
            commit=commit,
            repository=repository,
            content=content,
            line_count=line_count,
            size_bytes=size_bytes,
        )

    def _count_lines(self, content: str) -> int:
        """Count lines in content.

        Handles files with and without trailing newlines correctly.

        Args:
            content: File content

        Returns:
            Number of lines
        """
        if not content:
            return 0

        # Files ending with newline: count newlines
        # Files not ending with newline: count newlines + 1
        has_trailing_newline = content.endswith("\n")
        return content.count("\n") + (0 if has_trailing_newline else 1)
