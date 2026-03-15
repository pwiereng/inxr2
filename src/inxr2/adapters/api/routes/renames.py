"""File rename API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ....domain.entities import FileRename
from ....infrastructure.dependencies import (
    CommitAdapter,
    FileRenameAdapter,
    RepositoryAdapter,
)
from ..validation import validate_path, validate_repo_name

router = APIRouter(prefix="/renames", tags=["renames"])


class FileRenameResponse(BaseModel):
    """Single file rename response."""

    id: int
    old_path: str
    new_path: str
    similarity: int
    commit_id: int
    commit_hash: str


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
    commit_hash_str = db_commit.commit_hash.value

    return RenamesForCommitResponse(
        renames=[_to_response(r, commit_hash_str) for r in renames],
        total=len(renames),
    )


@router.get("/file-history", response_model=FileHistoryResponse)
async def get_file_history(
    file_rename_adapter: FileRenameAdapter,
    repo_adapter: RepositoryAdapter,
    commit_adapter: CommitAdapter,
    repo: str = Query(..., description="Repository name"),
    path: str = Query(..., description="File path to trace renames for"),
    branch: str | None = Query(None, description="Branch filter (optional)"),
) -> FileHistoryResponse:
    """Get rename history for a file path."""
    repo = validate_repo_name(repo)
    path = validate_path(path)

    repository = await repo_adapter.find_by_name(repo)
    if not repository or repository.id is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    renames = await file_rename_adapter.get_file_history(
        repository_id=repository.id,
        file_path=path,
        branch=branch,
    )

    # Batch-fetch commit hashes for all renames
    commit_ids = list({r.commit_id for r in renames})
    commits = await commit_adapter.find_by_ids(commit_ids) if commit_ids else []
    commit_hash_map: dict[int, str] = {
        c.id: c.commit_hash.value for c in commits if c.id is not None
    }

    return FileHistoryResponse(
        renames=[_to_response(r, commit_hash_map[r.commit_id]) for r in renames],
        total=len(renames),
    )


def _to_response(r: FileRename, commit_hash: str) -> FileRenameResponse:
    """Convert a FileRename entity to an API response."""
    assert r.id is not None, f"FileRename missing id: {r.old_path} -> {r.new_path}"
    return FileRenameResponse(
        id=r.id,
        old_path=r.old_path,
        new_path=r.new_path,
        similarity=r.similarity,
        commit_id=r.commit_id,
        commit_hash=commit_hash,
    )
