"""Service port interfaces - external service abstractions."""

from abc import ABC, abstractmethod
from pathlib import Path

from ...domain.entities import Symbol


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
