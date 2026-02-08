"""Service port interfaces - external service abstractions."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
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


class GitServicePort(ABC):
    """
    Port for git operations.

    Implementations will use GitPython or pygit2.

    TODO: Add authentication support
    TODO: Add progress callbacks
    """

    @abstractmethod
    async def clone_repository(self, url: str, destination: Path) -> None:
        """
        Clone a git repository.

        Args:
            url: Repository URL
            destination: Local destination path

        TODO: Implement in adapter layer
        """
        pass

    @abstractmethod
    async def get_file_content(
        self, repo_path: Path, commit_hash: str, file_path: Path
    ) -> str:
        """
        Get file content at specific commit.

        Args:
            repo_path: Path to repository
            commit_hash: Commit hash
            file_path: Path to file within repository

        Returns:
            File content

        TODO: Implement in adapter layer
        """
        pass


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
    - SQLite FTS5
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
