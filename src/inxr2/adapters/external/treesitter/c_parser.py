"""C language parser using Tree-sitter."""

from typing import Any

from tree_sitter import Node

from .base import BaseLanguageParser
from .builtins import _load

# C builtin functions to exclude from call references
C_BUILTINS = _load("c.json", "builtins")

# C primitive types and keywords to exclude from type references
C_PRIMITIVE_TYPES = _load("c.json", "primitive_types")


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

        def add_reference(ref: dict[str, Any]) -> None:
            self._add_reference(ref, references)

        def process_function_definition(node: Node) -> None:
            """Process a function definition."""
            # Get function declarator
            declarator = node.child_by_field_name("declarator")
            if not declarator:
                return

            # Find function name and its identifier node from declarator
            func_name, name_node = extract_function_name_and_node(declarator)
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

            # Use name_node position for start (where the name actually is),
            # but use the full function node for end (where the body ends).
            loc_node = name_node or node
            symbols.append(
                self._make_symbol(
                    func_name,
                    "function",
                    loc_node,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                    signature=signature,
                )
            )

        def extract_function_name_and_node(
            declarator: Node,
        ) -> tuple[str | None, Node | None]:
            """Extract function name and identifier node from a declarator."""
            if declarator.type == "function_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    if inner.type == "identifier":
                        return get_text(inner), inner
                    elif inner.type == "pointer_declarator":
                        return extract_function_name_and_node(inner)
                    elif inner.type == "parenthesized_declarator":
                        for child in inner.children:
                            if child.type == "pointer_declarator":
                                return extract_function_name_and_node(child)
                            if child.type == "identifier":
                                return get_text(child), child
            elif declarator.type == "pointer_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    return extract_function_name_and_node(inner)
            elif declarator.type == "identifier":
                return get_text(declarator), declarator
            return None, None

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
                        process_declarator(declarator, type_node)
                elif child.type in (
                    "identifier",
                    "function_declarator",
                    "pointer_declarator",
                    "array_declarator",
                ):
                    process_declarator(child, type_node)

        def process_declarator(declarator: Node, type_node: Node | None) -> None:
            """Process a declarator to extract variable or function declaration."""
            if declarator.type == "function_declarator":
                # Function declaration/prototype
                func_name = extract_function_name(declarator)
                if func_name:
                    return_type = get_text(type_node) if type_node else "void"
                    params = extract_parameters(declarator)
                    signature = f"{return_type} {func_name}({', '.join(params)})"

                    symbols.append(
                        self._make_symbol(
                            func_name,
                            "function",
                            declarator,
                            signature=signature,
                            is_declaration=True,
                        )
                    )
            elif declarator.type == "pointer_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    if inner.type == "function_declarator":
                        process_declarator(inner, type_node)
                    elif inner.type == "identifier":
                        # Pointer variable
                        var_name = get_text(inner)
                        symbols.append(
                            self._make_symbol(var_name, "variable", declarator)
                        )
                    else:
                        # Recursively handle nested declarators (e.g., pointer-to-pointer,
                        # pointers to arrays, etc.)
                        process_declarator(inner, type_node)
            elif declarator.type == "array_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    if inner.type == "identifier":
                        var_name = get_text(inner)
                        symbols.append(
                            self._make_symbol(var_name, "variable", declarator)
                        )
                    else:
                        # Recursively handle nested declarators (e.g., arrays of pointers,
                        # multi-dimensional arrays, etc.)
                        process_declarator(inner, type_node)
            elif declarator.type == "identifier":
                # Simple variable declaration
                var_name = get_text(declarator)
                symbols.append(self._make_symbol(var_name, "variable", declarator))
            elif declarator.type == "init_declarator":
                inner = declarator.child_by_field_name("declarator")
                if inner:
                    process_declarator(inner, type_node)

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
                symbols.append(self._make_symbol(typedef_name, "typedef", node))

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
            # in_typedef is accepted for API consistency but not currently used
            _ = in_typedef
            struct_name = self._extract_named_type_declaration(
                node,
                content,
                symbols,
                "struct",
                identifier_type="type_identifier",
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
            # in_typedef is accepted for API consistency but not currently used
            _ = in_typedef
            union_name = self._extract_named_type_declaration(
                node,
                content,
                symbols,
                "union",
                identifier_type="type_identifier",
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

        def extract_field_identifier(node: Node) -> str | None:
            """Recursively extract field_identifier from nested declarators."""
            if node.type == "field_identifier":
                return get_text(node)
            elif node.type == "pointer_declarator":
                # Check direct children first
                for child in node.children:
                    if child.type == "field_identifier":
                        return get_text(child)
                # Then try declarator field
                inner = node.child_by_field_name("declarator")
                if inner:
                    return extract_field_identifier(inner)
            elif node.type == "parenthesized_declarator":
                for child in node.children:
                    result = extract_field_identifier(child)
                    if result:
                        return result
            elif node.type == "function_declarator":
                inner = node.child_by_field_name("declarator")
                if inner:
                    return extract_field_identifier(inner)
            elif node.type == "array_declarator":
                inner = node.child_by_field_name("declarator")
                if inner:
                    return extract_field_identifier(inner)
            return None

        def process_field_declaration(
            node: Node, parent_name: str, field_kind: str
        ) -> None:
            """Process a struct/union field declaration."""
            for child in node.children:
                if child.type == "field_identifier":
                    field_name = get_text(child)
                    symbols.append(
                        self._make_symbol(field_name, field_kind, child, parent_name)
                    )
                elif child.type in (
                    "pointer_declarator",
                    "array_declarator",
                    "function_declarator",
                ):
                    # Handle pointer, array, and function pointer fields
                    extracted_name = extract_field_identifier(child)
                    if extracted_name:
                        symbols.append(
                            self._make_symbol(
                                extracted_name, field_kind, child, parent_name
                            )
                        )

        def process_enum_specifier(node: Node, in_typedef: bool = False) -> None:
            """Process an enum specifier."""
            # in_typedef is accepted for API consistency but not currently used
            _ = in_typedef
            enum_name = self._extract_named_type_declaration(
                node,
                content,
                symbols,
                "enum",
                identifier_type="type_identifier",
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
                                    # For anonymous enums, set qualified_name to just the value name
                                    qn = (
                                        f"{enum_name}.{enum_value_name}"
                                        if enum_name
                                        else enum_value_name
                                    )
                                    symbols.append(
                                        self._make_symbol(
                                            enum_value_name,
                                            "enum_value",
                                            enum_child,
                                            enum_name,
                                            qualified_name=qn,
                                        )
                                    )
                                    break

        def process_preproc_def(node: Node) -> None:
            """Process a simple #define macro."""
            # Get name from first identifier child
            for child in node.children:
                if child.type == "identifier":
                    macro_name = get_text(child)
                    symbols.append(self._make_symbol(macro_name, "macro", node))
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
                    self._make_symbol(macro_name, "macro", node, signature=signature)
                )

        def process_preproc_include(node: Node) -> None:
            """Process a #include directive."""
            path_node = node.child_by_field_name("path")
            if path_node:
                include_path = get_text(path_node)
                # Remove quotes or angle brackets
                include_path = include_path.strip('"<>')
                add_reference(self._make_reference(include_path, "include", node))

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
                                self._make_reference(
                                    call_name, "call", func_node, scope
                                )
                            )
                    elif func_node.type == "field_expression":
                        # function pointer in struct: s->func() or s.func()
                        field = func_node.child_by_field_name("field")
                        if field:
                            add_reference(
                                self._make_reference(
                                    get_text(field), "call", field, scope
                                )
                            )

            # Type references (struct/enum/union usage)
            if node.type == "type_identifier":
                type_name = get_text(node)
                if type_name not in C_PRIMITIVE_TYPES:
                    add_reference(
                        self._make_reference(type_name, "type_annotation", node, scope)
                    )

            # Variable usage references (field expressions like globals.field)
            if node.type == "field_expression":
                # Get the base object being accessed (e.g., "globals" in "globals.field")
                argument = node.child_by_field_name("argument")
                if argument and argument.type == "identifier":
                    var_name = get_text(argument)
                    # Don't add if it's a builtin or primitive
                    if var_name not in C_BUILTINS and var_name not in C_PRIMITIVE_TYPES:
                        add_reference(
                            self._make_reference(var_name, "usage", argument, scope)
                        )
                # Get the field being accessed (e.g., "numberOfNodes" in "config.numberOfNodes")
                # But skip if this field_expression is the function in a call_expression,
                # since the call_expression handler already records it as a "call" reference
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

            # sizeof expressions - extract references
            # sizeof(TypeName) parses as sizeof_expression with parenthesized_expression
            # sizeof(struct Foo) parses as sizeof_expression with type_descriptor
            # Note: We use "usage" instead of "type_annotation" because we can't
            # reliably distinguish sizeof(TypeName) from sizeof(variable) without
            # tracking all typedefs. Using "usage" is safer and technically correct.
            if node.type == "sizeof_expression":
                for child in node.children:
                    if child.type == "parenthesized_expression":
                        # sizeof(name) - could be typedef or variable
                        for inner in child.children:
                            if inner.type == "identifier":
                                name = get_text(inner)
                                if (
                                    name not in C_BUILTINS
                                    and name not in C_PRIMITIVE_TYPES
                                ):
                                    add_reference(
                                        self._make_reference(
                                            name, "usage", inner, scope
                                        )
                                    )
                    elif child.type == "type_descriptor":
                        # sizeof(struct Foo) - type_identifier inside type_descriptor
                        # The recursive traversal will handle type_identifier nodes

                        pass

            # Macro type specifier references (e.g., CJSON_PUBLIC(char *) in return types)
            # Tree-sitter parses this as macro_type_specifier with an identifier child
            if node.type == "macro_type_specifier":
                for child in node.children:
                    if child.type == "identifier":
                        macro_name = get_text(child)
                        add_reference(
                            self._make_reference(macro_name, "usage", child, scope)
                        )
                        break  # Only need the first identifier (the macro name)

            # Identifiers in initializer lists (function pointers, enum values, etc.)
            # e.g., { engine, engine_init, sizeof(EngineState), 0, 0 }
            if node.type == "initializer_list":
                for child in node.children:
                    if child.type == "identifier":
                        ident_name = get_text(child)
                        # Skip builtins, primitives, and common constants
                        if (
                            ident_name not in C_BUILTINS
                            and ident_name not in C_PRIMITIVE_TYPES
                            and ident_name not in ("NULL", "true", "false")
                        ):
                            add_reference(
                                self._make_reference(ident_name, "usage", child, scope)
                            )
                    elif child.type == "initializer_list":
                        # Nested initializer - will be handled by recursion
                        pass

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
                "linkage_specification",  # extern "C" { ... }
                "declaration_list",  # { ... } block inside linkage_specification
            ):
                # Recursively process children of preprocessor conditionals
                # and linkage specification blocks (extern "C")
                for child in node.children:
                    process_node(child)

        # Process top-level nodes
        for child in root.children:
            process_node(child)

        # Extract references
        extract_references(root)

        return symbols, references

    def _process_comment_node(self, node: Node, content: str) -> dict[str, Any] | None:
        """Classify and clean a C comment node."""
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
