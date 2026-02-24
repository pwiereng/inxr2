"""
Tree-sitter parsing service.

Provides code parsing and symbol extraction using tree-sitter grammars.
Delegates to language-specific parsers for extraction logic.
"""

import logging
from typing import Any

from tree_sitter import Language, Parser

from inxr2.application.ports.services import ParserServicePort

from .base import BaseLanguageParser
from .c_parser import CParser
from .csharp_parser import CSharpParser
from .java_parser import JavaParser
from .python_parser import PythonParser
from .typescript_parser import TypeScriptParser

logger = logging.getLogger(__name__)


class TreeSitterService(ParserServicePort):
    """
    Tree-sitter based code parsing service.

    Parses source code and extracts symbols and references
    using tree-sitter grammars. Delegates extraction logic
    to language-specific parser implementations.
    """

    # Supported languages and their file extensions
    SUPPORTED_LANGUAGES = {
        "python": [".py", ".pyi"],
        "typescript": [".ts", ".tsx"],
        "javascript": [".js", ".jsx", ".mjs", ".cjs"],
        "c": [".c", ".h"],
        "java": [".java"],
        "csharp": [".cs"],
    }

    def __init__(self) -> None:
        """Initialize the tree-sitter service."""
        self._parsers: dict[str, Parser] = {}
        self._language_parsers: dict[str, BaseLanguageParser] = {}
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of tree-sitter parsers."""
        if self._initialized:
            return

        try:
            import tree_sitter_c as tsc
            import tree_sitter_c_sharp as tscsharp
            import tree_sitter_java as tsjava
            import tree_sitter_javascript as tsjavascript
            import tree_sitter_python as tspython
            import tree_sitter_typescript as tstypescript

            # Create language objects
            py_language = Language(tspython.language())
            ts_language = Language(tstypescript.language_typescript())
            tsx_language = Language(tstypescript.language_tsx())
            js_language = Language(tsjavascript.language())
            c_language = Language(tsc.language())
            java_language = Language(tsjava.language())
            csharp_language = Language(tscsharp.language())

            # Create parsers for each language
            self._parsers["python"] = Parser(py_language)
            self._parsers["typescript"] = Parser(ts_language)
            self._parsers["tsx"] = Parser(tsx_language)
            self._parsers["javascript"] = Parser(js_language)
            self._parsers["c"] = Parser(c_language)
            self._parsers["java"] = Parser(java_language)
            self._parsers["csharp"] = Parser(csharp_language)

            # Create language-specific extraction parsers
            self._language_parsers["python"] = PythonParser()
            self._language_parsers["typescript"] = TypeScriptParser("typescript")
            self._language_parsers["javascript"] = TypeScriptParser("javascript")
            self._language_parsers["c"] = CParser()
            self._language_parsers["java"] = JavaParser()
            self._language_parsers["csharp"] = CSharpParser()

            logger.debug("Tree-sitter parsers initialized successfully")

        except ImportError as e:
            logger.warning(f"Tree-sitter grammars not available: {e}")

        self._initialized = True

    def supports_language(self, language: str) -> bool:
        """
        Check if a language is supported.

        Args:
            language: Language name (python, typescript, javascript)

        Returns:
            True if language is supported
        """
        return language.lower() in self.SUPPORTED_LANGUAGES

    def _get_parser(self, language: str, file_path: str) -> Parser | None:
        """Get the appropriate parser for the language and file."""
        language = language.lower()

        if language == "python":
            return self._parsers.get("python")
        elif language == "typescript":
            # Use TSX parser for .tsx files
            if file_path.endswith(".tsx"):
                return self._parsers.get("tsx")
            return self._parsers.get("typescript")
        elif language == "javascript":
            # Use TSX parser for .jsx files (handles JSX)
            if file_path.endswith(".jsx"):
                return self._parsers.get("tsx")
            return self._parsers.get("javascript")
        elif language == "c":
            return self._parsers.get("c")
        elif language == "java":
            return self._parsers.get("java")
        elif language == "csharp":
            return self._parsers.get("csharp")

        return None

    def _get_language_parser(self, language: str) -> BaseLanguageParser | None:
        """Get the language-specific extraction parser."""
        return self._language_parsers.get(language.lower())

    async def parse_file(
        self,
        content: str,
        language: str,
        file_path: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Parse a file and extract symbols and references.

        Args:
            content: File content as string
            language: Programming language
            file_path: Path to file (for error reporting)

        Returns:
            Tuple of (symbols, references) where each is a list of dicts
        """
        self._ensure_initialized()

        language = language.lower()
        if not self.supports_language(language):
            logger.warning(f"Unsupported language: {language}")
            return [], []

        parser = self._get_parser(language, file_path)
        if not parser:
            logger.warning(f"No parser available for {language}")
            return [], []

        language_parser = self._get_language_parser(language)
        if not language_parser:
            logger.warning(f"No language parser available for {language}")
            return [], []

        try:
            tree = parser.parse(content.encode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return [], []

        try:
            return language_parser.extract(tree.root_node, content)
        except Exception as e:
            logger.error("Failed to extract symbols from %s: %s", file_path, e)
            return [], []

    async def extract_comments(
        self,
        content: str,
        language: str,
        file_path: str,
    ) -> list[dict[str, Any]]:
        """
        Extract comments and docstrings from a file.

        Args:
            content: File content as string
            language: Programming language
            file_path: Path to file (for error reporting)

        Returns:
            List of comment dicts with keys:
            - content: The comment text (stripped of comment markers)
            - content_type: Type of comment (single_line_comment, block_comment, docstring, etc.)
            - source_line: Starting line number
            - source_end_line: Ending line number (for multi-line comments)
        """
        self._ensure_initialized()

        language = language.lower()
        if not self.supports_language(language):
            logger.warning(f"Unsupported language: {language}")
            return []

        parser = self._get_parser(language, file_path)
        if not parser:
            logger.warning(f"No parser available for {language}")
            return []

        language_parser = self._get_language_parser(language)
        if not language_parser:
            logger.warning(f"No language parser available for {language}")
            return []

        try:
            tree = parser.parse(content.encode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return []

        try:
            return language_parser.extract_comments(tree.root_node, content)
        except Exception as e:
            logger.error("Failed to extract comments from %s: %s", file_path, e)
            return []
