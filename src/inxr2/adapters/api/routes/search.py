"""Search API endpoints for free text search."""

import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from ....application.use_cases.dependencies import SearchDependenciesRequest
from ....application.use_cases.search import SearchFilesRequest, SearchTextRequest
from ....domain.value_objects import QueryMode, TextSearchSourceType
from ....infrastructure.dependencies import (
    FileSearchAdapter,
    SearchDependenciesUseCaseDep,
    SearchFilesUseCaseDep,
    SearchTextUseCaseDep,
)

router = APIRouter(prefix="/search", tags=["search"])

# Valid values for validation
VALID_MODES = [m.value for m in QueryMode]
VALID_SOURCE_TYPES = [s.value for s in TextSearchSourceType]

# Query length limits
MAX_TEXT_QUERY_LENGTH = 500
MAX_FILE_QUERY_LENGTH = 200

# Extension validation pattern: must start with dot, alphanumeric/dash/underscore, max 20 chars
_EXTENSION_RE = re.compile(r"^\.[a-zA-Z0-9_-]{1,19}$")


def _validate_extensions(extensions: list[str] | None) -> list[str] | None:
    """Validate and normalize extensions to lowercase.

    Allows the sentinel value "(none)" for extensionless files.
    Raises HTTPException 422 for invalid values.
    """
    if extensions is None:
        return None
    normalized = []
    for ext in extensions:
        if ext == "(none)":
            normalized.append(ext)
            continue
        lower_ext = ext.lower()
        if not _EXTENSION_RE.match(lower_ext):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid extension format: '{ext}'. "
                "Extensions must start with '.' and contain only "
                "alphanumeric characters, dashes, or underscores (max 20 chars).",
            )
        normalized.append(lower_ext)
    return normalized


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
    commit_hash: str | None
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
    commit_id: int | None = None
    commit_hash: str | None = None

    model_config = ConfigDict(from_attributes=True)


class FileSearchListResponse(BaseModel):
    """File search results response."""

    files: list[FileSearchResultResponse]
    total_count: int
    limit: int
    offset: int

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
    source_types: (
        list[
            Literal[
                "comment", "docstring", "commit_message", "file_content", "reference"
            ]
        ]
        | None
    ) = Query(
        None, description="Source types filter (e.g., comment, docstring, reference)"
    ),
    languages: list[str] | None = Query(
        None, description="Languages filter (e.g., python, typescript)"
    ),
    extensions: list[str] | None = Query(
        None, description="File extension filter (e.g., .py, .ts)"
    ),
    case_sensitive: bool = Query(
        True,
        description="Case-sensitive matching (applies to all search modes)",
    ),
    scope: Literal["latest"] = Query(
        "latest",
        description="Search scope when no repository is specified",
    ),
    limit: int = Query(50, ge=1, le=500, description="Results per page"),
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
    - scope: Search scope for global search (currently only "latest")
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
    extensions = _validate_extensions(extensions)
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
                extensions=extensions,
                case_sensitive=case_sensitive,
                scope=scope,
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
    use_case: SearchFilesUseCaseDep,
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
    extensions: list[str] | None = Query(
        None, description="File extension filter (e.g., .py, .ts)"
    ),
    scope: Literal["latest"] = Query(
        "latest",
        description="Search scope when no repository is specified",
    ),
    limit: int = Query(50, ge=1, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
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
    - scope: Search scope for global search (currently only "latest")
    - limit: Maximum number of results (1-100, default 20)
    - offset: Pagination offset (default 0)

    Returns:
    - files: List of matching files with metadata
    - total_count: Total number of matching files (for pagination)
    - limit: The limit used
    - offset: The offset used
    """
    extensions = _validate_extensions(extensions)
    try:
        response = await use_case.execute(
            SearchFilesRequest(
                query=q,
                repository_name=repository,
                branch=branch,
                commit_hash=commit_hash,
                language=language,
                extensions=extensions,
                scope=scope,
                limit=limit,
                offset=offset,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return FileSearchListResponse(
        files=[
            FileSearchResultResponse(
                id=f.id,
                path=f.path,
                name=f.name,
                language=f.language,
                repository_id=f.repository_id,
                repository_name=f.repository_name,
                commit_id=f.commit_id,
                commit_hash=f.commit_hash,
            )
            for f in response.files
        ],
        total_count=response.total_count,
        limit=response.limit,
        offset=response.offset,
    )


class ExtensionsResponse(BaseModel):
    """Response containing available file extensions."""

    extensions: list[str]


@router.get("/extensions", response_model=ExtensionsResponse)
async def get_extensions(
    file_adapter: FileSearchAdapter,
    repository_id: int | None = Query(None, description="Repository ID filter"),
    branch: str | None = Query(None, description="Branch filter"),
    scope: Literal["latest"] = Query(
        "latest",
        description="Search scope when no repository is specified",
    ),
) -> ExtensionsResponse:
    """
    Get distinct file extensions available for filtering.

    Returns sorted list of file extensions (e.g., [".css", ".py", ".ts"]).
    Can be scoped by repository and/or branch.
    """
    extensions = await file_adapter.get_distinct_extensions(
        repository_id=repository_id,
        branch=branch,
        scope=scope,
    )
    return ExtensionsResponse(extensions=extensions)


# Dependency search response models
class DependencySearchResultResponse(BaseModel):
    """A single dependency search result."""

    id: int
    package_name: str
    language: str
    version_spec: str | None
    resolved_version: str | None
    dependency_type: str
    is_direct: bool
    file_id: int
    file_path: str | None
    repository_id: int
    repository_name: str

    model_config = ConfigDict(from_attributes=True)


class DependencySearchListResponse(BaseModel):
    """Paginated dependency search results response."""

    results: list[DependencySearchResultResponse]
    total: int
    query: str
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)


@router.get("/dependencies", response_model=DependencySearchListResponse)
async def search_dependencies(
    use_case: SearchDependenciesUseCaseDep,
    q: str = Query(
        ...,
        min_length=1,
        max_length=MAX_TEXT_QUERY_LENGTH,
        description="Package name search query",
    ),
    repo: int | None = Query(
        None, alias="repository_id", description="Repository ID filter"
    ),
    language: str | None = Query(None, description="Language filter"),
    dependency_type: str | None = Query(None, description="Dependency type filter"),
    is_direct: bool | None = Query(None, description="Direct/transitive filter"),
    branch: str | None = Query(None, description="Branch filter"),
    scope: Literal["latest"] = Query(
        "latest",
        description="Search scope — filters to latest file versions",
    ),
    limit: int = Query(50, ge=1, le=500, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> DependencySearchListResponse:
    """
    Search dependencies by package name with partial, case-insensitive matching.

    Returns matching dependencies across repositories, with package name,
    version, source file, and dependency type information.
    Results are scoped to the latest file versions by default.
    """
    response = await use_case.execute(
        SearchDependenciesRequest(
            query=q,
            repository_id=repo,
            language=language,
            dependency_type=dependency_type,
            is_direct=is_direct,
            branch=branch,
            scope=scope,
            limit=limit,
            offset=offset,
        )
    )

    return DependencySearchListResponse(
        results=[
            DependencySearchResultResponse(
                id=r.id,
                package_name=r.package_name,
                language=r.language,
                version_spec=r.version_spec,
                resolved_version=r.resolved_version,
                dependency_type=r.dependency_type,
                is_direct=r.is_direct,
                file_id=r.file_id,
                file_path=r.file_path,
                repository_id=r.repository_id,
                repository_name=r.repository_name,
            )
            for r in response.results
        ],
        total=response.total,
        query=response.query,
        limit=response.limit,
        offset=response.offset,
    )
