"""Parser service port interfaces and typed return structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParsedSymbol:
    """A symbol extracted from source code by a parser."""

    name: str
    kind: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    scope: str | None = None
    qualified_name: str | None = None
    signature: str | None = None
    docstring: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedReference:
    """A reference (usage, call, import, etc.) extracted from source code."""

    reference_text: str
    reference_type: str
    source_line: int
    source_column: int
    source_end_column: int | None = None
    scope: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedComment:
    """A comment or docstring extracted from source code."""

    content: str
    content_type: str
    source_line: int
    source_end_line: int | None = None


@dataclass(frozen=True)
class PlaintextChunk:
    """A searchable chunk of text extracted from a non-code file."""

    content: str
    content_type: str
    source_line: int
    source_end_line: int | None = None


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
    ) -> tuple[list[ParsedSymbol], list[ParsedReference]]:
        """Parse file content and return extracted symbols and references.

        Args:
            content: File content as string
            language: Programming language
            file_path: Path to file (for context/error reporting)

        Returns:
            Tuple of (symbols, references)
        """
        pass

    @abstractmethod
    async def extract_comments(
        self, content: str, language: str, file_path: str
    ) -> list[ParsedComment]:
        """Extract comments and docstrings from file content.

        Args:
            content: File content as string
            language: Programming language
            file_path: Path to file (for context/error reporting)

        Returns:
            List of ParsedComment with content, content_type, source_line,
            source_end_line
        """
        pass


class PlaintextParserPort(ABC):
    """Port for parsing non-code text files (markdown, YAML, config, etc.)."""

    @abstractmethod
    def supports_file(self, file_path: str) -> bool:
        """Check if this parser supports the given file."""
        pass

    @abstractmethod
    def parse(self, content: str, file_path: str) -> list[PlaintextChunk]:
        """Parse file content into searchable chunks."""
        pass
