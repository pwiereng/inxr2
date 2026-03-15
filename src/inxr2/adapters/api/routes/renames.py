"""File rename API endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ....infrastructure.dependencies import (
    CommitAdapter,
    FileRenameAdapter,
    RepositoryAdapter,
)
from ..validation import validate_repo_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/renames", tags=["renames"])


class FileRenameResponse(BaseModel):
    """Single file rename response."""

    id: int
    old_path: str
    new_path: str
    similarity: int
    commit_id: int


class RenamesForCommitResponse(BaseModel):
    """File renames for a specific commit."""

    renames: list[FileRenameResponse]
    total: int


class FileHistoryResponse(BaseModel):
    """Rename history for a file path."""

    renames: list[FileRenameResponse]
    total: int


@router.get("/by-commit", response_model=RenamesForCommitResponse)
async def get_renames_for_commit(
    file_rename_adapter: FileRenameAdapter,
    repo_adapter: RepositoryAdapter,
    commit_adapter: CommitAdapter,
    repo: str = Query(..., description="Repository name"),
    commit: str = Query(..., description="Commit hash"),
) -> RenamesForCommitResponse:
    """Get file renames detected in a specific commit."""
    repo = validate_repo_name(repo)

    repository = await repo_adapter.find_by_name(repo)
    if not repository or repository.id is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    db_commit = await commit_adapter.find_by_hash(
        repository_id=repository.id,
        commit_hash=commit,
    )
    if not db_commit or db_commit.id is None:
        raise HTTPException(status_code=404, detail="Commit not found")

    renames = await file_rename_adapter.get_renames_for_commit(db_commit.id)

    return RenamesForCommitResponse(
        renames=[
            FileRenameResponse(
                id=r.id or 0,
                old_path=r.old_path,
                new_path=r.new_path,
                similarity=r.similarity,
                commit_id=r.commit_id,
            )
            for r in renames
        ],
        total=len(renames),
    )


@router.get("/file-history", response_model=FileHistoryResponse)
async def get_file_history(
    file_rename_adapter: FileRenameAdapter,
    repo_adapter: RepositoryAdapter,
    repo: str = Query(..., description="Repository name"),
    path: str = Query(..., description="File path to trace renames for"),
    branch: str | None = Query(None, description="Branch filter (optional)"),
) -> FileHistoryResponse:
    """Get rename history for a file path."""
    repo = validate_repo_name(repo)

    repository = await repo_adapter.find_by_name(repo)
    if not repository or repository.id is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    renames = await file_rename_adapter.get_file_history(
        repository_id=repository.id,
        file_path=path,
        branch=branch,
    )

    return FileHistoryResponse(
        renames=[
            FileRenameResponse(
                id=r.id or 0,
                old_path=r.old_path,
                new_path=r.new_path,
                similarity=r.similarity,
                commit_id=r.commit_id,
            )
            for r in renames
        ],
        total=len(renames),
    )
