"""Repository API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from ....adapters.persistence.repositories.file_adapter import PostgresFileRepository
from ....adapters.persistence.repositories.reference_adapter import (
    PostgresReferenceRepository,
)
from ....adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from ....adapters.persistence.repositories.symbol_adapter import (
    PostgresSymbolRepository,
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

    model_config = ConfigDict(from_attributes=True)


class FileResponse(BaseModel):
    """File response model."""

    id: int
    repository_id: int
    commit_id: int
    path: str
    language: str | None
    size_bytes: int
    line_count: int | None

    model_config = ConfigDict(from_attributes=True)


# Tree node response models (defined early for use in multiple endpoints)
class TreeNodeResponse(BaseModel):
    """Tree node for file/directory."""

    name: str
    path: str
    type: str  # "file" or "directory"
    file_id: int | None = None
    language: str | None = None
    children: list["TreeNodeResponse"] | None = None

    model_config = ConfigDict(from_attributes=True)


class TreeResponse(BaseModel):
    """Repository file tree response."""

    repository_id: int
    repository_name: str
    root: list[TreeNodeResponse]
    total_files: int
    total_directories: int


class RepositoryStatsResponse(BaseModel):
    """Repository statistics response."""

    repository_id: int
    name: str
    total_files: int
    total_symbols: int
    total_references: int
    languages: dict[str, int]


@router.get("", response_model=list[RepositoryResponse])
async def list_repositories(
    session: AsyncSession = Depends(get_db_session),
) -> list[RepositoryResponse]:
    """List all repositories."""
    repo_adapter = PostgresRepositoryAdapter(session)
    use_case = ListRepositoriesUseCase(repository_repo=repo_adapter)

    response = await use_case.execute()

    # Convert to response models
    return [
        RepositoryResponse(
            id=repo.id if repo.id is not None else 0,
            name=repo.name,
            url=repo.url,
            description=repo.description,
            default_branch=repo.default_branch,
            created_at=repo.created_at.isoformat() if repo.created_at else None,
            updated_at=repo.updated_at.isoformat() if repo.updated_at else None,
        )
        for repo in response.repositories
    ]


@router.get("/by-name/{name}", response_model=RepositoryResponse)
async def get_repository_by_name(
    name: str,
    session: AsyncSession = Depends(get_db_session),
) -> RepositoryResponse:
    """Get a repository by name."""
    repo_adapter = PostgresRepositoryAdapter(session)
    repository = await repo_adapter.find_by_name(name)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    return RepositoryResponse(
        id=repository.id if repository.id is not None else 0,
        name=repository.name,
        url=repository.url,
        description=repository.description,
        default_branch=repository.default_branch,
        created_at=repository.created_at.isoformat() if repository.created_at else None,
        updated_at=repository.updated_at.isoformat() if repository.updated_at else None,
    )


@router.get("/by-name/{name}/tree", response_model=TreeResponse)
async def get_repository_tree_by_name(
    name: str,
    session: AsyncSession = Depends(get_db_session),
) -> TreeResponse:
    """Get the file tree structure for a repository by name."""
    repo_adapter = PostgresRepositoryAdapter(session)
    file_adapter = PostgresFileRepository(session)

    # Get repository by name
    repository = await repo_adapter.find_by_name(name)
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    repository_id = repository.id if repository.id is not None else 0

    # Get all files
    files = await file_adapter.list_by_repository(repository_id)

    # Build tree structure
    tree_dict: dict[str, TreeNodeResponse] = {}
    root_nodes: list[TreeNodeResponse] = []
    total_dirs = 0

    for file in files:
        parts = file.path.split("/")
        current_path = ""

        for i, part in enumerate(parts):
            parent_path = current_path
            current_path = f"{current_path}/{part}" if current_path else part
            is_file = i == len(parts) - 1

            if current_path not in tree_dict:
                node = TreeNodeResponse(
                    name=part,
                    path=current_path,
                    type="file" if is_file else "directory",
                    file_id=file.id if is_file else None,
                    language=file.language if is_file else None,
                    children=None if is_file else [],
                )
                tree_dict[current_path] = node

                if not is_file:
                    total_dirs += 1

                if parent_path:
                    parent_node = tree_dict.get(parent_path)
                    if parent_node and parent_node.children is not None:
                        parent_node.children.append(node)
                else:
                    root_nodes.append(node)

    # Sort nodes alphabetically (directories first, then files)
    def sort_nodes(nodes: list[TreeNodeResponse]) -> list[TreeNodeResponse]:
        dirs = [n for n in nodes if n.type == "directory"]
        files_list = [n for n in nodes if n.type == "file"]
        dirs = sorted(dirs, key=lambda x: x.name)
        files_list = sorted(files_list, key=lambda x: x.name)
        for d in dirs:
            if d.children:
                d.children = sort_nodes(d.children)
        return dirs + files_list

    root_nodes = sort_nodes(root_nodes)

    return TreeResponse(
        repository_id=repository_id,
        repository_name=repository.name,
        root=root_nodes,
        total_files=len(files),
        total_directories=total_dirs,
    )


@router.get("/{repository_id}", response_model=RepositoryResponse)
async def get_repository(
    repository_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> RepositoryResponse:
    """Get a specific repository."""
    repo_adapter = PostgresRepositoryAdapter(session)
    repository = await repo_adapter.find_by_id(repository_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    return RepositoryResponse(
        id=repository.id if repository.id is not None else 0,
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
) -> list[FileResponse]:
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
        raise HTTPException(status_code=404, detail=str(e)) from e

    # Convert to response models
    return [
        FileResponse(
            id=file.id if file.id is not None else 0,
            repository_id=file.repository_id,
            commit_id=file.commit_id,
            path=file.path,
            language=file.language,
            size_bytes=file.size_bytes,
            line_count=file.line_count,
        )
        for file in response.files
    ]


@router.get("/{repository_id}/tree", response_model=TreeResponse)
async def get_repository_tree(
    repository_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> TreeResponse:
    """
    Get the file tree structure for a repository.

    Returns a hierarchical tree of directories and files.
    """
    repo_adapter = PostgresRepositoryAdapter(session)
    file_adapter = PostgresFileRepository(session)

    # Get repository
    repository = await repo_adapter.find_by_id(repository_id)
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Get all files
    files = await file_adapter.list_by_repository(repository_id)

    # Build tree structure
    tree_dict: dict[str, TreeNodeResponse] = {}
    root_nodes: list[TreeNodeResponse] = []
    total_dirs = 0

    for file in files:
        parts = file.path.split("/")
        current_path = ""

        for i, part in enumerate(parts):
            parent_path = current_path
            current_path = f"{current_path}/{part}" if current_path else part
            is_file = i == len(parts) - 1

            if current_path not in tree_dict:
                node = TreeNodeResponse(
                    name=part,
                    path=current_path,
                    type="file" if is_file else "directory",
                    file_id=file.id if is_file else None,
                    language=file.language if is_file else None,
                    children=None if is_file else [],
                )
                tree_dict[current_path] = node

                if not is_file:
                    total_dirs += 1

                if parent_path:
                    parent_node = tree_dict.get(parent_path)
                    if parent_node and parent_node.children is not None:
                        parent_node.children.append(node)
                else:
                    root_nodes.append(node)

    # Sort nodes alphabetically (directories first, then files)
    def sort_nodes(nodes: list[TreeNodeResponse]) -> list[TreeNodeResponse]:
        dirs = [n for n in nodes if n.type == "directory"]
        files_list = [n for n in nodes if n.type == "file"]
        dirs = sorted(dirs, key=lambda x: x.name)
        files_list = sorted(files_list, key=lambda x: x.name)
        for d in dirs:
            if d.children:
                d.children = sort_nodes(d.children)
        return dirs + files_list

    root_nodes = sort_nodes(root_nodes)

    return TreeResponse(
        repository_id=repository_id,
        repository_name=repository.name,
        root=root_nodes,
        total_files=len(files),
        total_directories=total_dirs,
    )


@router.get("/{repository_id}/stats", response_model=RepositoryStatsResponse)
async def get_repository_stats(
    repository_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> RepositoryStatsResponse:
    """
    Get statistics for a repository.

    Returns counts of files, symbols, and references.
    """
    repo_adapter = PostgresRepositoryAdapter(session)
    file_adapter = PostgresFileRepository(session)
    symbol_repo = PostgresSymbolRepository(session)
    reference_repo = PostgresReferenceRepository(session)

    # Get repository
    repository = await repo_adapter.find_by_id(repository_id)
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Get counts
    files = await file_adapter.list_by_repository(repository_id)
    symbol_count = await symbol_repo.count_by_repository(repository_id)
    reference_count = await reference_repo.count_by_repository(repository_id)

    # Count languages
    languages: dict[str, int] = {}
    for file in files:
        lang = file.language or "unknown"
        languages[lang] = languages.get(lang, 0) + 1

    return RepositoryStatsResponse(
        repository_id=repository_id,
        name=repository.name,
        total_files=len(files),
        total_symbols=symbol_count,
        total_references=reference_count,
        languages=languages,
    )
