"""File rename API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ....application.ports.repositories import (
    CommitRepositoryPort,
    FileRenameRepositoryPort,
    FileRepositoryPort,
)
from ....domain.entities import Commit, FileRename
from ....infrastructure.dependencies import (
    CommitAdapter,
    FileAdapter,
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


class ResolvePathResponse(BaseModel):
    """Response for the resolve-path endpoint."""

    found: bool
    resolved_path: str | None = None
    renamed_from: str | None = None
    renamed_to: str | None = None
    rename_commit_hash: str | None = None


@router.get("/resolve-path", response_model=ResolvePathResponse)
async def resolve_path(
    file_rename_adapter: FileRenameAdapter,
    repo_adapter: RepositoryAdapter,
    commit_adapter: CommitAdapter,
    file_adapter: FileAdapter,
    repo: str = Query(..., description="Repository name"),
    path: str = Query(..., description="File path to resolve"),
    commit: str = Query(..., description="Commit hash"),
) -> ResolvePathResponse:
    """Resolve a file path at a specific commit, following rename chain if not found.

    Returns found=True if the file exists at path+commit.
    If not found, walks the file_renames table transitively to find the file's
    actual path at the given commit, returning rename direction info for the UI.
    """
    repo = validate_repo_name(repo)
    path = validate_path(path)

    repository = await repo_adapter.find_by_name(repo)
    if not repository or repository.id is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    db_commit = await commit_adapter.find_by_hash(
        repository_id=repository.id,
        commit_hash=commit,
    )
    if not db_commit or db_commit.id is None:
        raise HTTPException(status_code=404, detail="Commit not found")

    file = await file_adapter.find_by_path(repository.id, db_commit.id, path)
    if file is not None:
        return ResolvePathResponse(found=True)

    return await _walk_rename_chain(
        repository_id=repository.id,
        path=path,
        target_commit=db_commit,
        file_rename_adapter=file_rename_adapter,
        commit_adapter=commit_adapter,
        file_adapter=file_adapter,
    )


async def _walk_rename_chain(
    repository_id: int,
    path: str,
    target_commit: Commit,
    file_rename_adapter: FileRenameRepositoryPort,
    commit_adapter: CommitRepositoryPort,
    file_adapter: FileRepositoryPort,
) -> ResolvePathResponse:
    """Walk the rename chain to find the file's path at target_commit.

    Follows rename records transitively (A→B→C) until it finds a path where
    the file exists at target_commit, or exhausts all rename hops.

    Direction is determined by existence checks rather than commit timestamps,
    which avoids false results on non-linear histories (e.g. commits on separate
    branches whose clock times don't reflect git ancestry order).

    Limitation: when multiple rename records involve the same path (e.g. a name
    was reused across branches), only one candidate next-hop is followed at a
    time.  In practice rename graphs are linear (each path appears in at most
    one rename per repo), so this is sufficient.  A BFS/queue approach would be
    needed to handle genuinely branching rename graphs.
    """
    assert target_commit.id is not None

    current_path = path
    visited: set[str] = set()
    first_renamed_from: str | None = None
    first_renamed_to: str | None = None
    first_rename_commit_hash: str | None = None

    while current_path not in visited:
        visited.add(current_path)

        renames = await file_rename_adapter.get_file_history(
            repository_id, current_path
        )
        if not renames:
            break

        rename_commit_ids = list({r.commit_id for r in renames})
        rename_commits = await commit_adapter.find_by_ids(rename_commit_ids)
        hash_map: dict[int, str] = {
            c.id: c.commit_hash.value for c in rename_commits if c.id is not None
        }

        next_path: str | None = None
        for r in renames:
            rename_hash = hash_map.get(r.commit_id)
            if rename_hash is None:
                continue

            # Determine the "other end" of this rename relative to current_path.
            if r.old_path == current_path:
                candidate = r.new_path
                renamed_from: str | None = None
                renamed_to: str | None = r.new_path
            else:
                candidate = r.old_path
                renamed_from = r.old_path
                renamed_to = None

            if candidate in visited:
                continue

            # Check if the candidate actually exists at the target commit.
            # This is direction-agnostic: it works for both forward (browsing
            # an old name at a newer commit) and backward (browsing a new name
            # at an older commit), and correctly handles non-linear histories
            # where commit timestamps don't reflect git ancestry order.
            file = await file_adapter.find_by_path(
                repository_id, target_commit.id, candidate
            )
            if file is not None:
                if first_renamed_from is None and first_renamed_to is None:
                    first_renamed_from = renamed_from
                    first_renamed_to = renamed_to
                    first_rename_commit_hash = rename_hash
                return ResolvePathResponse(
                    found=False,
                    resolved_path=candidate,
                    renamed_from=first_renamed_from,
                    renamed_to=first_renamed_to,
                    rename_commit_hash=first_rename_commit_hash,
                )

            # Candidate not found at target — remember it as a fallback next hop
            # for multi-hop chains (will be checked in the next iteration).
            if next_path is None:
                next_path = candidate
                if first_renamed_from is None and first_renamed_to is None:
                    first_renamed_from = renamed_from
                    first_renamed_to = renamed_to
                    first_rename_commit_hash = rename_hash

        if next_path is None:
            break
        current_path = next_path

    return ResolvePathResponse(found=False)


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
