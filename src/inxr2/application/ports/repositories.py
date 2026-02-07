"""Repository port interfaces - data access abstractions.

These are Clean Architecture ports (interfaces) that define the contract
for data access. Implementations (adapters) will use specific persistence
mechanisms like PostgreSQL.
"""

from abc import ABC, abstractmethod

from ...domain.entities import (
    Commit,
    File,
    IndexStatus,
    Reference,
    Repository,
    Symbol,
    TextContent,
)


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

    @abstractmethod
    async def get_or_create(
        self,
        name: str,
        url: str | None = None,
        description: str | None = None,
        default_branch: str | None = None,
    ) -> tuple["Repository", bool]:
        """Get existing repository by name, or create if not exists.

        Atomically handles race conditions where multiple processes might
        try to create the same repository simultaneously.

        Args:
            name: Unique repository name
            url: Repository URL (local path or remote URL)
            description: Optional description
            default_branch: Default branch name

        Returns:
            Tuple of (Repository, created) where created is True if
            a new repository was created, False if existing was returned.
        """
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
    async def find_by_ids(self, file_ids: list[int]) -> dict[int, File]:
        """Find multiple files by IDs in a single query.

        Args:
            file_ids: List of file IDs to fetch

        Returns:
            Dictionary mapping file_id to File entity.
            Missing IDs are not included in the result.
        """
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
    async def list_changed_at_commit(
        self, repository_id: int, commit_id: int
    ) -> list[File]:
        """List only files that actually changed at a specific commit.

        Returns files where either:
        - The file is new (no prior version exists), OR
        - The file's content_hash differs from the most recent prior version

        This is used for the "changed files only" tree view, showing only
        files that were modified at the target commit, not the full tree.

        Args:
            repository_id: The repository ID
            commit_id: The target commit ID

        Returns:
            List of files that were actually changed/added at this commit
        """
        pass

    @abstractmethod
    async def list_at_or_before_commit(
        self, repository_id: int, commit_id: int
    ) -> list[File]:
        """List the latest version of each file at or before a specific commit.

        This returns the full file tree state as it existed at the given commit,
        including files that weren't modified at that commit but existed from
        earlier commits. For delta-indexed repositories, this aggregates across
        all commits up to and including the target.

        Args:
            repository_id: The repository ID
            commit_id: The target commit ID (must exist in the database)

        Returns:
            List of files representing the complete tree state at that commit
        """
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

    @abstractmethod
    async def find_one_by_content_hash_in_repo(
        self, repository_id: int, content_hash: str
    ) -> File | None:
        """Find first file with matching content hash within a repository.

        Used for content-hash based symbol/reference reuse optimization.
        When indexing multiple commits, files with identical content can
        reuse symbols/references from a previously indexed version.

        Args:
            repository_id: The repository to search within
            content_hash: The content hash to match

        Returns:
            The first matching file, or None if no match found
        """
        pass

    @abstractmethod
    async def get_content_hash_to_file_id_map(
        self, repository_id: int
    ) -> dict[str, int]:
        """Load all content hashes for a repository into memory.

        Returns a mapping of content_hash -> file_id for fast in-memory lookup
        during indexing. This avoids per-file database queries when checking
        for donor files with matching content.

        Args:
            repository_id: The repository to load hashes for

        Returns:
            Dict mapping content_hash to file_id
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

    @abstractmethod
    async def copy_symbols_to_file(
        self,
        source_file_id: int,
        target_file_id: int,
        target_commit_id: int,
        target_repository_id: int,
    ) -> int:
        """Copy all symbols from source file to target file.

        Used for content-hash based symbol reuse optimization.
        Creates new symbol records with the target file/commit IDs while
        preserving all other symbol attributes.

        Parent symbol IDs are remapped to point to the newly created symbols.

        Args:
            source_file_id: The file ID to copy symbols from
            target_file_id: The file ID to copy symbols to
            target_commit_id: The commit ID for the new symbols
            target_repository_id: The repository ID for the new symbols

        Returns:
            Number of symbols copied
        """
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
        self,
        symbol_id: int,
        limit: int = 100,
        commit_id: int | None = None,
        branch: str | None = None,
    ) -> list[Reference]:
        """Find all references TO a symbol (find usages).

        Args:
            symbol_id: The target symbol ID
            limit: Maximum number of results
            commit_id: Filter by specific commit for time travel (optional).
                       If None, returns from latest version of each file.
            branch: Filter by branch name (only show refs from files on this branch).
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
        branch: str | None = None,
    ) -> list[Reference]:
        """Find all references matching the given text.

        Args:
            text: The reference text to match
            repository_id: Filter by repository
            limit: Maximum number of results
            commit_id: Filter by specific commit for time travel (optional).
                       If None, returns from latest version of each file.
            branch: Filter by branch name (only show refs from files on this branch).
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
    async def count_unresolved_references(self, repository_id: int) -> int:
        """Count references that don't have a target_symbol_id set.

        Args:
            repository_id: The repository ID to count for

        Returns:
            Number of unresolved references
        """
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

    @abstractmethod
    async def resolve_references_batch(
        self,
        repository_id: int,
        batch_size: int = 1000,
        commit_aware: bool = False,
    ) -> int:
        """Resolve a batch of unlinked references.

        Processes up to batch_size references at a time. Call repeatedly
        until it returns 0 to resolve all references.

        Args:
            repository_id: The repository ID to resolve references for
            batch_size: Maximum references to resolve in this batch
            commit_aware: If True, only match to symbols from same commit

        Returns:
            Number of references resolved in this batch
        """
        pass

    @abstractmethod
    async def copy_references_to_file(
        self,
        source_file_id: int,
        target_file_id: int,
        target_commit_id: int,
        target_repository_id: int,
    ) -> int:
        """Copy all references from source file to target file.

        Used for content-hash based reference reuse optimization.
        Creates new reference records with the target file/commit IDs while
        preserving all other reference attributes.

        Note: target_symbol_id is set to NULL for copied references.
        They will be resolved later by resolve_unlinked_references.

        Args:
            source_file_id: The file ID to copy references from
            target_file_id: The file ID to copy references to
            target_commit_id: The commit ID for the new references
            target_repository_id: The repository ID for the new references

        Returns:
            Number of references copied
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


class TextContentRepositoryPort(ABC):
    """Port for text content operations.

    Manages searchable text extracted from various sources:
    - Comments and docstrings from code files
    - Commit messages
    - Content from non-code files (markdown, YAML, etc.)
    """

    @abstractmethod
    async def save(self, text_content: TextContent) -> TextContent:
        """Save or update a text content entry."""
        pass

    @abstractmethod
    async def save_batch(self, text_contents: list[TextContent]) -> list[TextContent]:
        """Bulk save text contents for performance.

        Args:
            text_contents: List of text content entities to save

        Returns:
            List of saved text content entities with IDs populated
        """
        pass

    @abstractmethod
    async def delete_by_commit(self, commit_id: int) -> int:
        """Delete all text contents for a commit (for re-indexing).

        Args:
            commit_id: The commit ID to delete text contents for

        Returns:
            Number of text contents deleted
        """
        pass

    @abstractmethod
    async def delete_by_file(self, file_id: int) -> int:
        """Delete all text contents for a file (for re-indexing).

        Args:
            file_id: The file ID to delete text contents for

        Returns:
            Number of text contents deleted
        """
        pass
