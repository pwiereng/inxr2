"""List commits use case.

Retrieves commits from git and marks which are indexed in the database.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ....domain.exceptions import RepositoryNotFound
from ...ports.repositories import CommitRepositoryPort, RepositoryPort
from ...ports.services import CommitInfo


class GitListCommitsProtocol(Protocol):
    """Protocol for git commit listing operations.

    This protocol defines the minimal interface needed by this use case.
    The concrete GitService class implements these methods.
    """

    def list_commits(
        self,
        repo_path: Path,
        branch: str,
        max_count: int | None = 1000,
        since_days: int | None = None,
    ) -> list[CommitInfo]: ...


@dataclass
class CommitWithMetadata:
    """Commit from git history with indexed status.

    Contains git commit metadata and whether the commit is indexed
    (has files browseable in the database).
    """

    hash: str
    short_hash: str
    message: str
    author_name: str
    author_email: str
    commit_date: str
    is_indexed: bool


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
        commits: List of commits from git history
        total: Total number of commits returned
    """

    commits: list[CommitWithMetadata]
    total: int


class ListCommitsUseCase:
    """Use case for listing commits from git with indexed status.

    Fetches commits directly from the git repository and cross-references
    with the database to determine which are indexed (browseable).

    Handles:
    - Repository resolution
    - Full git history listing for a branch
    - Cross-referencing with indexed commits in DB
    """

    def __init__(
        self,
        repository_repo: RepositoryPort,
        commit_repo: CommitRepositoryPort,
        git_service: GitListCommitsProtocol,
    ) -> None:
        self._repository_repo = repository_repo
        self._commit_repo = commit_repo
        self._git_service = git_service

    async def execute(self, request: ListCommitsRequest) -> ListCommitsResponse:
        """Execute commit listing.

        Args:
            request: Request parameters

        Returns:
            ListCommitsResponse with git commits and indexed status

        Raises:
            RepositoryNotFound: If repository doesn't exist
        """
        # Get repository
        repository = await self._repository_repo.find_by_name(request.repository_name)
        if not repository:
            raise RepositoryNotFound(request.repository_name)

        repository_id = repository.id if repository.id is not None else 0
        repo_path = Path(repository.url)
        branch = request.branch or repository.default_branch

        # Get commits from git (newest first — list_commits returns oldest first)
        # Git may fail if the repo path is invalid (e.g. remote URL, deleted clone)
        try:
            git_commits = self._git_service.list_commits(
                repo_path=repo_path,
                branch=branch,
                max_count=request.limit,
            )
            git_commits.reverse()
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to list git commits for %s: %s", repo_path, exc
            )
            git_commits = []

        # Get indexed commit hashes from DB for cross-referencing
        # Use branch=None to get all indexed commits — a commit is "indexed"
        # if it exists in the DB regardless of which branch it's on.
        indexed_commits = await self._commit_repo.list_by_repository(
            repository_id=repository_id,
            branch=None,
            limit=10000,
        )
        indexed_hashes = {c.commit_hash.value for c in indexed_commits}

        # Build response
        result = [
            CommitWithMetadata(
                hash=ci.hash,
                short_hash=ci.short_hash,
                message=ci.message,
                author_name=ci.author_name,
                author_email=ci.author_email,
                commit_date=ci.commit_date.isoformat(),
                is_indexed=ci.hash in indexed_hashes,
            )
            for ci in git_commits
        ]

        return ListCommitsResponse(
            commits=result,
            total=len(result),
        )
