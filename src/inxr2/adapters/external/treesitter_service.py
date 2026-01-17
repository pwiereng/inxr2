"""
Tree-sitter parsing service.

Provides code parsing and symbol extraction using tree-sitter grammars.
"""

import logging
import re
from typing import Any

from tree_sitter import Language, Node, Parser

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
        self._parsers: dict[str, Parser] = {}
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of tree-sitter parsers."""
        if self._initialized:
            return

        try:
            import tree_sitter_javascript as tsjavascript
            import tree_sitter_python as tspython
            import tree_sitter_typescript as tstypescript

            # Create language objects
            py_language = Language(tspython.language())
            ts_language = Language(tstypescript.language_typescript())
            tsx_language = Language(tstypescript.language_tsx())
            js_language = Language(tsjavascript.language())

            # Create parsers for each language
            self._parsers["python"] = Parser(py_language)
            self._parsers["typescript"] = Parser(ts_language)
            self._parsers["tsx"] = Parser(tsx_language)
            self._parsers["javascript"] = Parser(js_language)

            logger.info("Tree-sitter parsers initialized successfully")

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

        return None

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

        try:
            tree = parser.parse(content.encode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return [], []

        if language == "python":
            return self._extract_python(tree.root_node, content)
        elif language in ("typescript", "javascript"):
            return self._extract_typescript(tree.root_node, content)

        return [], []

    def _extract_python(
        self,
        root: Node,
        content: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract symbols and references from Python AST."""
        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        def get_text(node: Node) -> str:
            return content[node.start_byte : node.end_byte]

        def get_identifier_text(node: Node) -> str | None:
            """Get identifier text from a node or its first identifier child."""
            if node.type == "identifier":
                return get_text(node)
            for child in node.children:
                if child.type == "identifier":
                    return get_text(child)
            return None

        def add_reference(ref: dict[str, Any]) -> None:
            """Add reference only if it has non-empty text."""
            text = ref.get("text", "")
            if text and text.strip():
                references.append(ref)

        def process_class(node: Node, scope: str | None = None) -> None:
            """Process a class definition."""
            name_node = node.child_by_field_name("name")
            if not name_node:
                # Fallback: find identifier child
                for child in node.children:
                    if child.type == "identifier":
                        name_node = child
                        break

            if not name_node:
                return

            class_name = get_text(name_node)
            symbols.append(
                {
                    "name": class_name,
                    "kind": "class",
                    "start_line": node.start_point[0] + 1,
                    "start_column": node.start_point[1],
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": scope,
                }
            )

            # Process class body
            for child in node.children:
                if child.type == "block":
                    process_class_body(child, class_name)

        def process_class_body(node: Node, class_name: str) -> None:
            """Process the body of a class definition."""
            for child in node.children:
                if child.type == "function_definition":
                    process_method(child, class_name)
                elif child.type == "decorated_definition":
                    process_decorated(child, class_name)
                elif child.type == "expression_statement":
                    # Class variable
                    for expr_child in child.children:
                        if expr_child.type == "assignment":
                            process_class_variable(expr_child, class_name)

        def process_method(node: Node, class_name: str) -> None:
            """Process a method definition."""
            name_node = node.child_by_field_name("name")
            if not name_node:
                for child in node.children:
                    if child.type == "identifier":
                        name_node = child
                        break

            if not name_node:
                return

            method_name = get_text(name_node)
            symbols.append(
                {
                    "name": method_name,
                    "kind": "method",
                    "start_line": node.start_point[0] + 1,
                    "start_column": node.start_point[1],
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": class_name,
                    "qualified_name": f"{class_name}.{method_name}",
                }
            )

            # Look for instance variable assignments (self.x = ...)
            for child in node.children:
                if child.type == "block":
                    process_method_body(child, class_name, method_name)

        def process_method_body(node: Node, class_name: str, method_name: str) -> None:
            """Process method body for instance variable assignments."""
            for child in node.children:
                if child.type == "expression_statement":
                    for expr_child in child.children:
                        if expr_child.type == "assignment":
                            process_instance_variable(
                                expr_child, class_name, method_name
                            )
                # Recurse into control structures
                elif child.type in (
                    "if_statement",
                    "for_statement",
                    "while_statement",
                    "with_statement",
                    "try_statement",
                ):
                    for sub in child.children:
                        if sub.type == "block":
                            process_method_body(sub, class_name, method_name)

        def process_instance_variable(
            node: Node, class_name: str, method_name: str
        ) -> None:
            """Process a potential instance variable assignment."""
            if not node.children:
                return

            first_child = node.children[0]
            if first_child.type != "attribute":
                return

            # Check if it's self.something
            attr_children = list(first_child.children)
            if len(attr_children) < 3:
                return

            obj_node = attr_children[0]
            if obj_node.type != "identifier" or get_text(obj_node) != "self":
                return

            # Get the attribute name (last identifier)
            attr_name = None
            for child in reversed(attr_children):
                if child.type == "identifier" and get_text(child) != "self":
                    attr_name = get_text(child)
                    break

            if not attr_name:
                return

            # Only record if it's in __init__ or starts with _ (common patterns)
            if method_name != "__init__" and not attr_name.startswith("_"):
                return

            symbols.append(
                {
                    "name": attr_name,
                    "kind": "instance_variable",
                    "start_line": first_child.start_point[0] + 1,
                    "start_column": first_child.start_point[1],
                    "end_line": first_child.end_point[0] + 1,
                    "end_column": first_child.end_point[1],
                    "scope": class_name,
                    "qualified_name": f"{class_name}.{attr_name}",
                }
            )

        def process_class_variable(node: Node, class_name: str) -> None:
            """Process a class variable assignment."""
            if not node.children:
                return

            first_child = node.children[0]
            var_name = get_identifier_text(first_child)
            if not var_name:
                return

            # Determine kind - UPPER_CASE suggests a constant
            if re.match(r"^[A-Z][A-Z0-9_]*$", var_name):
                kind = "class_constant"
            else:
                kind = "class_variable"

            symbols.append(
                {
                    "name": var_name,
                    "kind": kind,
                    "start_line": node.start_point[0] + 1,
                    "start_column": node.start_point[1],
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": class_name,
                    "qualified_name": f"{class_name}.{var_name}",
                }
            )

        def process_decorated(node: Node, class_name: str | None) -> None:
            """Process a decorated definition."""
            decorators: list[str] = []
            func_def = None

            for child in node.children:
                if child.type == "decorator":
                    dec_text = get_text(child).lstrip("@").split("(")[0]
                    decorators.append(dec_text)
                elif child.type == "function_definition":
                    func_def = child
                elif child.type == "class_definition":
                    process_class(child, class_name)

            if not func_def:
                return

            name_node = func_def.child_by_field_name("name")
            if not name_node:
                for child in func_def.children:
                    if child.type == "identifier":
                        name_node = child
                        break

            if not name_node:
                return

            func_name = get_text(name_node)

            # Determine kind based on decorators
            if "property" in decorators:
                kind = "property"
            elif "staticmethod" in decorators:
                kind = "staticmethod"
            elif "classmethod" in decorators:
                kind = "classmethod"
            elif class_name:
                kind = "method"
            else:
                kind = "function"

            symbols.append(
                {
                    "name": func_name,
                    "kind": kind,
                    # Use func_def start point (the actual def line), not node (which includes decorators)
                    "start_line": func_def.start_point[0] + 1,
                    "start_column": func_def.start_point[1],
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": class_name,
                    "qualified_name": (
                        f"{class_name}.{func_name}" if class_name else func_name
                    ),
                }
            )

            # If it's a method, check for instance variables
            if class_name and func_def:
                for child in func_def.children:
                    if child.type == "block":
                        process_method_body(child, class_name, func_name)

        def process_function(node: Node, scope: str | None = None) -> None:
            """Process a standalone function definition."""
            name_node = node.child_by_field_name("name")
            if not name_node:
                for child in node.children:
                    if child.type == "identifier":
                        name_node = child
                        break

            if not name_node:
                return

            func_name = get_text(name_node)
            symbols.append(
                {
                    "name": func_name,
                    "kind": "function",
                    "start_line": node.start_point[0] + 1,
                    "start_column": node.start_point[1],
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": scope,
                }
            )

        def process_module_assignment(node: Node) -> None:
            """Process a module-level assignment (constant)."""
            if not node.children:
                return

            first_child = node.children[0]
            var_name = get_identifier_text(first_child)
            if not var_name:
                return

            # Only record UPPER_CASE as constants
            if re.match(r"^[A-Z][A-Z0-9_]*$", var_name):
                symbols.append(
                    {
                        "name": var_name,
                        "kind": "constant",
                        "start_line": node.start_point[0] + 1,
                        "start_column": node.start_point[1],
                        "end_line": node.end_point[0] + 1,
                        "end_column": node.end_point[1],
                        "scope": None,
                    }
                )

        def extract_references(node: Node, scope: str | None = None) -> None:
            """Extract references from the AST."""
            # Import statements
            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        add_reference(
                            {
                                "text": get_text(child),
                                "type": "import",
                                "source_line": child.start_point[0] + 1,
                                "source_column": child.start_point[1],
                            }
                        )
                    elif child.type == "aliased_import":
                        name = child.child_by_field_name("name")
                        if name:
                            add_reference(
                                {
                                    "text": get_text(name),
                                    "type": "import",
                                    "source_line": name.start_point[0] + 1,
                                    "source_column": name.start_point[1],
                                }
                            )
                return

            if node.type == "import_from_statement":
                module_node = None
                for child in node.children:
                    if child.type == "dotted_name":
                        module_node = get_text(child)
                        break

                for child in node.children:
                    if child.type == "dotted_name" and child != module_node:
                        add_reference(
                            {
                                "text": get_text(child),
                                "type": "import",
                                "source_line": child.start_point[0] + 1,
                                "source_column": child.start_point[1],
                                "from_module": module_node,
                            }
                        )
                    elif child.type == "aliased_import":
                        name = child.child_by_field_name("name")
                        if name:
                            add_reference(
                                {
                                    "text": get_text(name),
                                    "type": "import",
                                    "source_line": name.start_point[0] + 1,
                                    "source_column": name.start_point[1],
                                    "from_module": module_node,
                                }
                            )
                return

            # Function/method calls
            if node.type == "call":
                func_node = node.child_by_field_name("function")
                if func_node:
                    # Get the callable name
                    if func_node.type == "identifier":
                        call_name = get_text(func_node)
                        if not self._is_python_builtin(call_name):
                            add_reference(
                                {
                                    "text": call_name,
                                    "type": "call",
                                    "source_line": func_node.start_point[0] + 1,
                                    "source_column": func_node.start_point[1],
                                    "scope": scope,
                                }
                            )
                    elif func_node.type == "attribute":
                        # Method call like obj.method()
                        attr_name = None
                        for child in reversed(func_node.children):
                            if child.type == "identifier":
                                attr_name = get_text(child)
                                break
                        if attr_name:
                            add_reference(
                                {
                                    "text": attr_name,
                                    "type": "call",
                                    "source_line": func_node.start_point[0] + 1,
                                    "source_column": func_node.start_point[1],
                                    "scope": scope,
                                }
                            )

            # Type annotations
            if node.type in ("type", "generic_type"):
                type_id = node.child_by_field_name("identifier")
                if type_id:
                    type_name = get_text(type_id)
                    if not self._is_python_type_builtin(type_name):
                        add_reference(
                            {
                                "text": type_name,
                                "type": "type_annotation",
                                "source_line": type_id.start_point[0] + 1,
                                "source_column": type_id.start_point[1],
                                "scope": scope,
                            }
                        )
                # Also check for the first identifier child
                for child in node.children:
                    if child.type == "identifier":
                        type_name = get_text(child)
                        if not self._is_python_type_builtin(type_name):
                            add_reference(
                                {
                                    "text": type_name,
                                    "type": "type_annotation",
                                    "source_line": child.start_point[0] + 1,
                                    "source_column": child.start_point[1],
                                    "scope": scope,
                                }
                            )
                        break

            # Recurse into children
            for child in node.children:
                child_scope = scope
                if node.type == "class_definition":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        child_scope = get_text(name_node)
                extract_references(child, child_scope)

        # Process top-level nodes
        for child in root.children:
            if child.type == "class_definition":
                process_class(child)
            elif child.type == "function_definition":
                process_function(child)
            elif child.type == "decorated_definition":
                process_decorated(child, None)
            elif child.type == "expression_statement":
                for expr_child in child.children:
                    if expr_child.type == "assignment":
                        process_module_assignment(expr_child)

        # Extract references
        extract_references(root)

        return symbols, references

    def _extract_typescript(
        self,
        root: Node,
        content: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract symbols and references from TypeScript/JavaScript AST."""
        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        def get_text(node: Node) -> str:
            return content[node.start_byte : node.end_byte]

        def get_name_from_node(node: Node) -> str | None:
            """Extract name from various node types."""
            if node.type in ("identifier", "type_identifier", "property_identifier"):
                return get_text(node)
            name_node = node.child_by_field_name("name")
            if name_node:
                return get_text(name_node)
            for child in node.children:
                if child.type in (
                    "identifier",
                    "type_identifier",
                    "property_identifier",
                ):
                    return get_text(child)
            return None

        def add_reference(ref: dict[str, Any]) -> None:
            """Add reference only if it has non-empty text."""
            text = ref.get("text", "")
            if text and text.strip():
                references.append(ref)

        def process_interface(node: Node) -> None:
            """Process an interface declaration."""
            name = get_name_from_node(node)
            if not name:
                return

            symbols.append(
                {
                    "name": name,
                    "kind": "interface",
                    "start_line": node.start_point[0] + 1,
                    "start_column": node.start_point[1],
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": None,
                }
            )

            # Extract interface properties
            for child in node.children:
                if child.type == "interface_body":
                    for prop in child.children:
                        if prop.type == "property_signature":
                            prop_name = get_name_from_node(prop)
                            if prop_name:
                                symbols.append(
                                    {
                                        "name": prop_name,
                                        "kind": "interface_property",
                                        "start_line": prop.start_point[0] + 1,
                                        "start_column": prop.start_point[1],
                                        "end_line": prop.end_point[0] + 1,
                                        "end_column": prop.end_point[1],
                                        "scope": name,
                                        "qualified_name": f"{name}.{prop_name}",
                                    }
                                )
                        elif prop.type == "method_signature":
                            method_name = get_name_from_node(prop)
                            if method_name:
                                symbols.append(
                                    {
                                        "name": method_name,
                                        "kind": "interface_method",
                                        "start_line": prop.start_point[0] + 1,
                                        "start_column": prop.start_point[1],
                                        "end_line": prop.end_point[0] + 1,
                                        "end_column": prop.end_point[1],
                                        "scope": name,
                                        "qualified_name": f"{name}.{method_name}",
                                    }
                                )

        def process_type_alias(node: Node) -> None:
            """Process a type alias declaration."""
            name = get_name_from_node(node)
            if not name:
                return

            symbols.append(
                {
                    "name": name,
                    "kind": "type",
                    "start_line": node.start_point[0] + 1,
                    "start_column": node.start_point[1],
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": None,
                }
            )

        def process_enum(node: Node) -> None:
            """Process an enum declaration."""
            name = get_name_from_node(node)
            if not name:
                return

            symbols.append(
                {
                    "name": name,
                    "kind": "enum",
                    "start_line": node.start_point[0] + 1,
                    "start_column": node.start_point[1],
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": None,
                }
            )

            # Extract enum members
            for child in node.children:
                if child.type == "enum_body":
                    for member in child.children:
                        # Enum members can be property_identifier or enum_assignment
                        if member.type in ("property_identifier", "enum_assignment"):
                            member_name = get_name_from_node(member)
                            if member_name:
                                symbols.append(
                                    {
                                        "name": member_name,
                                        "kind": "enum_member",
                                        "start_line": member.start_point[0] + 1,
                                        "start_column": member.start_point[1],
                                        "end_line": member.end_point[0] + 1,
                                        "end_column": member.end_point[1],
                                        "scope": name,
                                        "qualified_name": f"{name}.{member_name}",
                                    }
                                )

        def process_class(node: Node) -> None:
            """Process a class declaration."""
            name = get_name_from_node(node)
            if not name:
                return

            symbols.append(
                {
                    "name": name,
                    "kind": "class",
                    "start_line": node.start_point[0] + 1,
                    "start_column": node.start_point[1],
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": None,
                }
            )

            # Process class body
            for child in node.children:
                if child.type == "class_body":
                    for member in child.children:
                        if member.type == "method_definition":
                            process_method(member, name)
                        elif member.type == "public_field_definition":
                            process_field(member, name)

        def process_method(node: Node, class_name: str) -> None:
            """Process a method definition."""
            name = get_name_from_node(node)
            if not name:
                return

            # Check for static modifier
            is_static = any(child.type == "static" for child in node.children)
            kind = "staticmethod" if is_static else "method"

            # Check for getter/setter
            for child in node.children:
                if child.type == "get":
                    kind = "getter"
                elif child.type == "set":
                    kind = "setter"

            symbols.append(
                {
                    "name": name,
                    "kind": kind,
                    "start_line": node.start_point[0] + 1,
                    "start_column": node.start_point[1],
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": class_name,
                    "qualified_name": f"{class_name}.{name}",
                }
            )

        def process_field(node: Node, class_name: str) -> None:
            """Process a class field definition."""
            name = get_name_from_node(node)
            if not name:
                return

            # Check modifiers
            is_static = any(child.type == "static" for child in node.children)
            is_readonly = any(child.type == "readonly" for child in node.children)

            if is_static:
                kind = "static_field"
            elif is_readonly:
                kind = "readonly_field"
            else:
                kind = "field"

            symbols.append(
                {
                    "name": name,
                    "kind": kind,
                    "start_line": node.start_point[0] + 1,
                    "start_column": node.start_point[1],
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": class_name,
                    "qualified_name": f"{class_name}.{name}",
                }
            )

        def process_function(node: Node, is_exported: bool = False) -> None:
            """Process a function declaration."""
            name = get_name_from_node(node)
            if not name:
                return

            symbols.append(
                {
                    "name": name,
                    "kind": "function",
                    "start_line": node.start_point[0] + 1,
                    "start_column": node.start_point[1],
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": None,
                }
            )

        def process_variable_declaration(node: Node, is_exported: bool = False) -> None:
            """Process variable declarations (const, let, var)."""
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    if not name_node:
                        for sub in child.children:
                            if sub.type == "identifier":
                                name_node = sub
                                break

                    if not name_node:
                        continue

                    var_name = get_text(name_node)

                    # Check if it's an arrow function
                    value_node = child.child_by_field_name("value")
                    if value_node and value_node.type == "arrow_function":
                        symbols.append(
                            {
                                "name": var_name,
                                "kind": "function",
                                "start_line": child.start_point[0] + 1,
                                "start_column": child.start_point[1],
                                "end_line": child.end_point[0] + 1,
                                "end_column": child.end_point[1],
                                "scope": None,
                            }
                        )
                    elif re.match(r"^[A-Z][A-Z0-9_]*$", var_name):
                        # UPPER_CASE constant
                        symbols.append(
                            {
                                "name": var_name,
                                "kind": "constant",
                                "start_line": child.start_point[0] + 1,
                                "start_column": child.start_point[1],
                                "end_line": child.end_point[0] + 1,
                                "end_column": child.end_point[1],
                                "scope": None,
                            }
                        )

        def extract_references(node: Node, scope: str | None = None) -> None:
            """Extract references from the AST."""
            # Import statements
            if node.type == "import_statement":
                source_node = node.child_by_field_name("source")
                from_module = (
                    get_text(source_node).strip("'\"") if source_node else None
                )

                for child in node.children:
                    if child.type == "import_clause":
                        for sub in child.children:
                            if sub.type == "identifier":
                                add_reference(
                                    {
                                        "text": get_text(sub),
                                        "type": "import",
                                        "source_line": sub.start_point[0] + 1,
                                        "source_column": sub.start_point[1],
                                        "from_module": from_module,
                                    }
                                )
                            elif sub.type == "named_imports":
                                for imp in sub.children:
                                    if imp.type == "import_specifier":
                                        name = get_name_from_node(imp)
                                        if name:
                                            add_reference(
                                                {
                                                    "text": name,
                                                    "type": "import",
                                                    "source_line": imp.start_point[0]
                                                    + 1,
                                                    "source_column": imp.start_point[1],
                                                    "from_module": from_module,
                                                }
                                            )
                return

            # Function calls
            if node.type == "call_expression":
                func_node = node.child_by_field_name("function")
                if func_node:
                    if func_node.type == "identifier":
                        name = get_text(func_node)
                        if not self._is_ts_builtin(name):
                            add_reference(
                                {
                                    "text": name,
                                    "type": "call",
                                    "source_line": func_node.start_point[0] + 1,
                                    "source_column": func_node.start_point[1],
                                    "scope": scope,
                                }
                            )
                    elif func_node.type == "member_expression":
                        prop = func_node.child_by_field_name("property")
                        if prop:
                            add_reference(
                                {
                                    "text": get_text(prop),
                                    "type": "call",
                                    "source_line": prop.start_point[0] + 1,
                                    "source_column": prop.start_point[1],
                                    "scope": scope,
                                }
                            )

            # Type references
            if node.type == "type_identifier":
                type_name = get_text(node)
                if not self._is_ts_type_builtin(type_name):
                    add_reference(
                        {
                            "text": type_name,
                            "type": "type_annotation",
                            "source_line": node.start_point[0] + 1,
                            "source_column": node.start_point[1],
                            "scope": scope,
                        }
                    )

            # Recurse
            for child in node.children:
                child_scope = scope
                if node.type == "class_declaration":
                    name = get_name_from_node(node)
                    if name:
                        child_scope = name
                extract_references(child, child_scope)

        def process_node(node: Node, is_exported: bool = False) -> None:
            """Process a top-level node."""
            if node.type == "interface_declaration":
                process_interface(node)
            elif node.type == "type_alias_declaration":
                process_type_alias(node)
            elif node.type == "enum_declaration":
                process_enum(node)
            elif node.type == "class_declaration":
                process_class(node)
            elif node.type == "function_declaration":
                process_function(node, is_exported)
            elif node.type == "lexical_declaration":
                process_variable_declaration(node, is_exported)
            elif node.type == "export_statement":
                # Handle exported declarations
                for child in node.children:
                    process_node(child, is_exported=True)

        # Process top-level nodes
        for child in root.children:
            process_node(child)

        # Extract references
        extract_references(root)

        return symbols, references

    def _is_python_builtin(self, name: str) -> bool:
        """Check if name is a Python builtin."""
        return name in {
            "if",
            "else",
            "elif",
            "for",
            "while",
            "with",
            "try",
            "except",
            "finally",
            "def",
            "class",
            "return",
            "yield",
            "import",
            "from",
            "as",
            "and",
            "or",
            "not",
            "in",
            "is",
            "lambda",
            "assert",
            "raise",
            "pass",
            "break",
            "continue",
            "print",
            "len",
            "str",
            "int",
            "float",
            "bool",
            "list",
            "dict",
            "set",
            "tuple",
            "range",
            "enumerate",
            "zip",
            "map",
            "filter",
            "sorted",
            "reversed",
            "open",
            "type",
            "isinstance",
            "issubclass",
            "hasattr",
            "getattr",
            "setattr",
            "super",
            "property",
            "staticmethod",
            "classmethod",
            "abs",
            "all",
            "any",
            "ascii",
            "bin",
            "callable",
            "chr",
            "compile",
            "complex",
            "delattr",
            "dir",
            "divmod",
            "eval",
            "exec",
            "format",
            "frozenset",
            "globals",
            "hash",
            "help",
            "hex",
            "id",
            "input",
            "iter",
            "locals",
            "max",
            "min",
            "next",
            "object",
            "oct",
            "ord",
            "pow",
            "repr",
            "round",
            "slice",
            "sum",
            "vars",
            "None",
            "True",
            "False",
        }

    def _is_python_type_builtin(self, name: str) -> bool:
        """Check if name is a Python type builtin."""
        return name in {
            "str",
            "int",
            "float",
            "bool",
            "list",
            "dict",
            "set",
            "tuple",
            "bytes",
            "bytearray",
            "memoryview",
            "range",
            "frozenset",
            "object",
            "type",
            "None",
            "Any",
            "Union",
            "Optional",
            "List",
            "Dict",
            "Set",
            "Tuple",
            "Callable",
            "Type",
            "Generic",
            "TypeVar",
            "Protocol",
            "Literal",
            "Final",
            "ClassVar",
            "Sequence",
            "Mapping",
            "Iterable",
            "Iterator",
            "Generator",
            "Coroutine",
            "AsyncGenerator",
            "Awaitable",
            "AsyncIterable",
            "AsyncIterator",
        }

    def _is_ts_builtin(self, name: str) -> bool:
        """Check if name is a TypeScript/JavaScript builtin."""
        return name in {
            "if",
            "else",
            "for",
            "while",
            "switch",
            "case",
            "try",
            "catch",
            "finally",
            "function",
            "class",
            "return",
            "import",
            "export",
            "from",
            "as",
            "const",
            "let",
            "var",
            "new",
            "typeof",
            "instanceof",
            "await",
            "async",
            "console",
            "require",
            "module",
            "exports",
            "Object",
            "Array",
            "String",
            "Number",
            "Boolean",
            "Promise",
            "Map",
            "Set",
            "JSON",
            "Math",
            "Date",
            "Error",
            "RegExp",
            "Function",
            "Symbol",
            "BigInt",
            "parseInt",
            "parseFloat",
            "isNaN",
            "isFinite",
            "encodeURI",
            "decodeURI",
            "encodeURIComponent",
            "decodeURIComponent",
            "setTimeout",
            "setInterval",
            "clearTimeout",
            "clearInterval",
            "fetch",
            "undefined",
            "null",
            "NaN",
            "Infinity",
        }

    def _is_ts_type_builtin(self, name: str) -> bool:
        """Check if name is a TypeScript type builtin."""
        return name in {
            "Array",
            "Object",
            "String",
            "Number",
            "Boolean",
            "Promise",
            "Map",
            "Set",
            "Date",
            "Error",
            "Function",
            "Symbol",
            "RegExp",
            "Record",
            "Partial",
            "Required",
            "Readonly",
            "Pick",
            "Omit",
            "Exclude",
            "Extract",
            "NonNullable",
            "ReturnType",
            "Parameters",
            "InstanceType",
            "ThisType",
            "Uppercase",
            "Lowercase",
            "Capitalize",
            "Uncapitalize",
            "Awaited",
            "ConstructorParameters",
            "React",
            "FC",
            "Component",
            "HTMLElement",
            "Element",
            "Event",
            "MouseEvent",
            "KeyboardEvent",
            "ChangeEvent",
            "FormEvent",
            "FocusEvent",
            "TouchEvent",
            "DragEvent",
            "ClipboardEvent",
            "AnimationEvent",
            "TransitionEvent",
            "WheelEvent",
            "PointerEvent",
            "UIEvent",
            "HTMLDivElement",
            "HTMLInputElement",
            "HTMLButtonElement",
            "HTMLFormElement",
            "HTMLSpanElement",
            "HTMLAnchorElement",
            "void",
            "never",
            "unknown",
            "any",
            "undefined",
            "null",
        }
