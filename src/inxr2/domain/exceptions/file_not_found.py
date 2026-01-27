"""File not found exception."""

from .base import DomainException


class FileNotFound(DomainException):
    """Raised when a file cannot be found."""

    def __init__(
        self,
        path: str,
        repository_name: str | None = None,
        commit_hash: str | None = None,
        branch: str | None = None,
    ) -> None:
        """
        Initialize exception.

        Args:
            path: Path of file that was not found
            repository_name: Repository name (optional)
            commit_hash: Commit hash where file was expected (optional)
            branch: Branch where file was expected (optional)
        """
        if commit_hash:
            message = f"File '{path}' not found at commit {commit_hash}"
        elif branch:
            message = (
                f"File '{path}' not found on branch '{branch}'. "
                f"This branch may not have indexed data for this file."
            )
        else:
            message = f"File not found: {path}"

        super().__init__(
            message,
            details={
                "path": path,
                "repository_name": repository_name,
                "commit_hash": commit_hash,
                "branch": branch,
            },
        )
        self.path = path
        self.repository_name = repository_name
        self.commit_hash = commit_hash
        self.branch = branch
