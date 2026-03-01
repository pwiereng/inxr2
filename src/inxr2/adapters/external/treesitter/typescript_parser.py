"""TypeScript and JavaScript language parser using Tree-sitter."""

import re
from typing import Any

from tree_sitter import Node

from .base import BaseLanguageParser

# TypeScript/JavaScript builtin functions and keywords to exclude from references
TS_BUILTINS = {
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

# TypeScript type builtins to exclude from type references
TS_TYPE_BUILTINS = {
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


class TypeScriptParser(BaseLanguageParser):
    """
    Parser for TypeScript and JavaScript source code using Tree-sitter.

    Handles both TypeScript (.ts, .tsx) and JavaScript (.js, .jsx, .mjs, .cjs)
    since they share the same AST structure for common constructs.
    """

    def __init__(self, language: str = "typescript") -> None:
        """
        Initialize parser for a specific language variant.

        Args:
            language: Either "typescript" or "javascript"
        """
        super().__init__()
        self._language = language

    @property
    def language_name(self) -> str:
        return self._language

    def extract(
        self,
        root: Node,
        content: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract symbols and references from TypeScript/JavaScript AST."""
        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        def get_text(node: Node) -> str:
            return self._get_text(node, content)

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
            self._add_reference(ref, references)

        def process_interface(node: Node) -> None:
            """Process an interface declaration."""
            name = get_name_from_node(node)
            if not name:
                return

            symbols.append(self._make_symbol(name, "interface", node))

            # Extract interface properties
            for child in node.children:
                if child.type == "interface_body":
                    for prop in child.children:
                        if prop.type == "property_signature":
                            prop_name = get_name_from_node(prop)
                            if prop_name:
                                symbols.append(
                                    self._make_symbol(
                                        prop_name, "interface_property", prop, name
                                    )
                                )
                        elif prop.type == "method_signature":
                            method_name = get_name_from_node(prop)
                            if method_name:
                                symbols.append(
                                    self._make_symbol(
                                        method_name, "interface_method", prop, name
                                    )
                                )

        def process_type_alias(node: Node) -> None:
            """Process a type alias declaration."""
            name = get_name_from_node(node)
            if not name:
                return

            symbols.append(self._make_symbol(name, "type", node))

        def process_enum(node: Node) -> None:
            """Process an enum declaration."""
            name = get_name_from_node(node)
            if not name:
                return

            symbols.append(self._make_symbol(name, "enum", node))

            # Extract enum members
            for child in node.children:
                if child.type == "enum_body":
                    for member in child.children:
                        if member.type in ("property_identifier", "enum_assignment"):
                            member_name = get_name_from_node(member)
                            if member_name:
                                symbols.append(
                                    self._make_symbol(
                                        member_name, "enum_member", member, name
                                    )
                                )

        def _add_heritage_ref(node: Node, class_name: str | None) -> None:
            """Add an inheritance reference for a heritage type node.

            Handles identifier, type_identifier, member_expression (ns.Parent),
            and generic_type (IFoo<Bar>) by extracting the primary type name.
            """
            if node.type in ("identifier", "type_identifier"):
                name = get_text(node)
                if name not in TS_BUILTINS and name not in TS_TYPE_BUILTINS:
                    add_reference(
                        self._make_reference(name, "inheritance", node, class_name)
                    )
            elif node.type == "member_expression":
                # ns.Parent — use the property (rightmost identifier)
                prop = node.child_by_field_name("property")
                if prop:
                    name = get_text(prop)
                    if name not in TS_BUILTINS and name not in TS_TYPE_BUILTINS:
                        add_reference(
                            self._make_reference(name, "inheritance", prop, class_name)
                        )
            elif node.type == "generic_type":
                # IFoo<Bar> — extract the base type identifier
                for sub in node.children:
                    if sub.type in ("identifier", "type_identifier"):
                        name = get_text(sub)
                        if name not in TS_BUILTINS and name not in TS_TYPE_BUILTINS:
                            add_reference(
                                self._make_reference(
                                    name, "inheritance", sub, class_name
                                )
                            )
                        break

        def _extract_heritage_references(
            heritage_node: Node, class_name: str | None
        ) -> None:
            """Extract inheritance references from class_heritage node.

            Handles both TypeScript (extends_clause/implements_clause children)
            and JavaScript (identifier children directly under class_heritage).
            """
            for child in heritage_node.children:
                if child.type in ("extends_clause", "implements_clause"):
                    for sub in child.children:
                        _add_heritage_ref(sub, class_name)
                else:
                    # JS: identifiers/member_expression directly under class_heritage
                    _add_heritage_ref(child, class_name)

        def process_class(node: Node) -> None:
            """Process a class declaration."""
            name = get_name_from_node(node)
            if not name:
                return

            symbols.append(self._make_symbol(name, "class", node))

            # Process class body (inheritance refs extracted in extract_references)
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

            symbols.append(self._make_symbol(name, kind, node, class_name))

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

            symbols.append(self._make_symbol(name, kind, node, class_name))

        def process_function(node: Node, is_exported: bool = False) -> None:
            """Process a function declaration."""
            name = get_name_from_node(node)
            if not name:
                return

            symbols.append(self._make_symbol(name, "function", node))

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
                        symbols.append(self._make_symbol(var_name, "function", child))
                    elif re.match(r"^[A-Z][A-Z0-9_]*$", var_name):
                        # UPPER_CASE constant
                        symbols.append(self._make_symbol(var_name, "constant", child))

        def _is_heritage_base_type(node: Node) -> bool:
            """Check if a type_identifier is a heritage base type (not a type argument).

            Returns True for the primary type in extends/implements clauses:
              - `implements IFoo` → IFoo is a heritage base (parent is implements_clause)
              - `implements IFoo<Bar>` → IFoo is a heritage base (parent is generic_type
                whose parent is implements_clause), but Bar is NOT (it's a type argument)
              - `extends Parent` → Parent is heritage base (parent is extends_clause)
            """
            parent = node.parent
            if parent is None:
                return False
            # Direct child of extends_clause or implements_clause
            if parent.type in ("extends_clause", "implements_clause"):
                return True
            # Base type of a generic_type that is a direct child of a heritage clause
            if parent.type == "generic_type":
                grandparent = parent.parent
                if grandparent is not None and grandparent.type in (
                    "extends_clause",
                    "implements_clause",
                ):
                    # Only the first type_identifier in generic_type is the base
                    for child in parent.children:
                        if child.type in ("identifier", "type_identifier"):
                            return child.id == node.id
                        break
            return False

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
                                    self._make_reference(
                                        get_text(sub),
                                        "import",
                                        sub,
                                        from_module=from_module,
                                    )
                                )
                            elif sub.type == "named_imports":
                                for imp in sub.children:
                                    if imp.type == "import_specifier":
                                        imp_name = get_name_from_node(imp)
                                        if imp_name:
                                            add_reference(
                                                self._make_reference(
                                                    imp_name,
                                                    "import",
                                                    imp,
                                                    from_module=from_module,
                                                )
                                            )
                return

            # Function calls
            if node.type == "call_expression":
                func_node = node.child_by_field_name("function")
                if func_node:
                    if func_node.type == "identifier":
                        call_name = get_text(func_node)
                        if call_name not in TS_BUILTINS:
                            add_reference(
                                self._make_reference(
                                    call_name, "call", func_node, scope
                                )
                            )
                    elif func_node.type == "member_expression":
                        prop = func_node.child_by_field_name("property")
                        if prop:
                            add_reference(
                                self._make_reference(
                                    get_text(prop), "call", prop, scope
                                )
                            )

            # New object creation (new ClassName())
            if node.type == "new_expression":
                constructor_node = node.child_by_field_name("constructor")
                if constructor_node:
                    if constructor_node.type == "identifier":
                        class_name = get_text(constructor_node)
                        if class_name not in TS_BUILTINS:
                            add_reference(
                                self._make_reference(
                                    class_name,
                                    "instantiation",
                                    constructor_node,
                                    scope,
                                )
                            )
                    elif constructor_node.type == "member_expression":
                        prop = constructor_node.child_by_field_name("property")
                        if prop:
                            add_reference(
                                self._make_reference(
                                    get_text(prop),
                                    "instantiation",
                                    prop,
                                    scope,
                                )
                            )

            # Member access (reads and writes) — skip call/new/heritage
            if node.type == "member_expression":
                parent = node.parent
                skip = parent is not None and parent.type in (
                    "call_expression",
                    "new_expression",
                )
                if not skip:
                    # Walk ancestors to skip nested member_expressions
                    # inside heritage clauses (e.g. extends ns.sub.Parent)
                    ancestor = parent
                    while ancestor is not None:
                        if ancestor.type in (
                            "extends_clause",
                            "implements_clause",
                            "class_heritage",
                        ):
                            skip = True
                            break
                        if ancestor.type != "member_expression":
                            break
                        ancestor = ancestor.parent
                if not skip:
                    prop = node.child_by_field_name("property")
                    if prop:
                        prop_name = get_text(prop)
                        add_reference(
                            self._make_reference(prop_name, "usage", prop, scope)
                        )

            # Type references (skip heritage base types — handled as inheritance)
            if node.type == "type_identifier":
                if not _is_heritage_base_type(node):
                    type_name = get_text(node)
                    if type_name not in TS_TYPE_BUILTINS:
                        add_reference(
                            self._make_reference(
                                type_name, "type_annotation", node, scope
                            )
                        )

            # Class heritage (extends/implements) — handled here so nested classes work
            if node.type == "class_heritage":
                _extract_heritage_references(node, scope)

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

    def _process_comment_node(self, node: Node, content: str) -> dict[str, Any] | None:
        """Classify and clean a TypeScript/JavaScript comment node."""
        if node.type != "comment":
            return None

        text = self._get_text(node, content)

        # Determine comment type
        is_jsdoc = text.startswith("/**")
        is_block = text.startswith("/*") and not is_jsdoc

        if is_jsdoc:
            content_type = "jsdoc_comment"
        elif is_block:
            content_type = "block_comment"
        else:
            content_type = "single_line_comment"

        if is_jsdoc or is_block:
            cleaned = self._strip_block_comment(text)
        else:
            cleaned = text[2:].strip() if text.startswith("//") else text.strip()

        if not cleaned:
            return None

        return {
            "content": cleaned,
            "content_type": content_type,
            "source_line": node.start_point[0] + 1,
            "source_end_line": node.end_point[0] + 1,
        }
