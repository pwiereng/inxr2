"""Commits API endpoints for time travel functionality.

Design note: Only essential commit data is stored in DB (hash, dates).
Author info, message, and parent hashes are queried from git on-demand.
See ARCHITECTURAL_REVIEW.md for rationale.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ....application.use_cases.commits import ListCommitsRequest
from ....domain.exceptions import RepositoryNotFound
from ....infrastructure.dependencies import (
    CommitAdapter,
    GitServiceDep,
    ListCommitsUseCaseDep,
    RepositoryAdapter,
)
from ..validation import validate_repo_name

router = APIRouter(prefix="/commits", tags=["commits"])


# Response models
class CommitResponse(BaseModel):
    """Commit response model.

    Note: A commit can exist on multiple branches. Branch information is stored
    in the branch_commits junction table, not on the commit itself.
    """

    hash: str
    short_hash: str
    message: str
    author_name: str
    author_email: str
    commit_date: str
    is_indexed: bool
    tags: list[str] = []


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


@router.get("", response_model=CommitListResponse)
async def list_commits(
    use_case: ListCommitsUseCaseDep,
    repo: str = Query(..., description="Repository name"),
    branch: str | None = Query(None, description="Branch name (optional)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum commits to return"),
) -> CommitListResponse:
    """
    List commits for a repository.

    Query parameters:
    - repo: Repository name (required)
    - branch: Branch name (optional, defaults to repository's default branch)
    - limit: Maximum number of commits to return (default: 50, max: 500)
    """
    # Validate inputs
    repo = validate_repo_name(repo)

    try:
        result = await use_case.execute(
            ListCommitsRequest(
                repository_name=repo,
                branch=branch,
                limit=limit,
            )
        )
    except RepositoryNotFound:
        raise HTTPException(status_code=404, detail="Repository not found") from None

    return CommitListResponse(
        commits=[
            CommitResponse(
                hash=c.hash,
                short_hash=c.short_hash,
                message=c.message or "",
                author_name=c.author_name or "",
                author_email=c.author_email or "",
                commit_date=c.commit_date,
                is_indexed=c.is_indexed,
                tags=c.tags,
            )
            for c in result.commits
        ],
        total=result.total,
    )


@router.get("/{commit_id}", response_model=CommitDetailResponse)
async def get_commit(
    commit_id: int,
    commit_adapter: CommitAdapter,
    repo_adapter: RepositoryAdapter,
    git_service: GitServiceDep,
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
        message = info.message
        author_name = info.author_name
        author_email = info.author_email
        committer_name = info.committer_name
        committer_email = info.committer_email
        parent_hashes = info.parent_hashes
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
