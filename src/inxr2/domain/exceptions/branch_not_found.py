"""Branch not found exception."""

from .base import DomainException


class BranchNotFound(DomainException):
    """Raised when a git branch cannot be found."""

    def __init__(
        self,
        branch_name: str,
        repository_name: str | None = None,
    ) -> None:
        """Initialize exception.

        Args:
            branch_name: Name of the branch that was not found
            repository_name: Name of the repository (optional)
        """
        if repository_name:
            msg = f"Branch '{branch_name}' not found in repository '{repository_name}'"
        else:
            msg = f"Branch not found: {branch_name}"

        super().__init__(
            msg,
            details={
                "branch_name": branch_name,
                "repository_name": repository_name,
            },
        )
        self.branch_name = branch_name
        self.repository_name = repository_name
