"""List commits use case.

Retrieves commits from the database and hydrates with git metadata.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ....domain.entities import Commit
from ....domain.exceptions import RepositoryNotFound
from ...ports.repositories import CommitRepositoryPort, RepositoryPort
from ...ports.services import CommitInfo


class GitCommitInfoProtocol(Protocol):
    """Protocol for git commit info operations.

    This protocol defines the minimal interface needed by this use case.
    The concrete GitService class implements these methods.
    """

    def get_commit_info(self, repo_path: Path, commit_hash: str) -> CommitInfo:
        """Get commit information including message and author.

        Args:
            repo_path: Path to the git repository
            commit_hash: The commit hash to look up

        Returns:
            CommitInfo with commit metadata
        """
        ...


@dataclass
class CommitWithMetadata:
    """Commit enriched with git metadata.

    Contains DB commit data plus author/message info from git.
    """

    commit: Commit
    message: str
    author_name: str
    author_email: str


@dataclass
class ListCommitsRequest:
    """Request to list commits.

    Args:
        repository_name: Name of the repository
        branch: Optional branch filter
        limit: Maximum commits to return
    """

    repository_name: str
    branch: str | None = None
    limit: int = 50


@dataclass
class ListCommitsResponse:
    """Response containing commits with metadata.

    Args:
        commits: List of commits with hydrated metadata
        total: Total number of commits returned
    """

    commits: list[CommitWithMetadata]
    total: int


class ListCommitsUseCase:
    """Use case for listing commits with git metadata hydration.

    Fetches commits from the database and hydrates each with author
    and message information from the git repository.

    Handles:
    - Repository resolution
    - Commit listing with branch filter
    - Batch git metadata hydration
    - Graceful handling of git lookup failures
    """

    def __init__(
        self,
        repository_repo: RepositoryPort,
        commit_repo: CommitRepositoryPort,
        git_service: GitCommitInfoProtocol,
    ) -> None:
        """Initialize use case with dependencies.

        Args:
            repository_repo: Repository for accessing repositories
            commit_repo: Repository for accessing commits
            git_service: Git service for hydrating commit metadata
        """
        self._repository_repo = repository_repo
        self._commit_repo = commit_repo
        self._git_service = git_service

    async def execute(self, request: ListCommitsRequest) -> ListCommitsResponse:
        """Execute commit listing.

        Args:
            request: Request parameters

        Returns:
            ListCommitsResponse with hydrated commits

        Raises:
            RepositoryNotFound: If repository doesn't exist
        """
        # Get repository
        repository = await self._repository_repo.find_by_name(request.repository_name)
        if not repository:
            raise RepositoryNotFound(request.repository_name)

        repository_id = repository.id if repository.id is not None else 0

        # Get commits from DB
        commits = await self._commit_repo.list_by_repository(
            repository_id=repository_id,
            branch=request.branch,
            limit=request.limit,
        )

        # Hydrate with git metadata
        repo_path = Path(repository.url)
        enriched_commits = self._hydrate_commits(commits, repo_path)

        return ListCommitsResponse(
            commits=enriched_commits,
            total=len(enriched_commits),
        )

    def _hydrate_commits(
        self, commits: list[Commit], repo_path: Path
    ) -> list[CommitWithMetadata]:
        """Hydrate commits with git metadata.

        Args:
            commits: List of commits from database
            repo_path: Path to git repository

        Returns:
            List of commits with metadata
        """
        result = []
        for commit in commits:
            try:
                info = self._git_service.get_commit_info(
                    repo_path, commit.commit_hash.value
                )
                message = info.message[:200]  # Truncate for list view
                author_name = info.author_name
                author_email = info.author_email
            except Exception:
                # Git query failed - use empty values
                message = ""
                author_name = ""
                author_email = ""

            result.append(
                CommitWithMetadata(
                    commit=commit,
                    message=message,
                    author_name=author_name,
                    author_email=author_email,
                )
            )

        return result
