"""Reference entity - represents a symbol reference."""

from dataclasses import dataclass

from ..value_objects.symbol_location import SymbolLocation


@dataclass(frozen=True)
class Reference:
    """
    A reference to a symbol (usage, call, import, etc).

    Attributes:
        id: Unique reference identifier
        source_location: Where the reference occurs
        source_file_id: File containing the reference
        target_symbol_id: Symbol being referenced (None if unresolved)
        reference_type: Type of reference (usage, call, definition, etc)

    TODO: Add reference type enum
    TODO: Add methods for reference resolution
    """

    id: str
    source_location: SymbolLocation
    source_file_id: str
    target_symbol_id: str | None = None  # None if unresolved
    reference_type: str = "usage"
