"""Commit not found exception."""

from .base import DomainException


class CommitNotFound(DomainException):
    """Raised when a commit cannot be found."""

    def __init__(
        self,
        commit_id: int | None = None,
        commit_hash: str | None = None,
    ) -> None:
        """
        Initialize exception.

        Args:
            commit_id: Database ID of commit that was not found (optional)
            commit_hash: Hash of commit that was not found (optional)
        """
        if commit_hash:
            message = f"Commit not found: {commit_hash}"
        elif commit_id:
            message = f"Commit not found with ID: {commit_id}"
        else:
            message = "Commit not found"

        super().__init__(
            message,
            details={
                "commit_id": commit_id,
                "commit_hash": commit_hash,
            },
        )
        self.commit_id = commit_id
        self.commit_hash = commit_hash
