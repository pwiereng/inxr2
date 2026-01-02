"""Symbol location value object."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolLocation:
    """
    Location of a symbol in source code.

    Attributes:
        line: Line number (1-indexed)
        column: Column number (0-indexed)
        end_line: End line number (optional, for ranges)
        end_column: End column number (optional, for ranges)

    TODO: Add validation for line/column numbers
    TODO: Add methods for range checking
    """

    line: int
    column: int
    end_line: int | None = None
    end_column: int | None = None

    def __post_init__(self) -> None:
        """Validate location."""
        # TODO: Validate line >= 1, column >= 0
        # TODO: Validate end_line >= line if present
        # TODO: Validate end_column >= column if on same line
        pass
