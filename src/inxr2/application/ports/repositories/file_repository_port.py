"""File repository port interfaces for file entity operations."""

from abc import ABC, abstractmethod

from ....domain.entities import File


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
    async def find_or_create_version(
        self,
        repository_id: int,
        path: str,
        content_hash: str,
        size_bytes: int,
        language: str | None = None,
        extension: str | None = None,
        encoding: str = "utf-8",
        is_binary: bool = False,
        line_count: int | None = None,
    ) -> tuple[File, bool]:
        """Find existing file version or create a new one.

        Atomically looks up a file version by (repository_id, path, content_hash).
        If found, returns it. If not, creates it with the provided attributes.

        Args:
            repository_id: Repository this file belongs to
            path: File path relative to repository root
            content_hash: SHA-1 hash of file content
            size_bytes: File size in bytes
            language: Detected programming language
            extension: File extension (e.g., ".py", ".tsx")
            encoding: File encoding
            is_binary: Whether file is binary
            line_count: Number of lines

        Returns:
            Tuple of (File, created) where created is True if a new file
            version was created, False if existing was returned.
        """
        pass

    @abstractmethod
    async def link_file_to_commit(self, file_id: int, commit_id: int) -> None:
        """Link a file version to a commit via commit_files junction table.

        Idempotent - if the link already exists, does nothing.

        Args:
            file_id: The file version ID
            commit_id: The commit ID
        """
        pass

    @abstractmethod
    async def link_files_to_commit(self, file_ids: list[int], commit_id: int) -> None:
        """Bulk link file versions to a commit.

        Idempotent - existing links are ignored.

        Args:
            file_ids: List of file version IDs
            commit_id: The commit ID
        """
        pass

    @abstractmethod
    async def find_by_path(
        self, repository_id: int, commit_id: int, path: str
    ) -> File | None:
        """Find file by repository, commit, and path.

        Joins through commit_files to find the file version linked to the
        given commit with the given path.
        """
        pass

    @abstractmethod
    async def list_by_repository(self, repository_id: int) -> list[File]:
        """List all files for a repository (latest version)."""
        pass

    @abstractmethod
    async def find_by_content_hash(
        self,
        content_hash: str,
        repository_id: int | None = None,
        path: str | None = None,
    ) -> list[File]:
        """Find files with matching content hash.

        Args:
            content_hash: The SHA-1 content hash to search for
            repository_id: Filter to a specific repository (recommended for performance)
            path: Filter to a specific file path (recommended for performance)

        Returns:
            List of files matching the content hash (and optional filters)
        """
        pass

    @abstractmethod
    async def load_file_version_index(
        self, repository_id: int
    ) -> dict[tuple[str, str], int]:
        """Load all file version keys for a repository in a single query.

        Returns a dict mapping (path, content_hash) to file_id for every
        file version in the repository. This allows callers to check file
        existence with a dict lookup instead of individual DB queries.

        Args:
            repository_id: The repository ID

        Returns:
            Dict mapping (path, content_hash) to file_id
        """
        pass

    @abstractmethod
    async def find_by_repository_and_path(
        self, repository_id: int, path: str
    ) -> File | None:
        """Find file by repository and path (latest version for now)."""
        pass


class FileSearchPort(ABC):
    """Port for file search operations.

    Handles file name/path searching and extension discovery.
    Split from FileRepositoryPort to follow Single Responsibility Principle.
    """

    @abstractmethod
    async def search_by_name(
        self,
        query: str,
        repository_id: int | None = None,
        commit_id: int | None = None,
        language: str | None = None,
        extensions: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
        scope: str | None = None,
    ) -> tuple[list[File], int]:
        """Search files by name/path pattern.

        Uses case-insensitive pattern matching on file paths.
        Results are ordered by relevance (exact match first, then prefix, then contains).

        Version selection semantics:
        - If ``commit_id`` is provided, search is scoped to files at that commit
          via commit_files junction.
        - If ``commit_id`` is ``None``, results are deduplicated such that only
          the latest indexed version of each unique (repository_id, path) pair
          is returned.

        Args:
            query: The search pattern to match against file names/paths
            repository_id: Filter by repository (optional)
            commit_id: Filter by specific commit for time travel (optional).
                When None, returns latest version per (repo, path).
            language: Filter by programming language (optional)
            extensions: Filter by file extensions (e.g., [".py", ".ts"]) (optional)
            limit: Maximum number of results (default 50)
            offset: Pagination offset (default 0)
            scope: Search scope for global search (e.g. "latest") when no
                repository_id is specified. Ignored when repository_id is set.

        Returns:
            Tuple of (matching files ordered by relevance, total count of matches).
        """
        pass

    @abstractmethod
    async def get_distinct_extensions(
        self,
        repository_id: int | None = None,
        branch: str | None = None,
        scope: str | None = None,
    ) -> list[str]:
        """Get distinct file extensions across indexed files.

        Args:
            repository_id: Filter by repository (optional)
            branch: Filter by branch (optional, requires repository_id)
            scope: Search scope for global search (e.g. "latest") when no
                repository_id is specified.

        Returns:
            Sorted list of distinct file extensions (e.g., [".css", ".py", ".ts"])
        """
        pass


class FileVersionPort(ABC):
    """Port for file version and temporal navigation operations.

    Handles file listing by commit, branch-based listing, version history,
    and commit-file linkage queries.
    Split from FileRepositoryPort to follow Single Responsibility Principle.
    """

    @abstractmethod
    async def list_by_commit(self, commit_id: int) -> list[File]:
        """List all files at a specific commit.

        Joins through commit_files junction table.
        """
        pass

    @abstractmethod
    async def list_at_or_before_commit(
        self, repository_id: int, commit_id: int
    ) -> list[File]:
        """List the latest version of each file at or before a specific commit.

        With full snapshot indexing via commit_files, this is equivalent
        to list_by_commit since every commit has its complete file tree.
        Falls back to window function for delta-indexed commits.

        Args:
            repository_id: The repository ID
            commit_id: The target commit ID

        Returns:
            List of files representing the complete tree state at that commit
        """
        pass

    @abstractmethod
    async def list_versions_by_path(
        self, repository_id: int, path: str, branch: str | None = None
    ) -> list[File]:
        """List all versions of a file across commits (for time travel).

        Returns distinct file versions (unique content_hash) for this path,
        ordered by newest first.

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

        Gets the latest commit on the branch, then returns all files
        linked to that commit via commit_files.

        Args:
            repository_id: The repository ID
            branch: The branch name

        Returns:
            List of files (latest version of each unique path on the branch)
        """
        pass

    @abstractmethod
    async def list_changed_at_commit(
        self, repository_id: int, commit_id: int
    ) -> list[File]:
        """List only files that actually changed at a specific commit.

        Compares the commit's file set with its parent commit's file set
        to find files that are new or have a different content_hash.

        Args:
            repository_id: The repository ID
            commit_id: The target commit ID

        Returns:
            List of files that were actually changed/added at this commit
        """
        pass

    @abstractmethod
    async def get_commit_ids_for_files(
        self,
        file_ids: list[int],
        repository_id: int | None = None,
        branch: str | None = None,
    ) -> dict[int, list[int]]:
        """Get commit IDs linked to file versions via commit_files junction.

        For each file_id, returns the list of commit IDs that include it,
        ordered by most recent first (by commit_date descending).

        Args:
            file_ids: List of file version IDs to look up
            repository_id: Required when branch is provided
            branch: When provided, only return commit IDs on this branch

        Returns:
            Dict mapping file_id to list of commit_ids.
            Files with no linked commits are omitted.
        """
        pass
