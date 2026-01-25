"""Commits API endpoints for time travel functionality.

Design note: Only essential commit data is stored in DB (hash, dates).
Author info, message, and parent hashes are queried from git on-demand.
See ARCHITECTURAL_REVIEW.md for rationale.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from ....adapters.external.git_service import GitService
from ....infrastructure.dependencies import (
    CommitAdapter,
    RepositoryAdapter,
)
from ..validation import validate_repo_name

router = APIRouter(prefix="/commits", tags=["commits"])


def get_git_service() -> GitService:
    """Get GitService instance."""
    return GitService()


# Response models
class CommitResponse(BaseModel):
    """Commit response model.

    Note: A commit can exist on multiple branches. Branch information is stored
    in the branch_commits junction table, not on the commit itself.
    """

    id: int
    hash: str
    short_hash: str
    message: str
    author_name: str
    author_email: str
    commit_date: str

    model_config = ConfigDict(from_attributes=True)


class CommitListResponse(BaseModel):
    """List of commits response."""

    commits: list[CommitResponse]
    total: int


class CommitDetailResponse(BaseModel):
    """Detailed commit response model.

    Note: A commit can exist on multiple branches. Branch information is stored
    in the branch_commits junction table, not on the commit itself.
    """

    id: int
    hash: str
    short_hash: str
    message: str
    author_name: str
    author_email: str
    author_date: str
    committer_name: str
    committer_email: str
    commit_date: str
    parent_hashes: list[str]

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=CommitListResponse)
async def list_commits(
    repo_adapter: RepositoryAdapter,
    commit_adapter: CommitAdapter,
    repo: str = Query(..., description="Repository name"),
    branch: str | None = Query(None, description="Branch name (optional)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum commits to return"),
    git_service: GitService = Depends(get_git_service),
) -> CommitListResponse:
    """
    List commits for a repository.

    Query parameters:
    - repo: Repository name (required)
    - branch: Branch name (optional, returns all branches if not specified)
    - limit: Maximum number of commits to return (default: 50, max: 500)
    """
    # Validate inputs
    repo = validate_repo_name(repo)

    # Get repository
    repository = await repo_adapter.find_by_name(repo)
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    repository_id = repository.id if repository.id is not None else 0

    # Get commits from DB (only has hash, dates)
    commits = await commit_adapter.list_by_repository(
        repository_id=repository_id,
        branch=branch,
        limit=limit,
    )

    # Hydrate commit info from git if repo path is available
    repo_path = Path(repository.url)  # url contains local path for indexed repos
    commit_info_cache: dict[str, dict[str, str]] = {}

    for c in commits:
        try:
            info = git_service.get_commit_info(repo_path, c.commit_hash.value)
            commit_info_cache[c.commit_hash.value] = {
                "message": info.get("message", "")[:200],
                "author_name": info.get("author_name", ""),
                "author_email": info.get("author_email", ""),
            }
        except Exception:
            # Git query failed - use empty values
            commit_info_cache[c.commit_hash.value] = {
                "message": "",
                "author_name": "",
                "author_email": "",
            }

    return CommitListResponse(
        commits=[
            CommitResponse(
                id=c.id or 0,
                hash=c.commit_hash.value,
                short_hash=c.short_hash,
                message=commit_info_cache.get(c.commit_hash.value, {}).get(
                    "message", ""
                ),
                author_name=commit_info_cache.get(c.commit_hash.value, {}).get(
                    "author_name", ""
                ),
                author_email=commit_info_cache.get(c.commit_hash.value, {}).get(
                    "author_email", ""
                ),
                commit_date=c.commit_date.isoformat() if c.commit_date else "",
            )
            for c in commits
        ],
        total=len(commits),
    )


@router.get("/{commit_id}", response_model=CommitDetailResponse)
async def get_commit(
    commit_id: int,
    commit_adapter: CommitAdapter,
    repo_adapter: RepositoryAdapter,
    git_service: GitService = Depends(get_git_service),
) -> CommitDetailResponse:
    """
    Get detailed information about a specific commit.
    """
    commit = await commit_adapter.find_by_id(commit_id)
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    # Get repository to find git path
    repository = await repo_adapter.find_by_id(commit.repository_id)
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Hydrate full commit info from git
    repo_path = Path(repository.url)
    try:
        info = git_service.get_commit_info(repo_path, commit.commit_hash.value)
        message = info.get("message", "")
        author_name = info.get("author_name", "")
        author_email = info.get("author_email", "")
        committer_name = info.get("committer_name", "")
        committer_email = info.get("committer_email", "")
        parent_hashes = info.get("parent_hashes", [])
    except Exception:
        # Git query failed - use empty values
        message = ""
        author_name = ""
        author_email = ""
        committer_name = ""
        committer_email = ""
        parent_hashes = []

    return CommitDetailResponse(
        id=commit.id or 0,
        hash=commit.commit_hash.value,
        short_hash=commit.short_hash,
        message=message,
        author_name=author_name,
        author_email=author_email,
        author_date=commit.author_date.isoformat() if commit.author_date else "",
        committer_name=committer_name,
        committer_email=committer_email,
        commit_date=commit.commit_date.isoformat() if commit.commit_date else "",
        parent_hashes=parent_hashes,
    )
