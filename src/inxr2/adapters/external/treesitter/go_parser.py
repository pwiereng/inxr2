"""Go language parser using Tree-sitter."""

from typing import Any

from tree_sitter import Node

from .base import BaseLanguageParser
from .builtins import _load

# Go builtin functions and identifiers to exclude from references
GO_BUILTINS = _load("go.json", "builtins")

# Go primitive types to exclude from type references
GO_PRIMITIVE_TYPES = _load("go.json", "primitive_types")

# Go standard library prefixes to exclude from references
GO_STD_LIB_PREFIXES = _load("go.json", "standard_library_prefixes")


class GoParser(BaseLanguageParser):
    """Parser for Go source code using Tree-sitter."""

    @property
    def language_name(self) -> str:
        return "go"

    def extract(
        self,
        root: Node,
        content: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract symbols and references from Go AST."""
        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        def get_text(node: Node) -> str:
            return self._get_text(node, content)

        def add_reference(ref: dict[str, Any]) -> None:
            self._add_reference(ref, references)

        def is_builtin_or_primitive(name: str) -> bool:
            return name in GO_BUILTINS or name in GO_PRIMITIVE_TYPES

        def is_std_lib_prefix(name: str) -> bool:
            return name in GO_STD_LIB_PREFIXES

        def process_package_clause(node: Node) -> None:
            """Process a package clause."""
            for child in node.children:
                if child.type == "package_identifier":
                    pkg_name = get_text(child)
                    symbols.append(self._make_symbol(pkg_name, "package", child, None))
                    break

        def process_import_declaration(node: Node) -> None:
            """Process import declarations (single and grouped)."""
            for child in node.children:
                if child.type == "import_spec":
                    process_import_spec(child)
                elif child.type == "import_spec_list":
                    for spec_child in child.children:
                        if spec_child.type == "import_spec":
                            process_import_spec(spec_child)

        def process_import_spec(node: Node) -> None:
            """Process a single import spec."""
            import_path = None
            path_node = None

            for child in node.children:
                if child.type == "interpreted_string_literal":
                    import_path = get_text(child).strip('"')
                    path_node = child
                    break

            if import_path and path_node:
                add_reference(self._make_reference(import_path, "import", path_node))

        def process_function_declaration(node: Node) -> None:
            """Process a top-level function declaration."""
            func_name = None
            name_node = None

            for child in node.children:
                if child.type == "identifier":
                    func_name = get_text(child)
                    name_node = child
                    break

            if not func_name:
                return

            # Build signature
            params = extract_parameter_list(node)
            result_type = extract_result_type(node)
            signature = f"func {func_name}({params})"
            if result_type:
                signature += f" {result_type}"

            loc_node = name_node or node
            symbols.append(
                self._make_symbol(
                    func_name,
                    "function",
                    loc_node,
                    None,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    signature=signature,
                )
            )

        def process_method_declaration(node: Node) -> None:
            """Process a method declaration (has receiver)."""
            method_name = None
            name_node = None
            receiver_type = None

            for child in node.children:
                if child.type == "parameter_list":
                    # First parameter_list is the receiver
                    if receiver_type is None:
                        receiver_type = extract_receiver_type(child)
                elif child.type == "field_identifier":
                    method_name = get_text(child)
                    name_node = child

            if not method_name:
                return

            scope = receiver_type

            # Build signature
            params = extract_method_params(node)
            result_type = extract_result_type(node)
            receiver_str = f"({receiver_type})" if receiver_type else "()"
            signature = f"func {receiver_str} {method_name}({params})"
            if result_type:
                signature += f" {result_type}"

            loc_node = name_node or node
            symbols.append(
                self._make_symbol(
                    method_name,
                    "method",
                    loc_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    signature=signature,
                )
            )

        def extract_receiver_type(param_list: Node) -> str | None:
            """Extract the receiver type from a method's parameter list."""
            for child in param_list.children:
                if child.type == "parameter_declaration":
                    for param_child in child.children:
                        if param_child.type == "type_identifier":
                            return get_text(param_child)
                        elif param_child.type == "pointer_type":
                            for ptr_child in param_child.children:
                                if ptr_child.type == "type_identifier":
                                    return get_text(ptr_child)
            return None

        def extract_parameter_list(node: Node) -> str:
            """Extract the parameter list text from a function/method."""
            param_lists = [c for c in node.children if c.type == "parameter_list"]
            if param_lists:
                # For functions, first param list is params
                params_node = param_lists[0]
                inner = get_text(params_node)
                # Strip surrounding parens
                if inner.startswith("(") and inner.endswith(")"):
                    inner = inner[1:-1]
                return inner
            return ""

        def extract_method_params(node: Node) -> str:
            """Extract the parameter list for a method (skip receiver)."""
            param_lists = [c for c in node.children if c.type == "parameter_list"]
            if len(param_lists) >= 2:
                # Second param list is the actual params (first is receiver)
                params_node = param_lists[1]
                inner = get_text(params_node)
                if inner.startswith("(") and inner.endswith(")"):
                    inner = inner[1:-1]
                return inner
            return ""

        def extract_result_type(node: Node) -> str | None:
            """Extract the return type from a function/method."""
            for child in node.children:
                if child.type == "parameter_list":
                    continue
                if child.type in (
                    "type_identifier",
                    "qualified_type",
                    "pointer_type",
                    "slice_type",
                    "map_type",
                    "channel_type",
                    "interface_type",
                    "struct_type",
                    "function_type",
                ):
                    return get_text(child)
            # Check for multi-return: result is a parameter_list after the params
            # The last parameter_list might be the return types
            # We handle this by checking for a result node
            # tree-sitter-go uses "result" field
            result_node = node.child_by_field_name("result")
            if result_node:
                return get_text(result_node)
            return None

        def process_type_declaration(node: Node) -> None:
            """Process a type declaration (may contain multiple type_spec)."""
            for child in node.children:
                if child.type == "type_spec":
                    process_type_spec(child)
                elif child.type == "type_spec_list":
                    # Grouped type declarations: type ( ... )
                    for spec_child in child.children:
                        if spec_child.type == "type_spec":
                            process_type_spec(spec_child)

        def process_type_spec(node: Node) -> None:
            """Process a single type spec."""
            type_name = None
            name_node = None
            type_def_node = None

            for child in node.children:
                if child.type == "type_identifier":
                    type_name = get_text(child)
                    name_node = child
                elif child.type in (
                    "struct_type",
                    "interface_type",
                    "slice_type",
                    "map_type",
                    "channel_type",
                    "function_type",
                    "pointer_type",
                    "type_identifier",
                    "qualified_type",
                    "array_type",
                ):
                    type_def_node = child

            if not type_name:
                return

            if type_def_node is not None and type_def_node.type == "struct_type":
                process_struct_type(type_name, name_node or node, type_def_node, node)
            elif type_def_node is not None and type_def_node.type == "interface_type":
                process_interface_type(
                    type_name, name_node or node, type_def_node, node
                )
            else:
                # Type alias or other type definition
                loc_node = name_node or node
                symbols.append(
                    self._make_symbol(
                        type_name,
                        "type",
                        loc_node,
                        None,
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                    )
                )

        def process_struct_type(
            name: str,
            name_node: Node,
            struct_node: Node,
            decl_node: Node,
        ) -> None:
            """Process a struct type definition."""
            symbols.append(
                self._make_symbol(
                    name,
                    "struct",
                    name_node,
                    None,
                    end_line=decl_node.end_point[0] + 1,
                    end_column=decl_node.end_point[1],
                )
            )

            # Extract struct fields
            for child in struct_node.children:
                if child.type == "field_declaration_list":
                    for field_child in child.children:
                        if field_child.type == "field_declaration":
                            process_field_declaration(field_child, name)

        def process_field_declaration(node: Node, scope: str) -> None:
            """Process a struct field declaration."""
            field_names: list[tuple[str, Node]] = []

            for child in node.children:
                if child.type == "field_identifier":
                    field_names.append((get_text(child), child))

            if field_names:
                for field_name, field_node in field_names:
                    symbols.append(
                        self._make_symbol(field_name, "field", field_node, scope)
                    )
            else:
                # Embedded type (anonymous field) — e.g., `Bar` in `struct { Bar }`
                for child in node.children:
                    if child.type == "type_identifier":
                        embedded_name = get_text(child)
                        symbols.append(
                            self._make_symbol(embedded_name, "field", child, scope)
                        )
                        # Also add a type_usage reference
                        if not is_builtin_or_primitive(embedded_name):
                            add_reference(
                                self._make_reference(
                                    embedded_name,
                                    "type_annotation",
                                    child,
                                    scope,
                                )
                            )
                        break
                    elif child.type == "pointer_type":
                        for ptr_child in child.children:
                            if ptr_child.type == "type_identifier":
                                embedded_name = get_text(ptr_child)
                                symbols.append(
                                    self._make_symbol(
                                        embedded_name, "field", ptr_child, scope
                                    )
                                )
                                if not is_builtin_or_primitive(embedded_name):
                                    add_reference(
                                        self._make_reference(
                                            embedded_name,
                                            "type_annotation",
                                            ptr_child,
                                            scope,
                                        )
                                    )
                                break
                        break

        def process_interface_type(
            name: str,
            name_node: Node,
            interface_node: Node,
            decl_node: Node,
        ) -> None:
            """Process an interface type definition."""
            symbols.append(
                self._make_symbol(
                    name,
                    "interface",
                    name_node,
                    None,
                    end_line=decl_node.end_point[0] + 1,
                    end_column=decl_node.end_point[1],
                )
            )

            # Extract interface methods
            for child in interface_node.children:
                if child.type in ("method_spec", "method_elem"):
                    process_interface_method(child, name)
                elif child.type == "type_identifier":
                    # Embedded interface
                    embedded_name = get_text(child)
                    if not is_builtin_or_primitive(embedded_name):
                        add_reference(
                            self._make_reference(
                                embedded_name, "type_annotation", child, name
                            )
                        )
                elif child.type == "qualified_type":
                    qual_text = get_text(child)
                    add_reference(
                        self._make_reference(qual_text, "type_annotation", child, name)
                    )

        def process_interface_method(node: Node, scope: str) -> None:
            """Process an interface method specification."""
            method_name = None
            name_node = None

            for child in node.children:
                if child.type == "field_identifier":
                    method_name = get_text(child)
                    name_node = child
                    break

            if not method_name:
                return

            loc_node = name_node or node
            symbols.append(
                self._make_symbol(
                    method_name,
                    "property",
                    loc_node,
                    scope,
                )
            )

        def process_const_declaration(node: Node) -> None:
            """Process a const declaration (single or block)."""
            for child in node.children:
                if child.type == "const_spec":
                    process_const_spec(child)
                elif child.type == "const_spec_list":
                    # Grouped: const ( ... )
                    for spec_child in child.children:
                        if spec_child.type == "const_spec":
                            process_const_spec(spec_child)

        def process_const_spec(node: Node) -> None:
            """Process a single const spec."""
            for child in node.children:
                if child.type == "identifier":
                    const_name = get_text(child)
                    symbols.append(
                        self._make_symbol(const_name, "constant", child, None)
                    )

        def process_var_declaration(node: Node) -> None:
            """Process a var declaration (single or block)."""
            for child in node.children:
                if child.type == "var_spec":
                    process_var_spec(child)
                elif child.type == "var_spec_list":
                    # Grouped: var ( ... )
                    for spec_child in child.children:
                        if spec_child.type == "var_spec":
                            process_var_spec(spec_child)

        def process_var_spec(node: Node) -> None:
            """Process a single var spec."""
            for child in node.children:
                if child.type == "identifier":
                    var_name = get_text(child)
                    symbols.append(self._make_symbol(var_name, "variable", child, None))

        def extract_references(node: Node, scope: str | None = None) -> None:
            """Extract references from the AST recursively."""
            # Import declarations
            if node.type == "import_declaration":
                process_import_declaration(node)
                return

            # Function/method calls
            if node.type == "call_expression":
                process_call_reference(node, scope)

            # Selector expressions (pkg.Symbol)
            if node.type == "selector_expression":
                process_selector_reference(node, scope)

            # Type identifiers used as references
            if node.type == "type_identifier":
                parent = node.parent
                # Skip if already handled by parent nodes
                if parent and parent.type in (
                    "type_spec",
                    "qualified_type",
                    "method_spec",
                ):
                    pass
                else:
                    type_name = get_text(node)
                    if not is_builtin_or_primitive(type_name):
                        add_reference(
                            self._make_reference(
                                type_name, "type_annotation", node, scope
                            )
                        )

            # Recurse into children
            for child in node.children:
                child_scope = scope

                # Update scope based on context
                if node.type == "function_declaration":
                    for name_child in node.children:
                        if name_child.type == "identifier":
                            child_scope = get_text(name_child)
                            break
                elif node.type == "method_declaration":
                    for name_child in node.children:
                        if name_child.type == "field_identifier":
                            # Get receiver type for scope
                            recv = None
                            for rc in node.children:
                                if rc.type == "parameter_list":
                                    recv = extract_receiver_type(rc)
                                    break
                            method_name = get_text(name_child)
                            child_scope = (
                                f"{recv}.{method_name}" if recv else method_name
                            )
                            break
                elif node.type == "type_declaration":
                    for name_child in node.children:
                        if name_child.type == "type_spec":
                            for tc in name_child.children:
                                if tc.type == "type_identifier":
                                    child_scope = get_text(tc)
                                    break
                            break

                extract_references(child, child_scope)

        def process_call_reference(node: Node, scope: str | None) -> None:
            """Process a call expression to extract references."""
            func_node = node.child_by_field_name("function")
            if not func_node:
                return

            if func_node.type == "identifier":
                func_name = get_text(func_node)
                if not is_builtin_or_primitive(func_name):
                    add_reference(
                        self._make_reference(func_name, "call", func_node, scope)
                    )
            elif func_node.type == "selector_expression":
                # pkg.Func() or obj.Method() — handled by selector processing
                pass

        def process_selector_reference(node: Node, scope: str | None) -> None:
            """Process a selector expression (e.g., pkg.Symbol, obj.Method)."""
            parent = node.parent

            # Skip if parent is a call_expression — we'll let the call handler
            # decide, but we still want the selector parts
            operand_node = node.child_by_field_name("operand")
            field_node = node.child_by_field_name("field")

            if not operand_node or not field_node:
                return

            operand_text = get_text(operand_node) if operand_node else ""
            field_text = get_text(field_node) if field_node else ""

            # If the parent is a call_expression, this is a method/function call
            if parent and parent.type == "call_expression":
                if not is_builtin_or_primitive(field_text):
                    if operand_node.type == "identifier":
                        if is_std_lib_prefix(operand_text):
                            # Standard library call, e.g. fmt.Println
                            add_reference(
                                self._make_reference(
                                    f"{operand_text}.{field_text}",
                                    "call",
                                    field_node,
                                    scope,
                                )
                            )
                        elif not is_builtin_or_primitive(operand_text):
                            # Custom method call
                            add_reference(
                                self._make_reference(
                                    field_text, "call", field_node, scope
                                )
                            )
            else:
                # Field access or type reference
                if operand_node.type == "identifier" and not is_std_lib_prefix(
                    operand_text
                ):
                    if not is_builtin_or_primitive(field_text):
                        add_reference(
                            self._make_reference(field_text, "usage", field_node, scope)
                        )

        # --- Main processing ---

        # First pass: extract symbols
        for child in root.children:
            if child.type == "package_clause":
                process_package_clause(child)
            elif child.type == "import_declaration":
                process_import_declaration(child)
            elif child.type == "function_declaration":
                process_function_declaration(child)
            elif child.type == "method_declaration":
                process_method_declaration(child)
            elif child.type == "type_declaration":
                process_type_declaration(child)
            elif child.type == "const_declaration":
                process_const_declaration(child)
            elif child.type == "var_declaration":
                process_var_declaration(child)

        # Second pass: extract references
        extract_references(root)

        return symbols, references

    def _process_comment_node(self, node: Node, content: str) -> dict[str, Any] | None:
        """Classify and clean a Go comment node."""
        if node.type == "comment":
            text = self._get_text(node, content)
            if text.startswith("//"):
                cleaned = text[2:].strip()
                if not cleaned:
                    return None
                return {
                    "content": cleaned,
                    "content_type": "single_line_comment",
                    "source_line": node.start_point[0] + 1,
                    "source_end_line": node.end_point[0] + 1,
                }
            elif text.startswith("/*"):
                cleaned = self._strip_block_comment(text)
                if not cleaned:
                    return None
                return {
                    "content": cleaned,
                    "content_type": "block_comment",
                    "source_line": node.start_point[0] + 1,
                    "source_end_line": node.end_point[0] + 1,
                }

        return None
