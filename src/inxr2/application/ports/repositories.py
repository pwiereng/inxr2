"""Repository port interfaces - data access abstractions.

These are Clean Architecture ports (interfaces) that define the contract
for data access. Implementations (adapters) will use specific persistence
mechanisms like PostgreSQL.
"""

from abc import ABC, abstractmethod

from ...domain.entities import Commit, File, IndexStatus, Reference, Repository, Symbol


class RepositoryPort(ABC):
    """Port for repository entity operations."""

    @abstractmethod
    async def save(self, repository: Repository) -> Repository:
        """Save or update a repository."""
        pass

    @abstractmethod
    async def find_by_id(self, repository_id: int) -> Repository | None:
        """Find repository by ID."""
        pass

    @abstractmethod
    async def find_by_name(self, name: str) -> Repository | None:
        """Find repository by unique name."""
        pass

    @abstractmethod
    async def list_all(self) -> list[Repository]:
        """List all repositories."""
        pass

    @abstractmethod
    async def delete(self, repository_id: int) -> bool:
        """Delete repository and all related data (CASCADE)."""
        pass


class CommitRepositoryPort(ABC):
    """Port for commit entity operations."""

    @abstractmethod
    async def save(self, commit: Commit) -> Commit:
        """Save or update a commit."""
        pass

    @abstractmethod
    async def save_many(self, commits: list[Commit]) -> list[Commit]:
        """Bulk save commits for performance."""
        pass

    @abstractmethod
    async def find_by_id(self, commit_id: int) -> Commit | None:
        """Find commit by ID."""
        pass

    @abstractmethod
    async def find_by_hash(self, repository_id: int, commit_hash: str) -> Commit | None:
        """Find commit by repository and hash.

        Commits are unique per (repository_id, commit_hash) - the same commit
        hash represents the same commit regardless of which branches it's on.
        """
        pass

    @abstractmethod
    async def link_commit_to_branch(
        self, repository_id: int, commit_id: int, branch: str
    ) -> None:
        """Link an existing commit to a branch.

        Creates an entry in the branch_commits junction table.
        Idempotent - if the link already exists, does nothing.

        Args:
            repository_id: The repository ID
            commit_id: The commit database ID
            branch: The branch name to link
        """
        pass

    @abstractmethod
    async def link_commit_to_branches(
        self, repository_id: int, commit_id: int, branches: list[str]
    ) -> None:
        """Link an existing commit to multiple branches.

        Bulk version of link_commit_to_branch for efficiency.
        Idempotent - existing links are ignored.

        Args:
            repository_id: The repository ID
            commit_id: The commit database ID
            branches: List of branch names to link
        """
        pass

    @abstractmethod
    async def get_branches_for_commit(self, commit_id: int) -> list[str]:
        """Get all branches that contain a specific commit.

        Args:
            commit_id: The commit database ID

        Returns:
            List of branch names the commit is on
        """
        pass

    @abstractmethod
    async def list_by_repository(
        self, repository_id: int, branch: str | None = None, limit: int = 100
    ) -> list[Commit]:
        """List commits for a repository, optionally filtered by branch.

        If branch is specified, only returns commits linked to that branch
        via the branch_commits junction table.
        """
        pass

    @abstractmethod
    async def find_latest_by_branch(
        self, repository_id: int, branch: str
    ) -> Commit | None:
        """Find the latest indexed commit for a specific branch.

        Queries via the branch_commits junction table to find commits
        on the specified branch, returning the most recent by commit_date.

        Args:
            repository_id: The repository ID
            branch: The branch name

        Returns:
            The latest commit for the branch, or None if no commits found
        """
        pass


class FileRepositoryPort(ABC):
    """Port for file entity operations."""

    @abstractmethod
    async def save(self, file: File) -> File:
        """Save or update a file."""
        pass

    @abstractmethod
    async def save_many(self, files: list[File]) -> list[File]:
        """Bulk save files for performance."""
        pass

    @abstractmethod
    async def find_by_id(self, file_id: int) -> File | None:
        """Find file by ID."""
        pass

    @abstractmethod
    async def find_by_path(
        self, repository_id: int, commit_id: int, path: str
    ) -> File | None:
        """Find file by repository, commit, and path (temporal query)."""
        pass

    @abstractmethod
    async def list_by_commit(self, commit_id: int) -> list[File]:
        """List all files at a specific commit."""
        pass

    @abstractmethod
    async def list_by_repository(self, repository_id: int) -> list[File]:
        """List all files for a repository (latest version)."""
        pass

    @abstractmethod
    async def find_by_content_hash(self, content_hash: str) -> list[File]:
        """Find files with matching content hash (deduplication)."""
        pass

    @abstractmethod
    async def find_by_repository_and_path(
        self, repository_id: int, path: str
    ) -> File | None:
        """Find file by repository and path (latest version for now)."""
        pass

    @abstractmethod
    async def list_versions_by_path(
        self, repository_id: int, path: str, branch: str | None = None
    ) -> list[File]:
        """List all versions of a file across commits (for time travel).

        Returns files with this path from different commits, ordered by
        commit date descending (newest first).

        Args:
            repository_id: The repository ID
            path: The file path
            branch: Optional branch name to filter versions by
        """
        pass

    @abstractmethod
    async def find_by_repository_path_and_commit_hash(
        self, repository_id: int, path: str, commit_hash: str
    ) -> File | None:
        """Find file by repository, path, and commit hash (for time travel).

        This is useful when the caller has a commit hash instead of commit_id.
        """
        pass

    @abstractmethod
    async def list_latest_by_branch(
        self, repository_id: int, branch: str
    ) -> list[File]:
        """List the latest version of each file on a branch.

        For delta-indexed repositories, this aggregates files across all commits
        on the branch, returning only the most recent version of each unique path.

        Args:
            repository_id: The repository ID
            branch: The branch name

        Returns:
            List of files (latest version of each unique path on the branch)
        """
        pass


class SymbolRepositoryPort(ABC):
    """Port for symbol entity operations."""

    @abstractmethod
    async def save(self, symbol: Symbol) -> Symbol:
        """Save or update a symbol."""
        pass

    @abstractmethod
    async def save_many(self, symbols: list[Symbol]) -> list[Symbol]:
        """Bulk save symbols for performance."""
        pass

    @abstractmethod
    async def find_by_id(self, symbol_id: int) -> Symbol | None:
        """Find symbol by ID."""
        pass

    @abstractmethod
    async def search_by_name(
        self,
        name: str,
        repository_id: int | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> list[Symbol]:
        """Search symbols by name (supports autocomplete)."""
        pass

    @abstractmethod
    async def find_by_qualified_name(
        self, repository_id: int, qualified_name: str
    ) -> list[Symbol]:
        """Find symbols by fully qualified name."""
        pass

    @abstractmethod
    async def list_by_file(self, file_id: int) -> list[Symbol]:
        """List all symbols in a file."""
        pass

    @abstractmethod
    async def find_by_exact_name(
        self,
        name: str,
        repository_id: int | None = None,
        commit_id: int | None = None,
    ) -> list[Symbol]:
        """Find all symbols with exact name match.

        Args:
            name: The exact symbol name to match
            repository_id: Filter by repository (optional)
            commit_id: Filter by specific commit for time travel (optional)
        """
        pass

    @abstractmethod
    async def count_by_repository(self, repository_id: int) -> int:
        """Count total symbols in a repository."""
        pass

    @abstractmethod
    async def delete_by_file(self, file_id: int) -> int:
        """Delete all symbols for a file (for re-indexing). Returns count deleted."""
        pass


class ReferenceRepositoryPort(ABC):
    """Port for reference entity operations."""

    @abstractmethod
    async def save(self, reference: Reference) -> Reference:
        """Save or update a reference."""
        pass

    @abstractmethod
    async def save_many(self, references: list[Reference]) -> list[Reference]:
        """Bulk save references for performance."""
        pass

    @abstractmethod
    async def find_by_id(self, reference_id: int) -> Reference | None:
        """Find reference by ID."""
        pass

    @abstractmethod
    async def find_references_to_symbol(
        self, symbol_id: int, limit: int = 100, commit_id: int | None = None
    ) -> list[Reference]:
        """Find all references TO a symbol (find usages).

        Args:
            symbol_id: The target symbol ID
            limit: Maximum number of results
            commit_id: Filter by specific commit for time travel (optional).
                       If None, returns from latest version of each file.
        """
        pass

    @abstractmethod
    async def list_by_file(self, file_id: int) -> list[Reference]:
        """List all references in a file."""
        pass

    @abstractmethod
    async def find_references_by_text(
        self,
        text: str,
        repository_id: int,
        limit: int = 100,
        commit_id: int | None = None,
    ) -> list[Reference]:
        """Find all references matching the given text.

        Args:
            text: The reference text to match
            repository_id: Filter by repository
            limit: Maximum number of results
            commit_id: Filter by specific commit for time travel (optional).
                       If None, returns from latest version of each file.
        """
        pass

    @abstractmethod
    async def count_by_repository(self, repository_id: int) -> int:
        """Count total references in a repository."""
        pass

    @abstractmethod
    async def delete_by_file(self, file_id: int) -> int:
        """Delete all references for a file (for re-indexing). Returns count deleted."""
        pass

    @abstractmethod
    async def resolve_unlinked_references(
        self, repository_id: int, commit_aware: bool = False
    ) -> int:
        """Resolve references to their target symbols.

        After indexing, this method matches reference_text to symbol names
        and updates the target_symbol_id for each reference.

        Args:
            repository_id: The repository ID to resolve references for
            commit_aware: If True, only match references to symbols from the
                         same commit (for time travel consistency). If False,
                         match across all commits in the repository.

        Returns:
            Number of references resolved
        """
        pass


class IndexStatusRepositoryPort(ABC):
    """Port for index status operations."""

    @abstractmethod
    async def save(self, status: IndexStatus) -> IndexStatus:
        """Save or update index status."""
        pass

    @abstractmethod
    async def find_by_repository_and_branch(
        self, repository_id: int, branch: str
    ) -> IndexStatus | None:
        """Find index status for a repository/branch combination."""
        pass

    @abstractmethod
    async def list_by_repository(self, repository_id: int) -> list[IndexStatus]:
        """List all index statuses for a repository (all branches)."""
        pass
