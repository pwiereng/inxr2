"""Repository API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from ....application.use_cases.dependencies import (
    GetRepositoryDependenciesRequest,
)
from ....application.use_cases.repositories import (
    GetRepositoryBranchesRequest,
    GetRepositoryStatsRequest,
)
from ....application.use_cases.repositories.get_repository_files import (
    GetRepositoryFilesRequest,
)
from ....application.use_cases.repositories.get_repository_stats import RepositoryStats
from ....application.use_cases.repositories.get_repository_tree import (
    GetRepositoryTreeRequest,
    TreeNode,
)
from ....application.use_cases.symbols import (
    GetSymbolTreeFilesResponse,
    GetSymbolTreeRequest,
)
from ....infrastructure.dependencies import (
    GetAllRepositoryStatsUseCaseDep,
    GetRepositoryBranchesUseCaseDep,
    GetRepositoryDependenciesUseCaseDep,
    GetRepositoryFilesUseCaseDep,
    GetRepositoryStatsUseCaseDep,
    GetRepositoryTreeUseCaseDep,
    GetSymbolTreeUseCaseDep,
    ListRepositoriesUseCaseDep,
    RepositoryAdapter,
)
from ..converters import RepositoryResponse, repository_to_response

router = APIRouter(prefix="/repositories", tags=["repositories"])


# Response models


class FileResponse(BaseModel):
    """File response model."""

    id: int
    repository_id: int
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
    total_lines: int = 0
    total_references_resolved: int = 0
    total_references_unresolved: int = 0
    commit_date_earliest: str | None = None
    commit_date_latest: str | None = None
    last_indexed_at: str | None = None
    last_indexed_commit: str | None = None
    last_indexing_duration_seconds: float | None = None
    last_resolving_duration_seconds: float | None = None
    git_head_commit: str | None = None
    is_stale: bool = False


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

    return [repository_to_response(repo) for repo in response.repositories]


@router.get("/by-name/{name}", response_model=RepositoryResponse)
async def get_repository_by_name(
    name: str,
    repo_adapter: RepositoryAdapter,
) -> RepositoryResponse:
    """Get a repository by name."""
    repository = await repo_adapter.find_by_name(name)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    return repository_to_response(repository)


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
    repo_adapter: RepositoryAdapter,
    commit: str | None = None,
    branch: str | None = None,
    changed_only: bool = False,
) -> TreeResponse:
    """Get the file tree structure for a repository by name.

    Query parameters:
    - commit: Commit hash for time travel (optional). If provided, returns
              the tree as it existed at that specific commit.
    - branch: Branch name (optional). If provided, resolves to latest
              indexed commit for that branch.
    - changed_only: If true and commit is provided, only show files that were
                    changed at that specific commit (default: false).

    Priority: commit > branch > default (latest)
    """
    try:
        response = await use_case.execute(
            GetRepositoryTreeRequest(
                repository_name=name,
                commit_hash=commit,
                branch=branch,
                changed_only=changed_only,
            )
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


def _stats_to_response(
    stats: RepositoryStats,
) -> RepositoryStatsResponse:
    """Convert RepositoryStats domain object to response model."""
    return RepositoryStatsResponse(
        repository_id=stats.repository_id,
        name=stats.name,
        total_files=stats.total_files,
        total_symbols=stats.total_symbols,
        total_references=stats.total_references,
        languages=stats.language_distribution,
        total_lines=stats.total_lines,
        total_references_resolved=stats.total_references_resolved,
        total_references_unresolved=stats.total_references_unresolved,
        commit_date_earliest=(
            stats.commit_date_earliest.isoformat()
            if stats.commit_date_earliest
            else None
        ),
        commit_date_latest=(
            stats.commit_date_latest.isoformat() if stats.commit_date_latest else None
        ),
        last_indexed_at=(
            stats.last_indexed_at.isoformat() if stats.last_indexed_at else None
        ),
        last_indexed_commit=stats.last_indexed_commit,
        last_indexing_duration_seconds=stats.last_indexing_duration_seconds,
        last_resolving_duration_seconds=stats.last_resolving_duration_seconds,
        git_head_commit=stats.git_head_commit,
        is_stale=stats.is_stale,
    )


@router.get("/stats", response_model=list[RepositoryStatsResponse])
async def get_all_repository_stats(
    use_case: GetAllRepositoryStatsUseCaseDep,
) -> list[RepositoryStatsResponse]:
    """Get statistics for all repositories in a single batch call."""
    all_stats = await use_case.execute()
    return [_stats_to_response(s) for s in all_stats]


@router.get("/{repository_id}", response_model=RepositoryResponse)
async def get_repository(
    repository_id: int,
    repo_adapter: RepositoryAdapter,
) -> RepositoryResponse:
    """Get a specific repository."""
    repository = await repo_adapter.find_by_id(repository_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    return repository_to_response(repository)


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
    branch: str | None = None,
    changed_only: bool = False,
) -> TreeResponse:
    """
    Get the file tree structure for a repository.

    Returns a hierarchical tree of directories and files.

    Query parameters:
    - commit: Commit hash for time travel (optional). If provided, returns
              the tree as it existed at that specific commit.
    - branch: Branch name (optional). If provided, resolves to latest
              indexed commit for that branch.
    - changed_only: If true and commit is provided, only show files that were
                    changed at that specific commit (default: false).

    Priority: commit > branch > default (latest)
    """
    try:
        response = await use_case.execute(
            GetRepositoryTreeRequest(
                repository_id=repository_id,
                commit_hash=commit,
                branch=branch,
                changed_only=changed_only,
            )
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
    use_case: GetRepositoryStatsUseCaseDep,
) -> RepositoryStatsResponse:
    """
    Get statistics for a repository.

    Returns counts of files, symbols, and references.
    """
    stats = await use_case.execute(
        GetRepositoryStatsRequest(repository_id=repository_id)
    )

    return _stats_to_response(stats)


@router.get("/{repository_id}/branches", response_model=BranchListResponse)
async def get_repository_branches(
    repository_id: int,
    use_case: GetRepositoryBranchesUseCaseDep,
) -> BranchListResponse:
    """
    Get all branches for a repository.

    Fetches branches live from the git repository. For each branch,
    also includes indexing status if the branch has been indexed.
    """
    try:
        response = await use_case.execute(
            GetRepositoryBranchesRequest(repository_id=repository_id)
        )
    except ValueError as e:
        # Path not found or git error
        error_msg = str(e).lower()
        if "path not found" in error_msg:
            raise HTTPException(status_code=500, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e

    return BranchListResponse(
        branches=[
            BranchInfoResponse(
                name=b.name,
                last_indexed_commit=b.last_indexed_commit,
                oldest_indexed_commit=b.oldest_indexed_commit,
                commit_count=b.commit_count,
                last_indexed_at=b.last_indexed_at,
            )
            for b in response.branches
        ]
    )


# ---------- Dependencies ----------


class DependencyResponse(BaseModel):
    """Single dependency item."""

    id: int
    package_name: str
    language: str
    version_spec: str | None = None
    resolved_version: str | None = None
    dependency_type: str
    is_direct: bool
    file_id: int
    file_path: str | None = None
    source_line: int | None = None

    model_config = ConfigDict(from_attributes=True)


class DependenciesListResponse(BaseModel):
    """List of dependencies for a repository."""

    repository_id: int
    repository_name: str
    commit_hash: str | None = None
    items: list[DependencyResponse]
    total: int


@router.get("/by-name/{name}/dependencies", response_model=DependenciesListResponse)
async def get_repository_dependencies_by_name(
    name: str,
    use_case: GetRepositoryDependenciesUseCaseDep,
    commit: str | None = None,
    branch: str | None = None,
    language: str | None = None,
    dependency_type: str | None = None,
    is_direct: bool | None = None,
) -> DependenciesListResponse:
    """Get dependencies for a repository by name.

    Query parameters:
    - commit: Commit hash for time travel (optional)
    - branch: Branch name (optional, resolves to latest indexed commit)
    - language: Filter by ecosystem (python, javascript, java, csharp)
    - dependency_type: Filter by type (runtime, dev, optional, build, peer)
    - is_direct: Filter by direct (true) or transitive (false)

    Priority: commit > branch > default branch
    """
    try:
        response = await use_case.execute(
            GetRepositoryDependenciesRequest(
                repository_name=name,
                commit_hash=commit,
                branch=branch,
                language=language,
                dependency_type=dependency_type,
                is_direct=is_direct,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return DependenciesListResponse(
        repository_id=response.repository_id,
        repository_name=response.repository_name,
        commit_hash=response.commit_hash,
        items=[
            DependencyResponse(
                id=item.id,
                package_name=item.package_name,
                language=item.language,
                version_spec=item.version_spec,
                resolved_version=item.resolved_version,
                dependency_type=item.dependency_type,
                is_direct=item.is_direct,
                file_id=item.file_id,
                file_path=item.file_path,
                source_line=item.source_line,
            )
            for item in response.items
        ],
        total=response.total,
    )


# Symbol tree response models


class SymbolTreeFileResponse(BaseModel):
    """A file entry in the symbol tree."""

    file_id: int
    path: str
    language: str | None
    symbol_count: int
    kind_counts: dict[str, int] = {}
    all_kind_counts: dict[str, int] = {}


class SymbolTreeInheritanceResponse(BaseModel):
    """Inheritance reference for a class symbol."""

    reference_text: str
    target_symbol_id: int | None
    target_file_id: int | None = None
    target_file_path: str | None = None
    target_line: int | None = None


class SymbolTreeSymbolResponse(BaseModel):
    """A symbol entry in the symbol tree."""

    id: int
    name: str
    kind: str
    start_line: int
    end_line: int
    file_path: str | None
    has_children: bool
    signature: str | None = None
    inheritance: list[SymbolTreeInheritanceResponse] = []


class SymbolTreeResponse(BaseModel):
    """Symbol tree response — either files (tier 1) or symbols (tier 2/3)."""

    repository_id: int
    files: list[SymbolTreeFileResponse] | None = None
    symbols: list[SymbolTreeSymbolResponse] | None = None
    available_kinds: list[str] | None = None
    total_kind_counts: dict[str, int] | None = None


@router.get("/by-name/{name}/symbol-tree", response_model=SymbolTreeResponse)
async def get_symbol_tree(
    name: str,
    use_case: GetSymbolTreeUseCaseDep,
    branch: str | None = Query(default=None, description="Branch name"),
    commit: str | None = Query(default=None, description="Commit hash"),
    file_id: int | None = Query(default=None, description="File ID to expand (tier 2)"),
    parent_symbol_id: int | None = Query(
        default=None, description="Symbol ID to expand (tier 3)"
    ),
    language: str | None = Query(
        default=None, description="Filter by language (tier 1)"
    ),
    kind: str | None = Query(
        default=None, description="Filter by symbol kind (tier 2/3)"
    ),
    kinds: str | None = Query(
        default=None,
        description="Comma-separated symbol kinds to filter files (tier 1)",
    ),
) -> SymbolTreeResponse:
    """Get the symbol tree for logical view browsing.

    Supports lazy loading in 3 tiers:
    - No file_id or parent_symbol_id: returns files with symbol counts
    - file_id set: returns top-level symbols in that file
    - parent_symbol_id set: returns children of that symbol

    The response is scoped to the given branch/commit for temporal
    consistency with the file browser.
    """
    try:
        kinds_list = (
            [k.strip() for k in kinds.split(",") if k.strip()] if kinds else None
        )
        result = await use_case.execute(
            GetSymbolTreeRequest(
                repository_name=name,
                branch=branch,
                commit_hash=commit,
                file_id=file_id,
                parent_symbol_id=parent_symbol_id,
                language=language,
                kind=kind,
                kinds=kinds_list,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    if isinstance(result, GetSymbolTreeFilesResponse):
        return SymbolTreeResponse(
            repository_id=result.repository_id,
            files=[
                SymbolTreeFileResponse(
                    file_id=f.file_id,
                    path=f.path,
                    language=f.language,
                    symbol_count=f.symbol_count,
                    kind_counts=f.kind_counts,
                    all_kind_counts=f.all_kind_counts,
                )
                for f in result.files
            ],
            available_kinds=result.available_kinds or None,
            total_kind_counts=result.total_kind_counts or None,
        )
    else:
        return SymbolTreeResponse(
            repository_id=result.repository_id,
            symbols=[
                SymbolTreeSymbolResponse(
                    id=n.symbol.id or 0,
                    name=n.symbol.name,
                    kind=n.symbol.kind.value,
                    start_line=n.symbol.start_line,
                    end_line=n.symbol.end_line,
                    file_path=n.file_path,
                    has_children=n.has_children,
                    signature=n.symbol.signature,
                    inheritance=[
                        SymbolTreeInheritanceResponse(
                            reference_text=inh.reference_text,
                            target_symbol_id=inh.target_symbol_id,
                            target_file_id=inh.target_file_id,
                            target_file_path=inh.target_file_path,
                            target_line=inh.target_line,
                        )
                        for inh in n.inheritance
                    ],
                )
                for n in result.symbols
            ],
        )
