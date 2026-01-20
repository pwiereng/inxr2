"""Repository API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from ....application.use_cases.repositories.get_repository_files import (
    GetRepositoryFilesRequest,
)
from ....application.use_cases.repositories.get_repository_tree import (
    GetRepositoryTreeRequest,
    TreeNode,
)
from ....infrastructure.dependencies import (
    FileAdapter,
    GetRepositoryFilesUseCaseDep,
    GetRepositoryTreeUseCaseDep,
    IndexStatusAdapter,
    ListRepositoriesUseCaseDep,
    ReferenceAdapter,
    RepositoryAdapter,
    SymbolAdapter,
)

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


class BranchInfoResponse(BaseModel):
    """Branch information response model."""

    name: str
    last_indexed_commit: str | None
    oldest_indexed_commit: str | None
    commit_count: int
    last_indexed_at: str | None


class BranchListResponse(BaseModel):
    """List of branches response."""

    branches: list[BranchInfoResponse]


@router.get("", response_model=list[RepositoryResponse])
async def list_repositories(
    use_case: ListRepositoriesUseCaseDep,
) -> list[RepositoryResponse]:
    """List all repositories."""
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
    repo_adapter: RepositoryAdapter,
) -> RepositoryResponse:
    """Get a repository by name."""
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


def _tree_node_to_response(node: TreeNode) -> TreeNodeResponse:
    """Convert a TreeNode from the use case to a TreeNodeResponse."""
    return TreeNodeResponse(
        name=node.name,
        path=node.path,
        type=node.node_type,
        file_id=node.file_id,
        language=node.language,
        children=(
            [_tree_node_to_response(child) for child in node.children]
            if node.children
            else None
        ),
    )


@router.get("/by-name/{name}/tree", response_model=TreeResponse)
async def get_repository_tree_by_name(
    name: str,
    use_case: GetRepositoryTreeUseCaseDep,
    commit: str | None = None,
) -> TreeResponse:
    """Get the file tree structure for a repository by name.

    Query parameters:
    - commit: Commit hash for time travel (optional). If provided, returns
              the tree as it existed at that specific commit.
    """
    try:
        response = await use_case.execute(
            GetRepositoryTreeRequest(repository_name=name, commit_hash=commit)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return TreeResponse(
        repository_id=response.repository_id,
        repository_name=response.repository_name,
        root=[_tree_node_to_response(node) for node in response.root],
        total_files=response.total_files,
        total_directories=response.total_directories,
    )


@router.get("/{repository_id}", response_model=RepositoryResponse)
async def get_repository(
    repository_id: int,
    repo_adapter: RepositoryAdapter,
) -> RepositoryResponse:
    """Get a specific repository."""
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
    use_case: GetRepositoryFilesUseCaseDep,
) -> list[FileResponse]:
    """Get all files for a repository."""
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
    use_case: GetRepositoryTreeUseCaseDep,
    commit: str | None = None,
) -> TreeResponse:
    """
    Get the file tree structure for a repository.

    Returns a hierarchical tree of directories and files.

    Query parameters:
    - commit: Commit hash for time travel (optional). If provided, returns
              the tree as it existed at that specific commit.
    """
    try:
        response = await use_case.execute(
            GetRepositoryTreeRequest(repository_id=repository_id, commit_hash=commit)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return TreeResponse(
        repository_id=response.repository_id,
        repository_name=response.repository_name,
        root=[_tree_node_to_response(node) for node in response.root],
        total_files=response.total_files,
        total_directories=response.total_directories,
    )


@router.get("/{repository_id}/stats", response_model=RepositoryStatsResponse)
async def get_repository_stats(
    repository_id: int,
    repo_adapter: RepositoryAdapter,
    file_adapter: FileAdapter,
    symbol_adapter: SymbolAdapter,
    reference_adapter: ReferenceAdapter,
) -> RepositoryStatsResponse:
    """
    Get statistics for a repository.

    Returns counts of files, symbols, and references.
    """
    # Get repository
    repository = await repo_adapter.find_by_id(repository_id)
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Get counts
    files = await file_adapter.list_by_repository(repository_id)
    symbol_count = await symbol_adapter.count_by_repository(repository_id)
    reference_count = await reference_adapter.count_by_repository(repository_id)

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


@router.get("/{repository_id}/branches", response_model=BranchListResponse)
async def get_repository_branches(
    repository_id: int,
    repo_adapter: RepositoryAdapter,
    index_status_adapter: IndexStatusAdapter,
) -> BranchListResponse:
    """
    Get indexed branches for a repository.

    Returns information about each branch including indexing status
    and commit range (for time travel).
    """
    # Verify repository exists
    repository = await repo_adapter.find_by_id(repository_id)
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Get index status for all branches
    statuses = await index_status_adapter.list_by_repository(repository_id)

    return BranchListResponse(
        branches=[
            BranchInfoResponse(
                name=status.branch,
                last_indexed_commit=status.last_indexed_commit,
                oldest_indexed_commit=status.oldest_indexed_commit,
                commit_count=status.total_commits_indexed,
                last_indexed_at=(
                    status.last_indexed_at.isoformat()
                    if status.last_indexed_at
                    else None
                ),
            )
            for status in statuses
            if status.indexing_status == "completed"
        ]
    )
