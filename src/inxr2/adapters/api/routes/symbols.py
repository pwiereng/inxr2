"""Symbol API endpoints for code browsing."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from ....adapters.persistence.repositories.file_adapter import PostgresFileRepository
from ....adapters.persistence.repositories.reference_adapter import (
    PostgresReferenceRepository,
)
from ....adapters.persistence.repositories.symbol_adapter import (
    PostgresSymbolRepository,
)
from ....infrastructure.database import get_db_session

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
    q: str = Query(default="", description="Search query for symbol name"),
    kind: str | None = Query(default=None, description="Filter by symbol kind"),
    repository_id: int | None = Query(default=None, description="Filter by repository"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_db_session),
) -> SymbolListResponse:
    """
    Search symbols by name with optional filters.

    Returns paginated list of symbols matching the query.
    """
    symbol_repo = PostgresSymbolRepository(session)
    file_repo = PostgresFileRepository(session)

    # Search symbols
    if q:
        symbols = await symbol_repo.search_by_name(
            name=q,
            repository_id=repository_id,
            kind=kind,
            limit=limit + offset,  # Fetch enough for pagination
        )
    else:
        # If no query, list all symbols (with filters)
        symbols = await symbol_repo.search_by_name(
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
            file = await file_repo.find_by_id(symbol.file_id)
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


@router.get("/{symbol_id}", response_model=SymbolResponse)
async def get_symbol(
    symbol_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> SymbolResponse:
    """Get a specific symbol by ID."""
    symbol_repo = PostgresSymbolRepository(session)
    file_repo = PostgresFileRepository(session)

    symbol = await symbol_repo.find_by_id(symbol_id)
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol not found")

    # Get file path
    file_path = None
    if symbol.file_id:
        file = await file_repo.find_by_id(symbol.file_id)
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
    limit: int = Query(default=100, ge=1, le=500, description="Max results"),
    session: AsyncSession = Depends(get_db_session),
) -> ReferencesListResponse:
    """
    Find all references to a symbol.

    Returns list of places where this symbol is referenced (used).
    """
    symbol_repo = PostgresSymbolRepository(session)
    reference_repo = PostgresReferenceRepository(session)
    file_repo = PostgresFileRepository(session)

    # Get the symbol first
    symbol = await symbol_repo.find_by_id(symbol_id)
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol not found")

    # Get references to this symbol
    references = await reference_repo.find_references_to_symbol(symbol_id, limit=limit)

    # Enrich with file paths
    items: list[ReferenceResponse] = []
    for ref in references:
        file_path = None
        if ref.source_file_id:
            file = await file_repo.find_by_id(ref.source_file_id)
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
