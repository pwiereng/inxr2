"""Service port interfaces - external service abstractions."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO

from ...domain.entities import Symbol, TextContent
from ...domain.value_objects import AppConfig

if TYPE_CHECKING:
    from ..use_cases.indexing.default_orchestrator import IndexingProgress
    from ..use_cases.indexing.orchestrator import (
        IndexRepositoryRequest,
        IndexRepositoryResponse,
    )

# Progress callback type for indexing operations
ProgressCallback = Callable[["IndexingProgress"], None]


@dataclass(frozen=True)
class FileStat:
    """File statistics returned by FileSystemPort.stat()."""

    size_bytes: int
    is_file: bool
    is_dir: bool


class ParserServicePort(ABC):
    """
    Port for code parsing service.

    Implementations will use tree-sitter or other parsers.

    TODO: Add incremental parsing support
    TODO: Add error recovery
    """

    @abstractmethod
    async def parse_file(self, file_path: Path, language: str) -> list[Symbol]:
        """
        Parse a file and extract symbols.

        Args:
            file_path: Path to file to parse
            language: Programming language

        Returns:
            List of symbols found in file

        TODO: Implement in adapter layer using tree-sitter
        """
        pass


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
    """

    @abstractmethod
    def get_repository_info(self, repo_path: Path) -> RepositoryInfo: ...

    @abstractmethod
    def get_current_commit(self, repo_path: Path, branch: str | None = None) -> str: ...

    @abstractmethod
    def get_commit_info(self, repo_path: Path, commit_hash: str) -> CommitInfo: ...

    @abstractmethod
    def list_commits(
        self,
        repo_path: Path,
        branch: str,
        max_count: int | None = 1000,
        since_days: int | None = None,
    ) -> list[CommitInfo]: ...

    @abstractmethod
    def list_branch_commits(
        self,
        repo_path: Path,
        branch: str,
        base_branch: str,
        max_count: int | None = 1000,
        since_days: int | None = None,
    ) -> list[CommitInfo]: ...

    @abstractmethod
    def list_files(
        self,
        repo_path: Path,
        commit_hash: str,
        patterns: list[str] | None = None,
    ) -> list[str]: ...

    @abstractmethod
    def list_files_with_hashes(
        self,
        repo_path: Path,
        commit_hash: str,
    ) -> dict[str, str]:
        """List all files with their git blob hashes at a specific commit.

        Returns:
            Dict mapping file path to git blob SHA hash.
        """
        ...

    @abstractmethod
    def get_changed_files_in_commit(
        self, repo_path: Path, commit_hash: str
    ) -> ChangedFiles: ...

    @abstractmethod
    def get_file_content(
        self, repo_path: Path, commit_hash: str, file_path: str
    ) -> str: ...

    @abstractmethod
    def list_branches(self, repo_path: Path) -> list[str]: ...

    @abstractmethod
    def get_tags(self, repo_path: Path) -> dict[str, list[str]]:
        """Return mapping of commit_hash -> [tag_names]."""
        ...

    @abstractmethod
    def get_merge_base(self, repo_path: Path, branch1: str, branch2: str) -> str | None:
        """Return the merge-base commit hash of two branches, or None."""
        ...

    @abstractmethod
    def get_blame(
        self, repo_path: Path, commit_hash: str, file_path: str
    ) -> list[BlameLineInfo]: ...

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
            FileNotFoundError: If file doesn't exist at commit
        """
        ...


class ConfigServicePort(ABC):
    """
    Port for configuration loading.

    Implementations will load config from YAML files.
    """

    @abstractmethod
    def load(self, config_path: Path) -> AppConfig:
        """
        Load configuration from a file.

        Args:
            config_path: Path to configuration file (YAML)

        Returns:
            Parsed AppConfig object

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        pass

    @abstractmethod
    def validate(self, config_path: Path) -> list[str]:
        """
        Validate a configuration file without loading it fully.

        Args:
            config_path: Path to configuration file

        Returns:
            List of validation errors (empty if valid)
        """
        pass


class FileSystemPort(ABC):
    """
    Port for file system operations.

    Abstracts file system access to enable testing without real I/O
    and to follow Clean Architecture principles (no I/O in use cases).
    """

    @abstractmethod
    def walk_directory(
        self,
        path: str | Path,
        skip_dirs: set[str] | None = None,
        skip_hidden: bool = True,
    ) -> list[Path]:
        """
        Walk directory tree and return all file paths.

        Args:
            path: Root directory to walk
            skip_dirs: Directory names to skip (e.g., {'__pycache__', 'node_modules'})
            skip_hidden: Whether to skip hidden files/directories (starting with '.')

        Returns:
            List of file paths found
        """
        pass

    @abstractmethod
    def stat(self, path: str | Path) -> FileStat:
        """
        Get file statistics.

        Args:
            path: Path to file

        Returns:
            FileStat with size and type information

        Raises:
            FileNotFoundError: If path doesn't exist
        """
        pass

    @abstractmethod
    def read_bytes(self, path: str | Path) -> bytes:
        """
        Read file content as bytes.

        Args:
            path: Path to file

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file can't be read
        """
        pass

    @abstractmethod
    def read_text(
        self, path: str | Path, encoding: str = "utf-8", errors: str = "strict"
    ) -> str:
        """
        Read file content as text.

        Args:
            path: Path to file
            encoding: Text encoding (default: utf-8)
            errors: Error handling ('strict', 'ignore', 'replace')

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If file doesn't exist
            UnicodeDecodeError: If decoding fails (with errors='strict')
        """
        pass

    @abstractmethod
    def relative_path(self, path: str | Path, base: str | Path) -> str:
        """
        Get path relative to base directory.

        Args:
            path: Absolute path
            base: Base directory path

        Returns:
            Relative path string
        """
        pass

    @abstractmethod
    def exists(self, path: str | Path) -> bool:
        """
        Check if path exists.

        Args:
            path: Path to check

        Returns:
            True if path exists
        """
        pass

    @abstractmethod
    @contextmanager
    def open_binary(self, path: str | Path) -> Iterator[BinaryIO]:
        """
        Open file for binary reading as a context manager.

        Enables streaming reads without loading entire file into memory.

        Args:
            path: Path to file

        Yields:
            Binary file handle

        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file can't be read

        Example:
            with filesystem.open_binary(path) as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    process(chunk)
        """
        pass


class IndexingOrchestratorPort(ABC):
    """
    Port for indexing orchestration.

    This port defines the interface for repository indexing operations,
    allowing different indexing strategies and implementations to be swapped.
    """

    @abstractmethod
    async def index_repository(
        self,
        request: "IndexRepositoryRequest",
        progress_callback: ProgressCallback | None = None,
    ) -> "IndexRepositoryResponse":
        """
        Index a repository with specified strategy.

        Args:
            request: Indexing request parameters
            progress_callback: Optional callback for progress updates

        Returns:
            Indexing results with statistics

        Raises:
            ValueError: If request parameters are invalid
            RuntimeError: If indexing fails critically
        """
        pass


@dataclass(frozen=True)
class TextSearchResult:
    """Result from a text search query.

    Attributes:
        text_content: The matching text content entity
        rank: Relevance score (higher is better, typically 0.0-1.0)
        headline: Optional highlighted snippet showing match context
    """

    text_content: TextContent
    rank: float
    headline: str | None = None


@dataclass(frozen=True)
class TextSearchQuery:
    """Query parameters for text search.

    Attributes:
        query: Search query string
        mode: Query mode (keyword, phrase, regex) - default: keyword
        repository_id: Optional repository filter
        branch: Optional branch name filter (uses branch_commits table)
        commit_id: Optional commit filter (for time travel)
        source_types: Optional list of source types to filter by
        languages: Optional list of languages to filter by
        scope: Search scope for cross-repo search (e.g. "latest").
            Only applies when repository_id is not provided.
        limit: Maximum results to return (default: 20)
        offset: Pagination offset (default: 0)
    """

    query: str
    mode: str = "keyword"  # Use str instead of enum for JSON compatibility
    repository_id: int | None = None
    branch: str | None = None
    commit_id: int | None = None
    source_types: list[str] | None = None
    languages: list[str] | None = None
    extensions: list[str] | None = None
    case_sensitive: bool = True
    scope: str | None = None
    limit: int = 20
    offset: int = 0


class PlaintextParserPort(ABC):
    """Port for parsing non-code text files (markdown, YAML, config, etc.)."""

    @abstractmethod
    def supports_file(self, file_path: str) -> bool:
        """Check if this parser supports the given file."""
        pass

    @abstractmethod
    def parse(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Parse file content into searchable chunks."""
        pass


class TextSearchPort(ABC):
    """
    Port for full-text search operations.

    This is the key abstraction for database-agnostic text search.
    Implementations can use:
    - PostgreSQL tsvector and GIN indexes
    - Elasticsearch (future)

    The port abstracts away database-specific query syntax and ranking algorithms.
    """

    @abstractmethod
    async def search(
        self, query: TextSearchQuery
    ) -> tuple[list[TextSearchResult], int]:
        """
        Execute full-text search.

        Args:
            query: Search query parameters

        Returns:
            Tuple of (results, total_count) where:
            - results: List of matching results (limited by query.limit/offset)
            - total_count: Total number of matches (for pagination)

        Raises:
            ValueError: If query is empty or invalid
        """
        pass
