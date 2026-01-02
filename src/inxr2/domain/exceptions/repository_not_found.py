"""Repository not found exception."""

from .base import DomainException


class RepositoryNotFound(DomainException):
    """Raised when a repository cannot be found."""

    def __init__(self, repository_id: str) -> None:
        """
        Initialize exception.

        Args:
            repository_id: ID of repository that was not found
        """
        super().__init__(
            f"Repository not found: {repository_id}",
            details={"repository_id": repository_id},
        )
