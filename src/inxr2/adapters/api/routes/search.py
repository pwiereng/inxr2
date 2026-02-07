"""Search API endpoints for free text search."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from ....application.use_cases.search import SearchTextRequest, SearchTextUseCase
from ....infrastructure.dependencies import SearchTextUseCaseDep

router = APIRouter(prefix="/search", tags=["search"])


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


@router.get("/text", response_model=SearchTextListResponse)
async def search_text(
    use_case: SearchTextUseCaseDep,
    q: str = Query(..., description="Search query"),
    mode: str = Query("keyword", description="Query mode: keyword, phrase, regex"),
    repo: int | None = Query(
        None, alias="repository_id", description="Repository ID filter"
    ),
    branch: str | None = Query(None, description="Branch filter"),
    commit: str | None = Query(
        None, alias="commit_hash", description="Commit hash filter"
    ),
    source_types: list[str] | None = Query(
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
                source_types=source_types,
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
