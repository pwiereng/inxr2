"""Invalid repository path exception."""

from .base import DomainException


class InvalidRepositoryPath(DomainException):
    """Raised when a path does not point to a valid git repository."""

    def __init__(self, path: str) -> None:
        """Initialize exception.

        Args:
            path: The filesystem path that is not a valid git repository
        """
        super().__init__(
            f"Not a valid git repository: {path}",
            details={"path": path},
        )
        self.path = path
