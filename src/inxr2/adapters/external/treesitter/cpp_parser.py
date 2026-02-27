"""C++ language parser using Tree-sitter."""

from typing import Any

from tree_sitter import Node

from .base import BaseLanguageParser
from .builtins import _load

# C++ builtin functions and keywords to exclude from references
CPP_BUILTINS = _load("cpp.json", "builtins")

# C++ primitive types to exclude from type references
CPP_PRIMITIVE_TYPES = _load("cpp.json", "primitive_types")

# C++ standard library prefixes to exclude from references
CPP_STD_LIB_PREFIXES = _load("cpp.json", "standard_library_prefixes")


class CppParser(BaseLanguageParser):
    """Parser for C++ source code using Tree-sitter."""

    @property
    def language_name(self) -> str:
        return "cpp"

    def extract(
        self,
        root: Node,
        content: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract symbols and references from C++ AST."""
        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        def get_text(node: Node) -> str:
            return self._get_text(node, content)

        def add_reference(ref: dict[str, Any]) -> None:
            self._add_reference(ref, references)

        def is_builtin_or_primitive(name: str) -> bool:
            return name in CPP_BUILTINS or name in CPP_PRIMITIVE_TYPES

        def is_std_lib_prefix(name: str) -> bool:
            return name in CPP_STD_LIB_PREFIXES

        def make_scope(parent_scope: str | None, name: str) -> str:
            if parent_scope:
                return f"{parent_scope}.{name}"
            return name

        # Track namespace names to distinguish namespace::func (function)
        # from Class::method (method) in out-of-class definitions.
        known_namespaces: set[str] = set()

        # --- Symbol extraction ---

        def process_node(node: Node, scope: str | None = None) -> None:
            """Process a node to extract symbols."""
            if node.type == "namespace_definition":
                process_namespace(node, scope)
            elif node.type == "class_specifier":
                process_class_or_struct(node, scope, "class")
            elif node.type == "struct_specifier":
                process_class_or_struct(node, scope, "struct")
            elif node.type == "function_definition":
                process_function_definition(node, scope)
            elif node.type == "declaration":
                process_declaration(node, scope)
            elif node.type == "field_declaration":
                process_field_declaration(node, scope)
            elif node.type == "enum_specifier":
                process_enum_specifier(node, scope)
            elif node.type == "type_definition":
                process_type_definition(node, scope)
            elif node.type == "alias_declaration":
                process_alias_declaration(node, scope)
            elif node.type == "template_declaration":
                process_template_declaration(node, scope)
            elif node.type == "preproc_def":
                process_preproc_def(node, scope)
            elif node.type == "preproc_function_def":
                process_preproc_function_def(node, scope)
            elif node.type in (
                "preproc_ifdef",
                "preproc_ifndef",
                "preproc_if",
                "preproc_elif",
                "preproc_else",
                "linkage_specification",
                "declaration_list",
            ):
                for child in node.children:
                    process_node(child, scope)

        def process_namespace(node: Node, scope: str | None) -> None:
            """Process a namespace definition."""
            ns_name = None
            name_node = None

            for child in node.children:
                if child.type in ("identifier", "namespace_identifier"):
                    ns_name = get_text(child)
                    name_node = child
                    break

            inner_scope: str | None
            if ns_name:
                loc_node = name_node or node
                symbols.append(
                    self._make_symbol(
                        ns_name,
                        "namespace",
                        loc_node,
                        scope,
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                    )
                )
                inner_scope = make_scope(scope, ns_name)
                known_namespaces.add(inner_scope)
            else:
                # Anonymous namespace
                inner_scope = scope

            # Process namespace body
            for child in node.children:
                if child.type == "declaration_list":
                    for decl_child in child.children:
                        process_node(decl_child, inner_scope)

        def process_class_or_struct(node: Node, scope: str | None, kind: str) -> None:
            """Process a class or struct specifier."""
            type_name = None
            name_node = None

            for child in node.children:
                if child.type == "type_identifier":
                    type_name = get_text(child)
                    name_node = child
                    break

            if not type_name:
                return

            loc_node = name_node or node
            symbols.append(
                self._make_symbol(
                    type_name,
                    kind,
                    loc_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                )
            )

            inner_scope = make_scope(scope, type_name)

            # Process class/struct body
            for child in node.children:
                if child.type == "field_declaration_list":
                    for member in child.children:
                        process_node(member, inner_scope)
                elif child.type == "base_class_clause":
                    process_base_class_clause(child, inner_scope)

        def process_base_class_clause(node: Node, scope: str | None) -> None:
            """Process base class clause for inheritance references."""
            for child in node.children:
                if child.type == "type_identifier":
                    base_name = get_text(child)
                    if not is_builtin_or_primitive(base_name):
                        add_reference(
                            self._make_reference(
                                base_name, "type_annotation", child, scope
                            )
                        )
                elif child.type == "qualified_identifier":
                    qual_name = get_text(child)
                    add_reference(
                        self._make_reference(qual_name, "type_annotation", child, scope)
                    )

        def process_function_definition(node: Node, scope: str | None) -> None:
            """Process a function definition (function or method)."""
            declarator = node.child_by_field_name("declarator")
            if not declarator:
                return

            func_name, name_node = extract_function_name_and_node(declarator)
            if not func_name:
                return

            # Determine if this is a method
            in_class = parent_is_class_body(node)
            qual_scope = extract_qualified_scope(declarator)

            if in_class:
                kind = "method"
                method_scope = scope
            elif qual_scope:
                full_qual = make_scope(scope, qual_scope) if scope else qual_scope
                # Namespace-qualified → free function, class-qualified → method
                kind = "function" if full_qual in known_namespaces else "method"
                method_scope = full_qual
            else:
                kind = "function"
                method_scope = scope

            # Build signature
            return_type = extract_return_type(node)
            params = extract_parameter_text(declarator)
            if return_type:
                signature = f"{return_type} {func_name}({params})"
            else:
                # Constructor/destructor (no return type)
                signature = f"{func_name}({params})"

            loc_node = name_node or node
            symbols.append(
                self._make_symbol(
                    func_name,
                    kind,
                    loc_node,
                    method_scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    signature=signature,
                )
            )

        def parent_is_class_body(node: Node) -> bool:
            """Check if a node is directly inside a class/struct body."""
            parent = node.parent
            while parent:
                if parent.type == "field_declaration_list":
                    grandparent = parent.parent
                    return grandparent is not None and grandparent.type in (
                        "class_specifier",
                        "struct_specifier",
                    )
                if parent.type == "template_declaration":
                    parent = parent.parent
                    continue
                break
            return False

        def extract_qualified_scope(declarator: Node) -> str | None:
            """Extract class/namespace scope from qualified identifier."""
            if declarator.type == "function_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner and inner.type == "qualified_identifier":
                    full_text = get_text(inner)
                    last_sep = full_text.rfind("::")
                    if last_sep >= 0:
                        scope_text = full_text[:last_sep]
                        if scope_text:
                            return scope_text.replace("::", ".")
            return None

        def extract_function_name_and_node(
            declarator: Node,
        ) -> tuple[str | None, Node | None]:
            """Extract function name and identifier node from a declarator."""
            if declarator.type == "function_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    if inner.type in ("identifier", "field_identifier"):
                        return get_text(inner), inner
                    elif inner.type == "qualified_identifier":
                        # Out-of-class: ClassName::method
                        name_child = inner.child_by_field_name("name")
                        if name_child:
                            return get_text(name_child), name_child
                        # Fallback: last child that's an identifier
                        for child in reversed(inner.children):
                            if child.type == "identifier":
                                return get_text(child), child
                    elif inner.type == "destructor_name":
                        return get_text(inner), inner
                    elif inner.type == "operator_name":
                        return get_text(inner), inner
                    elif inner.type in (
                        "pointer_declarator",
                        "reference_declarator",
                    ):
                        return extract_function_name_and_node(inner)
            elif declarator.type in (
                "pointer_declarator",
                "reference_declarator",
            ):
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    return extract_function_name_and_node(inner)
                for child in declarator.children:
                    if child.type in (
                        "function_declarator",
                        "identifier",
                        "field_identifier",
                    ):
                        return extract_function_name_and_node(child)
            elif declarator.type in ("identifier", "field_identifier"):
                return get_text(declarator), declarator
            return None, None

        def extract_return_type(node: Node) -> str | None:
            """Extract return type from a function definition."""
            type_node = node.child_by_field_name("type")
            if type_node:
                return get_text(type_node)
            return None

        def extract_parameter_text(declarator: Node) -> str:
            """Extract parameter list text from function declarator."""
            if declarator.type == "function_declarator":
                params_node = declarator.child_by_field_name("parameters")
                if params_node:
                    text = get_text(params_node)
                    if text.startswith("(") and text.endswith(")"):
                        text = text[1:-1]
                    return text
            return ""

        def process_field_declaration(node: Node, scope: str | None) -> None:
            """Process a field declaration in a class/struct."""
            if not scope:
                return

            # Skip method declarations (has function_declarator as direct child)
            for child in node.children:
                if child.type == "function_declarator":
                    return

            # Extract field names recursively from declarators
            _extract_field_identifiers(node, scope)

        def _extract_field_identifiers(node: Node, scope: str | None) -> None:
            """Recursively find field_identifier nodes in declarators."""
            for child in node.children:
                if child.type == "field_identifier":
                    field_name = get_text(child)
                    symbols.append(self._make_symbol(field_name, "field", child, scope))
                elif child.type in (
                    "init_declarator",
                    "pointer_declarator",
                    "array_declarator",
                    "reference_declarator",
                ):
                    _extract_field_identifiers(child, scope)

        def process_enum_specifier(node: Node, scope: str | None) -> None:
            """Process an enum specifier."""
            enum_name = None
            name_node = None

            for child in node.children:
                if child.type == "type_identifier":
                    enum_name = get_text(child)
                    name_node = child
                    break

            if enum_name:
                loc_node = name_node or node
                symbols.append(
                    self._make_symbol(
                        enum_name,
                        "enum",
                        loc_node,
                        scope,
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                    )
                )

            # Process enum values
            enum_scope = make_scope(scope, enum_name) if enum_name else scope
            for child in node.children:
                if child.type == "enumerator_list":
                    for enum_child in child.children:
                        if enum_child.type == "enumerator":
                            for name_child in enum_child.children:
                                if name_child.type == "identifier":
                                    value_name = get_text(name_child)
                                    qn = (
                                        f"{enum_scope}.{value_name}"
                                        if enum_scope
                                        else value_name
                                    )
                                    symbols.append(
                                        self._make_symbol(
                                            value_name,
                                            "enum_value",
                                            enum_child,
                                            enum_scope,
                                            qualified_name=qn,
                                        )
                                    )
                                    break

        def process_type_definition(node: Node, scope: str | None) -> None:
            """Process a typedef declaration."""
            typedef_name = None

            for child in node.children:
                if child.type == "type_identifier":
                    typedef_name = get_text(child)
                elif child.type in (
                    "pointer_declarator",
                    "function_declarator",
                    "array_declarator",
                ):
                    name = _extract_typedef_name(child)
                    if name:
                        typedef_name = name
                elif child.type == "struct_specifier":
                    process_class_or_struct(child, scope, "struct")
                elif child.type == "class_specifier":
                    process_class_or_struct(child, scope, "class")
                elif child.type == "enum_specifier":
                    process_enum_specifier(child, scope)

            if typedef_name:
                symbols.append(self._make_symbol(typedef_name, "typedef", node, scope))

        def _extract_typedef_name(declarator: Node) -> str | None:
            """Extract the name from a typedef declarator."""
            if declarator.type in ("identifier", "type_identifier"):
                return get_text(declarator)
            elif declarator.type == "pointer_declarator":
                for child in declarator.children:
                    if child.type == "type_identifier":
                        return get_text(child)
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    return _extract_typedef_name(inner)
            elif declarator.type in ("function_declarator", "array_declarator"):
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    return _extract_typedef_name(inner)
            elif declarator.type == "parenthesized_declarator":
                for child in declarator.children:
                    if child.type in (
                        "pointer_declarator",
                        "function_declarator",
                        "type_identifier",
                    ):
                        return _extract_typedef_name(child)
            return None

        def process_alias_declaration(node: Node, scope: str | None) -> None:
            """Process a using alias (e.g., using Vec = std::vector<int>)."""
            for child in node.children:
                if child.type == "type_identifier":
                    alias_name = get_text(child)
                    symbols.append(self._make_symbol(alias_name, "type", child, scope))
                    break

        def process_template_declaration(node: Node, scope: str | None) -> None:
            """Process a template declaration by extracting the inner declaration."""
            for child in node.children:
                if child.type in (
                    "function_definition",
                    "class_specifier",
                    "struct_specifier",
                    "declaration",
                    "alias_declaration",
                    "template_declaration",
                ):
                    process_node(child, scope)

        def process_declaration(node: Node, scope: str | None) -> None:
            """Process a declaration (variables, constants, function prototypes)."""
            # Check for const/constexpr
            is_constexpr = False
            for child in node.children:
                child_text = (
                    get_text(child)
                    if child.type
                    in (
                        "storage_class_specifier",
                        "type_qualifier",
                    )
                    else ""
                )
                if child_text in ("constexpr", "const"):
                    is_constexpr = True

            # Check for struct/class/enum specifier in type
            type_node = node.child_by_field_name("type")
            if type_node:
                if type_node.type == "struct_specifier":
                    process_class_or_struct(type_node, scope, "struct")
                elif type_node.type == "class_specifier":
                    process_class_or_struct(type_node, scope, "class")
                elif type_node.type == "enum_specifier":
                    process_enum_specifier(type_node, scope)

            # Process declarators
            for child in node.children:
                if child.type == "init_declarator":
                    declarator = child.child_by_field_name("declarator")
                    if declarator:
                        _process_var_declarator(declarator, scope, is_constexpr)
                elif child.type == "identifier":
                    var_name = get_text(child)
                    kind = "constant" if is_constexpr else "variable"
                    symbols.append(self._make_symbol(var_name, kind, child, scope))
                elif child.type == "function_declarator":
                    # Function prototype
                    func_name, name_node_inner = extract_function_name_and_node(child)
                    if func_name:
                        return_type = get_text(type_node) if type_node else "void"
                        params = extract_parameter_text(child)
                        signature = f"{return_type} {func_name}({params})"
                        symbols.append(
                            self._make_symbol(
                                func_name,
                                "function",
                                name_node_inner or child,
                                scope,
                                signature=signature,
                                is_declaration=True,
                            )
                        )

        def _process_var_declarator(
            declarator: Node, scope: str | None, is_constexpr: bool
        ) -> None:
            """Process a variable declarator."""
            if declarator.type == "identifier":
                var_name = get_text(declarator)
                kind = "constant" if is_constexpr else "variable"
                symbols.append(self._make_symbol(var_name, kind, declarator, scope))
            elif declarator.type in (
                "pointer_declarator",
                "reference_declarator",
            ):
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    _process_var_declarator(inner, scope, is_constexpr)
                else:
                    for child in declarator.children:
                        if child.type == "identifier":
                            var_name = get_text(child)
                            kind = "constant" if is_constexpr else "variable"
                            symbols.append(
                                self._make_symbol(var_name, kind, child, scope)
                            )
                            break
            elif declarator.type == "array_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    _process_var_declarator(inner, scope, is_constexpr)
            elif declarator.type == "function_declarator":
                # Function declaration, not a variable
                pass

        def process_preproc_def(node: Node, scope: str | None) -> None:
            """Process a #define macro as a constant."""
            for child in node.children:
                if child.type == "identifier":
                    macro_name = get_text(child)
                    symbols.append(
                        self._make_symbol(macro_name, "constant", node, scope)
                    )
                    break

        def process_preproc_function_def(node: Node, scope: str | None) -> None:
            """Process a function-like #define macro."""
            macro_name = None
            params: list[str] = []

            for child in node.children:
                if child.type == "identifier" and macro_name is None:
                    macro_name = get_text(child)
                elif child.type == "preproc_params":
                    for param_child in child.children:
                        if param_child.type == "identifier":
                            params.append(get_text(param_child))

            if macro_name:
                signature = f"{macro_name}({', '.join(params)})"
                symbols.append(
                    self._make_symbol(
                        macro_name,
                        "constant",
                        node,
                        scope,
                        signature=signature,
                    )
                )

        # --- Reference extraction ---

        def extract_references(node: Node, scope: str | None = None) -> None:
            """Extract references from the AST recursively."""
            # #include directives
            if node.type == "preproc_include":
                process_include_reference(node)
                return

            # Function calls
            if node.type == "call_expression":
                process_call_reference(node, scope)

            # Type identifiers
            if node.type == "type_identifier":
                parent = node.parent
                # Skip the type's own name in definitions
                if parent and parent.type in (
                    "class_specifier",
                    "struct_specifier",
                    "enum_specifier",
                    "type_definition",
                    "alias_declaration",
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

            # Qualified identifiers (namespace::name)
            if node.type == "qualified_identifier":
                parent = node.parent
                # Skip if parent is a function_declarator (handled by function)
                if parent and parent.type == "function_declarator":
                    pass
                else:
                    qual_text = get_text(node)
                    parts = qual_text.split("::")
                    if parts and not is_std_lib_prefix(parts[0]):
                        if not is_builtin_or_primitive(qual_text):
                            add_reference(
                                self._make_reference(qual_text, "usage", node, scope)
                            )

            # using declarations
            if node.type == "using_declaration":
                process_using_reference(node, scope)

            # Recurse into children
            for child in node.children:
                child_scope = scope

                if node.type == "namespace_definition":
                    for nc in node.children:
                        if nc.type in ("identifier", "namespace_identifier"):
                            child_scope = make_scope(scope, get_text(nc))
                            break
                elif node.type in ("class_specifier", "struct_specifier"):
                    for nc in node.children:
                        if nc.type == "type_identifier":
                            child_scope = make_scope(scope, get_text(nc))
                            break
                elif node.type == "function_definition":
                    declarator = node.child_by_field_name("declarator")
                    if declarator:
                        func_name, _ = extract_function_name_and_node(declarator)
                        if func_name:
                            child_scope = (
                                make_scope(scope, func_name) if scope else func_name
                            )

                extract_references(child, child_scope)

        def process_include_reference(node: Node) -> None:
            """Process a #include directive."""
            path_node = node.child_by_field_name("path")
            if path_node:
                include_path = get_text(path_node)
                include_path = include_path.strip('"<>')
                add_reference(self._make_reference(include_path, "include", node))

        def process_call_reference(node: Node, scope: str | None) -> None:
            """Process a call expression."""
            func_node = node.child_by_field_name("function")
            if not func_node:
                return

            if func_node.type == "identifier":
                func_name = get_text(func_node)
                if not is_builtin_or_primitive(func_name):
                    add_reference(
                        self._make_reference(func_name, "call", func_node, scope)
                    )
            elif func_node.type == "qualified_identifier":
                qual_text = get_text(func_node)
                parts = qual_text.split("::")
                if parts and is_std_lib_prefix(parts[0]):
                    # Standard library call — exclude from references
                    return
                add_reference(self._make_reference(qual_text, "call", func_node, scope))
            elif func_node.type == "field_expression":
                # obj.method() or obj->method()
                field = func_node.child_by_field_name("field")
                if field:
                    field_name = get_text(field)
                    if not is_builtin_or_primitive(field_name):
                        add_reference(
                            self._make_reference(field_name, "call", field, scope)
                        )
            elif func_node.type == "template_function":
                name_child = func_node.child_by_field_name("name")
                if name_child:
                    func_name = get_text(name_child)
                    if not is_builtin_or_primitive(func_name):
                        add_reference(
                            self._make_reference(func_name, "call", name_child, scope)
                        )

        def process_using_reference(node: Node, scope: str | None) -> None:
            """Process a using declaration (e.g., using std::vector)."""
            for child in node.children:
                if child.type == "qualified_identifier":
                    qual_text = get_text(child)
                    add_reference(
                        self._make_reference(qual_text, "import", child, scope)
                    )

        # --- Main processing ---

        # First pass: extract symbols
        for child in root.children:
            process_node(child)

        # Second pass: extract references
        extract_references(root)

        return symbols, references

    def _process_comment_node(self, node: Node, content: str) -> dict[str, Any] | None:
        """Classify and clean a C++ comment node."""
        if node.type != "comment":
            return None

        text = self._get_text(node, content)
        is_block = text.startswith("/*")

        if is_block:
            cleaned = self._strip_block_comment(text)
        else:
            cleaned = text[2:].strip() if text.startswith("//") else text.strip()

        if not cleaned:
            return None

        return {
            "content": cleaned,
            "content_type": "block_comment" if is_block else "single_line_comment",
            "source_line": node.start_point[0] + 1,
            "source_end_line": node.end_point[0] + 1,
        }
