"""Resolve file use case.

Provides centralized file resolution logic with priority:
commit > branch > default (latest).

This eliminates duplication across multiple file-related endpoints.
"""

from dataclasses import dataclass

from ....domain.entities import Commit, File, Repository
from ....domain.exceptions import CommitNotFound, FileNotFound, RepositoryNotFound
from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    RepositoryPort,
)


@dataclass
class ResolveFileRequest:
    """Request to resolve a file.

    Resolution priority:
    1. If commit_hash provided, get file at that exact commit
    2. If branch provided, get latest file version on that branch
    3. Otherwise, get latest file version across all branches
    """

    repository_name: str
    file_path: str
    commit_hash: str | None = None
    branch: str | None = None


@dataclass
class ResolveFileResponse:
    """Response containing resolved file with context.

    Provides the file entity along with related commit and repository
    entities for complete context.
    """

    file: File
    commit: Commit
    repository: Repository


class ResolveFileUseCase:
    """Use case for resolving a file with priority: commit > branch > default.

    This centralizes the file resolution logic used across multiple endpoints:
    - get_file_content_by_path
    - get_file_symbols_by_path
    - get_file_references_by_path

    Resolution priority:
    1. If commit_hash provided, get file at that exact commit
    2. If branch provided, get latest file version on that branch
    3. Otherwise, get latest file version across all branches

    Raises domain exceptions for not-found cases, which controllers
    can translate to appropriate HTTP responses.
    """

    def __init__(
        self,
        repository_repo: RepositoryPort,
        file_repo: FileRepositoryPort,
        commit_repo: CommitRepositoryPort,
    ) -> None:
        """Initialize use case with required repositories.

        Args:
            repository_repo: Repository for accessing repositories
            file_repo: Repository for accessing files
            commit_repo: Repository for accessing commits
        """
        self._repository_repo = repository_repo
        self._file_repo = file_repo
        self._commit_repo = commit_repo

    async def execute(self, request: ResolveFileRequest) -> ResolveFileResponse:
        """Execute file resolution.

        Args:
            request: Resolution request with repository name, path, and
                     optional commit/branch specifiers

        Returns:
            ResolveFileResponse with file, commit, and repository

        Raises:
            RepositoryNotFound: If repository doesn't exist
            FileNotFound: If file doesn't exist at specified location
            CommitNotFound: If commit record is missing (data integrity issue)
        """
        # 1. Find repository by name
        repository = await self._repository_repo.find_by_name(request.repository_name)
        if not repository:
            raise RepositoryNotFound(request.repository_name)

        repository_id = repository.id if repository.id is not None else 0

        # 2. Resolve file and commit based on priority: commit > branch > default
        file, commit = await self._resolve_file_and_commit(
            repository_id=repository_id,
            repository=repository,
            path=request.file_path,
            commit_hash=request.commit_hash,
            branch=request.branch,
        )

        return ResolveFileResponse(
            file=file,
            commit=commit,
            repository=repository,
        )

    async def _resolve_file_and_commit(
        self,
        repository_id: int,
        repository: Repository,
        path: str,
        commit_hash: str | None,
        branch: str | None,
    ) -> tuple[File, Commit]:
        """Resolve file and its commit with priority: commit > branch > default.

        In the content-addressable model, files don't carry commit context.
        The commit is determined from the resolution path (commit_hash, branch,
        or latest on default branch).

        Args:
            repository_id: Repository database ID
            repository: Repository entity (for error messages)
            path: File path
            commit_hash: Optional commit hash for time travel
            branch: Optional branch for branch-specific resolution

        Returns:
            Tuple of (File, Commit)

        Raises:
            FileNotFound: If file doesn't exist at specified location
            CommitNotFound: If commit record is missing
        """
        if commit_hash:
            # Time travel mode: get file at specific commit
            file = await self._file_repo.find_by_repository_path_and_commit_hash(
                repository_id, path, commit_hash
            )
            if not file:
                raise FileNotFound(
                    path=path,
                    repository_name=repository.name,
                    commit_hash=commit_hash,
                )
            commit = await self._commit_repo.find_by_hash(repository_id, commit_hash)
            if not commit:
                raise CommitNotFound(commit_hash=commit_hash)
            return file, commit

        if branch:
            # Branch mode: get latest version of file on this branch
            versions = await self._file_repo.list_versions_by_path(
                repository_id, path, branch
            )
            if not versions:
                raise FileNotFound(
                    path=path,
                    repository_name=repository.name,
                    branch=branch,
                )
            file = versions[0]  # Most recent version on this branch
            commit = await self._commit_repo.find_latest_by_branch(
                repository_id, branch
            )
            if not commit:
                raise CommitNotFound(commit_hash=f"(no commits on branch {branch})")
            return file, commit

        # Default: get latest version across all branches
        file = await self._file_repo.find_by_repository_and_path(repository_id, path)
        if not file:
            raise FileNotFound(path=path, repository_name=repository.name)

        # Find any commit that includes this file
        default_branch = repository.default_branch or "main"
        commit = await self._commit_repo.find_latest_by_branch(
            repository_id, default_branch
        )
        if not commit:
            # Try to find any commit at all
            commits = await self._commit_repo.list_by_repository(
                repository_id=repository_id
            )
            if not commits:
                raise CommitNotFound(commit_hash="(no commits found for repository)")
            commit = commits[0]

        return file, commit
