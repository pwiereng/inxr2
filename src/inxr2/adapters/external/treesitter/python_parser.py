"""Python language parser using Tree-sitter."""

import logging
import re
from typing import Any

from tree_sitter import Node

from .base import BaseLanguageParser
from .builtins import _load

logger = logging.getLogger(__name__)

# Python builtin functions and keywords to exclude from references
PYTHON_BUILTINS = _load("python.json", "builtins")

# Python type builtins to exclude from type references
PYTHON_TYPE_BUILTINS = _load("python.json", "type_builtins")


def _is_write_target(node: Node) -> bool:
    """Check if a node is in a write-target position.

    Covers: simple assignment LHS, tuple unpacking, for-loop targets,
    with-as targets, and del statements.
    """
    current = node
    while current.parent is not None:
        parent = current.parent
        if parent.type == "assignment" and current == parent.children[0]:
            return True
        if parent.type == "augmented_assignment":
            return False  # augmented assignment is a read+write, treat as usage
        if parent.type in ("pattern_list", "tuple_pattern"):
            current = parent
            continue
        if parent.type == "for_statement":
            # Target is the node right after "for" keyword
            children = parent.children
            if len(children) >= 2 and current == children[1]:
                return True
            return False
        if parent.type == "as_pattern_target":
            # "with expr as self.x" — the alias target is a write
            return True
        if parent.type == "delete_statement":
            return True
        break
    return False


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
            self._add_reference(ref, references)

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
            symbols.append(self._make_symbol(class_name, "class", node, scope))

            # Extract superclass references (inheritance)
            for child in node.children:
                if child.type == "argument_list":
                    for arg in child.children:
                        if arg.type == "identifier":
                            base_name = get_text(arg)
                            if base_name not in PYTHON_TYPE_BUILTINS:
                                add_reference(
                                    self._make_reference(
                                        base_name, "inheritance", arg, class_name
                                    )
                                )
                        elif arg.type == "attribute":
                            # e.g., module.ClassName or pkg.module.ClassName
                            full_name = get_text(arg)
                            add_reference(
                                self._make_reference(
                                    full_name, "inheritance", arg, class_name
                                )
                            )
                        elif arg.type == "keyword_argument":
                            # e.g., metaclass=ABCMeta — skip
                            pass

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
            symbols.append(self._make_symbol(method_name, "method", node, class_name))

            # Look for instance variable assignments and nested functions
            for child in node.children:
                if child.type == "block":
                    process_method_body(child, class_name, method_name)
                    process_nested_functions(child, f"{class_name}.{method_name}")

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

            # Get the attribute name (last identifier) and its node
            attr_name = None
            attr_name_node = None
            for child in reversed(attr_children):
                if child.type == "identifier" and get_text(child) != "self":
                    attr_name = get_text(child)
                    attr_name_node = child
                    break

            if not attr_name or not attr_name_node:
                return

            # Only record if it's in __init__ or starts with _ (common patterns)
            if method_name != "__init__" and not attr_name.startswith("_"):
                return

            symbols.append(
                self._make_symbol(
                    attr_name, "instance_variable", attr_name_node, class_name
                )
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

            symbols.append(self._make_symbol(var_name, kind, node, class_name))

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

            # Use func_def start point (the actual def line), not node
            qualified = f"{class_name}.{func_name}" if class_name else func_name
            symbols.append(
                self._make_symbol(
                    func_name,
                    kind,
                    func_def,
                    class_name,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    qualified_name=qualified,
                )
            )

            # Process body of decorated function/method
            if func_def:
                for child in func_def.children:
                    if child.type == "block":
                        if class_name:
                            process_method_body(child, class_name, func_name)
                        process_nested_functions(child, qualified)

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
            symbols.append(self._make_symbol(func_name, "function", node, scope))

            # Extract nested functions
            parent_qualified = f"{scope}.{func_name}" if scope else func_name
            for child in node.children:
                if child.type == "block":
                    process_nested_functions(child, parent_qualified)

        def process_nested_functions(block: Node, parent_qualified_name: str) -> None:
            """Recursively extract nested function definitions from a block."""
            for child in block.children:
                if child.type == "function_definition":
                    name_node = child.child_by_field_name("name")
                    if not name_node:
                        for sub in child.children:
                            if sub.type == "identifier":
                                name_node = sub
                                break
                    if name_node:
                        func_name = get_text(name_node)
                        symbols.append(
                            self._make_symbol(
                                func_name,
                                "function",
                                child,
                                parent_qualified_name,
                            )
                        )
                        nested_qualified = f"{parent_qualified_name}.{func_name}"
                        for sub in child.children:
                            if sub.type == "block":
                                process_nested_functions(sub, nested_qualified)
                elif child.type == "decorated_definition":
                    func_def = None
                    for sub in child.children:
                        if sub.type == "function_definition":
                            func_def = sub
                            break
                    if func_def:
                        name_node = func_def.child_by_field_name("name")
                        if not name_node:
                            for sub in func_def.children:
                                if sub.type == "identifier":
                                    name_node = sub
                                    break
                        if name_node:
                            func_name = get_text(name_node)
                            symbols.append(
                                self._make_symbol(
                                    func_name,
                                    "function",
                                    func_def,
                                    parent_qualified_name,
                                    end_line=child.end_point[0] + 1,
                                    end_column=child.end_point[1],
                                )
                            )
                            nested_qualified = f"{parent_qualified_name}.{func_name}"
                            for sub in func_def.children:
                                if sub.type == "block":
                                    process_nested_functions(sub, nested_qualified)
                elif child.type in (
                    "if_statement",
                    "for_statement",
                    "while_statement",
                    "with_statement",
                    "try_statement",
                ):
                    for sub in child.children:
                        if sub.type == "block":
                            process_nested_functions(sub, parent_qualified_name)

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
                symbols.append(self._make_symbol(var_name, "constant", node))

        def extract_references(node: Node, scope: str | None = None) -> None:
            """Extract references from the AST."""
            # Import statements
            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        add_reference(
                            self._make_reference(get_text(child), "import", child)
                        )
                    elif child.type == "aliased_import":
                        name = child.child_by_field_name("name")
                        if name:
                            add_reference(
                                self._make_reference(get_text(name), "import", name)
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
                            self._make_reference(
                                get_text(child),
                                "import",
                                child,
                                from_module=module_node,
                            )
                        )
                    elif child.type == "aliased_import":
                        name = child.child_by_field_name("name")
                        if name:
                            add_reference(
                                self._make_reference(
                                    get_text(name),
                                    "import",
                                    name,
                                    from_module=module_node,
                                )
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
                                self._make_reference(
                                    call_name, "call", func_node, scope
                                )
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
                                self._make_reference(
                                    get_text(attr_node), "call", attr_node, scope
                                )
                            )
                        # Also reference the receiver (e.g., FileFilter in
                        # FileFilter.should_skip()), but not self/cls/builtins
                        obj_node = func_node.children[0] if func_node.children else None
                        if obj_node and obj_node.type == "identifier":
                            obj_name = get_text(obj_node)
                            if (
                                obj_name not in ("self", "cls")
                                and obj_name not in PYTHON_BUILTINS
                                and obj_name not in PYTHON_TYPE_BUILTINS
                            ):
                                add_reference(
                                    self._make_reference(
                                        obj_name, "usage", obj_node, scope
                                    )
                                )

            # Attribute references (obj.attr usage)
            if node.type == "attribute":
                children = list(node.children)
                if len(children) >= 3:
                    obj_node = children[0]
                    parent = node.parent
                    is_call = parent is not None and parent.type == "call"
                    is_write_target = _is_write_target(node)
                    if obj_node.type == "identifier" and get_text(obj_node) == "self":
                        # self.attribute — extract attr but not self
                        attr_name = None
                        attr_node = None
                        for child in reversed(children):
                            if child.type == "identifier" and get_text(child) != "self":
                                attr_name = get_text(child)
                                attr_node = child
                                break
                        if attr_name and attr_node:
                            if not is_call and not is_write_target:
                                add_reference(
                                    self._make_reference(
                                        attr_name, "usage", attr_node, scope
                                    )
                                )
                    elif not is_call:
                        # Non-self attribute access (not a call — calls handled
                        # above). Extract both receiver and attribute.
                        if obj_node.type == "identifier":
                            obj_name = get_text(obj_node)
                            if (
                                obj_name not in ("self", "cls")
                                and obj_name not in PYTHON_BUILTINS
                                and obj_name not in PYTHON_TYPE_BUILTINS
                            ):
                                add_reference(
                                    self._make_reference(
                                        obj_name, "usage", obj_node, scope
                                    )
                                )
                        # Extract the attribute name
                        attr_node = None
                        for child in reversed(children):
                            if child.type == "identifier" and child != obj_node:
                                attr_node = child
                                break
                        if attr_node:
                            attr_name = get_text(attr_node)
                            if not is_write_target:
                                add_reference(
                                    self._make_reference(
                                        attr_name, "usage", attr_node, scope
                                    )
                                )

            # Type annotations
            if node.type in ("type", "generic_type"):
                type_id = node.child_by_field_name("identifier")
                if type_id:
                    type_name = get_text(type_id)
                    if type_name not in PYTHON_TYPE_BUILTINS:
                        add_reference(
                            self._make_reference(
                                type_name, "type_annotation", type_id, scope
                            )
                        )
                # Also check for the first identifier child
                for child in node.children:
                    if child.type == "identifier":
                        type_name = get_text(child)
                        if type_name not in PYTHON_TYPE_BUILTINS:
                            add_reference(
                                self._make_reference(
                                    type_name, "type_annotation", child, scope
                                )
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

    def extract_comments(
        self,
        root: Node,
        content: str,
    ) -> list[dict[str, Any]]:
        """Extract comments and docstrings from Python AST."""
        comments: list[dict[str, Any]] = []

        def get_text(node: Node) -> str:
            return self._get_text(node, content)

        def should_skip_comment(original_text: str, stripped_text: str) -> bool:
            """Check if a comment should be skipped (shebang, encoding, etc.)."""
            # Skip shebangs (check original text before stripping)
            if original_text.startswith("#!"):
                return True
            # Skip encoding declarations
            if "coding:" in stripped_text or "coding=" in stripped_text:
                return True
            return False

        def extract_docstring_from_string_node(
            node: Node, parent_type: str
        ) -> dict[str, Any] | None:
            """Extract a docstring from a string node."""
            text = get_text(node)
            # Strip triple quotes
            if text.startswith('"""') and text.endswith('"""'):
                content_text = text[3:-3].strip()
            elif text.startswith("'''") and text.endswith("'''"):
                content_text = text[3:-3].strip()
            else:
                return None

            if not content_text:
                return None

            return {
                "content": content_text,
                "content_type": "docstring",
                "source_line": node.start_point[0] + 1,
                "source_end_line": node.end_point[0] + 1,
            }

        def visit_node(node: Node, parent_node: Node | None = None) -> None:
            """Recursively visit nodes to extract comments and docstrings."""
            try:
                # Extract inline comments
                if node.type == "comment":
                    original_text = get_text(node)
                    # Strip the # marker and whitespace
                    stripped_text = original_text
                    if stripped_text.startswith("#"):
                        stripped_text = stripped_text[1:].strip()

                    if not should_skip_comment(original_text, stripped_text):
                        comments.append(
                            {
                                "content": stripped_text,
                                "content_type": "single_line_comment",
                                "source_line": node.start_point[0] + 1,
                                "source_end_line": node.end_point[0] + 1,
                            }
                        )

                # Extract docstrings (first string in function/class/module)
                elif node.type == "expression_statement":
                    # Check if this is the first statement in a function/class/module/block
                    if parent_node and parent_node.type in (
                        "function_definition",
                        "class_definition",
                        "module",
                        "block",
                    ):
                        # Verify this is actually the FIRST statement (not just any string)
                        # A docstring must be the first non-comment child
                        is_first_statement = True
                        for sibling in parent_node.children:
                            # Skip non-statement nodes (decorators, def/class keywords, etc.)
                            if sibling.type in (
                                "comment",
                                "decorator",
                                "def",
                                "class",
                                "identifier",
                                "parameters",
                                "argument_list",
                                ":",
                                "type",
                                "return_type",
                            ):
                                continue
                            # First real statement found
                            if sibling.type == "expression_statement":
                                # This is the first statement - is it our node?
                                is_first_statement = sibling.id == node.id
                            else:
                                # First statement is not an expression_statement
                                is_first_statement = False
                            break

                        if is_first_statement:
                            # Find the first child that is a string
                            for child in node.children:
                                if child.type == "string":
                                    docstring = extract_docstring_from_string_node(
                                        child, parent_node.type
                                    )
                                    if docstring:
                                        comments.append(docstring)
                                    break
            except (
                AttributeError,
                IndexError,
                KeyError,
                ValueError,
                RuntimeError,
            ) as e:
                # Unexpected AST node structure during comment/docstring extraction
                logger.warning(
                    "Skipping comment node %s at line %d: %s",
                    node.type,
                    node.start_point[0] + 1,
                    e,
                )

            # Recurse into children (outside try/except to continue traversal)
            for child in node.children:
                visit_node(child, node)

        # Start extraction
        visit_node(root)

        return comments
