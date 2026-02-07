"""Search API endpoints for free text search."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from ....application.use_cases.search import SearchTextRequest
from ....domain.value_objects import QueryMode, TextSearchSourceType
from ....infrastructure.dependencies import (
    CommitAdapter,
    FileAdapter,
    RepositoryAdapter,
    SearchTextUseCaseDep,
)

router = APIRouter(prefix="/search", tags=["search"])

# Valid values for validation
VALID_MODES = [m.value for m in QueryMode]
VALID_SOURCE_TYPES = [s.value for s in TextSearchSourceType]

# Query length limits
MAX_TEXT_QUERY_LENGTH = 500
MAX_FILE_QUERY_LENGTH = 200


# Response models
class SearchTextResultResponse(BaseModel):
    """A single text search result."""

    id: int
    repository_id: int
    repository_name: str
    file_path: str | None
    source_line: int | None
    source_end_line: int | None
    source_type: str
    content: str
    content_type: str | None
    language: str | None
    commit_hash: str
    branch: str | None
    rank: float
    headline: str | None

    model_config = ConfigDict(from_attributes=True)


class SearchTextListResponse(BaseModel):
    """Paginated search results response."""

    results: list[SearchTextResultResponse]
    total: int
    query: str
    mode: str
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)


class FileSearchResultResponse(BaseModel):
    """A single file search result."""

    id: int
    path: str
    name: str
    language: str | None
    repository_id: int
    repository_name: str
    commit_id: int
    commit_hash: str

    model_config = ConfigDict(from_attributes=True)


class FileSearchListResponse(BaseModel):
    """File search results response."""

    files: list[FileSearchResultResponse]
    total_count: int

    model_config = ConfigDict(from_attributes=True)


@router.get("/text", response_model=SearchTextListResponse)
async def search_text(
    use_case: SearchTextUseCaseDep,
    q: str = Query(
        ...,
        min_length=1,
        max_length=MAX_TEXT_QUERY_LENGTH,
        description="Search query",
    ),
    mode: Literal["keyword", "phrase", "regex"] = Query(
        "keyword", description="Query mode: keyword, phrase, regex"
    ),
    repo: int | None = Query(
        None, alias="repository_id", description="Repository ID filter"
    ),
    branch: str | None = Query(None, description="Branch filter"),
    commit: str | None = Query(
        None, alias="commit_hash", description="Commit hash filter"
    ),
    source_types: list[Literal["comment", "docstring", "commit_message", "file_content"]]
    | None = Query(
        None, description="Source types filter (e.g., comment, docstring)"
    ),
    languages: list[str] | None = Query(
        None, description="Languages filter (e.g., python, typescript)"
    ),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> SearchTextListResponse:
    """
    Search text content across comments, docstrings, commit messages, and non-code files.

    Supports multiple query modes:
    - keyword: Full-text search with individual words (default)
    - phrase: Exact phrase matching
    - regex: Regular expression search

    Query parameters:
    - q: Search query string (required)
    - mode: Query mode (keyword, phrase, regex)
    - repository_id: Filter by repository
    - branch: Filter by branch name
    - commit_hash: Filter by specific commit (time travel)
    - source_types: Filter by source type (comment, docstring, commit_message, file_content)
    - languages: Filter by language (python, typescript, markdown, etc.)
    - limit: Results per page (1-100, default 20)
    - offset: Pagination offset (default 0)

    Returns:
    - results: List of matching text content items
    - total: Total number of matches (for pagination)
    - query: The search query used
    - mode: The query mode used
    - limit: The limit used
    - offset: The offset used
    """
    try:
        response = await use_case.execute(
            SearchTextRequest(
                query=q,
                mode=mode,
                repository_id=repo,
                branch=branch,
                commit_hash=commit,
                source_types=list(source_types) if source_types else None,
                languages=languages,
                limit=limit,
                offset=offset,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return SearchTextListResponse(
        results=[
            SearchTextResultResponse(
                id=r.id,
                repository_id=r.repository_id,
                repository_name=r.repository_name,
                file_path=r.file_path,
                source_line=r.source_line,
                source_end_line=r.source_end_line,
                source_type=r.source_type,
                content=r.content,
                content_type=r.content_type,
                language=r.language,
                commit_hash=r.commit_hash,
                branch=r.branch,
                rank=r.rank,
                headline=r.headline,
            )
            for r in response.results
        ],
        total=response.total,
        query=response.query,
        mode=response.mode,
        limit=response.limit,
        offset=response.offset,
    )


@router.get("/files", response_model=FileSearchListResponse)
async def search_files(
    file_adapter: FileAdapter,
    repository_adapter: RepositoryAdapter,
    commit_adapter: CommitAdapter,
    q: str = Query(
        ...,
        min_length=1,
        max_length=MAX_FILE_QUERY_LENGTH,
        description="File name/path search query",
    ),
    repository: str | None = Query(None, description="Repository name filter"),
    branch: str | None = Query(None, description="Branch filter"),
    commit_hash: str | None = Query(None, description="Commit hash filter"),
    language: str | None = Query(None, description="Language filter"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
) -> FileSearchListResponse:
    """
    Search files by name or path pattern.

    Returns files matching the query pattern, respecting branch/commit context.
    Results are ordered by relevance (exact filename match, then prefix, then contains).

    Query parameters:
    - q: Search query for file name/path (required, min 1 character)
    - repository: Filter by repository name
    - branch: Filter by branch name
    - commit_hash: Filter by specific commit (time travel)
    - language: Filter by programming language
    - limit: Maximum number of results (1-100, default 20)

    Returns:
    - files: List of matching files with metadata
    - total_count: Number of files returned (at most ``limit``)
    """
    # Validate: branch/commit_hash require repository to be specified
    if (branch or commit_hash) and not repository:
        raise HTTPException(
            status_code=400,
            detail="repository parameter is required when using branch or commit_hash",
        )

    # Resolve repository ID from name if provided
    repository_id: int | None = None
    if repository:
        repo = await repository_adapter.find_by_name(repository)
        if not repo:
            raise HTTPException(
                status_code=404, detail=f"Repository '{repository}' not found"
            )
        repository_id = repo.id

    # Resolve commit ID from hash if provided
    commit_id: int | None = None
    if commit_hash and repository_id:
        commit = await commit_adapter.find_by_hash(repository_id, commit_hash)
        if not commit:
            raise HTTPException(
                status_code=404, detail=f"Commit '{commit_hash}' not found"
            )
        commit_id = commit.id
    elif branch and repository_id:
        # If branch is specified but no commit, get latest commit on branch
        commit = await commit_adapter.find_latest_by_branch(repository_id, branch)
        if commit:
            commit_id = commit.id

    # Search files
    files = await file_adapter.search_by_name(
        query=q,
        repository_id=repository_id,
        commit_id=commit_id,
        language=language,
        limit=limit,
    )

    # Build response with repository names and commit hashes
    results: list[FileSearchResultResponse] = []

    # Collect unique IDs for lookup (using is not None to handle ID=0 correctly)
    repo_ids = {f.repository_id for f in files if f.repository_id is not None}
    commit_ids = {f.commit_id for f in files if f.commit_id is not None}

    # Fetch repositories (N+1 for now; bulk fetch would require new port method)
    repo_map: dict[int, str] = {}
    for rid in repo_ids:
        repo = await repository_adapter.find_by_id(rid)
        if repo:
            repo_map[rid] = repo.name

    # Fetch commits (N+1 for now; bulk fetch would require new port method)
    commit_map: dict[int, str] = {}
    for cid in commit_ids:
        commit = await commit_adapter.find_by_id(cid)
        if commit:
            commit_map[cid] = commit.commit_hash.value

    for file in files:
        # Validate required fields - these should always be set for persisted files
        if file.id is None or file.repository_id is None or file.commit_id is None:
            raise HTTPException(
                status_code=500,
                detail="File search returned incomplete data; this indicates a data integrity issue.",
            )

        # Validate we have the required metadata
        if file.repository_id not in repo_map:
            raise HTTPException(
                status_code=500,
                detail="File references unknown repository; data integrity issue.",
            )
        if file.commit_id not in commit_map:
            raise HTTPException(
                status_code=500,
                detail="File references unknown commit; data integrity issue.",
            )

        # Extract filename from path
        filename = file.path.rsplit("/", 1)[-1] if "/" in file.path else file.path

        results.append(
            FileSearchResultResponse(
                id=file.id,
                path=file.path,
                name=filename,
                language=file.language,
                repository_id=file.repository_id,
                repository_name=repo_map[file.repository_id],
                commit_id=file.commit_id,
                commit_hash=commit_map[file.commit_id],
            )
        )

    return FileSearchListResponse(files=results, total_count=len(results))
