"""Git operation error exception."""

from .base import DomainException


class GitOperationError(DomainException):
    """Raised when a git operation fails.

    This is the domain-level abstraction for git backend errors.
    Adapter code should catch implementation-specific exceptions
    (e.g. GitPython's GitCommandError) and re-raise as this type.
    """

    def __init__(
        self,
        operation: str,
        message: str,
    ) -> None:
        """Initialize exception.

        Args:
            operation: The git operation that failed (e.g. "list_commits", "get_blame")
            message: Human-readable error description
        """
        super().__init__(
            f"Git operation '{operation}' failed: {message}",
            details={
                "operation": operation,
            },
        )
        self.operation = operation
