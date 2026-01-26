"""Get repository branches use case.

Provides branch listing with indexing status by correlating
live git data with database indexing information.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ....domain.entities import Repository
from ....domain.exceptions import RepositoryNotFound
from ...ports.repositories import IndexStatusRepositoryPort, RepositoryPort


class GitBranchServiceProtocol(Protocol):
    """Protocol for git branch operations.

    This protocol defines the minimal interface needed by this use case.
    The concrete GitService class implements these methods.
    """

    def list_branches(self, repo_path: Path) -> list[str]:
        """List all branches in the repository."""
        ...


@dataclass
class BranchInfo:
    """Information about a single branch.

    Combines live git data with database indexing status.
    """

    name: str
    last_indexed_commit: str | None
    oldest_indexed_commit: str | None
    commit_count: int
    last_indexed_at: str | None


@dataclass
class GetRepositoryBranchesRequest:
    """Request to get repository branches.

    Can specify repository by ID or name.
    """

    repository_id: int | None = None
    repository_name: str | None = None


@dataclass
class GetRepositoryBranchesResponse:
    """Response containing branches with indexing status."""

    branches: list[BranchInfo]
    default_branch: str


class GetRepositoryBranchesUseCase:
    """Use case for getting repository branches with indexing status.

    Fetches branches live from git and correlates with database
    indexing status to provide a complete view of which branches
    have been indexed and their current state.

    This centralizes the git + DB correlation logic that was
    previously in the controller.
    """

    def __init__(
        self,
        repository_repo: RepositoryPort,
        index_status_repo: IndexStatusRepositoryPort,
        git_service: GitBranchServiceProtocol,
    ) -> None:
        """Initialize use case with required dependencies.

        Args:
            repository_repo: Repository for accessing repositories
            index_status_repo: Repository for accessing index status
            git_service: Git service for listing branches
        """
        self._repository_repo = repository_repo
        self._index_status_repo = index_status_repo
        self._git_service = git_service

    async def execute(
        self, request: GetRepositoryBranchesRequest
    ) -> GetRepositoryBranchesResponse:
        """Execute branch listing with indexing status.

        Args:
            request: Request with repository ID or name

        Returns:
            GetRepositoryBranchesResponse with branches and default branch

        Raises:
            RepositoryNotFound: If repository doesn't exist
            ValueError: If neither repository_id nor repository_name provided
            ValueError: If repository path doesn't exist
        """
        # 1. Resolve repository
        repository = await self._resolve_repository(request)

        repository_id = repository.id if repository.id is not None else 0

        # 2. Verify repository path exists
        repo_path = Path(repository.url)
        if not repo_path.exists():
            raise ValueError(f"Repository path not found: {repository.url}")

        # 3. Get branches from git
        branch_names = self._git_service.list_branches(repo_path)

        # 4. Get indexing status for all branches
        statuses = await self._index_status_repo.list_by_repository(repository_id)
        status_by_branch = {
            s.branch: s for s in statuses if s.indexing_status == "completed"
        }

        # 5. Build branch info with indexing status
        branches = []
        for branch_name in branch_names:
            status = status_by_branch.get(branch_name)
            branches.append(
                BranchInfo(
                    name=branch_name,
                    last_indexed_commit=status.last_indexed_commit if status else None,
                    oldest_indexed_commit=(
                        status.oldest_indexed_commit if status else None
                    ),
                    commit_count=status.total_commits_indexed if status else 0,
                    last_indexed_at=(
                        status.last_indexed_at.isoformat()
                        if status and status.last_indexed_at
                        else None
                    ),
                )
            )

        return GetRepositoryBranchesResponse(
            branches=branches,
            default_branch=repository.default_branch,
        )

    async def _resolve_repository(
        self, request: GetRepositoryBranchesRequest
    ) -> Repository:
        """Resolve repository from request.

        Args:
            request: Request with repository ID or name

        Returns:
            Repository entity

        Raises:
            RepositoryNotFound: If repository doesn't exist
            ValueError: If neither repository_id nor repository_name provided
        """
        if request.repository_id is not None:
            repository = await self._repository_repo.find_by_id(request.repository_id)
            if not repository:
                raise RepositoryNotFound(f"Repository ID: {request.repository_id}")
            return repository

        if request.repository_name is not None:
            repository = await self._repository_repo.find_by_name(
                request.repository_name
            )
            if not repository:
                raise RepositoryNotFound(request.repository_name)
            return repository

        raise ValueError("Either repository_id or repository_name must be provided")
