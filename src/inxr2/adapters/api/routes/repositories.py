"""Repository API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ....adapters.persistence.mappers import FileMapper, RepositoryMapper
from ....adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from ....adapters.persistence.repositories.file_adapter import PostgresFileRepository
from ....adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from ....application.use_cases.repositories.get_repository_files import (
    GetRepositoryFilesRequest,
    GetRepositoryFilesUseCase,
)
from ....application.use_cases.repositories.list_repositories import (
    ListRepositoriesUseCase,
)
from ....infrastructure.database import get_db_session

router = APIRouter(prefix="/repositories", tags=["repositories"])


# Response models
class RepositoryResponse(BaseModel):
    """Repository response model."""

    id: int
    name: str
    url: str
    description: str | None
    default_branch: str
    created_at: str | None
    updated_at: str | None

    class Config:
        from_attributes = True


class FileResponse(BaseModel):
    """File response model."""

    id: int
    repository_id: int
    commit_id: int
    path: str
    language: str | None
    size_bytes: int
    line_count: int | None

    class Config:
        from_attributes = True


@router.get("", response_model=list[RepositoryResponse])
async def list_repositories(
    session: AsyncSession = Depends(get_db_session),
):
    """List all repositories."""
    repo_adapter = PostgresRepositoryAdapter(session)
    use_case = ListRepositoriesUseCase(repository_repo=repo_adapter)

    response = await use_case.execute()

    # Convert to response models
    return [
        RepositoryResponse(
            id=repo.id,
            name=repo.name,
            url=repo.url,
            description=repo.description,
            default_branch=repo.default_branch,
            created_at=repo.created_at.isoformat() if repo.created_at else None,
            updated_at=repo.updated_at.isoformat() if repo.updated_at else None,
        )
        for repo in response.repositories
    ]


@router.get("/{repository_id}", response_model=RepositoryResponse)
async def get_repository(
    repository_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """Get a specific repository."""
    repo_adapter = PostgresRepositoryAdapter(session)
    repository = await repo_adapter.find_by_id(repository_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    return RepositoryResponse(
        id=repository.id,
        name=repository.name,
        url=repository.url,
        description=repository.description,
        default_branch=repository.default_branch,
        created_at=repository.created_at.isoformat() if repository.created_at else None,
        updated_at=repository.updated_at.isoformat() if repository.updated_at else None,
    )


@router.get("/{repository_id}/files", response_model=list[FileResponse])
async def get_repository_files(
    repository_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """Get all files for a repository."""
    repo_adapter = PostgresRepositoryAdapter(session)
    file_adapter = PostgresFileRepository(session)

    use_case = GetRepositoryFilesUseCase(
        repository_repo=repo_adapter, file_repo=file_adapter
    )

    try:
        response = await use_case.execute(
            GetRepositoryFilesRequest(repository_id=repository_id)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Convert to response models
    return [
        FileResponse(
            id=file.id,
            repository_id=file.repository_id,
            commit_id=file.commit_id,
            path=file.path,
            language=file.language,
            size_bytes=file.size_bytes,
            line_count=file.line_count,
        )
        for file in response.files
    ]
