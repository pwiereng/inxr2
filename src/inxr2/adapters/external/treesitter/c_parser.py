"""C language parser using Tree-sitter."""

from typing import Any

from tree_sitter import Node

from .base import BaseLanguageParser

# C builtin functions to exclude from call references
C_BUILTINS = {
    # Standard I/O
    "printf",
    "fprintf",
    "sprintf",
    "snprintf",
    "scanf",
    "fscanf",
    "sscanf",
    "puts",
    "fputs",
    "gets",
    "fgets",
    "putchar",
    "getchar",
    "fopen",
    "fclose",
    "fread",
    "fwrite",
    "fseek",
    "ftell",
    "rewind",
    "fflush",
    "feof",
    "ferror",
    "clearerr",
    "perror",
    # Memory management
    "malloc",
    "calloc",
    "realloc",
    "free",
    "memcpy",
    "memmove",
    "memset",
    "memcmp",
    # String functions
    "strlen",
    "strcpy",
    "strncpy",
    "strcat",
    "strncat",
    "strcmp",
    "strncmp",
    "strchr",
    "strrchr",
    "strstr",
    "strtok",
    "strdup",
    # Character functions
    "isalpha",
    "isdigit",
    "isalnum",
    "isspace",
    "isupper",
    "islower",
    "toupper",
    "tolower",
    # Math functions
    "abs",
    "labs",
    "fabs",
    "ceil",
    "floor",
    "sqrt",
    "pow",
    "exp",
    "log",
    "log10",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "atan2",
    # Utility functions
    "exit",
    "abort",
    "atexit",
    "atoi",
    "atof",
    "atol",
    "strtol",
    "strtoul",
    "strtod",
    "rand",
    "srand",
    "qsort",
    "bsearch",
    # Assert
    "assert",
    # Size/offset
    "sizeof",
    "offsetof",
}

# C primitive types to exclude from type references
C_PRIMITIVE_TYPES = {
    "void",
    "char",
    "short",
    "int",
    "long",
    "float",
    "double",
    "signed",
    "unsigned",
    "size_t",
    "ssize_t",
    "ptrdiff_t",
    "intptr_t",
    "uintptr_t",
    "int8_t",
    "int16_t",
    "int32_t",
    "int64_t",
    "uint8_t",
    "uint16_t",
    "uint32_t",
    "uint64_t",
    "bool",
    "_Bool",
    "FILE",
    "NULL",
    "true",
    "false",
    "const",
    "static",
    "extern",
    "volatile",
    "register",
    "inline",
    "restrict",
    "__attribute__",
}


class CParser(BaseLanguageParser):
    """Parser for C source code using Tree-sitter."""

    @property
    def language_name(self) -> str:
        return "c"

    def extract(
        self,
        root: Node,
        content: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract symbols and references from C AST."""
        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        def get_text(node: Node) -> str:
            return self._get_text(node, content)

        def get_identifier_text(node: Node) -> str | None:
            """Get identifier text from a node or its first identifier child."""
            if node.type == "identifier":
                return get_text(node)
            if node.type == "type_identifier":
                return get_text(node)
            for child in node.children:
                if child.type in ("identifier", "type_identifier"):
                    return get_text(child)
            return None

        def add_reference(ref: dict[str, Any]) -> None:
            """Add reference only if it has non-empty text."""
            text = ref.get("text", "")
            if text and text.strip():
                references.append(ref)

        def process_function_definition(node: Node) -> None:
            """Process a function definition."""
            # Get function declarator
            declarator = node.child_by_field_name("declarator")
            if not declarator:
                return

            # Find function name from declarator
            func_name = extract_function_name(declarator)
            if not func_name:
                return

            # Get return type
            return_type = None
            type_node = node.child_by_field_name("type")
            if type_node:
                return_type = get_text(type_node)

            # Get parameters for signature
            params = extract_parameters(declarator)
            signature = f"{return_type or 'void'} {func_name}({', '.join(params)})"

            symbols.append(
                {
                    "name": func_name,
                    "kind": "function",
                    **self._node_location(node),
                    "scope": None,
                    "signature": signature,
                }
            )

        def extract_function_name(declarator: Node) -> str | None:
            """Extract function name from a declarator."""
            if declarator.type == "function_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    if inner.type == "identifier":
                        return get_text(inner)
                    elif inner.type == "pointer_declarator":
                        return extract_function_name(inner)
                    elif inner.type == "parenthesized_declarator":
                        for child in inner.children:
                            if child.type == "pointer_declarator":
                                return extract_function_name(child)
                            if child.type == "identifier":
                                return get_text(child)
            elif declarator.type == "pointer_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    return extract_function_name(inner)
            elif declarator.type == "identifier":
                return get_text(declarator)
            return None

        def extract_parameters(declarator: Node) -> list[str]:
            """Extract parameter list from function declarator."""
            params: list[str] = []
            if declarator.type == "function_declarator":
                params_node = declarator.child_by_field_name("parameters")
                if params_node:
                    for child in params_node.children:
                        if child.type == "parameter_declaration":
                            params.append(get_text(child))
            return params

        def process_declaration(node: Node) -> None:
            """Process a declaration (variable or function prototype)."""
            # Note: typedef declarations are handled by process_type_definition
            # Check for extern storage class
            has_extern = False
            for child in node.children:
                if child.type == "storage_class_specifier":
                    spec_text = get_text(child)
                    if spec_text == "extern":
                        has_extern = True

            # Get the type specifier
            type_node = node.child_by_field_name("type")

            # Check for struct/union/enum specifier that defines a new type
            if type_node:
                if type_node.type == "struct_specifier":
                    process_struct_specifier(type_node)
                elif type_node.type == "union_specifier":
                    process_union_specifier(type_node)
                elif type_node.type == "enum_specifier":
                    process_enum_specifier(type_node)

            # Process declarators
            for child in node.children:
                if child.type == "init_declarator":
                    declarator = child.child_by_field_name("declarator")
                    if declarator:
                        process_declarator(declarator, type_node, has_extern)
                elif child.type in (
                    "identifier",
                    "function_declarator",
                    "pointer_declarator",
                    "array_declarator",
                ):
                    process_declarator(child, type_node, has_extern)

        def process_declarator(
            declarator: Node, type_node: Node | None, is_extern: bool
        ) -> None:
            """Process a declarator to extract variable or function declaration."""
            if declarator.type == "function_declarator":
                # Function declaration/prototype
                func_name = extract_function_name(declarator)
                if func_name:
                    return_type = get_text(type_node) if type_node else "void"
                    params = extract_parameters(declarator)
                    signature = f"{return_type} {func_name}({', '.join(params)})"

                    symbols.append(
                        {
                            "name": func_name,
                            "kind": "function",
                            **self._node_location(declarator),
                            "scope": None,
                            "signature": signature,
                            "is_declaration": True,
                        }
                    )
            elif declarator.type == "pointer_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    if inner.type == "function_declarator":
                        process_declarator(inner, type_node, is_extern)
                    elif inner.type == "identifier":
                        # Pointer variable
                        var_name = get_text(inner)
                        symbols.append(
                            {
                                "name": var_name,
                                "kind": "variable",
                                **self._node_location(declarator),
                                "scope": None,
                            }
                        )
            elif declarator.type == "array_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner and inner.type == "identifier":
                    var_name = get_text(inner)
                    symbols.append(
                        {
                            "name": var_name,
                            "kind": "variable",
                            **self._node_location(declarator),
                            "scope": None,
                        }
                    )
            elif declarator.type == "identifier":
                # Simple variable declaration
                var_name = get_text(declarator)
                symbols.append(
                    {
                        "name": var_name,
                        "kind": "variable",
                        **self._node_location(declarator),
                        "scope": None,
                    }
                )
            elif declarator.type == "init_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    process_declarator(inner, type_node, is_extern)

        def process_type_definition(node: Node) -> None:
            """Process a typedef declaration (type_definition node)."""
            # Find the typedef name - it's usually a type_identifier at the end
            # Also look for struct/union/enum specifiers that define types
            typedef_name = None

            for child in node.children:
                if child.type == "type_identifier":
                    # This is the typedef alias name (last type_identifier)
                    typedef_name = get_text(child)
                elif child.type in (
                    "pointer_declarator",
                    "function_declarator",
                    "array_declarator",
                ):
                    name = extract_typedef_name(child)
                    if name:
                        typedef_name = name
                elif child.type == "struct_specifier":
                    process_struct_specifier(child, in_typedef=True)
                elif child.type == "union_specifier":
                    process_union_specifier(child, in_typedef=True)
                elif child.type == "enum_specifier":
                    process_enum_specifier(child, in_typedef=True)

            if typedef_name:
                symbols.append(
                    {
                        "name": typedef_name,
                        "kind": "typedef",
                        **self._node_location(node),
                        "scope": None,
                    }
                )

        def extract_typedef_name(declarator: Node) -> str | None:
            """Extract the name from a typedef declarator."""
            if declarator.type == "identifier":
                return get_text(declarator)
            elif declarator.type == "type_identifier":
                return get_text(declarator)
            elif declarator.type == "pointer_declarator":
                # Check for type_identifier child first (function pointer case)
                for child in declarator.children:
                    if child.type == "type_identifier":
                        return get_text(child)
                # Then try the declarator field
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    return extract_typedef_name(inner)
            elif declarator.type == "function_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    return extract_typedef_name(inner)
            elif declarator.type == "array_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    return extract_typedef_name(inner)
            elif declarator.type == "parenthesized_declarator":
                # Handle (parenthesized) declarators
                for child in declarator.children:
                    if child.type in (
                        "pointer_declarator",
                        "function_declarator",
                        "type_identifier",
                    ):
                        return extract_typedef_name(child)
            return None

        def process_struct_specifier(node: Node, in_typedef: bool = False) -> None:
            """Process a struct specifier."""
            # Find the name (type_identifier)
            struct_name = None
            for child in node.children:
                if child.type == "type_identifier":
                    struct_name = get_text(child)
                    break

            # Only add struct symbol if it has a name
            if struct_name:
                symbols.append(
                    {
                        "name": struct_name,
                        "kind": "struct",
                        **self._node_location(node),
                        "scope": None,
                    }
                )

            # Process fields from field_declaration_list (only if struct has a name)
            if struct_name:
                for child in node.children:
                    if child.type == "field_declaration_list":
                        for field_child in child.children:
                            if field_child.type == "field_declaration":
                                process_field_declaration(
                                    field_child, struct_name, "struct_field"
                                )

        def process_union_specifier(node: Node, in_typedef: bool = False) -> None:
            """Process a union specifier."""
            # Find the name (type_identifier)
            union_name = None
            for child in node.children:
                if child.type == "type_identifier":
                    union_name = get_text(child)
                    break

            if union_name:
                symbols.append(
                    {
                        "name": union_name,
                        "kind": "union",
                        **self._node_location(node),
                        "scope": None,
                    }
                )

            # Process fields from field_declaration_list (only if union has a name)
            if union_name:
                for child in node.children:
                    if child.type == "field_declaration_list":
                        for field_child in child.children:
                            if field_child.type == "field_declaration":
                                process_field_declaration(
                                    field_child, union_name, "union_field"
                                )

        def process_field_declaration(
            node: Node, parent_name: str, field_kind: str
        ) -> None:
            """Process a struct/union field declaration."""
            for child in node.children:
                if child.type == "field_identifier":
                    field_name = get_text(child)
                    symbols.append(
                        {
                            "name": field_name,
                            "kind": field_kind,
                            **self._node_location(child),
                            "scope": parent_name,
                            "qualified_name": f"{parent_name}.{field_name}",
                        }
                    )
                elif child.type == "pointer_declarator":
                    # Pointer field
                    inner = child.child_by_field_name("declarator")
                    if inner and inner.type == "field_identifier":
                        field_name = get_text(inner)
                        symbols.append(
                            {
                                "name": field_name,
                                "kind": field_kind,
                                **self._node_location(child),
                                "scope": parent_name,
                                "qualified_name": f"{parent_name}.{field_name}",
                            }
                        )
                elif child.type == "array_declarator":
                    # Array field
                    inner = child.child_by_field_name("declarator")
                    if inner and inner.type == "field_identifier":
                        field_name = get_text(inner)
                        symbols.append(
                            {
                                "name": field_name,
                                "kind": field_kind,
                                **self._node_location(child),
                                "scope": parent_name,
                                "qualified_name": f"{parent_name}.{field_name}",
                            }
                        )

        def process_enum_specifier(node: Node, in_typedef: bool = False) -> None:
            """Process an enum specifier."""
            # Find the name (type_identifier)
            enum_name = None
            for child in node.children:
                if child.type == "type_identifier":
                    enum_name = get_text(child)
                    break

            if enum_name:
                symbols.append(
                    {
                        "name": enum_name,
                        "kind": "enum",
                        **self._node_location(node),
                        "scope": None,
                    }
                )

            # Process enumerators from enumerator_list
            for child in node.children:
                if child.type == "enumerator_list":
                    for enum_child in child.children:
                        if enum_child.type == "enumerator":
                            # Get name from first identifier child
                            for name_child in enum_child.children:
                                if name_child.type == "identifier":
                                    enum_value_name = get_text(name_child)
                                    symbols.append(
                                        {
                                            "name": enum_value_name,
                                            "kind": "enum_value",
                                            **self._node_location(enum_child),
                                            "scope": enum_name,
                                            "qualified_name": (
                                                f"{enum_name}.{enum_value_name}"
                                                if enum_name
                                                else enum_value_name
                                            ),
                                        }
                                    )
                                    break

        def process_preproc_def(node: Node) -> None:
            """Process a simple #define macro."""
            # Get name from first identifier child
            for child in node.children:
                if child.type == "identifier":
                    macro_name = get_text(child)
                    symbols.append(
                        {
                            "name": macro_name,
                            "kind": "macro",
                            **self._node_location(node),
                            "scope": None,
                        }
                    )
                    break

        def process_preproc_function_def(node: Node) -> None:
            """Process a function-like #define macro."""
            # Get name from first identifier child
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
                    {
                        "name": macro_name,
                        "kind": "macro",
                        **self._node_location(node),
                        "scope": None,
                        "signature": signature,
                    }
                )

        def process_preproc_include(node: Node) -> None:
            """Process a #include directive."""
            path_node = node.child_by_field_name("path")
            if path_node:
                include_path = get_text(path_node)
                # Remove quotes or angle brackets
                include_path = include_path.strip('"<>')
                add_reference(
                    {
                        "text": include_path,
                        "type": "include",
                        "source_line": node.start_point[0] + 1,
                        "source_column": node.start_point[1],
                    }
                )

        def extract_references(node: Node, scope: str | None = None) -> None:
            """Extract references from the AST."""
            # Function calls
            if node.type == "call_expression":
                func_node = node.child_by_field_name("function")
                if func_node:
                    if func_node.type == "identifier":
                        call_name = get_text(func_node)
                        if call_name not in C_BUILTINS:
                            add_reference(
                                {
                                    "text": call_name,
                                    "type": "call",
                                    "source_line": func_node.start_point[0] + 1,
                                    "source_column": func_node.start_point[1],
                                    "scope": scope,
                                }
                            )
                    elif func_node.type == "field_expression":
                        # function pointer in struct: s->func() or s.func()
                        field = func_node.child_by_field_name("field")
                        if field:
                            add_reference(
                                {
                                    "text": get_text(field),
                                    "type": "call",
                                    "source_line": field.start_point[0] + 1,
                                    "source_column": field.start_point[1],
                                    "scope": scope,
                                }
                            )

            # Type references (struct/enum/union usage)
            if node.type == "type_identifier":
                type_name = get_text(node)
                if type_name not in C_PRIMITIVE_TYPES:
                    add_reference(
                        {
                            "text": type_name,
                            "type": "type_annotation",
                            "source_line": node.start_point[0] + 1,
                            "source_column": node.start_point[1],
                            "scope": scope,
                        }
                    )

            # Recurse into children
            for child in node.children:
                child_scope = scope
                if node.type == "function_definition":
                    declarator = node.child_by_field_name("declarator")
                    if declarator:
                        func_name = extract_function_name(declarator)
                        if func_name:
                            child_scope = func_name
                extract_references(child, child_scope)

        def process_node(node: Node) -> None:
            """Process a node and its children recursively."""
            if node.type == "function_definition":
                process_function_definition(node)
            elif node.type == "declaration":
                process_declaration(node)
            elif node.type == "type_definition":
                process_type_definition(node)
            elif node.type == "struct_specifier":
                process_struct_specifier(node)
            elif node.type == "union_specifier":
                process_union_specifier(node)
            elif node.type == "enum_specifier":
                process_enum_specifier(node)
            elif node.type == "preproc_def":
                process_preproc_def(node)
            elif node.type == "preproc_function_def":
                process_preproc_function_def(node)
            elif node.type == "preproc_include":
                process_preproc_include(node)
            elif node.type in (
                "preproc_ifdef",
                "preproc_ifndef",
                "preproc_if",
                "preproc_elif",
                "preproc_else",
            ):
                # Recursively process children of preprocessor conditionals
                for child in node.children:
                    process_node(child)

        # Process top-level nodes
        for child in root.children:
            process_node(child)

        # Extract references
        extract_references(root)

        return symbols, references
