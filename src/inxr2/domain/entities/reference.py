"""Reference entity - represents a symbol reference."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..value_objects.reference_type import ReferenceType


@dataclass(frozen=True)
class Reference:
    """
    A reference to a symbol (usage, call, import, etc).

    Domain entity (framework-agnostic). Separate from SQLAlchemy ORM model.
    References belong to a file version; commit context is provided through
    the commit_files junction table.

    Attributes:
        repository_id: Repository containing this reference
        source_file_id: File version containing the reference
        source_line: Line number where reference occurs (1-indexed)
        source_column: Column number where reference starts (0-indexed)
        source_end_column: Column number where reference ends
        reference_text: The actual text being referenced (e.g., 'calculate_total')
        reference_type: Type of reference (call, import, etc)
        id: Database ID (None for new entities)
        target_symbol_id: Symbol being referenced (None if unresolved)
        target_repository_id: Repository of target (for cross-repo references)
        is_definition: True if this is the definition site
        is_write: True if reference modifies the symbol
        resolution_confidence: Confidence in resolution (0.0-1.0)
        metadata: Language-specific reference metadata (JSONB)
        indexed_at: When reference was indexed
    """

    repository_id: int
    source_file_id: int
    source_line: int
    source_column: int
    source_end_column: int
    reference_text: str
    reference_type: ReferenceType
    id: int | None = None
    target_symbol_id: int | None = None
    target_repository_id: int | None = None
    is_definition: bool = False
    is_write: bool = False
    resolution_confidence: float = 1.0
    metadata: dict[str, Any] | None = None
    indexed_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate reference entity."""
        if not self.reference_text:
            raise ValueError("Reference text cannot be empty")
        if self.source_line < 1:
            raise ValueError(f"Source line must be >= 1: {self.source_line}")
        if self.source_column < 0:
            raise ValueError(f"Source column must be >= 0: {self.source_column}")
        if self.source_end_column < self.source_column:
            raise ValueError(
                f"End column ({self.source_end_column}) cannot be before "
                f"start column ({self.source_column})"
            )
        if not 0.0 <= self.resolution_confidence <= 1.0:
            raise ValueError(
                f"Resolution confidence must be between 0.0 and 1.0: "
                f"{self.resolution_confidence}"
            )
