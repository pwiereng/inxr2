"""Symbol API endpoints for code browsing."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from ....infrastructure.dependencies import (
    FileAdapter,
    ReferenceAdapter,
    SymbolAdapter,
)

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
    commit_id: int
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
    symbol_adapter: SymbolAdapter,
    file_adapter: FileAdapter,
    q: str = Query(default="", description="Search query for symbol name"),
    kind: str | None = Query(default=None, description="Filter by symbol kind"),
    repository_id: int | None = Query(default=None, description="Filter by repository"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
) -> SymbolListResponse:
    """
    Search symbols by name with optional filters.

    Returns paginated list of symbols matching the query.
    """
    # Search symbols
    if q:
        symbols = await symbol_adapter.search_by_name(
            name=q,
            repository_id=repository_id,
            kind=kind,
            limit=limit + offset,  # Fetch enough for pagination
        )
    else:
        # If no query, list all symbols (with filters)
        symbols = await symbol_adapter.search_by_name(
            name="",
            repository_id=repository_id,
            kind=kind,
            limit=limit + offset,
        )

    # Apply offset
    symbols = symbols[offset : offset + limit]

    # Enrich with file paths
    items: list[SymbolResponse] = []
    for symbol in symbols:
        file_path = None
        if symbol.file_id:
            file = await file_adapter.find_by_id(symbol.file_id)
            if file:
                file_path = file.path

        items.append(
            SymbolResponse(
                id=symbol.id or 0,
                name=symbol.name,
                qualified_name=symbol.qualified_name,
                kind=symbol.kind,
                file_id=symbol.file_id,
                file_path=file_path,
                repository_id=symbol.repository_id,
                commit_id=symbol.commit_id,
                start_line=symbol.start_line,
                start_column=symbol.start_column,
                end_line=symbol.end_line,
                end_column=symbol.end_column,
                signature=symbol.signature,
                docstring=symbol.docstring,
            )
        )

    return SymbolListResponse(
        items=items,
        total=len(items),  # TODO: Get actual total count
        limit=limit,
        offset=offset,
    )


@router.get("/by-name/{name}", response_model=SymbolListResponse)
async def get_symbols_by_name(
    name: str,
    symbol_adapter: SymbolAdapter,
    file_adapter: FileAdapter,
    repository_id: int | None = Query(default=None, description="Filter by repository"),
) -> SymbolListResponse:
    """
    Get all symbols with the exact given name.

    Useful for disambiguation when multiple symbols have the same name
    (e.g., save() methods in different classes).
    """
    # Find all symbols with exact name match
    symbols = await symbol_adapter.find_by_exact_name(
        name=name,
        repository_id=repository_id,
    )

    # Enrich with file paths
    items: list[SymbolResponse] = []
    for symbol in symbols:
        file_path = None
        if symbol.file_id:
            file = await file_adapter.find_by_id(symbol.file_id)
            if file:
                file_path = file.path

        items.append(
            SymbolResponse(
                id=symbol.id or 0,
                name=symbol.name,
                qualified_name=symbol.qualified_name,
                kind=symbol.kind,
                file_id=symbol.file_id,
                file_path=file_path,
                repository_id=symbol.repository_id,
                commit_id=symbol.commit_id,
                start_line=symbol.start_line,
                start_column=symbol.start_column,
                end_line=symbol.end_line,
                end_column=symbol.end_column,
                signature=symbol.signature,
                docstring=symbol.docstring,
            )
        )

    return SymbolListResponse(
        items=items,
        total=len(items),
        limit=len(items),
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
        commit_id=symbol.commit_id,
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
    symbol_adapter: SymbolAdapter,
    reference_adapter: ReferenceAdapter,
    file_adapter: FileAdapter,
    by_name: bool = Query(
        default=True,
        description="If true, find all references matching the symbol name "
        "(useful when multiple symbols have the same name)",
    ),
    limit: int = Query(default=100, ge=1, le=500, description="Max results"),
) -> ReferencesListResponse:
    """
    Find all references to a symbol.

    Returns list of places where this symbol is referenced (used).
    When by_name=true (default), finds all references matching the symbol name,
    which is useful when multiple symbols share the same name (e.g., save() methods).
    """
    # Get the symbol first
    symbol = await symbol_adapter.find_by_id(symbol_id)
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol not found")

    # Get references - either by symbol ID or by name
    if by_name:
        # Find all references matching the symbol name (for disambiguation)
        references = await reference_adapter.find_references_by_text(
            symbol.name, symbol.repository_id, limit=limit
        )
    else:
        # Find only references pointing to this specific symbol
        references = await reference_adapter.find_references_to_symbol(
            symbol_id, limit=limit
        )

    # Enrich with file paths
    items: list[ReferenceResponse] = []
    for ref in references:
        file_path = None
        if ref.source_file_id:
            file = await file_adapter.find_by_id(ref.source_file_id)
            if file:
                file_path = file.path

        items.append(
            ReferenceResponse(
                id=ref.id or 0,
                source_file_id=ref.source_file_id,
                source_file_path=file_path,
                source_line=ref.source_line,
                source_column=ref.source_column,
                target_symbol_id=ref.target_symbol_id,
                reference_text=ref.reference_text,
                reference_type=ref.reference_type.value,
            )
        )

    return ReferencesListResponse(
        items=items,
        total=len(items),
        symbol_name=symbol.name,
    )
