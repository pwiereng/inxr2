"""Indexing API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ....application.use_cases.indexing.index_local_directory import (
    IndexLocalDirectoryRequest,
)
from ....infrastructure.dependencies import IndexLocalDirectoryUseCaseDep

router = APIRouter(prefix="/index", tags=["indexing"])


# Request/Response models
class IndexLocalRequest(BaseModel):
    """Request to index a local directory."""

    path: str
    name: str
    description: str | None = None


class IndexLocalResponse(BaseModel):
    """Response from indexing a local directory."""

    repository_id: int
    total_files: int
    indexed_files: int
    skipped_files: int


@router.post("/local", response_model=IndexLocalResponse)
async def index_local_directory(
    request: IndexLocalRequest,
    use_case: IndexLocalDirectoryUseCaseDep,
) -> IndexLocalResponse:
    """
    Index a local directory.

    This creates a repository and indexes all text files in the directory.
    """
    # Execute indexing
    try:
        response = await use_case.execute(
            IndexLocalDirectoryRequest(
                path=request.path, name=request.name, description=request.description
            )
        )
    except (ValueError, OSError, RuntimeError) as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}") from e

    return IndexLocalResponse(
        repository_id=response.repository_id,
        total_files=response.total_files,
        indexed_files=response.indexed_files,
        skipped_files=response.skipped_files,
    )
