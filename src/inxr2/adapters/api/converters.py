"""Shared response models and converter functions for API routes.

Centralizes entity-to-response conversion logic that was previously
duplicated across multiple route files.
"""

from pydantic import BaseModel, ConfigDict

from ...domain.entities.reference import Reference
from ...domain.entities.repository import Repository
from ...domain.entities.symbol import Symbol

# --- Response models (shared across routes) ---


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


class FileSymbolResponse(BaseModel):
    """Symbol in a file response model."""

    id: int
    name: str
    qualified_name: str | None
    kind: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    signature: str | None = None

    model_config = ConfigDict(from_attributes=True)


class FileReferenceResponse(BaseModel):
    """Reference from a file response model."""

    id: int
    reference_text: str
    reference_type: str
    source_line: int
    source_column: int
    target_symbol_id: int | None

    model_config = ConfigDict(from_attributes=True)


# --- Converter functions ---


def repository_to_response(repo: Repository) -> RepositoryResponse:
    """Convert a Repository domain entity to a RepositoryResponse."""
    return RepositoryResponse(
        id=repo.id if repo.id is not None else 0,
        name=repo.name,
        url=repo.url,
        description=repo.description,
        default_branch=repo.default_branch,
        created_at=repo.created_at.isoformat() if repo.created_at else None,
        updated_at=repo.updated_at.isoformat() if repo.updated_at else None,
    )


def symbol_to_response(s: Symbol) -> FileSymbolResponse:
    """Convert a Symbol domain entity to a FileSymbolResponse."""
    return FileSymbolResponse(
        id=s.id or 0,
        name=s.name,
        qualified_name=s.qualified_name,
        kind=s.kind.value,
        start_line=s.start_line,
        start_column=s.start_column,
        end_line=s.end_line,
        end_column=s.end_column,
        signature=s.signature,
    )


def reference_to_response(r: Reference) -> FileReferenceResponse:
    """Convert a Reference domain entity to a FileReferenceResponse."""
    return FileReferenceResponse(
        id=r.id or 0,
        reference_text=r.reference_text,
        reference_type=r.reference_type.value,
        source_line=r.source_line,
        source_column=r.source_column,
        target_symbol_id=r.target_symbol_id,
    )
