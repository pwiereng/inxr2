"""Symbol entity - represents a code symbol (function, class, etc)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..value_objects.symbol_kind import SymbolKind
from ..value_objects.symbol_location import SymbolLocation


@dataclass(frozen=True)
class Symbol:
    """
    A code symbol (function, class, variable, etc) at a specific file version.

    Domain entity (framework-agnostic). Separate from SQLAlchemy ORM model.

    Attributes:
        file_id: File containing this symbol
        repository_id: Repository containing this symbol
        commit_id: Commit where this symbol version exists
        name: Simple symbol name (e.g., 'calculate_total')
        kind: Symbol kind (function, class, variable, etc)
        start_line: Starting line number (1-indexed)
        start_column: Starting column number (0-indexed)
        end_line: Ending line number
        end_column: Ending column number
        id: Database ID (None for new entities)
        qualified_name: Fully qualified name (e.g., 'module.Class.method')
        parent_symbol_id: Parent symbol ID (for nested symbols)
        scope: Scope path (e.g., 'Class.method')
        signature: Function/method signature with types
        docstring: Documentation string
        metadata: Language-specific metadata (JSONB)
        indexed_at: When symbol was indexed
    """

    file_id: int
    repository_id: int
    commit_id: int
    name: str
    kind: SymbolKind
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    id: int | None = None
    qualified_name: str | None = None
    parent_symbol_id: int | None = None
    scope: str | None = None
    signature: str | None = None
    docstring: str | None = None
    metadata: dict[str, Any] | None = None
    indexed_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate symbol entity."""
        if not self.name:
            raise ValueError("Symbol name cannot be empty")
        if self.start_line < 1:
            raise ValueError(f"Start line must be >= 1: {self.start_line}")
        if self.start_column < 0:
            raise ValueError(f"Start column must be >= 0: {self.start_column}")
        if self.end_line < self.start_line:
            raise ValueError(
                f"End line ({self.end_line}) cannot be before start line ({self.start_line})"
            )
        if self.end_line == self.start_line and self.end_column < self.start_column:
            raise ValueError(
                f"End column ({self.end_column}) cannot be before start column ({self.start_column}) on same line"
            )

    @property
    def location(self) -> SymbolLocation:
        """Return location as SymbolLocation value object."""
        return SymbolLocation(
            line=self.start_line,
            column=self.start_column,
            end_line=self.end_line,
            end_column=self.end_column,
        )
