"""Get file history use case.

Retrieves version history for a file across commits, with commit message
hydration from git.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ....domain.entities import Repository
from ....domain.exceptions import FileNotFound, RepositoryNotFound
from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    RepositoryPort,
)


class GitCommitInfoProtocol(Protocol):
    """Protocol for git commit info operations.

    This protocol defines the minimal interface needed by this use case.
    The concrete GitService class implements these methods.
    """

    def get_commit_info(self, repo_path: Path, commit_hash: str) -> dict[str, str]:
        """Get commit information including message.

        Args:
            repo_path: Path to the git repository
            commit_hash: The commit hash to look up

        Returns:
            Dictionary with commit info including 'message' key
        """
        ...


@dataclass
class FileVersion:
    """A single version of a file.

    Contains commit metadata and content hash for identifying
    changes between versions.
    """

    commit_id: int
    commit_hash: str
    short_hash: str
    commit_date: str
    message: str
    content_hash: str


@dataclass
class FileHistory:
    """File version history.

    Contains all indexed versions of a file, ordered by commit date
    (newest first).
    """

    path: str
    repository_name: str
    versions: list[FileVersion]
    total: int


@dataclass
class GetFileHistoryRequest:
    """Request to get file history.

    Args:
        repository_name: Name of the repository
        file_path: Path to the file within the repository
        branch: Optional branch name to filter history
    """

    repository_name: str
    file_path: str
    branch: str | None = None


class GetFileHistoryUseCase:
    """Use case for getting file version history.

    Retrieves all indexed versions of a file, optionally filtered by branch.
    Hydrates commit messages from git on-demand for display.

    Handles:
    - Repository resolution
    - File version listing with branch filtering
    - Fallback to default branch for merged branches
    - Commit message hydration from git
    """

    def __init__(
        self,
        repository_repo: RepositoryPort,
        file_repo: FileRepositoryPort,
        commit_repo: CommitRepositoryPort,
        git_service: GitCommitInfoProtocol,
    ) -> None:
        """Initialize use case with dependencies.

        Args:
            repository_repo: Repository for accessing repositories
            file_repo: Repository for accessing files
            commit_repo: Repository for accessing commits
            git_service: Git service for hydrating commit messages
        """
        self._repository_repo = repository_repo
        self._file_repo = file_repo
        self._commit_repo = commit_repo
        self._git_service = git_service

    async def execute(self, request: GetFileHistoryRequest) -> FileHistory:
        """Execute file history retrieval.

        Args:
            request: Request with repository name, file path, and optional branch

        Returns:
            FileHistory with all versions of the file

        Raises:
            RepositoryNotFound: If repository doesn't exist
            FileNotFound: If file has no indexed versions
        """
        # 1. Find repository by name
        repository = await self._repository_repo.find_by_name(request.repository_name)
        if not repository:
            raise RepositoryNotFound(request.repository_name)

        repository_id = repository.id if repository.id is not None else 0

        # 2. Get all versions of this file (optionally filtered by branch)
        files = await self._file_repo.list_versions_by_path(
            repository_id, request.file_path, request.branch
        )

        if not files:
            raise FileNotFound(
                path=request.file_path,
                repository_name=repository.name,
                branch=request.branch,
            )

        # 4. Build version list with hydrated commit info
        versions = await self._build_versions(repository, files)

        return FileHistory(
            path=request.file_path,
            repository_name=repository.name,
            versions=versions,
            total=len(versions),
        )

    async def _build_versions(
        self,
        repository: Repository,
        files: list,
    ) -> list[FileVersion]:
        """Build version list with hydrated commit messages.

        Args:
            repository: Repository entity for git path
            files: List of file entities for versions

        Returns:
            List of FileVersion with hydrated commit info
        """
        repo_path = Path(repository.url)
        versions = []

        for file in files:
            commit_record = await self._commit_repo.find_by_id(file.commit_id)
            if not commit_record:
                continue

            # Hydrate message from git
            message = self._get_commit_message(
                repo_path, commit_record.commit_hash.value
            )

            versions.append(
                FileVersion(
                    commit_id=commit_record.id or 0,
                    commit_hash=commit_record.commit_hash.value,
                    short_hash=commit_record.short_hash,
                    commit_date=(
                        commit_record.commit_date.isoformat()
                        if commit_record.commit_date
                        else ""
                    ),
                    message=message,
                    content_hash=file.content_hash or "",
                )
            )

        return versions

    def _get_commit_message(self, repo_path: Path, commit_hash: str) -> str:
        """Get commit message from git, truncated for display.

        Args:
            repo_path: Path to the git repository
            commit_hash: The commit hash to look up

        Returns:
            Commit message truncated to 100 chars, or empty string on error
        """
        try:
            git_info = self._git_service.get_commit_info(repo_path, commit_hash)
            return git_info.get("message", "")[:100]
        except Exception:
            return ""
