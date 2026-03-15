"""Git service port interface and related data classes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class CommitInfo:
    """Git commit metadata returned by GitServicePort."""

    hash: str
    short_hash: str
    author_name: str
    author_email: str
    author_date: datetime
    committer_name: str
    committer_email: str
    commit_date: datetime
    message: str
    parent_hashes: list[str]


@dataclass(frozen=True)
class ChangedFiles:
    """Files changed in a single commit."""

    added: list[str]
    modified: list[str]
    deleted: list[str]


@dataclass(frozen=True)
class RepositoryInfo:
    """Basic git repository information."""

    name: str
    url: str | None
    current_branch: str | None
    is_bare: bool


@dataclass(frozen=True)
class RenameInfo:
    """A file rename detected in a commit."""

    old_path: str
    new_path: str
    similarity: int  # 0-100 rename similarity score


@dataclass(frozen=True)
class BlameLineInfo:
    """Blame information for a single line of a file."""

    line_number: int
    commit_hash: str
    short_hash: str
    author_name: str
    commit_date: datetime
    message: str


class GitServicePort(ABC):
    """Port for git operations.

    Defines the full synchronous interface for git operations needed by
    the indexing orchestrator and other consumers.

    Exception contract:
        All methods may raise ``InvalidRepositoryPath`` if the repo path
        is not a valid git repository.  Method-specific domain exceptions
        are documented on each method.  Implementations are expected to
        translate backend-specific exceptions (e.g. GitPython's ``git.exc``)
        into domain exceptions for methods called by the application layer.
        Internal/indexing methods may let backend exceptions propagate when
        the caller already handles them.
    """

    @abstractmethod
    def get_repository_info(self, repo_path: Path) -> RepositoryInfo:
        """Get basic repository information.

        Raises:
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        ...

    @abstractmethod
    def get_current_commit(self, repo_path: Path, branch: str | None = None) -> str:
        """Get the current HEAD commit hash.

        Raises:
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        ...

    @abstractmethod
    def get_commit_info(self, repo_path: Path, commit_hash: str) -> CommitInfo:
        """Get detailed information about a commit.

        Raises:
            CommitNotFound: If the commit hash cannot be resolved.
            GitOperationError: If the git operation fails.
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        ...

    @abstractmethod
    def list_commits(
        self,
        repo_path: Path,
        branch: str,
        max_count: int | None = 1000,
        since_days: int | None = None,
    ) -> list[CommitInfo]:
        """List commits for a branch, from oldest to newest.

        Returns an empty list if the branch cannot be found.

        Raises:
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        ...

    @abstractmethod
    def list_branch_commits(
        self,
        repo_path: Path,
        branch: str,
        base_branch: str,
        max_count: int | None = 1000,
        since_days: int | None = None,
    ) -> list[CommitInfo]:
        """List commits made on a branch (from creation to merge/HEAD).

        Returns an empty list if the branch cannot be found.

        Raises:
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        ...

    @abstractmethod
    def list_files(
        self,
        repo_path: Path,
        commit_hash: str,
        patterns: list[str] | None = None,
    ) -> list[str]:
        """List all files in the repository at a specific commit.

        Note: Used by the indexing orchestrator. Backend exceptions may
        propagate; callers should handle accordingly.

        Raises:
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        ...

    @abstractmethod
    def list_files_with_hashes(
        self,
        repo_path: Path,
        commit_hash: str,
    ) -> dict[str, str]:
        """List all files with their git blob hashes at a specific commit.

        Note: Used by the indexing orchestrator. Backend exceptions may
        propagate; callers should handle accordingly.

        Returns:
            Dict mapping file path to git blob SHA hash.

        Raises:
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        ...

    @abstractmethod
    def get_changed_files_in_commit(
        self, repo_path: Path, commit_hash: str
    ) -> ChangedFiles:
        """Get files changed in a single commit (vs its parent).

        Raises:
            CommitNotFound: If the commit hash cannot be resolved.
            GitOperationError: If the git operation fails.
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        ...

    @abstractmethod
    def get_file_content(
        self, repo_path: Path, commit_hash: str, file_path: str
    ) -> str:
        """Get the content of a file at a specific commit.

        Raises:
            FileNotFoundError: If file doesn't exist at commit.
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        ...

    @abstractmethod
    def list_branches(self, repo_path: Path) -> list[str]:
        """List all branches in the repository.

        Raises:
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        ...

    @abstractmethod
    def get_tags(self, repo_path: Path) -> dict[str, list[str]]:
        """Return mapping of commit_hash -> [tag_names].

        Raises:
            GitOperationError: If the git operation fails.
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        ...

    @abstractmethod
    def get_merge_base(self, repo_path: Path, branch1: str, branch2: str) -> str | None:
        """Return the merge-base commit hash of two branches, or None.

        Returns None if no common ancestor is found or if branches
        cannot be resolved.

        Raises:
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        ...

    @abstractmethod
    def get_blame(
        self, repo_path: Path, commit_hash: str, file_path: str
    ) -> list[BlameLineInfo]:
        """Get blame information for each line of a file.

        Raises:
            CommitNotFound: If the commit hash cannot be resolved.
            GitOperationError: If the git operation fails.
            FileNotFoundError: If file doesn't exist at commit.
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        ...

    @abstractmethod
    def get_file_renames_in_commit(
        self, repo_path: Path, commit_hash: str
    ) -> list[RenameInfo]:
        """Get file renames detected in a single commit (vs its parent).

        Uses git's rename detection (similarity-based) to identify files
        that were renamed in this commit.

        Returns:
            List of RenameInfo with old_path, new_path, and similarity score.

        Raises:
            CommitNotFound: If the commit hash cannot be resolved.
            GitOperationError: If the git operation fails.
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        ...

    @abstractmethod
    def get_file_raw_content(
        self, repo_path: Path, commit_hash: str, file_path: str
    ) -> bytes:
        """
        Get the raw bytes of a file at a specific commit.

        Unlike get_file_content() which decodes to str, this returns
        raw bytes for binary files (images, etc.).

        Args:
            repo_path: Path to the git repository
            commit_hash: Commit hash
            file_path: Path to file (relative to repo root)

        Returns:
            Raw file content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist at commit.
            InvalidRepositoryPath: If the path is not a valid git repository.
        """
        ...
