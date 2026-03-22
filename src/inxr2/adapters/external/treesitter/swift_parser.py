"""Swift language parser using Tree-sitter."""

from typing import Any

from tree_sitter import Node

from .base import BaseLanguageParser
from .builtins import _load

# Swift builtin functions and identifiers to exclude from references
SWIFT_BUILTINS = _load("swift.json", "builtins")

# Swift primitive/stdlib types to exclude from type references
SWIFT_PRIMITIVE_TYPES = _load("swift.json", "primitive_types")

# Swift standard library module names to exclude from references
SWIFT_STD_LIB_MODULES = _load("swift.json", "standard_library_modules")


class SwiftParser(BaseLanguageParser):
    """Parser for Swift source code using Tree-sitter."""

    @property
    def language_name(self) -> str:
        return "swift"

    def extract(
        self,
        root: Node,
        content: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract symbols and references from Swift AST."""
        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        def get_text(node: Node) -> str:
            return self._get_text(node, content)

        def add_reference(ref: dict[str, Any]) -> None:
            self._add_reference(ref, references)

        def is_builtin_or_primitive(name: str) -> bool:
            return name in SWIFT_BUILTINS or name in SWIFT_PRIMITIVE_TYPES

        def is_std_lib_module(name: str) -> bool:
            return name in SWIFT_STD_LIB_MODULES

        # --- Symbol extraction helpers ---

        def get_class_decl_keyword(node: Node) -> str:
            """Return the keyword ('class', 'struct', 'enum', 'extension') for a class_declaration."""
            for child in node.children:
                if not child.is_named and child.type in (
                    "class",
                    "struct",
                    "enum",
                    "extension",
                    "actor",
                ):
                    return child.type
            return "class"

        def get_type_identifier(node: Node) -> tuple[str, Node] | None:
            """Return the (name, name_node) from the first type_identifier child."""
            for child in node.children:
                if child.type == "type_identifier":
                    return get_text(child), child
            return None

        def get_user_type_identifier(node: Node) -> tuple[str, Node] | None:
            """Return (name, name_node) from user_type > type_identifier child."""
            for child in node.children:
                if child.type == "user_type":
                    for grandchild in child.children:
                        if grandchild.type == "type_identifier":
                            return get_text(grandchild), grandchild
            return None

        def get_inheritance_types(node: Node) -> list[str]:
            """Return all inherited/conformed type names from inheritance_specifier children."""
            types: list[str] = []
            for child in node.children:
                if child.type == "inheritance_specifier":
                    for spec_child in child.children:
                        if spec_child.type == "user_type":
                            for gc in spec_child.children:
                                if gc.type == "type_identifier":
                                    types.append(get_text(gc))
                        elif spec_child.type == "type_identifier":
                            types.append(get_text(spec_child))
            return types

        def process_import_declaration(node: Node) -> None:
            """Process import statements."""
            for child in node.children:
                if child.type == "identifier":
                    # identifier > simple_identifier
                    for gc in child.children:
                        if gc.type == "simple_identifier":
                            module_name = get_text(gc)
                            add_reference(
                                self._make_reference(module_name, "import", gc)
                            )
                    break

        def process_class_declaration(
            node: Node, scope: str | None = None
        ) -> str | None:
            """Process class/struct/enum/extension declaration. Returns name for scoping."""
            keyword = get_class_decl_keyword(node)

            if keyword == "extension":
                return process_extension_declaration(node, scope)
            elif keyword == "enum":
                return process_enum_declaration(node, scope)
            else:
                kind = keyword  # "class", "struct", or "actor"
                result = get_type_identifier(node)
                if not result:
                    return None
                type_name, name_node = result

                qualified_name = f"{scope}.{type_name}" if scope else type_name
                symbols.append(
                    self._make_symbol(
                        type_name,
                        kind,
                        name_node,
                        scope,
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                        qualified_name=qualified_name,
                    )
                )

                # Add protocol conformance references (not filtered by primitive_types
                # — protocol names like Identifiable, Equatable are meaningful links)
                for inherited in get_inheritance_types(node):
                    if inherited not in SWIFT_BUILTINS:
                        add_reference(
                            self._make_reference(
                                inherited,
                                "protocol_conformance",
                                name_node,
                                qualified_name,
                            )
                        )

                # Process body
                for child in node.children:
                    if child.type == "class_body":
                        process_class_body(child, qualified_name)
                        break

                return qualified_name

        def process_extension_declaration(
            node: Node, scope: str | None = None
        ) -> str | None:
            """Process extension declaration."""
            result = get_user_type_identifier(node) or get_type_identifier(node)
            if not result:
                return None
            type_name, name_node = result

            qualified_name = f"{scope}.{type_name}" if scope else type_name
            # Give extensions a distinct qualified_name to avoid collision with
            # a class/struct of the same name in the same file.
            line_no = name_node.start_point[0] + 1
            ext_qualified_name = f"{qualified_name}.<extension>@{line_no}"
            symbols.append(
                self._make_symbol(
                    type_name,
                    "extension",
                    name_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    qualified_name=ext_qualified_name,
                )
            )

            # Add protocol conformance references
            for inherited in get_inheritance_types(node):
                if inherited not in SWIFT_BUILTINS:
                    add_reference(
                        self._make_reference(
                            inherited,
                            "protocol_conformance",
                            name_node,
                            ext_qualified_name,
                        )
                    )

            # Process body using the plain type name as scope so that extension
            # members are associated with the type, not the extension symbol.
            for child in node.children:
                if child.type == "class_body":
                    process_class_body(child, qualified_name)
                    break

            return ext_qualified_name

        def process_enum_declaration(
            node: Node, scope: str | None = None
        ) -> str | None:
            """Process enum declaration."""
            result = get_type_identifier(node)
            if not result:
                return None
            type_name, name_node = result

            qualified_name = f"{scope}.{type_name}" if scope else type_name
            symbols.append(
                self._make_symbol(
                    type_name,
                    "enum",
                    name_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    qualified_name=qualified_name,
                )
            )

            # Add protocol conformance references
            for inherited in get_inheritance_types(node):
                if inherited not in SWIFT_BUILTINS:
                    add_reference(
                        self._make_reference(
                            inherited,
                            "protocol_conformance",
                            name_node,
                            qualified_name,
                        )
                    )

            # Process enum body
            for child in node.children:
                if child.type == "enum_class_body":
                    process_enum_body(child, qualified_name)
                    break

            return qualified_name

        def process_enum_body(node: Node, scope: str) -> None:
            """Process enum body — extract cases and nested declarations."""
            for child in node.children:
                if child.type == "enum_entry":
                    process_enum_entry(child, scope)
                elif child.type == "class_declaration":
                    process_class_declaration(child, scope)
                elif child.type == "protocol_declaration":
                    process_protocol_declaration(child, scope)
                elif child.type == "function_declaration":
                    process_function_declaration(child, scope)

        def process_enum_entry(node: Node, scope: str) -> None:
            """Process an enum case entry."""
            for child in node.children:
                if child.type == "simple_identifier":
                    case_name = get_text(child)
                    symbols.append(
                        self._make_symbol(
                            case_name,
                            "enum_case",
                            child,
                            scope,
                        )
                    )

        def process_protocol_declaration(
            node: Node, scope: str | None = None
        ) -> str | None:
            """Process protocol declaration."""
            result = get_type_identifier(node)
            if not result:
                return None
            type_name, name_node = result

            qualified_name = f"{scope}.{type_name}" if scope else type_name
            symbols.append(
                self._make_symbol(
                    type_name,
                    "protocol",
                    name_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    qualified_name=qualified_name,
                )
            )

            # Add protocol inheritance references
            for inherited in get_inheritance_types(node):
                if inherited not in SWIFT_BUILTINS:
                    add_reference(
                        self._make_reference(
                            inherited,
                            "protocol_conformance",
                            name_node,
                            qualified_name,
                        )
                    )

            # Process protocol body
            for child in node.children:
                if child.type == "protocol_body":
                    process_protocol_body(child, qualified_name)
                    break

            return qualified_name

        def process_protocol_body(node: Node, scope: str) -> None:
            """Process protocol body — extract requirements."""
            for child in node.children:
                if child.type == "protocol_function_declaration":
                    process_protocol_function_declaration(child, scope)
                elif child.type == "protocol_property_declaration":
                    process_protocol_property_declaration(child, scope)
                elif child.type == "associatedtype_declaration":
                    process_associatedtype_declaration(child, scope)

        def process_protocol_function_declaration(node: Node, scope: str) -> None:
            """Process a protocol function requirement."""
            for child in node.children:
                if child.type == "simple_identifier":
                    func_name = get_text(child)
                    signature = _build_function_signature(func_name, node)
                    symbols.append(
                        self._make_symbol(
                            func_name,
                            "method",
                            child,
                            scope,
                            end_line=node.end_point[0] + 1,
                            end_column=node.end_point[1],
                            signature=signature,
                        )
                    )
                    return

        def process_protocol_property_declaration(node: Node, scope: str) -> None:
            """Process a protocol property requirement."""
            for child in node.children:
                if child.type == "pattern":
                    for gc in child.children:
                        if gc.type == "simple_identifier":
                            prop_name = get_text(gc)
                            symbols.append(
                                self._make_symbol(
                                    prop_name,
                                    "property",
                                    gc,
                                    scope,
                                )
                            )
                            return
                        elif gc.type == "value_binding_pattern":
                            # pattern may contain value_binding_pattern > simple_identifier
                            pass
            # Alternative pattern: value_binding_pattern then simple_identifier as sibling
            vbp_seen = False
            for child in node.children:
                if child.type == "value_binding_pattern":
                    vbp_seen = True
                elif vbp_seen and child.type == "simple_identifier":
                    prop_name = get_text(child)
                    symbols.append(
                        self._make_symbol(prop_name, "property", child, scope)
                    )
                    return

        def process_associatedtype_declaration(node: Node, scope: str) -> None:
            """Process an associatedtype declaration."""
            for child in node.children:
                if child.type == "type_identifier":
                    type_name = get_text(child)
                    symbols.append(self._make_symbol(type_name, "type", child, scope))
                    return

        def process_class_body(node: Node, scope: str) -> None:
            """Process class/struct/extension body — extract methods, properties, nested types."""
            for child in node.children:
                if child.type == "function_declaration":
                    process_function_declaration(child, scope)
                elif child.type == "init_declaration":
                    process_init_declaration(child, scope)
                elif child.type == "property_declaration":
                    process_property_declaration(child, scope)
                elif child.type == "class_declaration":
                    process_class_declaration(child, scope)
                elif child.type == "protocol_declaration":
                    process_protocol_declaration(child, scope)
                elif child.type == "subscript_declaration":
                    process_subscript_declaration(child, scope)
                elif child.type == "typealias_declaration":
                    process_typealias_declaration(child, scope)

        def _build_function_signature(func_name: str, node: Node) -> str:
            """Build a human-readable function signature string."""
            params_parts: list[str] = []
            return_type: str | None = None

            for child in node.children:
                if child.type == "parameter":
                    params_parts.append(get_text(child))
                elif child.type == "user_type" and return_type is None:
                    # Return type after '->'
                    return_type = get_text(child)
                elif child.type == "optional_type" and return_type is None:
                    return_type = get_text(child)
                elif child.type == "tuple_type" and return_type is None:
                    return_type = get_text(child)

            sig = f"func {func_name}({', '.join(params_parts)})"
            if return_type:
                sig += f" -> {return_type}"
            return sig

        def process_function_declaration(node: Node, scope: str | None = None) -> None:
            """Process a function/method declaration."""
            func_name = None
            name_node = None

            for child in node.children:
                if child.type == "simple_identifier":
                    func_name = get_text(child)
                    name_node = child
                    break

            if not func_name:
                return

            signature = _build_function_signature(func_name, node)
            kind = "method" if scope else "function"

            loc_node = name_node or node
            symbols.append(
                self._make_symbol(
                    func_name,
                    kind,
                    loc_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    signature=signature,
                )
            )

        def process_init_declaration(node: Node, scope: str | None = None) -> None:
            """Process an init declaration."""
            init_node = None
            for child in node.children:
                if not child.is_named and child.type == "init":
                    init_node = child
                    break

            if init_node is None:
                init_node = node

            symbols.append(
                self._make_symbol(
                    "init",
                    "init",
                    init_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                )
            )

        def process_property_declaration(node: Node, scope: str | None = None) -> None:
            """Process a property declaration (let/var)."""
            # Name is in: pattern > simple_identifier
            for child in node.children:
                if child.type == "pattern":
                    for gc in child.children:
                        if gc.type == "simple_identifier":
                            prop_name = get_text(gc)
                            symbols.append(
                                self._make_symbol(
                                    prop_name,
                                    "property",
                                    gc,
                                    scope,
                                    end_line=node.end_point[0] + 1,
                                    end_column=node.end_point[1],
                                )
                            )
                            return

        def process_subscript_declaration(node: Node, scope: str | None = None) -> None:
            """Process a subscript declaration."""
            symbols.append(
                self._make_symbol(
                    "subscript",
                    "method",
                    node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                )
            )

        def process_typealias_declaration(node: Node, scope: str | None = None) -> None:
            """Process a typealias declaration."""
            for child in node.children:
                if child.type == "type_identifier":
                    alias_name = get_text(child)
                    symbols.append(self._make_symbol(alias_name, "type", child, scope))
                    return

        # --- Reference extraction ---

        def extract_references(node: Node, scope: str | None = None) -> None:
            """Recursively extract references from the AST."""
            if node.type == "import_declaration":
                process_import_declaration(node)
                return

            if node.type == "call_expression":
                process_call_reference(node, scope)

            if node.type == "navigation_expression":
                process_navigation_reference(node, scope)

            if node.type == "user_type":
                process_type_reference(node, scope)

            # Recurse into children, updating scope for function/type bodies
            for child in node.children:
                child_scope = scope

                if node.type in (
                    "function_declaration",
                    "protocol_function_declaration",
                ):
                    name_node = _get_first_simple_identifier(node)
                    if name_node:
                        func_name = get_text(name_node)
                        child_scope = f"{scope}.{func_name}" if scope else func_name
                elif node.type == "class_declaration":
                    keyword = get_class_decl_keyword(node)
                    if keyword == "extension":
                        result = get_user_type_identifier(node) or get_type_identifier(
                            node
                        )
                    else:
                        result = get_type_identifier(node)
                    if result:
                        type_name, _ = result
                        child_scope = f"{scope}.{type_name}" if scope else type_name
                elif node.type == "protocol_declaration":
                    result = get_type_identifier(node)
                    if result:
                        type_name, _ = result
                        child_scope = f"{scope}.{type_name}" if scope else type_name

                extract_references(child, child_scope)

        def _get_first_simple_identifier(node: Node) -> Node | None:
            """Return the first simple_identifier child of a node."""
            for child in node.children:
                if child.type == "simple_identifier":
                    return child
            return None

        def process_call_reference(node: Node, scope: str | None) -> None:
            """Process a call expression."""
            if not node.children:
                return
            callee = node.children[0]

            if callee.type == "simple_identifier":
                func_name = get_text(callee)
                if not is_builtin_or_primitive(func_name):
                    add_reference(
                        self._make_reference(func_name, "call", callee, scope)
                    )
            elif callee.type == "navigation_expression":
                # obj.method() — extract method name from last navigation_suffix
                method_node = _get_last_navigation_identifier(callee)
                if method_node:
                    method_name = get_text(method_node)
                    if not is_builtin_or_primitive(method_name):
                        add_reference(
                            self._make_reference(
                                method_name, "call", method_node, scope
                            )
                        )

        def _get_last_navigation_identifier(node: Node) -> Node | None:
            """Get the final identifier in a navigation_expression chain."""
            for child in reversed(node.children):
                if child.type == "navigation_suffix":
                    for gc in child.children:
                        if gc.type == "simple_identifier":
                            return gc
            return None

        def process_navigation_reference(node: Node, scope: str | None) -> None:
            """Process a navigation expression (field access / method lookup)."""
            parent = node.parent
            # Skip if parent is call_expression — handled by call reference
            if parent and parent.type == "call_expression":
                return

            for child in node.children:
                if child.type == "navigation_suffix":
                    for gc in child.children:
                        if gc.type == "simple_identifier":
                            field_name = get_text(gc)
                            if not is_builtin_or_primitive(field_name):
                                add_reference(
                                    self._make_reference(field_name, "usage", gc, scope)
                                )

        def process_type_reference(node: Node, scope: str | None) -> None:
            """Process a user_type node — extract type references."""
            # Avoid double-counting user_type children nested in other user_types
            parent = node.parent
            if parent and parent.type == "user_type":
                return

            for child in node.children:
                if child.type == "type_identifier":
                    type_name = get_text(child)
                    if not is_builtin_or_primitive(type_name) and not is_std_lib_module(
                        type_name
                    ):
                        add_reference(
                            self._make_reference(
                                type_name, "type_annotation", child, scope
                            )
                        )

        # --- Main processing ---

        def process_top_level_node(node: Node, scope: str | None = None) -> None:
            """Dispatch a node to the appropriate symbol extractor."""
            if node.type == "class_declaration":
                process_class_declaration(node, scope)
            elif node.type == "protocol_declaration":
                process_protocol_declaration(node, scope)
            elif node.type == "function_declaration":
                process_function_declaration(node, scope)
            elif node.type == "property_declaration":
                process_property_declaration(node, scope)
            elif node.type == "typealias_declaration":
                process_typealias_declaration(node, scope)
            elif node.type == "ERROR":
                # Partial-parse error recovery: an ERROR node may represent a
                # top-level declaration that tree-sitter couldn't fully parse
                # (e.g. a protocol with a syntactically invalid member).
                # Detect the keyword from unnamed children and treat accordingly.
                keyword = next(
                    (
                        c.type
                        for c in node.children
                        if not c.is_named
                        and c.type
                        in (
                            "class",
                            "struct",
                            "enum",
                            "extension",
                            "actor",
                            "protocol",
                            "func",
                        )
                    ),
                    None,
                )
                if keyword == "protocol":
                    # Synthesise extraction: find name, then recurse into any
                    # ERROR sub-node for members.
                    name_node = next(
                        (c for c in node.children if c.type == "simple_identifier"),
                        None,
                    )
                    if name_node:
                        type_name = get_text(name_node)
                        qualified_name = f"{scope}.{type_name}" if scope else type_name
                        symbols.append(
                            self._make_symbol(
                                type_name,
                                "protocol",
                                name_node,
                                scope,
                                end_line=node.end_point[0] + 1,
                                end_column=node.end_point[1],
                                qualified_name=qualified_name,
                            )
                        )
                        # Recurse into any inner ERROR node to extract members
                        for child in node.children:
                            if child.type == "ERROR":
                                process_protocol_body(child, qualified_name)
                                process_class_body(child, qualified_name)
                elif keyword in ("class", "struct", "enum", "extension", "actor"):
                    # Fall back to normal class_declaration processing by
                    # recursing into children for any parseable sub-nodes.
                    for child in node.children:
                        process_top_level_node(child, scope)
                else:
                    for child in node.children:
                        process_top_level_node(child, scope)

        # First pass: extract symbols (top-level declarations)
        for child in root.children:
            process_top_level_node(child)

        # Second pass: extract references
        extract_references(root)

        return symbols, references

    def _process_comment_node(self, node: Node, content: str) -> dict[str, Any] | None:
        """Classify and clean a Swift comment node."""
        if node.type == "multiline_comment":
            text = self._get_text(node, content)
            # Swift doc comments: /** ... */ or /*! ... */
            if text.startswith("/**") or text.startswith("/*!"):
                cleaned = self._strip_block_comment(text)
                if not cleaned:
                    return None
                # _strip_block_comment handles /** but not /*!; strip the
                # leading '!' (and optional space) left by the /*! marker.
                if text.startswith("/*!") and cleaned.startswith("!"):
                    cleaned = cleaned[1:].lstrip()
                if not cleaned:
                    return None
                return {
                    "content": cleaned,
                    "content_type": "docstring",
                    "source_line": node.start_point[0] + 1,
                    "source_end_line": node.end_point[0] + 1,
                }
            cleaned = self._strip_block_comment(text)
            if not cleaned:
                return None
            return {
                "content": cleaned,
                "content_type": "block_comment",
                "source_line": node.start_point[0] + 1,
                "source_end_line": node.end_point[0] + 1,
            }
        elif node.type == "comment":
            text = self._get_text(node, content)
            if text.startswith("///"):
                # Swift doc comment (single line)
                cleaned = text[3:].strip()
                if not cleaned:
                    return None
                return {
                    "content": cleaned,
                    "content_type": "docstring",
                    "source_line": node.start_point[0] + 1,
                    "source_end_line": node.end_point[0] + 1,
                }
            elif text.startswith("//"):
                cleaned = text[2:].strip()
                if not cleaned:
                    return None
                return {
                    "content": cleaned,
                    "content_type": "single_line_comment",
                    "source_line": node.start_point[0] + 1,
                    "source_end_line": node.end_point[0] + 1,
                }
        return None
