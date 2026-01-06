"""Indexing API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ....adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from ....adapters.persistence.repositories.file_adapter import PostgresFileRepository
from ....adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from ....application.use_cases.indexing.index_local_directory import (
    IndexLocalDirectoryRequest,
    IndexLocalDirectoryUseCase,
)
from ....infrastructure.database import get_db_session

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
    session: AsyncSession = Depends(get_db_session),
):
    """
    Index a local directory.

    This creates a repository and indexes all text files in the directory.
    """
    # Create adapters
    repo_adapter = PostgresRepositoryAdapter(session)
    commit_adapter = PostgresCommitRepository(session)
    file_adapter = PostgresFileRepository(session)

    # Create use case
    use_case = IndexLocalDirectoryUseCase(
        repository_repo=repo_adapter,
        commit_repo=commit_adapter,
        file_repo=file_adapter,
    )

    # Execute indexing
    try:
        response = await use_case.execute(
            IndexLocalDirectoryRequest(
                path=request.path, name=request.name, description=request.description
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")

    return IndexLocalResponse(
        repository_id=response.repository_id,
        total_files=response.total_files,
        indexed_files=response.indexed_files,
        skipped_files=response.skipped_files,
    )
