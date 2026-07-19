"""PHP language parser using Tree-sitter."""

from typing import Any

from tree_sitter import Node

from .base import BaseLanguageParser
from .builtins import _load

# PHP builtin/standard-library functions to exclude from call references
PHP_BUILTINS = _load("php.json", "builtins")

# PHP primitive/pseudo types to exclude from type references
PHP_PRIMITIVE_TYPES = _load("php.json", "primitive_types")


class PhpParser(BaseLanguageParser):
    """Parser for PHP source code using Tree-sitter.

    Extracts classes, interfaces, traits, enums, functions, methods,
    properties and constants as symbols, and resolves function/method/static
    calls, instantiation (``new``), inheritance (``extends``), interface
    implementation (``implements``), trait usage (``use``), namespace imports
    (``use``) and type annotations as references.
    """

    @property
    def language_name(self) -> str:
        return "php"

    def extract(
        self,
        root: Node,
        content: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract symbols and references from a PHP AST."""
        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        def get_text(node: Node) -> str:
            return self._get_text(node, content)

        def add_reference(ref: dict[str, Any]) -> None:
            self._add_reference(ref, references)

        # --- Small AST helpers ---

        def first_child(node: Node, type_name: str) -> Node | None:
            for child in node.children:
                if child.type == type_name:
                    return child
            return None

        def name_node_of(node: Node) -> Node | None:
            """Return the first ``name`` child (a declaration's own name)."""
            return first_child(node, "name")

        def simple_name(node: Node) -> tuple[str, Node] | None:
            """Resolve a ``name`` or ``qualified_name`` node to (text, node).

            For a qualified name (``App\\Models\\User``) the final segment is
            returned so the reference matches a simple class symbol name.
            """
            if node.type == "name":
                return get_text(node), node
            if node.type == "qualified_name":
                last = None
                for child in node.children:
                    if child.type == "name":
                        last = child
                if last is not None:
                    return get_text(last), last
            return None

        def qualify(name: str, namespace: str | None) -> str:
            return f"{namespace}\\{name}" if namespace else name

        # --- Symbol extraction ---

        def process_base_clause(node: Node, ref_type: str, scope: str) -> None:
            """Emit inheritance/implementation refs from a base/interface clause."""
            for child in node.children:
                resolved = simple_name(child)
                if resolved is not None:
                    ref_name, ref_node = resolved
                    add_reference(
                        self._make_reference(ref_name, ref_type, ref_node, scope)
                    )

        def process_type_declaration(
            node: Node, kind: str, namespace: str | None
        ) -> None:
            """Process a class/interface/trait/enum declaration."""
            name_node = name_node_of(node)
            if name_node is None:
                return
            type_name = get_text(name_node)
            type_qn = qualify(type_name, namespace)

            symbols.append(
                self._make_symbol(
                    type_name,
                    kind,
                    name_node,
                    None,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    qualified_name=type_qn,
                )
            )

            # extends → inheritance ; implements → implementation
            base = first_child(node, "base_clause")
            if base is not None:
                process_base_clause(base, "inheritance", type_qn)
            impls = first_child(node, "class_interface_clause")
            if impls is not None:
                process_base_clause(impls, "implementation", type_qn)

            body = first_child(node, "declaration_list") or first_child(
                node, "enum_declaration_list"
            )
            if body is not None:
                process_member_list(body, type_qn)

        def process_member_list(node: Node, scope: str) -> None:
            """Process a class/interface/trait/enum body."""
            for child in node.children:
                if child.type == "method_declaration":
                    process_method(child, scope)
                elif child.type == "property_declaration":
                    process_property(child, scope)
                elif child.type == "const_declaration":
                    process_const(child, scope)
                elif child.type == "enum_case":
                    process_enum_case(child, scope)
                elif child.type == "use_declaration":
                    process_trait_use(child, scope)

        def build_signature(name: str, node: Node) -> str:
            """Build a readable signature ``name(params): return``."""
            params = first_child(node, "formal_parameters")
            params_text = get_text(params) if params is not None else "()"
            return_type: str | None = None
            seen_colon = False
            for child in node.children:
                if not child.is_named and child.type == ":":
                    seen_colon = True
                elif (
                    seen_colon and child.is_named and child.type != "compound_statement"
                ):
                    return_type = get_text(child)
                    break
            sig = f"{name}{params_text}"
            if return_type:
                sig += f": {return_type}"
            return sig

        def process_method(node: Node, scope: str) -> None:
            name_node = name_node_of(node)
            if name_node is None:
                return
            method_name = get_text(name_node)
            symbols.append(
                self._make_symbol(
                    method_name,
                    "method",
                    name_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    qualified_name=f"{scope}::{method_name}",
                    signature=build_signature(method_name, node),
                )
            )

        def process_property(node: Node, scope: str) -> None:
            for child in node.children:
                if child.type != "property_element":
                    continue
                var_node = first_child(child, "variable_name")
                if var_node is None:
                    continue
                inner = name_node_of(var_node)
                if inner is None:
                    continue
                prop_name = get_text(inner)
                symbols.append(
                    self._make_symbol(
                        prop_name,
                        "property",
                        inner,
                        scope,
                        qualified_name=f"{scope}::${prop_name}",
                    )
                )

        def process_const(node: Node, scope: str) -> None:
            for child in node.children:
                if child.type != "const_element":
                    continue
                name_node = name_node_of(child)
                if name_node is None:
                    continue
                const_name = get_text(name_node)
                symbols.append(
                    self._make_symbol(
                        const_name,
                        "constant",
                        name_node,
                        scope,
                        qualified_name=f"{scope}::{const_name}",
                    )
                )

        def process_enum_case(node: Node, scope: str) -> None:
            name_node = name_node_of(node)
            if name_node is None:
                return
            case_name = get_text(name_node)
            symbols.append(
                self._make_symbol(
                    case_name,
                    "enum_case",
                    name_node,
                    scope,
                    qualified_name=f"{scope}::{case_name}",
                )
            )

        def process_trait_use(node: Node, scope: str) -> None:
            for child in node.children:
                resolved = simple_name(child)
                if resolved is not None:
                    trait_name, trait_node = resolved
                    add_reference(
                        self._make_reference(trait_name, "trait_use", trait_node, scope)
                    )

        def process_function(node: Node, namespace: str | None) -> None:
            name_node = name_node_of(node)
            if name_node is None:
                return
            func_name = get_text(name_node)
            symbols.append(
                self._make_symbol(
                    func_name,
                    "function",
                    name_node,
                    None,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    qualified_name=qualify(func_name, namespace),
                    signature=build_signature(func_name, node),
                )
            )

        def process_use_import(node: Node, namespace: str | None) -> None:
            """Emit ``import`` references for ``use`` namespace declarations."""
            for clause in _descendants(node, "namespace_use_clause"):
                # An aliased import (``use A\\B as C``) still references B.
                target = None
                for child in clause.children:
                    if child.type in ("name", "qualified_name"):
                        target = child
                        break
                if target is None:
                    continue
                resolved = simple_name(target)
                if resolved is not None:
                    import_name, import_node = resolved
                    add_reference(
                        self._make_reference(import_name, "import", import_node)
                    )

        def _descendants(node: Node, type_name: str) -> list[Node]:
            found: list[Node] = []

            def walk(n: Node) -> None:
                if n.type == type_name:
                    found.append(n)
                for c in n.children:
                    walk(c)

            walk(node)
            return found

        def process_top_level(node: Node, namespace: str | None) -> str | None:
            """Dispatch a top-level node; returns the (possibly new) namespace."""
            if node.type == "namespace_definition":
                ns_name_node = first_child(node, "namespace_name")
                ns_name = get_text(ns_name_node) if ns_name_node is not None else None
                body = first_child(node, "compound_statement")
                if body is not None:
                    # Braced form: declarations are nested; namespace does not
                    # leak to following siblings.
                    for child in body.children:
                        process_top_level(child, ns_name)
                    return namespace
                # Semicolon form: applies to the rest of the file.
                return ns_name
            if node.type == "class_declaration":
                process_type_declaration(node, "class", namespace)
            elif node.type == "interface_declaration":
                process_type_declaration(node, "interface", namespace)
            elif node.type == "trait_declaration":
                process_type_declaration(node, "trait", namespace)
            elif node.type == "enum_declaration":
                process_type_declaration(node, "enum", namespace)
            elif node.type == "function_definition":
                process_function(node, namespace)
            elif node.type == "namespace_use_declaration":
                process_use_import(node, namespace)
            return namespace

        # --- Reference extraction ---

        def call_target_after_operator(node: Node, operator: str) -> Node | None:
            """Return the ``name`` node that follows ``operator`` (-> or ::)."""
            seen = False
            for child in node.children:
                if not child.is_named and child.type == operator:
                    seen = True
                elif seen and child.type == "name":
                    return child
            return None

        def extract_references(
            node: Node, scope: str | None, namespace: str | None
        ) -> None:
            node_type = node.type

            if node_type == "function_call_expression":
                callee = node.children[0] if node.children else None
                if callee is not None:
                    resolved = simple_name(callee)
                    if resolved is not None:
                        func_name, func_node = resolved
                        # PHP function names are case-insensitive; PHP_BUILTINS
                        # is stored lowercase, so fold before the membership test
                        # (Strlen/COUNT must be filtered like strlen/count).
                        if func_name.lower() not in PHP_BUILTINS:
                            add_reference(
                                self._make_reference(
                                    func_name, "call", func_node, scope
                                )
                            )
            elif node_type in (
                "member_call_expression",
                "nullsafe_member_call_expression",
            ):
                operator = "->" if node_type == "member_call_expression" else "?->"
                method_node = call_target_after_operator(node, operator)
                if method_node is not None:
                    add_reference(
                        self._make_reference(
                            get_text(method_node), "call", method_node, scope
                        )
                    )
            elif node_type == "scoped_call_expression":
                method_node = call_target_after_operator(node, "::")
                if method_node is not None:
                    add_reference(
                        self._make_reference(
                            get_text(method_node), "call", method_node, scope
                        )
                    )
                # The class part (before ::) is a static usage of a type.
                _emit_scope_class(node, scope)
            elif node_type == "object_creation_expression":
                for child in node.children:
                    resolved = simple_name(child)
                    if resolved is not None:
                        cls_name, cls_node = resolved
                        # `new self()` / `new static()` / `new parent()` name a
                        # pseudo-class, not a real symbol — skip so we don't emit
                        # dangling instantiation refs. (PHP class names are
                        # case-insensitive, so fold before the check.)
                        if cls_name.lower() not in PHP_PRIMITIVE_TYPES:
                            add_reference(
                                self._make_reference(
                                    cls_name, "instantiation", cls_node, scope
                                )
                            )
                        break
            elif node_type == "class_constant_access_expression":
                _emit_scope_class(node, scope)
            elif node_type == "named_type":
                resolved = simple_name(node.children[0]) if node.children else None
                if resolved is not None:
                    type_name, type_node = resolved
                    # PHP type names are case-insensitive; a capitalized scalar
                    # hint (Int/Array/Void) parses as a named_type, so fold
                    # before the primitive check to avoid a dangling ref.
                    if type_name.lower() not in PHP_PRIMITIVE_TYPES:
                        add_reference(
                            self._make_reference(
                                type_name, "type_annotation", type_node, scope
                            )
                        )

            # Thread scope AND namespace into children so reference scopes match
            # the namespace-qualified scopes the symbol pass produces.
            child_scope = _scope_for_children(node, scope, namespace)
            child_ns = namespace
            for child in node.children:
                if child.type == "namespace_definition":
                    ns_node = first_child(child, "namespace_name")
                    ns_name = get_text(ns_node) if ns_node is not None else None
                    if first_child(child, "compound_statement") is not None:
                        # Braced form: namespace applies to this subtree only.
                        extract_references(child, child_scope, ns_name)
                    else:
                        # Semicolon form: applies to the rest of the file.
                        extract_references(child, child_scope, ns_name)
                        child_ns = ns_name
                else:
                    extract_references(child, child_scope, child_ns)

        def _emit_scope_class(node: Node, scope: str | None) -> None:
            """Emit a usage ref for the class in ``Class::member`` expressions."""
            first = node.children[0] if node.children else None
            if first is None or first.type == "relative_scope":
                return  # self:: / static:: / parent:: — not a named type
            resolved = simple_name(first)
            if resolved is not None:
                cls_name, cls_node = resolved
                # Case-insensitive: keep in step with the other primitive filters.
                if cls_name.lower() not in PHP_PRIMITIVE_TYPES:
                    add_reference(
                        self._make_reference(cls_name, "usage", cls_node, scope)
                    )

        def _scope_for_children(
            node: Node, scope: str | None, namespace: str | None
        ) -> str | None:
            """Compute the scope string for a node's children.

            Class/interface/trait/enum scopes are namespace-qualified so that
            reference scopes match the qualified names emitted by the symbol
            pass (e.g. ``App\\Models\\User::method``).
            """
            if node.type in (
                "class_declaration",
                "interface_declaration",
                "trait_declaration",
                "enum_declaration",
            ):
                name_node = name_node_of(node)
                if name_node is not None:
                    return qualify(get_text(name_node), namespace)
            elif node.type in ("method_declaration", "function_definition"):
                name_node = name_node_of(node)
                if name_node is not None:
                    func_name = get_text(name_node)
                    return f"{scope}::{func_name}" if scope else func_name
            return scope

        # First pass: symbols (namespace threads through top-level siblings).
        current_namespace: str | None = None
        for child in root.children:
            current_namespace = process_top_level(child, current_namespace)

        # Second pass: references.
        extract_references(root, None, None)

        return symbols, references

    def _process_comment_node(self, node: Node, content: str) -> dict[str, Any] | None:
        """Classify and clean a PHP comment node.

        PHP comments are all a single ``comment`` node type; the marker
        (``//``, ``#``, ``/* */`` or ``/** */``) determines the content type.
        """
        if node.type != "comment":
            return None

        text = self._get_text(node, content)

        if text.startswith("/**"):
            cleaned = self._strip_block_comment(text)
            if not cleaned:
                return None
            return {
                "content": cleaned,
                "content_type": "docstring",
                "source_line": node.start_point[0] + 1,
                "source_end_line": node.end_point[0] + 1,
            }
        if text.startswith("/*"):
            cleaned = self._strip_block_comment(text)
            if not cleaned:
                return None
            return {
                "content": cleaned,
                "content_type": "block_comment",
                "source_line": node.start_point[0] + 1,
                "source_end_line": node.end_point[0] + 1,
            }
        if text.startswith("//") or text.startswith("#"):
            marker_len = 2 if text.startswith("//") else 1
            cleaned = text[marker_len:].strip()
            if not cleaned:
                return None
            return {
                "content": cleaned,
                "content_type": "single_line_comment",
                "source_line": node.start_point[0] + 1,
                "source_end_line": node.end_point[0] + 1,
            }
        return None
