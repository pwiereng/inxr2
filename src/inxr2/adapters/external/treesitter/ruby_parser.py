"""Ruby language parser using Tree-sitter."""

from typing import Any

from tree_sitter import Node

from .base import BaseLanguageParser
from .builtins import _load

RUBY_BUILTINS = _load("ruby.json", "builtins")
RUBY_PRIMITIVE_TYPES = _load("ruby.json", "primitive_types")
RUBY_STD_LIB_MODULES = _load("ruby.json", "standard_library_modules")


class RubyParser(BaseLanguageParser):
    """Parser for Ruby source code using Tree-sitter."""

    @property
    def language_name(self) -> str:
        return "ruby"

    def extract(
        self,
        root: Node,
        content: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract symbols and references from Ruby AST."""
        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        def get_text(node: Node) -> str:
            return self._get_text(node, content)

        def add_reference(ref: dict[str, Any]) -> None:
            self._add_reference(ref, references)

        def is_builtin(name: str) -> bool:
            return name in RUBY_BUILTINS

        def is_primitive_type(name: str) -> bool:
            return name in RUBY_PRIMITIVE_TYPES

        def is_std_lib_module(name: str) -> bool:
            return name in RUBY_STD_LIB_MODULES

        def is_in_declaration_context(node: Node) -> bool:
            """Check if a constant is part of a class/module/superclass declaration name.

            Walks up through scope_resolution parents to see if the chain
            ultimately belongs to a class, module, or superclass declaration.
            """
            current = node.parent
            while current and current.type == "scope_resolution":
                current = current.parent
            return current is not None and current.type in (
                "class",
                "module",
                "superclass",
            )

        def process_module(node: Node, scope: str | None) -> None:
            """Process a module definition."""
            module_name = None
            name_node = None

            for child in node.children:
                if child.type == "constant":
                    module_name = get_text(child)
                    name_node = child
                    break
                elif child.type == "scope_resolution":
                    module_name = get_text(child)
                    name_node = child
                    break

            if not module_name:
                return

            qualified = f"{scope}::{module_name}" if scope else module_name
            loc_node = name_node or node
            symbols.append(
                self._make_symbol(
                    module_name,
                    "module",
                    loc_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    qualified_name=qualified,
                )
            )

            # Process body
            for child in node.children:
                if child.type == "body_statement":
                    process_body(child, qualified)

        def process_class(node: Node, scope: str | None) -> None:
            """Process a class definition."""
            class_name = None
            name_node = None

            for child in node.children:
                if child.type == "constant":
                    class_name = get_text(child)
                    name_node = child
                    break
                elif child.type == "scope_resolution":
                    class_name = get_text(child)
                    name_node = child
                    break

            if not class_name:
                return

            qualified = f"{scope}::{class_name}" if scope else class_name
            loc_node = name_node or node
            symbols.append(
                self._make_symbol(
                    class_name,
                    "class",
                    loc_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    qualified_name=qualified,
                )
            )

            # Extract superclass reference
            for child in node.children:
                if child.type == "superclass":
                    process_superclass(child, qualified)

            # Process body
            for child in node.children:
                if child.type == "body_statement":
                    process_body(child, qualified)

        def process_superclass(node: Node, scope: str | None) -> None:
            """Process a superclass declaration to extract inheritance reference."""
            for child in node.children:
                if child.type == "constant":
                    parent_name = get_text(child)
                    if not is_primitive_type(parent_name):
                        add_reference(
                            self._make_reference(
                                parent_name, "inheritance", child, scope
                            )
                        )
                elif child.type == "scope_resolution":
                    parent_name = get_text(child)
                    add_reference(
                        self._make_reference(parent_name, "inheritance", child, scope)
                    )

        def process_method(node: Node, scope: str | None) -> None:
            """Process a method definition."""
            method_name = None
            name_node = None

            for child in node.children:
                if child.type == "identifier":
                    method_name = get_text(child)
                    name_node = child
                    break

            if not method_name:
                return

            loc_node = name_node or node
            symbols.append(
                self._make_symbol(
                    method_name,
                    "method",
                    loc_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                )
            )

        def process_singleton_method(node: Node, scope: str | None) -> None:
            """Process a singleton method (def receiver.method_name)."""
            method_name = None
            name_node = None

            # Find the identifier after the '.' token — that's the method name.
            # This handles `def self.foo`, `def MyClass.foo`, and `def obj.foo`.
            dot_seen = False
            for child in node.children:
                if child.type == ".":
                    dot_seen = True
                    continue
                if dot_seen and child.type == "identifier":
                    method_name = get_text(child)
                    name_node = child
                    break

            # Fallback: first identifier child (for unexpected AST shapes)
            if not method_name:
                for child in node.children:
                    if child.type == "identifier":
                        method_name = get_text(child)
                        name_node = child
                        break

            if not method_name:
                return

            loc_node = name_node or node
            symbols.append(
                self._make_symbol(
                    method_name,
                    "staticmethod",
                    loc_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                )
            )

        def process_constant_assignment(node: Node, scope: str | None) -> None:
            """Process a constant assignment (MY_CONST = value) at module/class level."""
            first_child = node.children[0] if node.children else None
            if first_child and first_child.type == "constant":
                const_name = get_text(first_child)
                symbols.append(
                    self._make_symbol(const_name, "constant", first_child, scope)
                )

        def process_body(node: Node, scope: str | None) -> None:
            """Process the body of a module/class."""
            for child in node.children:
                if child.type == "module":
                    process_module(child, scope)
                elif child.type == "class":
                    process_class(child, scope)
                elif child.type == "method":
                    process_method(child, scope)
                elif child.type == "singleton_method":
                    process_singleton_method(child, scope)
                elif child.type == "assignment":
                    process_constant_assignment(child, scope)

        def extract_references(node: Node, scope: str | None = None) -> None:
            """Extract references from the AST recursively."""
            if node.type == "call":
                process_call_reference(node, scope)
                # Recurse into all non-identifier children for nested references
                for child in node.children:
                    if child.type != "identifier":
                        extract_references(child, scope)
                return

            if node.type == "instance_variable":
                ivar_name = get_text(node)
                add_reference(self._make_reference(ivar_name, "usage", node, scope))

            if node.type == "constant":
                parent = node.parent
                # Skip class/module declaration names
                if parent and parent.type in ("class", "module"):
                    pass
                # Skip superclass constants (handled by process_superclass)
                elif parent and parent.type == "superclass":
                    pass
                # Constants inside scope_resolution: allow unless it's a declaration
                elif parent and parent.type == "scope_resolution":
                    if not is_in_declaration_context(node):
                        const_name = get_text(node)
                        if not is_primitive_type(const_name) and not is_std_lib_module(
                            const_name
                        ):
                            add_reference(
                                self._make_reference(const_name, "usage", node, scope)
                            )
                # Skip LHS of assignment (constant definition)
                elif parent and parent.type == "assignment":
                    if not (parent.children and parent.children[0] is node):
                        const_name = get_text(node)
                        if not is_primitive_type(const_name) and not is_std_lib_module(
                            const_name
                        ):
                            add_reference(
                                self._make_reference(const_name, "usage", node, scope)
                            )
                else:
                    const_name = get_text(node)
                    if not is_primitive_type(const_name) and not is_std_lib_module(
                        const_name
                    ):
                        add_reference(
                            self._make_reference(const_name, "usage", node, scope)
                        )

            # Update scope for class/module/method bodies
            child_scope = scope
            if node.type == "class":
                for child in node.children:
                    if child.type == "constant":
                        name = get_text(child)
                        child_scope = f"{scope}::{name}" if scope else name
                        break
                    elif child.type == "scope_resolution":
                        name = get_text(child)
                        child_scope = f"{scope}::{name}" if scope else name
                        break
            elif node.type == "module":
                for child in node.children:
                    if child.type == "constant":
                        name = get_text(child)
                        child_scope = f"{scope}::{name}" if scope else name
                        break
                    elif child.type == "scope_resolution":
                        name = get_text(child)
                        child_scope = f"{scope}::{name}" if scope else name
                        break
            elif node.type == "method" or node.type == "singleton_method":
                # For singleton methods, find identifier after '.' to handle
                # `def obj.foo` where `obj` is also an identifier node.
                scope_name_node: Node | None = None
                if node.type == "singleton_method":
                    children = node.children
                    for i, child in enumerate(children):
                        if child.type == ".":
                            if (
                                i + 1 < len(children)
                                and children[i + 1].type == "identifier"
                            ):
                                scope_name_node = children[i + 1]
                            break
                if scope_name_node is None:
                    for child in node.children:
                        if child.type == "identifier":
                            scope_name_node = child
                            break
                if scope_name_node is not None:
                    method_name = get_text(scope_name_node)
                    child_scope = f"{scope}.{method_name}" if scope else method_name

            for child in node.children:
                extract_references(child, child_scope)

        def process_call_reference(node: Node, scope: str | None) -> None:
            """Process a call node to extract references."""
            children = node.children
            if not children:
                return

            # Check if this is a dotted call (receiver.method) or scope resolution call
            has_dot = any(c.type == "." for c in children)

            if has_dot:
                # receiver.method(...) or ScopeRes.method(...)
                method_node = None
                for i, child in enumerate(children):
                    if child.type == ".":
                        if (
                            i + 1 < len(children)
                            and children[i + 1].type == "identifier"
                        ):
                            method_node = children[i + 1]
                        break

                if method_node:
                    method_name = get_text(method_node)
                    if not is_builtin(method_name):
                        add_reference(
                            self._make_reference(
                                method_name, "call", method_node, scope
                            )
                        )
            else:
                # Direct call: identifier(args) or identifier args
                first = children[0]
                if first.type == "identifier":
                    func_name = get_text(first)
                    # Handle require/require_relative as imports
                    if func_name in ("require", "require_relative"):
                        process_require_reference(node, scope)
                    elif not is_builtin(func_name):
                        add_reference(
                            self._make_reference(func_name, "call", first, scope)
                        )

        def _extract_string_import(string_node: Node, scope: str | None) -> None:
            """Extract import reference from a string node."""
            for sc in string_node.children:
                if sc.type == "string_content":
                    import_path = get_text(sc)
                    add_reference(
                        self._make_reference(import_path, "import", sc, scope)
                    )
                    break

        def process_require_reference(node: Node, scope: str | None) -> None:
            """Extract import reference from require/require_relative."""
            # Try argument_list first (parenthesized or grammar-wrapped args)
            for child in node.children:
                if child.type == "argument_list":
                    for arg in child.children:
                        if arg.type == "string":
                            _extract_string_import(arg, scope)
                    return
            # Fallback: string as direct child (some grammar versions)
            for child in node.children:
                if child.type == "string":
                    _extract_string_import(child, scope)

        # --- Main processing ---

        # First pass: extract symbols from top-level declarations
        for child in root.children:
            if child.type == "module":
                process_module(child, None)
            elif child.type == "class":
                process_class(child, None)
            elif child.type == "method":
                process_method(child, None)
            elif child.type == "singleton_method":
                process_singleton_method(child, None)
            elif child.type == "assignment":
                process_constant_assignment(child, None)

        # Second pass: extract references
        extract_references(root)

        return symbols, references

    def _process_comment_node(self, node: Node, content: str) -> dict[str, Any] | None:
        """Classify and clean a Ruby comment node."""
        if node.type == "comment":
            text = self._get_text(node, content)
            if text.startswith("#"):
                cleaned = text[1:].strip()
                if not cleaned:
                    return None
                return {
                    "content": cleaned,
                    "content_type": "single_line_comment",
                    "source_line": node.start_point[0] + 1,
                    "source_end_line": node.end_point[0] + 1,
                }
        return None
