"""List commits use case.

Retrieves commits from git and marks which are indexed in the database.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ....domain.exceptions import RepositoryNotFound
from ...ports.repositories import CommitRepositoryPort, RepositoryPort
from ...ports.services import CommitInfo

logger = logging.getLogger(__name__)


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

    def get_tags(self, repo_path: Path) -> dict[str, list[str]]: ...

    def get_merge_base(
        self, repo_path: Path, branch1: str, branch2: str
    ) -> str | None: ...

    def list_branch_commits(
        self,
        repo_path: Path,
        branch: str,
        base_branch: str,
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
    tags: list[str]
    is_branch_specific: bool = False
    is_merge_base: bool = False


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
        except Exception:
            logger.warning(
                "Failed to list git commits for %s",
                repo_path,
                exc_info=True,
            )
            git_commits = []

        # Check which of the returned git commits are indexed in the DB
        git_hashes = [ci.hash for ci in git_commits]
        indexed_hashes = await self._commit_repo.find_indexed_hashes(
            repository_id=repository_id,
            commit_hashes=git_hashes,
        )

        # Fetch tags (commit_hash -> [tag_names])
        try:
            tags_map = self._git_service.get_tags(repo_path)
        except Exception:
            logger.warning(
                "Failed to get tags for %s",
                repo_path,
                exc_info=True,
            )
            tags_map = {}

        # Determine branch-specific commits via list_branch_commits
        # This correctly handles both merged and unmerged branches
        branch_specific_hashes: set[str] = set()
        merge_base_hash: str | None = None
        default_branch = repository.default_branch
        if branch != default_branch:
            try:
                branch_commits = self._git_service.list_branch_commits(
                    repo_path, branch, default_branch
                )
                branch_specific_hashes = {ci.hash for ci in branch_commits}
            except Exception:
                logger.warning(
                    "Failed to list branch commits for %s vs %s",
                    branch,
                    default_branch,
                    exc_info=True,
                )
            # Find the actual merge-base (last common ancestor)
            try:
                merge_base_hash = self._git_service.get_merge_base(
                    repo_path, branch, default_branch
                )
            except Exception:
                logger.warning(
                    "Failed to get merge-base for %s vs %s",
                    branch,
                    default_branch,
                    exc_info=True,
                )

        # For merged branches, git merge-base returns the branch tip (since
        # it's now reachable from main).  In that case, derive the fork point
        # from the commit list: the first non-branch-specific commit after the
        # branch-specific section is the actual fork point.
        if merge_base_hash and merge_base_hash in branch_specific_hashes:
            merge_base_hash = None
            seen_branch_specific = False
            for ci in git_commits:  # newest-first
                if ci.hash in branch_specific_hashes:
                    seen_branch_specific = True
                elif seen_branch_specific:
                    merge_base_hash = ci.hash
                    break

        # Build response (git_commits is newest-first after reverse above)
        result: list[CommitWithMetadata] = []
        for ci in git_commits:
            is_branch_specific = ci.hash in branch_specific_hashes
            is_merge_base = ci.hash == merge_base_hash
            result.append(
                CommitWithMetadata(
                    hash=ci.hash,
                    short_hash=ci.short_hash,
                    message=ci.message,
                    author_name=ci.author_name,
                    author_email=ci.author_email,
                    commit_date=ci.commit_date.isoformat(),
                    is_indexed=ci.hash in indexed_hashes,
                    tags=tags_map.get(ci.hash, []),
                    is_branch_specific=is_branch_specific,
                    is_merge_base=is_merge_base,
                )
            )

        return ListCommitsResponse(
            commits=result,
            total=len(result),
        )
