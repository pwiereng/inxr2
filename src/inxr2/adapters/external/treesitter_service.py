"""
Tree-sitter parsing service.

Provides code parsing and symbol extraction using tree-sitter grammars.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TreeSitterService:
    """
    Tree-sitter based code parsing service.

    Parses source code and extracts symbols and references
    using tree-sitter grammars for Python and TypeScript.
    """

    # Supported languages and their file extensions
    SUPPORTED_LANGUAGES = {
        "python": [".py", ".pyi"],
        "typescript": [".ts", ".tsx"],
        "javascript": [".js", ".jsx", ".mjs", ".cjs"],
    }

    def __init__(self) -> None:
        """Initialize the tree-sitter service."""
        self._parsers: dict[str, Any] = {}
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of tree-sitter parsers."""
        if self._initialized:
            return

        # TODO: Initialize tree-sitter parsers
        # try:
        #     import tree_sitter_python
        #     import tree_sitter_typescript
        #     from tree_sitter import Language, Parser
        #
        #     # Build language libraries
        #     PY_LANGUAGE = Language(tree_sitter_python.language())
        #     TS_LANGUAGE = Language(tree_sitter_typescript.language_typescript())
        #     JS_LANGUAGE = Language(tree_sitter_typescript.language_tsx())
        #
        #     # Create parsers
        #     self._parsers["python"] = Parser()
        #     self._parsers["python"].language = PY_LANGUAGE
        #     ...
        # except ImportError as e:
        #     logger.warning(f"Tree-sitter grammars not available: {e}")

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

        # TODO: Implement actual tree-sitter parsing
        # For now, use placeholder extraction based on language
        if language == "python":
            return await self._extract_python_symbols(content, file_path)
        elif language in ("typescript", "javascript"):
            return await self._extract_typescript_symbols(content, file_path)

        return [], []

    async def _extract_python_symbols(
        self,
        content: str,
        file_path: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Extract symbols from Python code.

        Uses simple regex-based extraction as placeholder until
        tree-sitter grammars are properly configured.
        """
        import re

        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        lines = content.split("\n")

        # Regex patterns for Python
        class_pattern = re.compile(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[\(:]")
        func_pattern = re.compile(
            r"^(\s*)(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("
        )
        import_pattern = re.compile(r"^(?:from\s+(\S+)\s+)?import\s+(.+)$")
        assign_pattern = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=")  # Constants

        current_class: str | None = None
        class_indent = 0

        for line_num, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            indent = len(line) - len(stripped)

            # Check if we've exited the class
            if current_class and indent <= class_indent and stripped:
                current_class = None

            # Class definition
            match = class_pattern.match(stripped)
            if match:
                class_name = match.group(1)
                current_class = class_name
                class_indent = indent
                symbols.append(
                    {
                        "name": class_name,
                        "kind": "class",
                        "start_line": line_num,
                        "start_column": indent,
                        "end_line": line_num,
                        "end_column": len(line),
                        "scope": None,
                    }
                )
                continue

            # Function/method definition
            match = func_pattern.match(line)
            if match:
                func_indent = len(match.group(1))
                func_name = match.group(2)

                kind = "method" if current_class else "function"
                scope = current_class

                symbols.append(
                    {
                        "name": func_name,
                        "kind": kind,
                        "start_line": line_num,
                        "start_column": func_indent,
                        "end_line": line_num,
                        "end_column": len(line),
                        "scope": scope,
                        "qualified_name": (
                            f"{scope}.{func_name}" if scope else func_name
                        ),
                    }
                )
                continue

            # Import statements
            match = import_pattern.match(stripped)
            if match:
                from_module = match.group(1)
                imports = match.group(2)

                # Parse imported names
                for imp in imports.split(","):
                    imp = imp.strip()
                    if " as " in imp:
                        imp = imp.split(" as ")[0].strip()

                    references.append(
                        {
                            "text": imp,
                            "type": "import",
                            "source_line": line_num,
                            "source_column": line.find(imp),
                            "from_module": from_module,
                        }
                    )
                continue

            # Constants (UPPER_CASE assignments)
            match = assign_pattern.match(stripped)
            if match:
                const_name = match.group(1)
                symbols.append(
                    {
                        "name": const_name,
                        "kind": "constant",
                        "start_line": line_num,
                        "start_column": indent,
                        "end_line": line_num,
                        "end_column": len(line),
                        "scope": None,
                    }
                )

            # Extract function calls and identifier usages
            # Pattern for function calls: identifier followed by (
            call_pattern = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
            for call_match in call_pattern.finditer(line):
                name = call_match.group(1)
                # Skip Python keywords and common builtins
                if name in (
                    "if", "else", "elif", "for", "while", "with", "try",
                    "except", "finally", "def", "class", "return", "yield",
                    "import", "from", "as", "and", "or", "not", "in", "is",
                    "lambda", "assert", "raise", "pass", "break", "continue",
                    "print", "len", "str", "int", "float", "bool", "list",
                    "dict", "set", "tuple", "range", "enumerate", "zip",
                    "map", "filter", "sorted", "reversed", "open", "type",
                    "isinstance", "issubclass", "hasattr", "getattr", "setattr",
                    "super", "property", "staticmethod", "classmethod",
                ):
                    continue
                references.append(
                    {
                        "text": name,
                        "type": "call",
                        "source_line": line_num,
                        "source_column": call_match.start(1),
                    }
                )

            # Extract UPPER_CASE identifier usages (constants)
            const_usage_pattern = re.compile(r"\b([A-Z][A-Z0-9_]{2,})\b")
            for const_match in const_usage_pattern.finditer(line):
                name = const_match.group(1)
                # Skip if it's the definition itself
                if stripped.startswith(name + " ="):
                    continue
                # Skip common non-reference patterns
                if name in ("TRUE", "FALSE", "NONE", "AND", "OR", "NOT"):
                    continue
                references.append(
                    {
                        "text": name,
                        "type": "usage",
                        "source_line": line_num,
                        "source_column": const_match.start(1),
                    }
                )

        return symbols, references

    async def _extract_typescript_symbols(
        self,
        content: str,
        file_path: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Extract symbols from TypeScript/JavaScript code.

        Uses simple regex-based extraction as placeholder until
        tree-sitter grammars are properly configured.
        """
        import re

        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        lines = content.split("\n")

        # Regex patterns for TypeScript/JavaScript
        class_pattern = re.compile(r"(?:export\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)")
        interface_pattern = re.compile(
            r"(?:export\s+)?interface\s+([A-Za-z_][A-Za-z0-9_]*)"
        )
        type_pattern = re.compile(r"(?:export\s+)?type\s+([A-Za-z_][A-Za-z0-9_]*)\s*=")
        func_pattern = re.compile(
            r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)"
        )
        arrow_pattern = re.compile(
            r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\("
        )
        const_pattern = re.compile(
            r"(?:export\s+)?(?:const|let|var)\s+([A-Z][A-Z0-9_]*)\s*="
        )
        import_pattern = re.compile(
            r"import\s+(?:\{([^}]+)\}|(\S+))\s+from\s+['\"]([^'\"]+)['\"]"
        )

        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Skip comments
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue

            # Class definition
            match = class_pattern.search(line)
            if match:
                symbols.append(
                    {
                        "name": match.group(1),
                        "kind": "class",
                        "start_line": line_num,
                        "start_column": match.start(),
                        "end_line": line_num,
                        "end_column": match.end(),
                    }
                )
                continue

            # Interface definition
            match = interface_pattern.search(line)
            if match:
                symbols.append(
                    {
                        "name": match.group(1),
                        "kind": "interface",
                        "start_line": line_num,
                        "start_column": match.start(),
                        "end_line": line_num,
                        "end_column": match.end(),
                    }
                )
                continue

            # Type alias
            match = type_pattern.search(line)
            if match:
                symbols.append(
                    {
                        "name": match.group(1),
                        "kind": "type",
                        "start_line": line_num,
                        "start_column": match.start(),
                        "end_line": line_num,
                        "end_column": match.end(),
                    }
                )
                continue

            # Function definition
            match = func_pattern.search(line)
            if match:
                symbols.append(
                    {
                        "name": match.group(1),
                        "kind": "function",
                        "start_line": line_num,
                        "start_column": match.start(),
                        "end_line": line_num,
                        "end_column": match.end(),
                    }
                )
                continue

            # Arrow function
            match = arrow_pattern.search(line)
            if match:
                symbols.append(
                    {
                        "name": match.group(1),
                        "kind": "function",
                        "start_line": line_num,
                        "start_column": match.start(),
                        "end_line": line_num,
                        "end_column": match.end(),
                    }
                )
                continue

            # Constants (UPPER_CASE)
            match = const_pattern.search(line)
            if match:
                symbols.append(
                    {
                        "name": match.group(1),
                        "kind": "constant",
                        "start_line": line_num,
                        "start_column": match.start(),
                        "end_line": line_num,
                        "end_column": match.end(),
                    }
                )
                continue

            # Import statements
            match = import_pattern.search(line)
            if match:
                named_imports = match.group(1)
                default_import = match.group(2)
                from_module = match.group(3)

                if named_imports:
                    for imp in named_imports.split(","):
                        imp = imp.strip()
                        if " as " in imp:
                            imp = imp.split(" as ")[0].strip()
                        if imp:
                            references.append(
                                {
                                    "text": imp,
                                    "type": "import",
                                    "source_line": line_num,
                                    "source_column": line.find(imp),
                                    "from_module": from_module,
                                }
                            )
                elif default_import:
                    references.append(
                        {
                            "text": default_import,
                            "type": "import",
                            "source_line": line_num,
                            "source_column": line.find(default_import),
                            "from_module": from_module,
                        }
                    )

            # Extract function/component calls
            call_pattern = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
            for call_match in call_pattern.finditer(line):
                name = call_match.group(1)
                # Skip JS/TS keywords and common builtins
                if name in (
                    "if", "else", "for", "while", "switch", "case", "try",
                    "catch", "finally", "function", "class", "return",
                    "import", "export", "from", "as", "const", "let", "var",
                    "new", "typeof", "instanceof", "await", "async",
                    "console", "require", "module", "exports",
                    "Object", "Array", "String", "Number", "Boolean",
                    "Promise", "Map", "Set", "JSON", "Math", "Date",
                    "Error", "RegExp", "Function", "Symbol",
                ):
                    continue
                references.append(
                    {
                        "text": name,
                        "type": "call",
                        "source_line": line_num,
                        "source_column": call_match.start(1),
                    }
                )

            # Extract UPPER_CASE identifier usages (constants)
            const_usage_pattern = re.compile(r"\b([A-Z][A-Z0-9_]{2,})\b")
            for const_match in const_usage_pattern.finditer(line):
                name = const_match.group(1)
                # Skip if it's a definition
                if f"const {name}" in line or f"let {name}" in line:
                    continue
                references.append(
                    {
                        "text": name,
                        "type": "usage",
                        "source_line": line_num,
                        "source_column": const_match.start(1),
                    }
                )

        return symbols, references
