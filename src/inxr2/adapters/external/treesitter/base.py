"""Base parser abstraction for Tree-sitter language parsers."""

from abc import ABC, abstractmethod
from typing import Any

from tree_sitter import Node


class BaseLanguageParser(ABC):
    """
    Abstract base class for language-specific Tree-sitter parsers.

    Each language parser implements symbol and reference extraction
    for a specific programming language using Tree-sitter AST traversal.
    """

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Return the language name this parser handles."""
        pass

    @abstractmethod
    def extract(
        self,
        root: Node,
        content: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Extract symbols and references from the AST.

        Args:
            root: Tree-sitter root node
            content: Original source code content

        Returns:
            Tuple of (symbols, references) where each is a list of dicts
        """
        pass

    def extract_comments(
        self,
        root: Node,
        content: str,
    ) -> list[dict[str, Any]]:
        """
        Extract comments and docstrings from the AST.

        Base implementation returns empty list. Language-specific parsers
        should override this method to extract comments.

        Args:
            root: Tree-sitter root node
            content: Original source code content

        Returns:
            List of comment dicts with keys:
            - content: The comment text (stripped of comment markers)
            - content_type: Type of comment (inline_comment, block_comment, docstring, etc.)
            - source_line: Starting line number
            - source_end_line: Ending line number (for multi-line comments)
        """
        return []

    def _get_text(self, node: Node, content: str) -> str:
        """Get the text content of a node."""
        return content[node.start_byte : node.end_byte]

    def _node_location(self, node: Node) -> dict[str, int]:
        """Get the location information for a node."""
        return {
            "start_line": node.start_point[0] + 1,
            "start_column": node.start_point[1],
            "end_line": node.end_point[0] + 1,
            "end_column": node.end_point[1],
        }
