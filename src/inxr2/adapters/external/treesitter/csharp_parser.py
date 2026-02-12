"""C# language parser using Tree-sitter."""

from typing import Any

from tree_sitter import Node

from .base import BaseLanguageParser

# C# builtin types and common System namespace types to exclude from references
CSHARP_BUILTINS = {
    # System namespace (auto-imported via global using)
    "Console",
    "Math",
    "Environment",
    "Convert",
    "Activator",
    "GC",
    "Type",
    "Attribute",
    "Exception",
    "SystemException",
    "ArgumentException",
    "ArgumentNullException",
    "InvalidOperationException",
    "NotSupportedException",
    "NotImplementedException",
    "NullReferenceException",
    "IndexOutOfRangeException",
    "OverflowException",
    "FormatException",
    "StackOverflowException",
    "OutOfMemoryException",
    "ObjectDisposedException",
    "AggregateException",
    # Collections
    "List",
    "Dictionary",
    "HashSet",
    "Queue",
    "Stack",
    "SortedSet",
    "SortedDictionary",
    "SortedList",
    "LinkedList",
    "IEnumerable",
    "IEnumerator",
    "ICollection",
    "IList",
    "IDictionary",
    "ISet",
    "IReadOnlyList",
    "IReadOnlyCollection",
    "IReadOnlyDictionary",
    # Async/Task
    "Task",
    "ValueTask",
    "CancellationToken",
    "CancellationTokenSource",
    # Common interfaces
    "IDisposable",
    "IComparable",
    "IEquatable",
    "ICloneable",
    "IFormattable",
    "IConvertible",
    "IAsyncDisposable",
    # Delegates
    "Action",
    "Func",
    "Predicate",
    "EventHandler",
    "Comparison",
    "Converter",
    # LINQ
    "Enumerable",
    "Queryable",
    # IO
    "File",
    "Directory",
    "Path",
    "Stream",
    "StreamReader",
    "StreamWriter",
    "TextReader",
    "TextWriter",
    "MemoryStream",
    "FileStream",
    # String
    "StringBuilder",
    "StringComparer",
    "StringComparison",
    # Common Object methods
    "ToString",
    "Equals",
    "GetHashCode",
    "GetType",
    "ReferenceEquals",
    "MemberwiseClone",
    # Literals and keywords
    "null",
    "true",
    "false",
    "this",
    "base",
    "value",
    "nameof",
    "typeof",
    "sizeof",
    "default",
}

# C# primitive/keyword types to exclude from type references
CSHARP_PRIMITIVE_TYPES = {
    "void",
    "bool",
    "byte",
    "sbyte",
    "char",
    "short",
    "ushort",
    "int",
    "uint",
    "long",
    "ulong",
    "float",
    "double",
    "decimal",
    "string",
    "object",
    "dynamic",
    "var",
    "nint",
    "nuint",
}


class CSharpParser(BaseLanguageParser):
    """Parser for C# source code using Tree-sitter."""

    @property
    def language_name(self) -> str:
        return "csharp"

    def extract(
        self,
        root: Node,
        content: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract symbols and references from C# AST."""
        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        def get_text(node: Node) -> str:
            return self._get_text(node, content)

        def add_reference(ref: dict[str, Any]) -> None:
            self._add_reference(ref, references)

        def get_modifiers(node: Node) -> list[str]:
            """Extract modifiers from a declaration node.

            C# uses individual `modifier` children (not a container node like Java).
            """
            modifiers: list[str] = []
            for child in node.children:
                if child.type == "modifier":
                    modifiers.append(get_text(child))
            return modifiers

        def has_modifier(modifiers: list[str], mod: str) -> bool:
            return mod in modifiers

        # --- Type declarations ---

        def process_class_declaration(
            node: Node, scope: str | None = None, is_inner: bool = False
        ) -> None:
            """Process a class declaration."""
            modifiers = get_modifiers(node)
            class_name = None
            name_node = None

            for child in node.children:
                if child.type == "identifier":
                    class_name = get_text(child)
                    name_node = child
                    break

            if not class_name:
                return

            qualified_name = f"{scope}.{class_name}" if scope else class_name
            loc_node = name_node or node

            symbols.append(
                self._make_symbol(
                    class_name,
                    "class",
                    loc_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    qualified_name=qualified_name,
                    is_abstract=has_modifier(modifiers, "abstract"),
                    is_static=has_modifier(modifiers, "static"),
                    is_sealed=has_modifier(modifiers, "sealed"),
                    is_partial=has_modifier(modifiers, "partial"),
                    is_inner=is_inner,
                )
            )

            # Process base list and body
            for child in node.children:
                if child.type == "base_list":
                    process_base_list(child, qualified_name)
                elif child.type == "declaration_list":
                    process_declaration_list(child, qualified_name)

        def process_struct_declaration(node: Node, scope: str | None = None) -> None:
            """Process a struct declaration."""
            modifiers = get_modifiers(node)
            struct_name = None
            name_node = None

            for child in node.children:
                if child.type == "identifier":
                    struct_name = get_text(child)
                    name_node = child
                    break

            if not struct_name:
                return

            qualified_name = f"{scope}.{struct_name}" if scope else struct_name
            loc_node = name_node or node

            symbols.append(
                self._make_symbol(
                    struct_name,
                    "struct",
                    loc_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    qualified_name=qualified_name,
                    is_readonly=has_modifier(modifiers, "readonly"),
                )
            )

            for child in node.children:
                if child.type == "base_list":
                    process_base_list(child, qualified_name)
                elif child.type == "declaration_list":
                    process_declaration_list(child, qualified_name)

        def process_record_declaration(node: Node, scope: str | None = None) -> None:
            """Process a record declaration (record class or record struct)."""
            modifiers = get_modifiers(node)
            record_name = None
            name_node = None

            for child in node.children:
                if child.type == "identifier":
                    record_name = get_text(child)
                    name_node = child
                    break

            if not record_name:
                return

            qualified_name = f"{scope}.{record_name}" if scope else record_name
            loc_node = name_node or node

            symbols.append(
                self._make_symbol(
                    record_name,
                    "record",
                    loc_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    qualified_name=qualified_name,
                    is_abstract=has_modifier(modifiers, "abstract"),
                    is_sealed=has_modifier(modifiers, "sealed"),
                )
            )

            # Process parameter list (positional record parameters)
            for child in node.children:
                if child.type == "parameter_list":
                    process_record_parameters(child, qualified_name)
                elif child.type == "base_list":
                    process_base_list(child, qualified_name)
                elif child.type == "declaration_list":
                    process_declaration_list(child, qualified_name)

        def process_record_parameters(node: Node, scope: str) -> None:
            """Process record positional parameters as properties."""
            for child in node.children:
                if child.type == "parameter":
                    for param_child in child.children:
                        if param_child.type == "identifier":
                            param_name = get_text(param_child)
                            symbols.append(
                                self._make_symbol(
                                    param_name,
                                    "property",
                                    param_child,
                                    scope,
                                )
                            )
                            break

        def process_interface_declaration(node: Node, scope: str | None = None) -> None:
            """Process an interface declaration."""
            interface_name = None
            name_node = None

            for child in node.children:
                if child.type == "identifier":
                    interface_name = get_text(child)
                    name_node = child
                    break

            if not interface_name:
                return

            qualified_name = f"{scope}.{interface_name}" if scope else interface_name
            loc_node = name_node or node

            symbols.append(
                self._make_symbol(
                    interface_name,
                    "interface",
                    loc_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    qualified_name=qualified_name,
                )
            )

            for child in node.children:
                if child.type == "base_list":
                    process_base_list(child, qualified_name)
                elif child.type == "declaration_list":
                    process_declaration_list(child, qualified_name)

        def process_enum_declaration(node: Node, scope: str | None = None) -> None:
            """Process an enum declaration."""
            enum_name = None
            name_node = None

            for child in node.children:
                if child.type == "identifier":
                    enum_name = get_text(child)
                    name_node = child
                    break

            if not enum_name:
                return

            qualified_name = f"{scope}.{enum_name}" if scope else enum_name
            loc_node = name_node or node

            symbols.append(
                self._make_symbol(
                    enum_name,
                    "enum",
                    loc_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    qualified_name=qualified_name,
                )
            )

            for child in node.children:
                if child.type == "enum_member_declaration_list":
                    process_enum_member_list(child, qualified_name)

        def process_enum_member_list(node: Node, scope: str) -> None:
            """Process enum member declarations."""
            for child in node.children:
                if child.type == "enum_member_declaration":
                    for member_child in child.children:
                        if member_child.type == "identifier":
                            member_name = get_text(member_child)
                            symbols.append(
                                self._make_symbol(
                                    member_name,
                                    "enum_value",
                                    member_child,
                                    scope,
                                )
                            )
                            break

        def process_delegate_declaration(node: Node, scope: str | None = None) -> None:
            """Process a delegate declaration."""
            delegate_name = None
            name_node = None

            for child in node.children:
                if child.type == "identifier":
                    delegate_name = get_text(child)
                    name_node = child
                    break

            if not delegate_name:
                return

            qualified_name = f"{scope}.{delegate_name}" if scope else delegate_name
            loc_node = name_node or node

            symbols.append(
                self._make_symbol(
                    delegate_name,
                    "delegate",
                    loc_node,
                    scope,
                    qualified_name=qualified_name,
                )
            )

        # --- Namespace handling ---

        def process_namespace_declaration(
            node: Node,
            parent_scope: str | None = None,
            is_file_scoped: bool = False,
        ) -> str | None:
            """Process a namespace declaration (block-scoped or file-scoped).

            Returns the fully qualified namespace name so file-scoped
            namespaces can scope subsequent sibling declarations.
            """
            ns_name = None
            name_node = None

            for child in node.children:
                if child.type in ("identifier", "qualified_name"):
                    ns_name = get_text(child)
                    name_node = child
                    break

            if not ns_name:
                return None

            qualified_ns = f"{parent_scope}.{ns_name}" if parent_scope else ns_name
            loc_node = name_node or node

            symbols.append(
                self._make_symbol(
                    ns_name,
                    "namespace",
                    loc_node,
                    parent_scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    qualified_name=qualified_ns,
                )
            )

            # For block-scoped namespaces, process the body
            for child in node.children:
                if child.type == "declaration_list":
                    process_declaration_list(child, qualified_ns)
                elif child.type in (
                    "class_declaration",
                    "struct_declaration",
                    "record_declaration",
                    "interface_declaration",
                    "enum_declaration",
                    "delegate_declaration",
                    "namespace_declaration",
                ):
                    process_node(child, qualified_ns)

            return qualified_ns

        # --- Members ---

        def process_method_declaration(node: Node, scope: str) -> None:
            """Process a method declaration."""
            modifiers = get_modifiers(node)
            method_name = None
            name_node = None
            return_type = None

            for child in node.children:
                if child.type == "identifier" and method_name is None:
                    # First identifier after type is the method name
                    # But we need to skip the return type identifier
                    if return_type is not None:
                        method_name = get_text(child)
                        name_node = child
                    else:
                        # Could be the return type or method name
                        # Check if next sibling is parameter_list
                        next_sib = child.next_named_sibling
                        if next_sib and next_sib.type == "parameter_list":
                            method_name = get_text(child)
                            name_node = child
                        else:
                            return_type = get_text(child)
                elif child.type in (
                    "predefined_type",
                    "nullable_type",
                    "generic_name",
                    "array_type",
                    "tuple_type",
                    "qualified_name",
                ):
                    return_type = get_text(child)
                elif child.type == "void_keyword":
                    return_type = "void"

            if not method_name:
                return

            # Build signature
            params = extract_parameters(node)
            signature = f"{return_type or 'void'} {method_name}({', '.join(params)})"

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
                    is_static=has_modifier(modifiers, "static"),
                    is_abstract=has_modifier(modifiers, "abstract"),
                    is_virtual=has_modifier(modifiers, "virtual"),
                    is_override=has_modifier(modifiers, "override"),
                    is_async=has_modifier(modifiers, "async"),
                )
            )

        def process_constructor_declaration(node: Node, scope: str) -> None:
            """Process a constructor declaration."""
            constructor_name = None
            name_node = None

            for child in node.children:
                if child.type == "identifier":
                    constructor_name = get_text(child)
                    name_node = child
                    break

            if not constructor_name:
                return

            params = extract_parameters(node)
            signature = f"{constructor_name}({', '.join(params)})"

            loc_node = name_node or node
            symbols.append(
                self._make_symbol(
                    constructor_name,
                    "constructor",
                    loc_node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    signature=signature,
                )
            )

        def process_operator_declaration(node: Node, scope: str) -> None:
            """Process an operator declaration (treated as method)."""
            modifiers = get_modifiers(node)
            # Operator name from the operator token
            op_name = None
            for child in node.children:
                if child.type in ("operator_keyword",):
                    continue
                # The operator symbol comes after "operator" keyword
                if child.type not in (
                    "modifier",
                    "predefined_type",
                    "identifier",
                    "nullable_type",
                    "generic_name",
                    "parameter_list",
                    "block",
                    "arrow_expression_clause",
                ):
                    op_text = get_text(child)
                    if op_text in (
                        "+",
                        "-",
                        "*",
                        "/",
                        "%",
                        "==",
                        "!=",
                        "<",
                        ">",
                        "<=",
                        ">=",
                        "&",
                        "|",
                        "^",
                        "~",
                        "!",
                        "++",
                        "--",
                        "<<",
                        ">>",
                        "implicit",
                        "explicit",
                        "true",
                        "false",
                    ):
                        op_name = f"operator {op_text}"
                        break

            if not op_name:
                op_name = "operator"

            symbols.append(
                self._make_symbol(
                    op_name,
                    "method",
                    node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    is_static=has_modifier(modifiers, "static"),
                )
            )

        def extract_parameters(node: Node) -> list[str]:
            """Extract parameter list from method/constructor."""
            params: list[str] = []
            for child in node.children:
                if child.type == "parameter_list":
                    for param_child in child.children:
                        if param_child.type == "parameter":
                            param_type = None
                            param_name = None
                            for p_child in param_child.children:
                                if p_child.type in (
                                    "predefined_type",
                                    "identifier",
                                    "generic_name",
                                    "nullable_type",
                                    "array_type",
                                    "tuple_type",
                                    "qualified_name",
                                ):
                                    if param_type is None:
                                        param_type = get_text(p_child)
                                    else:
                                        param_name = get_text(p_child)
                            if param_type and param_name:
                                params.append(f"{param_type} {param_name}")
                            elif param_type:
                                params.append(param_type)
            return params

        def process_property_declaration(node: Node, scope: str) -> None:
            """Process a property declaration.

            AST: modifier* type_node identifier accessor_list
            The type can be ``identifier``, ``predefined_type``, ``generic_name``, etc.
            When the type is also ``identifier``, there are two consecutive identifier
            children — the first is the type, the second is the property name.
            We locate the name by finding the identifier immediately before
            ``accessor_list`` or ``arrow_expression_clause``.
            """
            modifiers = get_modifiers(node)

            # Collect all identifier children in order
            identifiers: list[tuple[str, Node]] = []
            for child in node.children:
                if child.type == "identifier":
                    identifiers.append((get_text(child), child))

            if not identifiers:
                return

            # The last identifier is the property name (the one before accessor_list)
            prop_name, name_node = identifiers[-1]

            loc_node = name_node or node
            symbols.append(
                self._make_symbol(
                    prop_name,
                    "property",
                    loc_node,
                    scope,
                    is_static=has_modifier(modifiers, "static"),
                    is_abstract=has_modifier(modifiers, "abstract"),
                    is_virtual=has_modifier(modifiers, "virtual"),
                    is_override=has_modifier(modifiers, "override"),
                )
            )

        def process_indexer_declaration(node: Node, scope: str) -> None:
            """Process an indexer declaration (this[])."""
            symbols.append(
                self._make_symbol(
                    "this[]",
                    "indexer",
                    node,
                    scope,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                )
            )

        def process_field_declaration(node: Node, scope: str) -> None:
            """Process a field declaration."""
            modifiers = get_modifiers(node)
            is_const = has_modifier(modifiers, "const")
            is_readonly = has_modifier(modifiers, "readonly")
            is_static = has_modifier(modifiers, "static")

            for child in node.children:
                if child.type == "variable_declaration":
                    for var_child in child.children:
                        if var_child.type == "variable_declarator":
                            for id_child in var_child.children:
                                if id_child.type == "identifier":
                                    field_name = get_text(id_child)
                                    kind = "constant" if is_const else "field"
                                    symbols.append(
                                        self._make_symbol(
                                            field_name,
                                            kind,
                                            id_child,
                                            scope,
                                            is_static=is_static or is_const,
                                            is_readonly=is_readonly,
                                        )
                                    )
                                    break

        def process_event_declaration(node: Node, scope: str) -> None:
            """Process an event declaration."""
            modifiers = get_modifiers(node)
            event_name = None
            name_node = None

            for child in node.children:
                if child.type == "identifier":
                    event_name = get_text(child)
                    name_node = child

            if not event_name:
                return

            loc_node = name_node or node
            symbols.append(
                self._make_symbol(
                    event_name,
                    "event",
                    loc_node,
                    scope,
                    is_static=has_modifier(modifiers, "static"),
                )
            )

        def process_event_field_declaration(node: Node, scope: str) -> None:
            """Process an event field declaration (event EventHandler OnClick;)."""
            modifiers = get_modifiers(node)

            for child in node.children:
                if child.type == "variable_declaration":
                    for var_child in child.children:
                        if var_child.type == "variable_declarator":
                            for id_child in var_child.children:
                                if id_child.type == "identifier":
                                    event_name = get_text(id_child)
                                    symbols.append(
                                        self._make_symbol(
                                            event_name,
                                            "event",
                                            id_child,
                                            scope,
                                            is_static=has_modifier(modifiers, "static"),
                                        )
                                    )
                                    break

        # --- Body processing ---

        def process_declaration_list(node: Node, scope: str) -> None:
            """Process a declaration list (class/struct/interface/namespace body)."""
            for child in node.children:
                if child.type == "method_declaration":
                    process_method_declaration(child, scope)
                elif child.type == "constructor_declaration":
                    process_constructor_declaration(child, scope)
                elif child.type == "property_declaration":
                    process_property_declaration(child, scope)
                elif child.type == "indexer_declaration":
                    process_indexer_declaration(child, scope)
                elif child.type == "field_declaration":
                    process_field_declaration(child, scope)
                elif child.type == "event_declaration":
                    process_event_declaration(child, scope)
                elif child.type == "event_field_declaration":
                    process_event_field_declaration(child, scope)
                elif child.type == "operator_declaration":
                    process_operator_declaration(child, scope)
                elif child.type == "conversion_operator_declaration":
                    process_operator_declaration(child, scope)
                elif child.type == "delegate_declaration":
                    process_delegate_declaration(child, scope)
                elif child.type == "class_declaration":
                    process_class_declaration(child, scope, is_inner=True)
                elif child.type == "struct_declaration":
                    process_struct_declaration(child, scope)
                elif child.type == "record_declaration":
                    process_record_declaration(child, scope)
                elif child.type == "interface_declaration":
                    process_interface_declaration(child, scope)
                elif child.type == "enum_declaration":
                    process_enum_declaration(child, scope)

        # --- Base list (inheritance) ---

        def process_base_list(node: Node, scope: str) -> None:
            """Process a base list (: BaseClass, IInterface, ...).

            In C# tree-sitter, base_list children can be:
            - direct ``identifier`` nodes (e.g., ``: Animal, IMovable``)
            - ``simple_base_type`` wrappers
            - ``generic_name`` nodes (e.g., ``: IEquatable<T>``)
            - ``primary_constructor_base_type`` (records)
            """
            for child in node.children:
                if child.type == "identifier":
                    type_name = get_text(child)
                    if (
                        type_name not in CSHARP_BUILTINS
                        and type_name not in CSHARP_PRIMITIVE_TYPES
                    ):
                        add_reference(
                            self._make_reference(type_name, "inheritance", child, scope)
                        )
                elif child.type == "generic_name":
                    process_generic_name_reference(child, scope, "inheritance")
                elif child.type == "qualified_name":
                    qname = get_text(child)
                    if (
                        qname not in CSHARP_BUILTINS
                        and qname not in CSHARP_PRIMITIVE_TYPES
                    ):
                        add_reference(
                            self._make_reference(qname, "inheritance", child, scope)
                        )
                elif child.type in (
                    "simple_base_type",
                    "primary_constructor_base_type",
                ):
                    process_base_type(child, scope)

        def process_base_type(node: Node, scope: str) -> None:
            """Process a single base type in a base list."""
            for child in node.children:
                if child.type == "identifier":
                    type_name = get_text(child)
                    if (
                        type_name not in CSHARP_BUILTINS
                        and type_name not in CSHARP_PRIMITIVE_TYPES
                    ):
                        add_reference(
                            self._make_reference(type_name, "inheritance", child, scope)
                        )
                elif child.type == "generic_name":
                    process_generic_name_reference(child, scope, "inheritance")
                elif child.type == "qualified_name":
                    qname = get_text(child)
                    if (
                        qname not in CSHARP_BUILTINS
                        and qname not in CSHARP_PRIMITIVE_TYPES
                    ):
                        add_reference(
                            self._make_reference(qname, "inheritance", child, scope)
                        )

        def process_generic_name_reference(
            node: Node, scope: str, ref_type: str = "type_annotation"
        ) -> None:
            """Process a generic name reference (e.g., List<T>)."""
            for child in node.children:
                if child.type == "identifier":
                    type_name = get_text(child)
                    if (
                        type_name not in CSHARP_BUILTINS
                        and type_name not in CSHARP_PRIMITIVE_TYPES
                    ):
                        add_reference(
                            self._make_reference(type_name, ref_type, child, scope)
                        )
                elif child.type == "type_argument_list":
                    for arg_child in child.children:
                        if arg_child.type == "identifier":
                            arg_name = get_text(arg_child)
                            if (
                                arg_name not in CSHARP_BUILTINS
                                and arg_name not in CSHARP_PRIMITIVE_TYPES
                            ):
                                add_reference(
                                    self._make_reference(
                                        arg_name,
                                        "type_annotation",
                                        arg_child,
                                        scope,
                                    )
                                )
                        elif arg_child.type == "generic_name":
                            process_generic_name_reference(arg_child, scope)

        # --- Reference extraction ---

        def extract_references(node: Node, scope: str | None = None) -> None:
            """Extract references from the AST."""
            # Using directives
            if node.type == "using_directive":
                process_using_directive(node)
                return

            # Method calls
            if node.type == "invocation_expression":
                process_invocation(node, scope)

            # Object creation (new Foo())
            if node.type == "object_creation_expression":
                for child in node.children:
                    if child.type == "identifier":
                        type_name = get_text(child)
                        if type_name not in CSHARP_BUILTINS:
                            add_reference(
                                self._make_reference(
                                    type_name,
                                    "instantiation",
                                    child,
                                    scope,
                                )
                            )
                    elif child.type == "generic_name":
                        process_generic_name_reference(
                            child, scope or "", "instantiation"
                        )
                    elif child.type == "qualified_name":
                        qname = get_text(child)
                        if qname not in CSHARP_BUILTINS:
                            add_reference(
                                self._make_reference(
                                    qname,
                                    "instantiation",
                                    child,
                                    scope,
                                )
                            )

            # Generic name references
            if node.type == "generic_name":
                parent = node.parent
                if parent and parent.type in (
                    "object_creation_expression",
                    "base_list",
                    "simple_base_type",
                    "primary_constructor_base_type",
                    "variable_declaration",
                ):
                    pass  # Handled by parent
                else:
                    process_generic_name_reference(node, scope or "", "type_annotation")

            # Variable declaration type references (field types, local vars)
            # AST: variable_declaration -> identifier (type) variable_declarator (name)
            if node.type == "variable_declaration":
                for child in node.children:
                    if child.type == "identifier":
                        type_name = get_text(child)
                        if (
                            type_name not in CSHARP_BUILTINS
                            and type_name not in CSHARP_PRIMITIVE_TYPES
                        ):
                            add_reference(
                                self._make_reference(
                                    type_name,
                                    "type_annotation",
                                    child,
                                    scope,
                                )
                            )
                        break  # Only the first identifier is the type
                    elif child.type == "generic_name":
                        process_generic_name_reference(
                            child, scope or "", "type_annotation"
                        )
                        break

            # Type identifier references (catch-all for remaining cases)
            if node.type == "identifier":
                parent = node.parent
                if parent and parent.type in (
                    "generic_name",
                    "object_creation_expression",
                    "base_list",
                    "simple_base_type",
                    "primary_constructor_base_type",
                    "using_directive",
                    "qualified_name",
                    "invocation_expression",
                    "member_access_expression",
                    "class_declaration",
                    "struct_declaration",
                    "record_declaration",
                    "interface_declaration",
                    "enum_declaration",
                    "delegate_declaration",
                    "namespace_declaration",
                    "file_scoped_namespace_declaration",
                    "method_declaration",
                    "constructor_declaration",
                    "property_declaration",
                    "field_declaration",
                    "event_declaration",
                    "event_field_declaration",
                    "parameter",
                    "variable_declarator",
                    "variable_declaration",
                    "enum_member_declaration",
                    "attribute",
                    "type_argument_list",
                ):
                    pass  # Handled elsewhere or is a declaration name
                else:
                    id_text = get_text(node)
                    if (
                        id_text not in CSHARP_BUILTINS
                        and id_text not in CSHARP_PRIMITIVE_TYPES
                        and id_text[0:1].isupper()
                    ):
                        add_reference(
                            self._make_reference(
                                id_text, "type_annotation", node, scope
                            )
                        )

            # Attribute usage
            if node.type == "attribute":
                for child in node.children:
                    if child.type == "identifier":
                        attr_name = get_text(child)
                        if attr_name not in CSHARP_BUILTINS:
                            add_reference(
                                self._make_reference(attr_name, "usage", child, scope)
                            )
                        break
                    elif child.type == "qualified_name":
                        qname = get_text(child)
                        if qname not in CSHARP_BUILTINS:
                            add_reference(
                                self._make_reference(qname, "usage", child, scope)
                            )
                        break

            # Handle compilation_unit with file-scoped namespace (mirrors process_node)
            if node.type == "compilation_unit":
                file_ref_scope: str | None = None
                for child in node.children:
                    if child.type == "file_scoped_namespace_declaration":
                        for name_child in child.children:
                            if name_child.type in ("identifier", "qualified_name"):
                                file_ref_scope = get_text(name_child)
                                break
                        extract_references(child, file_ref_scope)
                    else:
                        extract_references(child, file_ref_scope or scope)
                return

            # Recurse into children
            for child in node.children:
                child_scope = scope
                # Update scope when entering named declarations
                if node.type in (
                    "class_declaration",
                    "struct_declaration",
                    "record_declaration",
                    "interface_declaration",
                ):
                    for name_child in node.children:
                        if name_child.type == "identifier":
                            child_scope = (
                                f"{scope}.{get_text(name_child)}"
                                if scope
                                else get_text(name_child)
                            )
                            break
                elif node.type == "method_declaration":
                    for name_child in node.children:
                        if name_child.type == "identifier":
                            # Skip the return-type identifier
                            next_sib = name_child.next_named_sibling
                            if next_sib and next_sib.type == "parameter_list":
                                child_scope = (
                                    f"{scope}.{get_text(name_child)}"
                                    if scope
                                    else get_text(name_child)
                                )
                                break
                elif node.type in (
                    "namespace_declaration",
                    "file_scoped_namespace_declaration",
                ):
                    for name_child in node.children:
                        if name_child.type in (
                            "identifier",
                            "qualified_name",
                        ):
                            child_scope = (
                                f"{scope}.{get_text(name_child)}"
                                if scope
                                else get_text(name_child)
                            )
                            break

                extract_references(child, child_scope)

        def process_using_directive(node: Node) -> None:
            """Process a using directive."""
            # Collect the namespace/type being imported
            using_target = None
            target_node: Node | None = None
            is_static = False

            for child in node.children:
                if child.type == "identifier":
                    using_target = get_text(child)
                    target_node = child
                elif child.type == "qualified_name":
                    using_target = get_text(child)
                    target_node = child
                elif child.type == "static":
                    is_static = True
                elif child.type == "using_directive" and child != node:
                    # Nested — skip
                    pass

            if using_target:
                location_node = target_node or node
                add_reference(
                    self._make_reference(
                        using_target,
                        "import",
                        location_node,
                        is_static=is_static,
                    )
                )

        def process_invocation(node: Node, scope: str | None = None) -> None:
            """Process a method invocation expression."""
            for child in node.children:
                if child.type == "identifier":
                    method_name = get_text(child)
                    if method_name not in CSHARP_BUILTINS:
                        add_reference(
                            self._make_reference(method_name, "call", child, scope)
                        )
                elif child.type == "member_access_expression":
                    # obj.Method() — extract the method name (rightmost identifier)
                    identifiers: list[tuple[str, Node]] = []
                    for mac_child in child.children:
                        if mac_child.type == "identifier":
                            identifiers.append((get_text(mac_child), mac_child))
                    if identifiers:
                        method_name, method_node = identifiers[-1]
                        if method_name not in CSHARP_BUILTINS:
                            add_reference(
                                self._make_reference(
                                    method_name, "call", method_node, scope
                                )
                            )
                        # If first identifier looks like a type, add type ref
                        if len(identifiers) > 1:
                            obj_name, obj_node = identifiers[0]
                            if (
                                obj_name not in CSHARP_BUILTINS
                                and obj_name not in CSHARP_PRIMITIVE_TYPES
                                and obj_name[0:1].isupper()
                            ):
                                add_reference(
                                    self._make_reference(
                                        obj_name,
                                        "type_annotation",
                                        obj_node,
                                        scope,
                                    )
                                )
                elif child.type == "generic_name":
                    # GenericMethod<T>()
                    for gc in child.children:
                        if gc.type == "identifier":
                            gname = get_text(gc)
                            if gname not in CSHARP_BUILTINS:
                                add_reference(
                                    self._make_reference(gname, "call", gc, scope)
                                )
                            break

        # --- Top-level node processing ---

        def process_node(node: Node, scope: str | None = None) -> None:
            """Process a node and its children recursively."""
            if node.type == "class_declaration":
                process_class_declaration(node, scope)
            elif node.type == "struct_declaration":
                process_struct_declaration(node, scope)
            elif node.type == "record_declaration":
                process_record_declaration(node, scope)
            elif node.type == "interface_declaration":
                process_interface_declaration(node, scope)
            elif node.type == "enum_declaration":
                process_enum_declaration(node, scope)
            elif node.type == "delegate_declaration":
                process_delegate_declaration(node, scope)
            elif node.type == "namespace_declaration":
                process_namespace_declaration(node, parent_scope=scope)
            elif node.type == "file_scoped_namespace_declaration":
                # File-scoped namespace: processed below in compilation_unit
                process_namespace_declaration(
                    node, parent_scope=scope, is_file_scoped=True
                )
            elif node.type == "compilation_unit":
                # Check for file-scoped namespace first — it scopes all
                # subsequent sibling declarations
                file_scope: str | None = None
                for child in node.children:
                    if child.type == "file_scoped_namespace_declaration":
                        ns = process_namespace_declaration(
                            child, parent_scope=scope, is_file_scoped=True
                        )
                        if ns:
                            file_scope = ns
                    else:
                        process_node(child, file_scope or scope)

        # Process symbols — handle the root (compilation_unit) directly
        process_node(root)

        # Extract references
        extract_references(root)

        return symbols, references

    def _process_comment_node(self, node: Node, content: str) -> dict[str, Any] | None:
        """Classify and clean a C# comment node.

        C# tree-sitter uses a single ``comment`` node type.
        We distinguish by text prefix:
        - ``///`` → XML doc comment
        - ``//``  → single-line comment
        - ``/* */`` → block comment
        """
        if node.type != "comment":
            return None

        text = self._get_text(node, content)

        if text.startswith("///"):
            cleaned = text[3:].strip()
            if not cleaned:
                return None
            return {
                "content": cleaned,
                "content_type": "xml_doc_comment",
                "source_line": node.start_point[0] + 1,
                "source_end_line": node.end_point[0] + 1,
            }

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

        return None
