"""Commits API endpoints for time travel functionality."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from ....infrastructure.dependencies import (
    CommitAdapter,
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

    # Get commits
    commits = await commit_adapter.list_by_repository(
        repository_id=repository_id,
        branch=branch,
        limit=limit,
    )

    return CommitListResponse(
        commits=[
            CommitResponse(
                id=c.id or 0,
                hash=c.commit_hash.value,
                short_hash=c.short_hash or c.commit_hash.value[:7],
                message=c.message[:200] if c.message else "",  # Truncate long messages
                author_name=c.author_name,
                author_email=c.author_email,
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
) -> CommitDetailResponse:
    """
    Get detailed information about a specific commit.
    """
    commit = await commit_adapter.find_by_id(commit_id)
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    return CommitDetailResponse(
        id=commit.id or 0,
        hash=commit.commit_hash.value,
        short_hash=commit.short_hash or commit.commit_hash.value[:7],
        message=commit.message,
        author_name=commit.author_name,
        author_email=commit.author_email,
        author_date=commit.author_date.isoformat() if commit.author_date else "",
        committer_name=commit.committer_name,
        committer_email=commit.committer_email,
        commit_date=commit.commit_date.isoformat() if commit.commit_date else "",
        parent_hashes=commit.parent_hashes or [],
    )
