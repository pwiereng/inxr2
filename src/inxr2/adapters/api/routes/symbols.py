"""Symbol API endpoints for code browsing."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from ....application.use_cases.symbols import (
    GetSymbolReferencesRequest,
    SearchSymbolsRequest,
)
from ....domain.exceptions import SymbolNotFound
from ....infrastructure.dependencies import (
    FileAdapter,
    GetSymbolReferencesUseCaseDep,
    SearchSymbolsUseCaseDep,
    SymbolAdapter,
)
from .search import _validate_extensions

router = APIRouter(prefix="/symbols", tags=["symbols"])


# Response models
class SymbolResponse(BaseModel):
    """Symbol response model."""

    id: int
    name: str
    qualified_name: str | None
    kind: str
    file_id: int
    file_path: str | None = None
    repository_id: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    signature: str | None = None
    docstring: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SymbolListResponse(BaseModel):
    """Paginated symbol list response."""

    items: list[SymbolResponse]
    total: int
    limit: int
    offset: int


class ReferenceResponse(BaseModel):
    """Reference response model."""

    id: int
    source_file_id: int
    source_file_path: str | None = None
    source_line: int
    source_column: int
    target_symbol_id: int | None
    reference_text: str
    reference_type: str

    model_config = ConfigDict(from_attributes=True)


class ReferencesListResponse(BaseModel):
    """References list response."""

    items: list[ReferenceResponse]
    total: int
    symbol_name: str


@router.get("", response_model=SymbolListResponse)
async def search_symbols(
    use_case: SearchSymbolsUseCaseDep,
    q: str = Query(default="", description="Search query for symbol name"),
    kind: str | None = Query(default=None, description="Filter by symbol kind"),
    repository_id: int | None = Query(default=None, description="Filter by repository"),
    branch: str | None = Query(default=None, description="Filter by branch name"),
    language: str | None = Query(
        default=None, description="Filter by programming language"
    ),
    extensions: list[str] | None = Query(
        default=None, description="Filter by file extension (e.g., .py, .ts)"
    ),
    mode: str | None = Query(
        default=None,
        description="Search mode: 'regex' for regex matching on symbol names",
    ),
    case_sensitive: bool = Query(
        default=True,
        description="Case-sensitive matching (applies to all search modes)",
    ),
    scope: Literal["latest"] = Query(
        default="latest",
        description="Search scope when no repository is specified",
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
) -> SymbolListResponse:
    """
    Search symbols by name with optional filters.

    Returns paginated list of symbols matching the query.
    """
    _validate_extensions(extensions)
    result = await use_case.execute(
        SearchSymbolsRequest(
            query=q,
            repository_id=repository_id,
            kind=kind,
            limit=limit,
            offset=offset,
            branch=branch,
            language=language,
            extensions=extensions,
            scope=scope,
            mode=mode,
            case_sensitive=case_sensitive,
        )
    )

    return SymbolListResponse(
        items=[
            SymbolResponse(
                id=s.symbol.id or 0,
                name=s.symbol.name,
                qualified_name=s.symbol.qualified_name,
                kind=s.symbol.kind.value,
                file_id=s.symbol.file_id,
                file_path=s.file_path,
                repository_id=s.symbol.repository_id,
                start_line=s.symbol.start_line,
                start_column=s.symbol.start_column,
                end_line=s.symbol.end_line,
                end_column=s.symbol.end_column,
                signature=s.symbol.signature,
                docstring=s.symbol.docstring,
            )
            for s in result.symbols
        ],
        total=result.total,
        limit=result.limit,
        offset=result.offset,
    )


@router.get("/by-name/{name}", response_model=SymbolListResponse)
async def get_symbols_by_name(
    name: str,
    use_case: SearchSymbolsUseCaseDep,
    repository_id: int | None = Query(default=None, description="Filter by repository"),
    commit: str | None = Query(
        default=None,
        description="Commit hash for time travel (requires repository_id)",
    ),
) -> SymbolListResponse:
    """
    Get all symbols with the exact given name.

    Useful for disambiguation when multiple symbols have the same name
    (e.g., save() methods in different classes).

    Query parameters:
    - repository_id: Filter by repository (optional, required if commit is set)
    - commit: Commit hash for time travel (optional, requires repository_id)
    """
    if commit and not repository_id:
        raise HTTPException(
            status_code=400,
            detail="repository_id is required when commit is specified",
        )

    result = await use_case.execute(
        SearchSymbolsRequest(
            query=name,
            repository_id=repository_id,
            commit_hash=commit,
            exact_match=True,
            limit=1000,  # High limit for exact match
        )
    )

    return SymbolListResponse(
        items=[
            SymbolResponse(
                id=s.symbol.id or 0,
                name=s.symbol.name,
                qualified_name=s.symbol.qualified_name,
                kind=s.symbol.kind.value,
                file_id=s.symbol.file_id,
                file_path=s.file_path,
                repository_id=s.symbol.repository_id,
                start_line=s.symbol.start_line,
                start_column=s.symbol.start_column,
                end_line=s.symbol.end_line,
                end_column=s.symbol.end_column,
                signature=s.symbol.signature,
                docstring=s.symbol.docstring,
            )
            for s in result.symbols
        ],
        total=result.total,
        limit=result.total,
        offset=0,
    )


@router.get("/{symbol_id}", response_model=SymbolResponse)
async def get_symbol(
    symbol_id: int,
    symbol_adapter: SymbolAdapter,
    file_adapter: FileAdapter,
) -> SymbolResponse:
    """Get a specific symbol by ID."""
    symbol = await symbol_adapter.find_by_id(symbol_id)
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol not found")

    # Get file path
    file_path = None
    if symbol.file_id:
        file = await file_adapter.find_by_id(symbol.file_id)
        if file:
            file_path = file.path

    return SymbolResponse(
        id=symbol.id or 0,
        name=symbol.name,
        qualified_name=symbol.qualified_name,
        kind=symbol.kind,
        file_id=symbol.file_id,
        file_path=file_path,
        repository_id=symbol.repository_id,
        start_line=symbol.start_line,
        start_column=symbol.start_column,
        end_line=symbol.end_line,
        end_column=symbol.end_column,
        signature=symbol.signature,
        docstring=symbol.docstring,
    )


@router.get("/{symbol_id}/references", response_model=ReferencesListResponse)
async def get_symbol_references(
    symbol_id: int,
    use_case: GetSymbolReferencesUseCaseDep,
    by_name: bool = Query(
        default=True,
        description="If true, find all references matching the symbol name "
        "(useful when multiple symbols have the same name)",
    ),
    commit: str | None = Query(
        default=None, description="Commit hash for time travel (optional)"
    ),
    branch: str | None = Query(
        default=None,
        description="Branch name to filter references (only show references from files on this branch)",
    ),
    limit: int = Query(default=100, ge=1, le=500, description="Max results"),
) -> ReferencesListResponse:
    """
    Find all references to a symbol.

    Returns list of places where this symbol is referenced (used).
    When by_name=true (default), finds all references matching the symbol name,
    which is useful when multiple symbols share the same name (e.g., save() methods).

    Query parameters:
    - by_name: If true, find all references matching the symbol name
    - commit: Commit hash for time travel (optional). If provided, returns
              references from that specific commit only.
    - branch: Branch name to filter references. Only returns references from
              files that exist on this branch.
    """
    try:
        result = await use_case.execute(
            GetSymbolReferencesRequest(
                symbol_id=symbol_id,
                by_name=by_name,
                commit_hash=commit,
                branch=branch,
                limit=limit,
            )
        )
    except SymbolNotFound:
        raise HTTPException(status_code=404, detail="Symbol not found") from None

    return ReferencesListResponse(
        items=[
            ReferenceResponse(
                id=r.reference.id or 0,
                source_file_id=r.reference.source_file_id,
                source_file_path=r.source_file_path,
                source_line=r.reference.source_line,
                source_column=r.reference.source_column,
                target_symbol_id=r.reference.target_symbol_id,
                reference_text=r.reference.reference_text,
                reference_type=r.reference.reference_type.value,
            )
            for r in result.references
        ],
        total=result.total,
        symbol_name=result.symbol_name,
    )
