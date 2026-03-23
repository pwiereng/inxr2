"""
Tree-sitter parsing service.

Provides code parsing and symbol extraction using tree-sitter grammars.
Delegates to language-specific parsers for extraction logic.
"""

import logging
from typing import Any

from tree_sitter import Language, Parser

from inxr2.application.ports.services import (
    ParsedComment,
    ParsedReference,
    ParsedSymbol,
    ParserServicePort,
)

from .base import BaseLanguageParser
from .bash_parser import BashParser
from .c_cpp_parser import CppParser
from .csharp_parser import CSharpParser
from .go_parser import GoParser
from .java_parser import JavaParser
from .python_parser import PythonParser
from .ruby_parser import RubyParser
from .swift_parser import SwiftParser
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
        "c": [".c"],
        "java": [".java"],
        "csharp": [".cs"],
        "go": [".go"],
        "cpp": [".cpp", ".cc", ".cxx", ".c++", ".hpp", ".hh", ".hxx", ".h++", ".h"],
        "ruby": [".rb", ".rake"],
        "bash": [".sh", ".bash"],
        "swift": [".swift"],
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

        # Initialize each language independently so one missing grammar
        # doesn't prevent all other parsers from loading.
        def _init_language(
            name: str,
            grammar_loader: Any,
            parser_factory: Any,
            *,
            aliases: list[str] | None = None,
        ) -> None:
            try:
                lang = Language(grammar_loader())
                self._parsers[name] = Parser(lang)
                self._language_parsers[name] = parser_factory()
                for alias in aliases or []:
                    self._parsers[alias] = Parser(lang)
                    self._language_parsers[alias] = parser_factory()
            except ImportError as e:
                logger.warning(f"Tree-sitter grammar for {name} not available: {e}")

        try:
            import tree_sitter_python as tspython

            _init_language("python", tspython.language, PythonParser)
        except ImportError as e:
            logger.warning(f"Tree-sitter grammar for python not available: {e}")

        try:
            import tree_sitter_typescript as tstypescript

            _init_language(
                "typescript",
                tstypescript.language_typescript,
                lambda: TypeScriptParser("typescript"),
            )
            # TSX uses the same TypeScript grammar
            tsx_lang = Language(tstypescript.language_tsx())
            self._parsers["tsx"] = Parser(tsx_lang)
            self._language_parsers["tsx"] = TypeScriptParser("typescript")
        except ImportError as e:
            logger.warning(f"Tree-sitter grammar for typescript not available: {e}")

        try:
            import tree_sitter_javascript as tsjavascript

            _init_language(
                "javascript",
                tsjavascript.language,
                lambda: TypeScriptParser("javascript"),
            )
        except ImportError as e:
            logger.warning(f"Tree-sitter grammar for javascript not available: {e}")

        try:
            import tree_sitter_cpp as tscpp

            # C and C++ both use the C++ grammar (unified parser)
            _init_language("cpp", tscpp.language, CppParser, aliases=["c"])
            # Override C alias with c-mode parser
            self._language_parsers["c"] = CppParser("c")
        except ImportError as e:
            logger.warning(f"Tree-sitter grammar for cpp not available: {e}")

        try:
            import tree_sitter_java as tsjava

            _init_language("java", tsjava.language, JavaParser)
        except ImportError as e:
            logger.warning(f"Tree-sitter grammar for java not available: {e}")

        try:
            import tree_sitter_c_sharp as tscsharp

            _init_language("csharp", tscsharp.language, CSharpParser)
        except ImportError as e:
            logger.warning(f"Tree-sitter grammar for csharp not available: {e}")

        try:
            import tree_sitter_go as tsgo

            _init_language("go", tsgo.language, GoParser)
        except ImportError as e:
            logger.warning(f"Tree-sitter grammar for go not available: {e}")

        try:
            import tree_sitter_ruby as tsruby

            _init_language("ruby", tsruby.language, RubyParser)
        except ImportError as e:
            logger.warning(f"Tree-sitter grammar for ruby not available: {e}")

        try:
            import tree_sitter_bash as tsbash

            _init_language("bash", tsbash.language, BashParser)
        except ImportError as e:
            logger.warning(f"Tree-sitter grammar for bash not available: {e}")

        try:
            import tree_sitter_swift as tsswift

            _init_language("swift", tsswift.language, SwiftParser)
        except ImportError as e:
            logger.warning(f"Tree-sitter grammar for swift not available: {e}")

        loaded = list(self._parsers.keys())
        if loaded:
            logger.debug(
                f"Tree-sitter parsers initialized: {', '.join(sorted(loaded))}"
            )
        else:
            logger.warning("No tree-sitter grammars available")

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
        elif language == "go":
            return self._parsers.get("go")
        elif language == "ruby":
            return self._parsers.get("ruby")
        elif language == "bash":
            return self._parsers.get("bash")
        elif language == "cpp":
            return self._parsers.get("cpp")
        elif language == "swift":
            return self._parsers.get("swift")

        return None

    def _get_language_parser(self, language: str) -> BaseLanguageParser | None:
        """Get the language-specific extraction parser."""
        return self._language_parsers.get(language.lower())

    @staticmethod
    def _dict_to_parsed_symbol(sym: dict[str, Any]) -> ParsedSymbol:
        """Convert an internal symbol dict to a typed ParsedSymbol."""
        known_keys = {
            "name",
            "kind",
            "start_line",
            "start_column",
            "end_line",
            "end_column",
            "scope",
            "qualified_name",
            "signature",
            "docstring",
        }
        metadata: dict[str, Any] = {}
        for k, v in sym.items():
            if k not in known_keys:
                metadata[k] = v
        return ParsedSymbol(
            name=sym["name"],
            kind=sym["kind"],
            start_line=sym["start_line"],
            start_column=sym["start_column"],
            end_line=sym["end_line"],
            end_column=sym["end_column"],
            scope=sym.get("scope"),
            qualified_name=sym.get("qualified_name"),
            signature=sym.get("signature"),
            docstring=sym.get("docstring"),
            metadata=metadata,
        )

    @staticmethod
    def _dict_to_parsed_reference(ref: dict[str, Any]) -> ParsedReference:
        """Convert an internal reference dict to a typed ParsedReference."""
        known_keys = {
            "text",
            "reference_text",
            "type",
            "reference_type",
            "source_line",
            "source_column",
            "source_end_column",
            "scope",
        }
        reference_text = ref.get("text") or ref.get("reference_text", "")
        reference_type = ref.get("type") or ref.get("reference_type", "usage")
        metadata: dict[str, Any] = {}
        for k, v in ref.items():
            if k not in known_keys:
                metadata[k] = v
        return ParsedReference(
            reference_text=reference_text,
            reference_type=reference_type,
            source_line=ref["source_line"],
            source_column=ref["source_column"],
            source_end_column=ref.get("source_end_column"),
            scope=ref.get("scope"),
            metadata=metadata,
        )

    @staticmethod
    def _dict_to_parsed_comment(comment: dict[str, Any]) -> ParsedComment:
        """Convert an internal comment dict to a typed ParsedComment."""
        return ParsedComment(
            content=comment["content"],
            content_type=comment["content_type"],
            source_line=comment["source_line"],
            source_end_line=comment.get("source_end_line"),
        )

    async def parse_file(
        self,
        content: str,
        language: str,
        file_path: str,
    ) -> tuple[list[ParsedSymbol], list[ParsedReference]]:
        """
        Parse a file and extract symbols and references.

        Args:
            content: File content as string
            language: Programming language
            file_path: Path to file (for error reporting)

        Returns:
            Tuple of (symbols, references)
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
        except (UnicodeEncodeError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return [], []

        try:
            raw_symbols, raw_references = language_parser.extract(
                tree.root_node, content
            )
            symbols = [self._dict_to_parsed_symbol(s) for s in raw_symbols]
            references = [self._dict_to_parsed_reference(r) for r in raw_references]
        except (AttributeError, IndexError, KeyError, TypeError, RuntimeError) as e:
            # AST traversal errors from unexpected node structures or malformed dicts
            logger.error("Failed to extract symbols from %s: %s", file_path, e)
            return [], []

        return symbols, references

    async def extract_comments(
        self,
        content: str,
        language: str,
        file_path: str,
    ) -> list[ParsedComment]:
        """
        Extract comments and docstrings from a file.

        Args:
            content: File content as string
            language: Programming language
            file_path: Path to file (for error reporting)

        Returns:
            List of ParsedComment with content, content_type, source_line,
            source_end_line
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
        except (UnicodeEncodeError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return []

        try:
            raw_comments = language_parser.extract_comments(tree.root_node, content)
            return [self._dict_to_parsed_comment(c) for c in raw_comments]
        except (AttributeError, IndexError, KeyError, TypeError, RuntimeError) as e:
            # AST traversal errors from unexpected node structures or malformed dicts
            logger.error("Failed to extract comments from %s: %s", file_path, e)
            return []
