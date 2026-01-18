"""Python language parser using Tree-sitter."""

import re
from typing import Any

from tree_sitter import Node

from .base import BaseLanguageParser

# Python builtin functions and keywords to exclude from references
PYTHON_BUILTINS = {
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

# Python type builtins to exclude from type references
PYTHON_TYPE_BUILTINS = {
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


class PythonParser(BaseLanguageParser):
    """Parser for Python source code using Tree-sitter."""

    @property
    def language_name(self) -> str:
        return "python"

    def extract(
        self,
        root: Node,
        content: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract symbols and references from Python AST."""
        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        def get_text(node: Node) -> str:
            return self._get_text(node, content)

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
                    **self._node_location(node),
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
                    **self._node_location(node),
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
                    **self._node_location(first_child),
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
                    **self._node_location(node),
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
                    # Use func_def start point (the actual def line), not node
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
                    **self._node_location(node),
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
                        **self._node_location(node),
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
                    if func_node.type == "identifier":
                        call_name = get_text(func_node)
                        if call_name not in PYTHON_BUILTINS:
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
                        attr_node = None
                        for child in reversed(func_node.children):
                            if child.type == "identifier":
                                attr_node = child
                                break
                        if attr_node:
                            add_reference(
                                {
                                    "text": get_text(attr_node),
                                    "type": "call",
                                    "source_line": attr_node.start_point[0] + 1,
                                    "source_column": attr_node.start_point[1],
                                    "scope": scope,
                                }
                            )

            # Type annotations
            if node.type in ("type", "generic_type"):
                type_id = node.child_by_field_name("identifier")
                if type_id:
                    type_name = get_text(type_id)
                    if type_name not in PYTHON_TYPE_BUILTINS:
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
                        if type_name not in PYTHON_TYPE_BUILTINS:
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
