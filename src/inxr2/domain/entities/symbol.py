"""Symbol entity - represents a code symbol (function, class, etc)."""

from dataclasses import dataclass
from typing import Any

from ..value_objects.symbol_kind import SymbolKind
from ..value_objects.symbol_location import SymbolLocation


@dataclass(frozen=True)
class Symbol:
    """
    A code symbol (function, class, variable, etc).

    Attributes:
        id: Unique symbol identifier
        name: Symbol name
        kind: Symbol kind (function, class, variable, etc)
        location: Location in source code
        file_id: File containing this symbol
        scope: Namespace or scope path (e.g., "module.Class")
        metadata: Language-specific metadata (JSONB)

    TODO: Add qualified name computation
    TODO: Add scope resolution methods
    """

    id: str
    name: str
    kind: SymbolKind
    location: SymbolLocation
    file_id: str
    scope: str | None = None
    metadata: dict[str, Any] | None = None
