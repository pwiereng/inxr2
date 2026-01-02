"""Base domain exception."""

from typing import Any


class DomainException(Exception):
    """
    Base exception for all domain errors.

    All domain exceptions should inherit from this class.

    TODO: Add error codes/types
    TODO: Add structured error details
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """
        Initialize domain exception.

        Args:
            message: Human-readable error message
            details: Additional error details (optional)
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
