"""Symbol not found exception."""

from .base import DomainException


class SymbolNotFound(DomainException):
    """Raised when a symbol cannot be found."""

    def __init__(self, symbol_id: str) -> None:
        """
        Initialize exception.

        Args:
            symbol_id: ID of symbol that was not found
        """
        super().__init__(
            f"Symbol not found: {symbol_id}",
            details={"symbol_id": symbol_id},
        )
