"""Unified C/C++ language parser using Tree-sitter.

Handles both C and C++ via a language parameter, similar to how
TypeScriptParser handles both TypeScript and JavaScript.
Uses the C++ tree-sitter grammar for both languages.
"""

from typing import Any

from tree_sitter import Node

from .base import BaseLanguageParser
from .builtins import _load

# Merged C/C++ builtins (C stdlib + C++ keywords)
_BUILTINS = _load("c_cpp.json", "builtins")

# Merged primitive types
_PRIMITIVE_TYPES = _load("c_cpp.json", "primitive_types")

# C++ standard library prefixes (std::, boost::, etc.)
_STD_LIB_PREFIXES = _load("c_cpp.json", "standard_library_prefixes")


class CppParser(BaseLanguageParser):
    """Unified parser for C and C++ source code using Tree-sitter.

    Accepts a ``language`` parameter (``"c"`` or ``"cpp"``) to control
    which language-specific constructs are extracted.  The C++ tree-sitter
    grammar is used for both since it is a superset of C.
    """

    def __init__(self, language: str = "cpp") -> None:
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
        """Extract symbols and references from C/C++ AST."""
        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        def get_text(node: Node) -> str:
            return self._get_text(node, content)

        def add_reference(ref: dict[str, Any]) -> None:
            self._add_reference(ref, references)

        def is_builtin_or_primitive(name: str) -> bool:
            return name in _BUILTINS or name in _PRIMITIVE_TYPES

        def is_std_lib_prefix(name: str) -> bool:
            return name in _STD_LIB_PREFIXES

        def make_scope(parent_scope: str | None, name: str) -> str:
            if parent_scope:
                return f"{parent_scope}.{name}"
            return name

        # Track namespace names to distinguish namespace::func (function)
        # from Class::method (method) in out-of-class definitions.
        # Only relevant for C++ mode, but harmless for C.
        known_namespaces: set[str] = set()

        # ── Field kind helpers ──────────────────────────────────────

        def struct_field_kind() -> str:
            """Field kind for struct members."""
            return "struct_field" if self._language == "c" else "field"

        def union_field_kind() -> str:
            """Field kind for union members."""
            return "union_field" if self._language == "c" else "field"

        # ── Symbol extraction ───────────────────────────────────────

        def process_node(
            node: Node,
            scope: str | None = None,
            field_kind: str | None = None,
        ) -> None:
            """Process a node to extract symbols."""
            if node.type == "namespace_definition":
                process_namespace(node, scope)
            elif node.type == "class_specifier":
                process_class_or_struct(node, scope, "class")
            elif node.type == "struct_specifier":
                process_class_or_struct(node, scope, "struct")
            elif node.type == "union_specifier":
                process_union(node, scope)
            elif node.type == "function_definition":
                process_function_definition(node, scope)
            elif node.type == "declaration":
                process_declaration(node, scope)
            elif node.type == "field_declaration":
                process_field_declaration(node, scope, field_kind or "field")
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
            elif node.type == "preproc_include":
                process_preproc_include(node)
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
                    process_node(child, scope, field_kind)

        # ── Namespace (C++ only) ────────────────────────────────────

        def process_namespace(node: Node, scope: str | None) -> None:
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
                inner_scope = scope

            for child in node.children:
                if child.type == "declaration_list":
                    for decl_child in child.children:
                        process_node(decl_child, inner_scope)

        # ── Class / Struct ──────────────────────────────────────────

        def process_class_or_struct(node: Node, scope: str | None, kind: str) -> None:
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
            fk = struct_field_kind()

            for child in node.children:
                if child.type == "field_declaration_list":
                    for member in child.children:
                        process_node(member, inner_scope, field_kind=fk)
                elif child.type == "base_class_clause":
                    process_base_class_clause(child, inner_scope)

        def process_base_class_clause(node: Node, scope: str | None) -> None:
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

        # ── Union ───────────────────────────────────────────────────

        def process_union(node: Node, scope: str | None) -> None:
            union_name = None
            name_node = None
            for child in node.children:
                if child.type == "type_identifier":
                    union_name = get_text(child)
                    name_node = child
                    break

            if not union_name:
                return

            loc_node = name_node or node
            symbols.append(
                self._make_symbol(
                    union_name,
                    "union",
                    loc_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                )
            )

            inner_scope = make_scope(scope, union_name)
            fk = union_field_kind()
            for child in node.children:
                if child.type == "field_declaration_list":
                    for field_child in child.children:
                        if field_child.type == "field_declaration":
                            _extract_field_identifiers(field_child, inner_scope, fk)

        # ── Function / Method ───────────────────────────────────────

        def process_function_definition(node: Node, scope: str | None) -> None:
            declarator = node.child_by_field_name("declarator")
            if not declarator:
                return

            func_name, name_node = extract_function_name_and_node(declarator)
            if not func_name:
                return

            # Determine kind and scope
            if self._language == "cpp":
                in_class = parent_is_class_body(node)
                qual_scope = extract_qualified_scope(declarator)
                if in_class:
                    kind = "method"
                    method_scope = scope
                elif qual_scope:
                    full_qual = make_scope(scope, qual_scope) if scope else qual_scope
                    kind = "function" if full_qual in known_namespaces else "method"
                    method_scope = full_qual
                else:
                    kind = "function"
                    method_scope = scope
            else:
                kind = "function"
                method_scope = scope

            # Build signature
            return_type = _extract_return_type(node)
            params = extract_parameter_text(declarator)
            if return_type:
                signature = f"{return_type} {func_name}({params})"
            else:
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
            if declarator.type == "function_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    if inner.type in ("identifier", "field_identifier"):
                        return get_text(inner), inner
                    elif inner.type == "qualified_identifier":
                        name_child = inner.child_by_field_name("name")
                        if name_child:
                            return get_text(name_child), name_child
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
                        "parenthesized_declarator",
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
            elif declarator.type == "parenthesized_declarator":
                for child in declarator.children:
                    if child.type in (
                        "pointer_declarator",
                        "function_declarator",
                        "identifier",
                    ):
                        return extract_function_name_and_node(child)
            elif declarator.type in ("identifier", "field_identifier"):
                return get_text(declarator), declarator
            return None, None

        def _extract_return_type(node: Node) -> str | None:
            type_node = node.child_by_field_name("type")
            if type_node:
                return get_text(type_node)
            return None

        def extract_parameter_text(declarator: Node) -> str:
            if declarator.type == "function_declarator":
                params_node = declarator.child_by_field_name("parameters")
                if params_node:
                    text = get_text(params_node)
                    if text.startswith("(") and text.endswith(")"):
                        text = text[1:-1]
                    return text
            return ""

        # ── Field declarations ──────────────────────────────────────

        def process_field_declaration(
            node: Node, scope: str | None, field_kind: str
        ) -> None:
            if not scope:
                return

            # In C++ mode, function_declarator children are method
            # declarations (common in headers without bodies).
            if self._language == "cpp":
                has_method_declarator = False
                for child in node.children:
                    if child.type == "function_declarator":
                        has_method_declarator = True
                        method_name, name_node = extract_function_name_and_node(child)
                        if not method_name or not name_node:
                            continue
                        return_type = _extract_return_type(node)
                        params = extract_parameter_text(child)
                        signature = (
                            f"{return_type} {method_name}({params})"
                            if return_type
                            else f"{method_name}({params})"
                        )
                        symbols.append(
                            self._make_symbol(
                                method_name,
                                "method",
                                name_node,
                                scope,
                                signature=signature,
                                is_declaration=True,
                            )
                        )
                if has_method_declarator:
                    return

            _extract_field_identifiers(node, scope, field_kind)

        def _extract_field_identifiers(
            node: Node, scope: str | None, field_kind: str
        ) -> None:
            for child in node.children:
                if child.type == "field_identifier":
                    field_name = get_text(child)
                    symbols.append(
                        self._make_symbol(field_name, field_kind, child, scope)
                    )
                elif child.type in (
                    "init_declarator",
                    "pointer_declarator",
                    "array_declarator",
                    "reference_declarator",
                    "function_declarator",
                    "parenthesized_declarator",
                ):
                    _extract_field_identifiers(child, scope, field_kind)

        # ── Enum ────────────────────────────────────────────────────

        def process_enum_specifier(node: Node, scope: str | None) -> None:
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

        # ── Type definitions ────────────────────────────────────────

        def process_type_definition(node: Node, scope: str | None) -> None:
            typedef_name = None
            typedef_name_node: Node | None = None
            for child in node.children:
                if child.type == "type_identifier":
                    typedef_name = get_text(child)
                    typedef_name_node = child
                elif child.type in (
                    "pointer_declarator",
                    "function_declarator",
                    "array_declarator",
                ):
                    name, name_nd = _extract_typedef_name(child)
                    if name:
                        typedef_name = name
                        typedef_name_node = name_nd
                elif child.type == "struct_specifier":
                    process_class_or_struct(child, scope, "struct")
                elif child.type == "class_specifier":
                    process_class_or_struct(child, scope, "class")
                elif child.type == "enum_specifier":
                    process_enum_specifier(child, scope)
                elif child.type == "union_specifier":
                    process_union(child, scope)

            if typedef_name:
                loc_node = typedef_name_node or node
                symbols.append(
                    self._make_symbol(
                        typedef_name,
                        "typedef",
                        loc_node,
                        scope,
                        end_line=node.end_point[0] + 1,
                        end_column=node.end_point[1],
                    )
                )

        def _extract_typedef_name(
            declarator: Node,
        ) -> tuple[str | None, Node | None]:
            if declarator.type in ("identifier", "type_identifier"):
                return get_text(declarator), declarator
            elif declarator.type == "pointer_declarator":
                for child in declarator.children:
                    if child.type == "type_identifier":
                        return get_text(child), child
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    return _extract_typedef_name(inner)
            elif declarator.type in (
                "function_declarator",
                "array_declarator",
            ):
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
            return None, None

        # ── Alias declaration (C++ using) ───────────────────────────

        def process_alias_declaration(node: Node, scope: str | None) -> None:
            for child in node.children:
                if child.type == "type_identifier":
                    alias_name = get_text(child)
                    symbols.append(self._make_symbol(alias_name, "type", child, scope))
                    break

        # ── Template declaration (C++ only) ─────────────────────────

        def process_template_declaration(node: Node, scope: str | None) -> None:
            for child in node.children:
                if child.type in (
                    "function_definition",
                    "class_specifier",
                    "struct_specifier",
                    "union_specifier",
                    "declaration",
                    "alias_declaration",
                    "template_declaration",
                ):
                    process_node(child, scope)

        # ── Declarations (variables, prototypes, etc.) ──────────────

        def process_declaration(node: Node, scope: str | None) -> None:
            # Check for const/constexpr
            is_constexpr = False
            for child in node.children:
                child_text = (
                    get_text(child)
                    if child.type in ("storage_class_specifier", "type_qualifier")
                    else ""
                )
                if child_text in ("constexpr", "const"):
                    is_constexpr = True

            # Check for type specifiers that define new types
            type_node = node.child_by_field_name("type")
            if type_node:
                if type_node.type == "struct_specifier":
                    process_class_or_struct(type_node, scope, "struct")
                elif type_node.type == "class_specifier":
                    process_class_or_struct(type_node, scope, "class")
                elif type_node.type == "enum_specifier":
                    process_enum_specifier(type_node, scope)
                elif type_node.type == "union_specifier":
                    process_union(type_node, scope)

            # Process declarators
            for child in node.children:
                if child.type == "init_declarator":
                    declarator = child.child_by_field_name("declarator")
                    if declarator:
                        _process_var_declarator(
                            declarator, scope, is_constexpr, type_node
                        )
                elif child.type == "identifier":
                    var_name = get_text(child)
                    kind = "constant" if is_constexpr else "variable"
                    symbols.append(self._make_symbol(var_name, kind, child, scope))
                elif child.type == "function_declarator":
                    _process_func_prototype(child, scope, type_node)
                elif child.type in (
                    "pointer_declarator",
                    "array_declarator",
                ):
                    _process_var_declarator(child, scope, is_constexpr, type_node)

        def _process_func_prototype(
            declarator: Node,
            scope: str | None,
            type_node: Node | None,
        ) -> None:
            func_name, name_node_inner = extract_function_name_and_node(declarator)
            if func_name:
                return_type = get_text(type_node) if type_node else "void"
                params = extract_parameter_text(declarator)
                signature = f"{return_type} {func_name}({params})"
                symbols.append(
                    self._make_symbol(
                        func_name,
                        "function",
                        name_node_inner or declarator,
                        scope,
                        signature=signature,
                        is_declaration=True,
                    )
                )

        def _process_var_declarator(
            declarator: Node,
            scope: str | None,
            is_constexpr: bool,
            type_node: Node | None = None,
        ) -> None:
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
                    if inner.type == "function_declarator":
                        _process_func_prototype(inner, scope, type_node)
                    else:
                        _process_var_declarator(inner, scope, is_constexpr, type_node)
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
                    _process_var_declarator(inner, scope, is_constexpr, type_node)
            elif declarator.type == "function_declarator":
                _process_func_prototype(declarator, scope, type_node)

        # ── Preprocessor ────────────────────────────────────────────

        def process_preproc_def(node: Node, scope: str | None) -> None:
            for child in node.children:
                if child.type == "identifier":
                    macro_name = get_text(child)
                    symbols.append(
                        self._make_symbol(macro_name, "constant", node, scope)
                    )
                    break

        def process_preproc_function_def(node: Node, scope: str | None) -> None:
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

        def process_preproc_include(node: Node) -> None:
            path_node = node.child_by_field_name("path")
            if path_node:
                include_path = get_text(path_node).strip('"<>')
                add_reference(self._make_reference(include_path, "include", node))

        # ── Reference extraction ────────────────────────────────────

        def extract_references(node: Node, scope: str | None = None) -> None:
            # #include
            if node.type == "preproc_include":
                process_include_reference(node)
                return

            # #ifdef / #ifndef — the condition identifier is a macro reference
            if node.type == "preproc_ifdef":
                for child in node.children:
                    if child.type == "identifier":
                        macro_name = get_text(child)
                        if not is_builtin_or_primitive(macro_name):
                            add_reference(
                                self._make_reference(macro_name, "usage", child, scope)
                            )
                        break

            # Function calls
            if node.type == "call_expression":
                process_call_reference(node, scope)

            # Type identifiers
            if node.type == "type_identifier":
                parent = node.parent
                # Skip names that are being defined (not used as references)
                is_definition = False
                if parent and parent.type in ("type_definition", "alias_declaration"):
                    is_definition = True
                elif parent and parent.type in (
                    "class_specifier",
                    "struct_specifier",
                    "union_specifier",
                    "enum_specifier",
                ):
                    # Only a definition if the specifier has a body
                    is_definition = any(
                        c.type in ("field_declaration_list", "enumerator_list")
                        for c in parent.children
                    )

                if not is_definition:
                    type_name = get_text(node)
                    if not is_builtin_or_primitive(type_name):
                        add_reference(
                            self._make_reference(
                                type_name, "type_annotation", node, scope
                            )
                        )

            # Qualified identifiers (C++ namespace::name)
            if node.type == "qualified_identifier":
                parent = node.parent
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

            # using declarations (C++)
            if node.type == "using_declaration":
                process_using_reference(node, scope)

            # Field expressions (struct member access: obj.field, ptr->field)
            if node.type == "field_expression":
                _process_field_expression_refs(node, scope)

            # sizeof expressions
            if node.type == "sizeof_expression":
                _process_sizeof_refs(node, scope)

            # Macro type specifier (e.g., CJSON_PUBLIC(char *) in return types)
            if node.type == "macro_type_specifier":
                for child in node.children:
                    if child.type == "identifier":
                        macro_name = get_text(child)
                        add_reference(
                            self._make_reference(macro_name, "usage", child, scope)
                        )
                        break

            # Identifiers in initializer lists
            if node.type == "initializer_list":
                _process_initializer_list_refs(node, scope)

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
            path_node = node.child_by_field_name("path")
            if path_node:
                include_path = get_text(path_node).strip('"<>')
                add_reference(self._make_reference(include_path, "include", node))

        def process_call_reference(node: Node, scope: str | None) -> None:
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
                    return
                terminal_name = parts[-1] if parts else qual_text
                if not is_builtin_or_primitive(terminal_name):
                    add_reference(
                        self._make_reference(terminal_name, "call", func_node, scope)
                    )
            elif func_node.type == "field_expression":
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
            for child in node.children:
                if child.type == "qualified_identifier":
                    qual_text = get_text(child)
                    add_reference(
                        self._make_reference(qual_text, "import", child, scope)
                    )

        def _process_field_expression_refs(node: Node, scope: str | None) -> None:
            """Extract references from field expressions (obj.field, ptr->field)."""
            # Base object reference
            argument = node.child_by_field_name("argument")
            if argument and argument.type == "identifier":
                var_name = get_text(argument)
                if not is_builtin_or_primitive(var_name):
                    add_reference(
                        self._make_reference(var_name, "usage", argument, scope)
                    )

            # Field reference, but skip if this is the function in a
            # call_expression (already recorded as a "call" reference)
            parent = node.parent
            is_method_call = (
                parent is not None
                and parent.type == "call_expression"
                and parent.child_by_field_name("function") == node
            )
            if not is_method_call:
                field = node.child_by_field_name("field")
                if field and field.type == "field_identifier":
                    field_name = get_text(field)
                    add_reference(
                        self._make_reference(field_name, "usage", field, scope)
                    )

        def _process_sizeof_refs(node: Node, scope: str | None) -> None:
            """Extract references from sizeof expressions."""
            for child in node.children:
                if child.type == "parenthesized_expression":
                    for inner in child.children:
                        if inner.type == "identifier":
                            name = get_text(inner)
                            if not is_builtin_or_primitive(name):
                                add_reference(
                                    self._make_reference(name, "usage", inner, scope)
                                )

        def _process_initializer_list_refs(node: Node, scope: str | None) -> None:
            """Extract references from initializer lists."""
            for child in node.children:
                if child.type == "identifier":
                    ident_name = get_text(child)
                    if not is_builtin_or_primitive(ident_name) and ident_name not in (
                        "NULL",
                    ):
                        add_reference(
                            self._make_reference(ident_name, "usage", child, scope)
                        )

        # ── Main processing ─────────────────────────────────────────

        # First pass: extract symbols
        for child in root.children:
            process_node(child)

        # Second pass: extract references
        extract_references(root)

        return symbols, references

    def _process_comment_node(self, node: Node, content: str) -> dict[str, Any] | None:
        """Classify and clean a C/C++ comment node."""
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
            "content_type": ("block_comment" if is_block else "single_line_comment"),
            "source_line": node.start_point[0] + 1,
            "source_end_line": node.end_point[0] + 1,
        }
