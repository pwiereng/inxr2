"""Parser service port interfaces."""

from abc import ABC, abstractmethod
from typing import Any


class ParserServicePort(ABC):
    """
    Port for code parsing service.

    Implementations parse source code content and extract symbols, references,
    and comments. The primary implementation uses tree-sitter grammars.
    """

    @abstractmethod
    def supports_language(self, language: str) -> bool:
        """Check if the parser supports a given language.

        Args:
            language: Language name (e.g. "python", "typescript")

        Returns:
            True if language is supported
        """
        pass

    @abstractmethod
    async def parse_file(
        self, content: str, language: str, file_path: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Parse file content and return extracted symbols and references.

        Args:
            content: File content as string
            language: Programming language
            file_path: Path to file (for context/error reporting)

        Returns:
            Tuple of (symbols_data, references_data) as lists of dicts
        """
        pass

    @abstractmethod
    async def extract_comments(
        self, content: str, language: str, file_path: str
    ) -> list[dict[str, Any]]:
        """Extract comments and docstrings from file content.

        Args:
            content: File content as string
            language: Programming language
            file_path: Path to file (for context/error reporting)

        Returns:
            List of comment dicts with keys: content, content_type,
            source_line, source_end_line
        """
        pass


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
