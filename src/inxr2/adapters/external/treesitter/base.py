"""Base parser abstraction for Tree-sitter language parsers."""

import logging
from abc import ABC, abstractmethod
from typing import Any

from tree_sitter import Node

logger = logging.getLogger(__name__)


class BaseLanguageParser(ABC):
    """
    Abstract base class for language-specific Tree-sitter parsers.

    Each language parser implements symbol and reference extraction
    for a specific programming language using Tree-sitter AST traversal.
    """

    def __init__(self) -> None:
        self._cached_content: str | None = None
        self._cached_content_bytes: bytes = b""

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

        Walks the tree and delegates to ``_process_comment_node`` for each
        node.  Override ``_process_comment_node`` to classify and clean
        comment nodes.  Override this whole method when the visitor needs
        extra state (e.g. Python docstring detection needs ``parent_node``).

        Returns:
            List of comment dicts with keys:
            - content: The comment text (stripped of comment markers)
            - content_type: Type of comment (single_line_comment, block_comment, docstring, etc.)
            - source_line: Starting line number
            - source_end_line: Ending line number (for multi-line comments)
        """
        comments: list[dict[str, Any]] = []

        def visit_node(node: Node) -> None:
            try:
                result = self._process_comment_node(node, content)
                if result is not None:
                    comments.append(result)
            except (AttributeError, IndexError, KeyError, ValueError) as e:
                # Unexpected AST node structure during comment extraction
                logger.warning(
                    "Skipping comment node %s at line %d: %s",
                    node.type,
                    node.start_point[0] + 1,
                    e,
                )
            for child in node.children:
                visit_node(child)

        visit_node(root)
        return comments

    def _process_comment_node(self, node: Node, content: str) -> dict[str, Any] | None:
        """Override to classify and clean a comment node. Return dict or None."""
        return None

    def _extract_named_type_declaration(
        self,
        node: Node,
        content: str,
        symbols: list[dict[str, Any]],
        symbol_kind: str,
        scope: str | None = None,
        identifier_type: str = "identifier",
        **extra_kwargs: Any,
    ) -> str | None:
        """Extract a named type declaration from an AST node.

        Common pattern: find identifier child, build qualified name, append symbol.
        Used for class, interface, enum, struct, record, etc. declarations.

        Args:
            node: The declaration AST node
            content: Source file content
            symbols: List to append the symbol dict to
            symbol_kind: Symbol kind (e.g., "class", "enum", "struct")
            scope: Parent scope for qualified naming
            identifier_type: Type of identifier node to find (default "identifier")
            **extra_kwargs: Additional symbol metadata (is_abstract, is_final, etc.)

        Returns:
            The extracted type name, or None if no identifier found.
        """
        type_name = None
        name_node = None

        for child in node.children:
            if child.type == identifier_type:
                type_name = self._get_text(child, content)
                name_node = child
                break

        if not type_name:
            return None

        qualified_name = f"{scope}.{type_name}" if scope else type_name
        loc_node = name_node or node

        symbols.append(
            self._make_symbol(
                type_name,
                symbol_kind,
                loc_node,
                scope,
                end_line=node.end_point[0] + 1,
                end_column=node.end_point[1],
                qualified_name=qualified_name,
                **extra_kwargs,
            )
        )

        return type_name

    def _make_symbol(
        self,
        name: str,
        kind: str,
        node: Node,
        scope: str | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """Build a symbol dict from common fields."""
        sym: dict[str, Any] = {
            "name": name,
            "kind": kind,
            **self._node_location(node),
            "scope": scope,
        }
        if scope:
            sym["qualified_name"] = f"{scope}.{name}"
        sym.update(extra)
        return sym

    def _make_reference(
        self,
        text: str,
        ref_type: str,
        node: Node,
        scope: str | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """Build a reference dict from common fields."""
        ref: dict[str, Any] = {
            "text": text,
            "type": ref_type,
            "source_line": node.start_point[0] + 1,
            "source_column": node.start_point[1],
        }
        if scope is not None:
            ref["scope"] = scope
        ref.update(extra)
        return ref

    def _add_reference(
        self, ref: dict[str, Any], references: list[dict[str, Any]]
    ) -> None:
        """Add reference only if it has non-empty text."""
        text = ref.get("text", "")
        if text and text.strip():
            references.append(ref)

    def _strip_block_comment(self, text: str) -> str:
        """Strip /* */ or /** */ markers and leading * prefixes."""
        if text.startswith("/**"):
            text = text[3:-2] if text.endswith("*/") else text[3:]
        elif text.startswith("/*"):
            text = text[2:-2] if text.endswith("*/") else text[2:]
        lines = text.split("\n")
        cleaned: list[str] = []
        for line in lines:
            line = line.strip()
            if line.startswith("*"):
                line = line[1:].strip()
            cleaned.append(line)
        return "\n".join(cleaned).strip()

    def _get_text(self, node: Node, content: str) -> str:
        """Get the text content of a node.

        Tree-sitter byte offsets refer to the UTF-8 encoded representation,
        so we must slice the encoded bytes and decode back to str.  The
        encoded bytes are cached per content string to avoid re-encoding
        on every call within the same file.
        """
        if content is not self._cached_content:
            self._cached_content_bytes = content.encode("utf-8")
            self._cached_content = content
        return self._cached_content_bytes[node.start_byte : node.end_byte].decode(
            "utf-8"
        )

    def _node_location(self, node: Node) -> dict[str, int]:
        """Get the location information for a node."""
        return {
            "start_line": node.start_point[0] + 1,
            "start_column": node.start_point[1],
            "end_line": node.end_point[0] + 1,
            "end_column": node.end_point[1],
        }
