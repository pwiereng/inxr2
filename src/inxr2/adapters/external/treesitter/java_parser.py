"""Java language parser using Tree-sitter."""

from typing import Any

from tree_sitter import Node

from .base import BaseLanguageParser

# Java builtin types and classes to exclude from references
JAVA_BUILTINS = {
    # java.lang (auto-imported)
    "Object",
    "String",
    "System",
    "Class",
    "Throwable",
    "Exception",
    "RuntimeException",
    "Error",
    "Thread",
    "Runnable",
    "Comparable",
    "Integer",
    "Long",
    "Double",
    "Float",
    "Boolean",
    "Character",
    "Byte",
    "Short",
    "Number",
    "Void",
    "Math",
    "StringBuilder",
    "StringBuffer",
    "Iterable",
    "Cloneable",
    "Enum",
    "Override",
    "Deprecated",
    "SuppressWarnings",
    "FunctionalInterface",
    "SafeVarargs",
    # Common methods to exclude
    "toString",
    "equals",
    "hashCode",
    "getClass",
    "clone",
    "notify",
    "notifyAll",
    "wait",
    "finalize",
    # java.util common
    "List",
    "ArrayList",
    "LinkedList",
    "Set",
    "HashSet",
    "TreeSet",
    "LinkedHashSet",
    "Map",
    "HashMap",
    "TreeMap",
    "LinkedHashMap",
    "Collection",
    "Collections",
    "Arrays",
    "Optional",
    "Iterator",
    "Comparator",
    "Queue",
    "Deque",
    "Stack",
    "Vector",
    "Properties",
    "Date",
    "Calendar",
    "UUID",
    "Random",
    "Scanner",
    "Formatter",
    "Locale",
    "TimeZone",
    "Currency",
    # java.io common
    "File",
    "InputStream",
    "OutputStream",
    "Reader",
    "Writer",
    "BufferedReader",
    "BufferedWriter",
    "FileReader",
    "FileWriter",
    "PrintWriter",
    "IOException",
    "FileNotFoundException",
    "Serializable",
    # java.util.stream
    "Stream",
    "Collectors",
    # Literals and keywords
    "null",
    "true",
    "false",
    "this",
    "super",
}

# Java primitive types to exclude from type references
JAVA_PRIMITIVE_TYPES = {
    "void",
    "boolean",
    "byte",
    "char",
    "short",
    "int",
    "long",
    "float",
    "double",
    "var",  # Java 10+ local variable type inference
}


class JavaParser(BaseLanguageParser):
    """Parser for Java source code using Tree-sitter."""

    @property
    def language_name(self) -> str:
        return "java"

    def extract(
        self,
        root: Node,
        content: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract symbols and references from Java AST."""
        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        def get_text(node: Node) -> str:
            return self._get_text(node, content)

        def add_reference(ref: dict[str, Any]) -> None:
            """Add reference only if it has non-empty text."""
            text = ref.get("text", "")
            if text and text.strip():
                references.append(ref)

        def get_modifiers(node: Node) -> list[str]:
            """Extract modifiers from a declaration node."""
            modifiers: list[str] = []
            for child in node.children:
                if child.type == "modifiers":
                    for mod_child in child.children:
                        if mod_child.type in (
                            "public",
                            "private",
                            "protected",
                            "static",
                            "final",
                            "abstract",
                            "native",
                            "synchronized",
                            "transient",
                            "volatile",
                            "strictfp",
                            "default",
                        ):
                            modifiers.append(get_text(mod_child))
                        elif mod_child.type == "marker_annotation":
                            # Handle annotations in modifiers
                            pass
                        elif mod_child.type == "annotation":
                            # Handle annotations with arguments
                            pass
            return modifiers

        def is_static(modifiers: list[str]) -> bool:
            return "static" in modifiers

        def is_final(modifiers: list[str]) -> bool:
            return "final" in modifiers

        def is_abstract(modifiers: list[str]) -> bool:
            return "abstract" in modifiers

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

            symbols.append(
                {
                    "name": class_name,
                    "kind": "class",
                    "start_line": (
                        name_node.start_point[0] + 1
                        if name_node
                        else node.start_point[0] + 1
                    ),
                    "start_column": (
                        name_node.start_point[1] if name_node else node.start_point[1]
                    ),
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": scope,
                    "qualified_name": qualified_name,
                    "is_abstract": is_abstract(modifiers),
                    "is_final": is_final(modifiers),
                    "is_static": is_static(modifiers),
                    # In Java, static nested classes are not "inner" classes
                    "is_inner": is_inner and not is_static(modifiers),
                }
            )

            # Process extends and implements
            for child in node.children:
                if child.type == "superclass":
                    process_superclass(child, qualified_name)
                elif child.type == "super_interfaces":
                    process_super_interfaces(child, qualified_name)
                elif child.type == "class_body":
                    process_class_body(child, qualified_name)

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

            symbols.append(
                {
                    "name": interface_name,
                    "kind": "interface",
                    "start_line": (
                        name_node.start_point[0] + 1
                        if name_node
                        else node.start_point[0] + 1
                    ),
                    "start_column": (
                        name_node.start_point[1] if name_node else node.start_point[1]
                    ),
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": scope,
                    "qualified_name": qualified_name,
                }
            )

            # Process extends
            for child in node.children:
                if child.type == "extends_interfaces":
                    process_extends_interfaces(child, qualified_name)
                elif child.type == "interface_body":
                    process_interface_body(child, qualified_name)

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

            symbols.append(
                {
                    "name": enum_name,
                    "kind": "enum",
                    "start_line": (
                        name_node.start_point[0] + 1
                        if name_node
                        else node.start_point[0] + 1
                    ),
                    "start_column": (
                        name_node.start_point[1] if name_node else node.start_point[1]
                    ),
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": scope,
                    "qualified_name": qualified_name,
                }
            )

            # Process enum body
            for child in node.children:
                if child.type == "enum_body":
                    process_enum_body(child, qualified_name)
                elif child.type == "super_interfaces":
                    process_super_interfaces(child, qualified_name)

        def process_annotation_type_declaration(
            node: Node, scope: str | None = None
        ) -> None:
            """Process an annotation type declaration (@interface)."""
            annotation_name = None
            name_node = None

            for child in node.children:
                if child.type == "identifier":
                    annotation_name = get_text(child)
                    name_node = child
                    break

            if not annotation_name:
                return

            qualified_name = f"{scope}.{annotation_name}" if scope else annotation_name

            symbols.append(
                {
                    "name": annotation_name,
                    "kind": "annotation",
                    "start_line": (
                        name_node.start_point[0] + 1
                        if name_node
                        else node.start_point[0] + 1
                    ),
                    "start_column": (
                        name_node.start_point[1] if name_node else node.start_point[1]
                    ),
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": scope,
                    "qualified_name": qualified_name,
                }
            )

        def process_record_declaration(node: Node, scope: str | None = None) -> None:
            """Process a record declaration (Java 14+)."""
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

            symbols.append(
                {
                    "name": record_name,
                    "kind": "record",
                    "start_line": (
                        name_node.start_point[0] + 1
                        if name_node
                        else node.start_point[0] + 1
                    ),
                    "start_column": (
                        name_node.start_point[1] if name_node else node.start_point[1]
                    ),
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": scope,
                    "qualified_name": qualified_name,
                }
            )

            # Process record components as fields
            for child in node.children:
                if child.type == "formal_parameters":
                    process_record_components(child, qualified_name)
                elif child.type == "super_interfaces":
                    process_super_interfaces(child, qualified_name)
                elif child.type == "class_body":
                    process_class_body(child, qualified_name)

        def process_record_components(node: Node, scope: str) -> None:
            """Process record components as fields."""
            for child in node.children:
                if child.type == "formal_parameter":
                    param_name = None
                    for param_child in child.children:
                        if param_child.type == "identifier":
                            param_name = get_text(param_child)
                            symbols.append(
                                {
                                    "name": param_name,
                                    "kind": "field",
                                    **self._node_location(param_child),
                                    "scope": scope,
                                    "qualified_name": f"{scope}.{param_name}",
                                    "is_final": True,  # Record components are implicitly final
                                }
                            )
                            break

        def process_superclass(node: Node, scope: str) -> None:
            """Process superclass (extends) reference."""
            for child in node.children:
                if child.type == "type_identifier":
                    superclass_name = get_text(child)
                    if superclass_name not in JAVA_BUILTINS:
                        add_reference(
                            {
                                "text": superclass_name,
                                "type": "inheritance",
                                "source_line": child.start_point[0] + 1,
                                "source_column": child.start_point[1],
                                "scope": scope,
                            }
                        )
                elif child.type == "generic_type":
                    process_generic_type_reference(child, scope, "inheritance")

        def process_super_interfaces(node: Node, scope: str) -> None:
            """Process interfaces (implements) references."""
            for child in node.children:
                if child.type == "type_list":
                    for type_child in child.children:
                        if type_child.type == "type_identifier":
                            interface_name = get_text(type_child)
                            if interface_name not in JAVA_BUILTINS:
                                add_reference(
                                    {
                                        "text": interface_name,
                                        "type": "inheritance",
                                        "source_line": type_child.start_point[0] + 1,
                                        "source_column": type_child.start_point[1],
                                        "scope": scope,
                                    }
                                )
                        elif type_child.type == "generic_type":
                            process_generic_type_reference(
                                type_child, scope, "inheritance"
                            )

        def process_extends_interfaces(node: Node, scope: str) -> None:
            """Process interface extends references."""
            for child in node.children:
                if child.type == "type_list":
                    for type_child in child.children:
                        if type_child.type == "type_identifier":
                            interface_name = get_text(type_child)
                            if interface_name not in JAVA_BUILTINS:
                                add_reference(
                                    {
                                        "text": interface_name,
                                        "type": "inheritance",
                                        "source_line": type_child.start_point[0] + 1,
                                        "source_column": type_child.start_point[1],
                                        "scope": scope,
                                    }
                                )
                        elif type_child.type == "generic_type":
                            process_generic_type_reference(
                                type_child, scope, "inheritance"
                            )

        def process_generic_type_reference(
            node: Node, scope: str, ref_type: str = "type_annotation"
        ) -> None:
            """Process a generic type reference (e.g., List<String>)."""
            for child in node.children:
                if child.type == "type_identifier":
                    type_name = get_text(child)
                    if (
                        type_name not in JAVA_BUILTINS
                        and type_name not in JAVA_PRIMITIVE_TYPES
                    ):
                        add_reference(
                            {
                                "text": type_name,
                                "type": ref_type,
                                "source_line": child.start_point[0] + 1,
                                "source_column": child.start_point[1],
                                "scope": scope,
                            }
                        )
                elif child.type == "type_arguments":
                    # Process type arguments recursively
                    for arg_child in child.children:
                        if arg_child.type == "type_identifier":
                            arg_name = get_text(arg_child)
                            if (
                                arg_name not in JAVA_BUILTINS
                                and arg_name not in JAVA_PRIMITIVE_TYPES
                            ):
                                add_reference(
                                    {
                                        "text": arg_name,
                                        "type": "type_annotation",
                                        "source_line": arg_child.start_point[0] + 1,
                                        "source_column": arg_child.start_point[1],
                                        "scope": scope,
                                    }
                                )
                        elif arg_child.type == "generic_type":
                            process_generic_type_reference(arg_child, scope)

        def process_class_body(node: Node, scope: str) -> None:
            """Process a class body."""
            for child in node.children:
                if child.type == "method_declaration":
                    process_method_declaration(child, scope)
                elif child.type == "constructor_declaration":
                    process_constructor_declaration(child, scope)
                elif child.type == "field_declaration":
                    process_field_declaration(child, scope)
                elif child.type == "class_declaration":
                    process_class_declaration(child, scope, is_inner=True)
                elif child.type == "interface_declaration":
                    process_interface_declaration(child, scope)
                elif child.type == "enum_declaration":
                    process_enum_declaration(child, scope)
                elif child.type == "annotation_type_declaration":
                    process_annotation_type_declaration(child, scope)
                elif child.type == "record_declaration":
                    process_record_declaration(child, scope)

        def process_interface_body(node: Node, scope: str) -> None:
            """Process an interface body."""
            for child in node.children:
                if child.type == "method_declaration":
                    process_method_declaration(child, scope, is_interface=True)
                elif child.type == "constant_declaration":
                    process_constant_declaration(child, scope)
                elif child.type == "class_declaration":
                    process_class_declaration(child, scope, is_inner=True)
                elif child.type == "interface_declaration":
                    process_interface_declaration(child, scope)
                elif child.type == "enum_declaration":
                    process_enum_declaration(child, scope)
                elif child.type == "annotation_type_declaration":
                    process_annotation_type_declaration(child, scope)

        def process_enum_body(node: Node, scope: str) -> None:
            """Process an enum body."""
            for child in node.children:
                if child.type == "enum_constant":
                    process_enum_constant(child, scope)
                elif child.type == "enum_body_declarations":
                    # Process additional methods/fields in enum
                    for body_child in child.children:
                        if body_child.type == "method_declaration":
                            process_method_declaration(body_child, scope)
                        elif body_child.type == "constructor_declaration":
                            process_constructor_declaration(body_child, scope)
                        elif body_child.type == "field_declaration":
                            process_field_declaration(body_child, scope)

        def process_enum_constant(node: Node, scope: str) -> None:
            """Process an enum constant."""
            for child in node.children:
                if child.type == "identifier":
                    constant_name = get_text(child)
                    symbols.append(
                        {
                            "name": constant_name,
                            "kind": "enum_value",
                            **self._node_location(child),
                            "scope": scope,
                            "qualified_name": f"{scope}.{constant_name}",
                        }
                    )
                    break

        def process_method_declaration(
            node: Node, scope: str, is_interface: bool = False
        ) -> None:
            """Process a method declaration."""
            modifiers = get_modifiers(node)
            method_name = None
            name_node = None
            return_type = None

            for child in node.children:
                if child.type == "identifier":
                    method_name = get_text(child)
                    name_node = child
                elif child.type in (
                    "type_identifier",
                    "void_type",
                    "generic_type",
                    "array_type",
                    "integral_type",
                    "floating_point_type",
                    "boolean_type",
                ):
                    if child.type == "void_type":
                        return_type = "void"
                    else:
                        return_type = get_text(child)

            # Fallback: try to get return type from the "type" field
            if return_type is None:
                type_node = node.child_by_field_name("type")
                if type_node is not None:
                    return_type = get_text(type_node)

            if not method_name:
                return

            # Build signature
            params = extract_parameters(node)
            signature = f"{return_type or 'void'} {method_name}({', '.join(params)})"

            symbols.append(
                {
                    "name": method_name,
                    "kind": "method",
                    "start_line": (
                        name_node.start_point[0] + 1
                        if name_node
                        else node.start_point[0] + 1
                    ),
                    "start_column": (
                        name_node.start_point[1] if name_node else node.start_point[1]
                    ),
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": scope,
                    "qualified_name": f"{scope}.{method_name}",
                    "signature": signature,
                    "is_static": is_static(modifiers),
                    # Interface methods are abstract only if explicitly abstract or lacking a body
                    "is_abstract": is_abstract(modifiers)
                    or (
                        is_interface
                        and not any(child.type == "block" for child in node.children)
                    ),
                }
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

            # Build signature
            params = extract_parameters(node)
            signature = f"{constructor_name}({', '.join(params)})"

            symbols.append(
                {
                    "name": constructor_name,
                    "kind": "constructor",
                    "start_line": (
                        name_node.start_point[0] + 1
                        if name_node
                        else node.start_point[0] + 1
                    ),
                    "start_column": (
                        name_node.start_point[1] if name_node else node.start_point[1]
                    ),
                    "end_line": node.end_point[0] + 1,
                    "end_column": node.end_point[1],
                    "scope": scope,
                    "qualified_name": f"{scope}.{constructor_name}",
                    "signature": signature,
                }
            )

        def extract_parameters(node: Node) -> list[str]:
            """Extract parameter list from method/constructor."""
            params: list[str] = []
            for child in node.children:
                if child.type == "formal_parameters":
                    for param_child in child.children:
                        if param_child.type == "formal_parameter":
                            param_type = None
                            param_name = None
                            for p_child in param_child.children:
                                if p_child.type in (
                                    "type_identifier",
                                    "generic_type",
                                    "array_type",
                                ):
                                    param_type = get_text(p_child)
                                elif p_child.type == "integral_type":
                                    param_type = get_text(p_child)
                                elif p_child.type == "floating_point_type":
                                    param_type = get_text(p_child)
                                elif p_child.type == "boolean_type":
                                    param_type = "boolean"
                                elif p_child.type == "identifier":
                                    param_name = get_text(p_child)
                            if param_type and param_name:
                                params.append(f"{param_type} {param_name}")
                            elif param_type:
                                params.append(param_type)
                        elif param_child.type == "spread_parameter":
                            # Varargs parameter
                            param_type = None
                            for p_child in param_child.children:
                                if p_child.type in (
                                    "type_identifier",
                                    "generic_type",
                                    "array_type",
                                ):
                                    param_type = get_text(p_child)
                                elif p_child.type == "identifier":
                                    if param_type:
                                        params.append(
                                            f"{param_type}... {get_text(p_child)}"
                                        )
                                    break
            return params

        def process_field_declaration(node: Node, scope: str) -> None:
            """Process a field declaration."""
            modifiers = get_modifiers(node)

            for child in node.children:
                if child.type == "variable_declarator":
                    for var_child in child.children:
                        if var_child.type == "identifier":
                            field_name = get_text(var_child)
                            kind = (
                                "constant"
                                if is_static(modifiers) and is_final(modifiers)
                                else "field"
                            )
                            symbols.append(
                                {
                                    "name": field_name,
                                    "kind": kind,
                                    **self._node_location(var_child),
                                    "scope": scope,
                                    "qualified_name": f"{scope}.{field_name}",
                                    "is_static": is_static(modifiers),
                                    "is_final": is_final(modifiers),
                                }
                            )
                            break

        def process_constant_declaration(node: Node, scope: str) -> None:
            """Process a constant declaration in interface."""
            for child in node.children:
                if child.type == "variable_declarator":
                    for var_child in child.children:
                        if var_child.type == "identifier":
                            constant_name = get_text(var_child)
                            symbols.append(
                                {
                                    "name": constant_name,
                                    "kind": "constant",
                                    **self._node_location(var_child),
                                    "scope": scope,
                                    "qualified_name": f"{scope}.{constant_name}",
                                    "is_static": True,
                                    "is_final": True,
                                }
                            )
                            break

        def process_import_declaration(node: Node) -> None:
            """Process an import statement."""
            is_static_import = False
            is_wildcard = False
            import_path = None

            for child in node.children:
                if child.type == "static":
                    is_static_import = True
                elif child.type == "scoped_identifier":
                    import_path = get_text(child)
                elif child.type == "identifier":
                    import_path = get_text(child)
                elif child.type == "asterisk":
                    is_wildcard = True

            if import_path:
                if is_wildcard:
                    import_path = f"{import_path}.*"

                add_reference(
                    {
                        "text": import_path,
                        "type": "import",
                        "source_line": node.start_point[0] + 1,
                        "source_column": node.start_point[1],
                        "is_static": is_static_import,
                    }
                )

        def extract_references(node: Node, scope: str | None = None) -> None:
            """Extract references from the AST."""
            # Import statements
            if node.type == "import_declaration":
                process_import_declaration(node)
                return

            # Method calls
            if node.type == "method_invocation":
                # For method calls like obj.method() or ClassName.method(),
                # we need to extract the method name (last identifier after the dot)
                # and optionally the object/class being called on
                identifiers: list[tuple[str, Node]] = []
                for child in node.children:
                    if child.type == "identifier":
                        identifiers.append((get_text(child), child))

                if identifiers:
                    # The last identifier is always the method name
                    method_name, method_node = identifiers[-1]
                    if method_name not in JAVA_BUILTINS:
                        add_reference(
                            {
                                "text": method_name,
                                "type": "call",
                                "source_line": method_node.start_point[0] + 1,
                                "source_column": method_node.start_point[1],
                                "scope": scope,
                            }
                        )

                    # If there are multiple identifiers (e.g., ClassName.method()),
                    # the first one is a type/object reference
                    if len(identifiers) > 1:
                        obj_name, obj_node = identifiers[0]
                        if obj_name not in JAVA_BUILTINS and obj_name not in (
                            "this",
                            "super",
                        ):
                            # Check if it's a class name (starts with uppercase)
                            # or a variable (starts with lowercase)
                            ref_type = (
                                "type_annotation" if obj_name[0].isupper() else "usage"
                            )
                            add_reference(
                                {
                                    "text": obj_name,
                                    "type": ref_type,
                                    "source_line": obj_node.start_point[0] + 1,
                                    "source_column": obj_node.start_point[1],
                                    "scope": scope,
                                }
                            )

            # Object creation (new Foo())
            if node.type == "object_creation_expression":
                for child in node.children:
                    if child.type == "type_identifier":
                        type_name = get_text(child)
                        if type_name not in JAVA_BUILTINS:
                            add_reference(
                                {
                                    "text": type_name,
                                    "type": "instantiation",
                                    "source_line": child.start_point[0] + 1,
                                    "source_column": child.start_point[1],
                                    "scope": scope,
                                }
                            )
                    elif child.type == "generic_type":
                        process_generic_type_reference(
                            child, scope or "", "instantiation"
                        )

            # Generic type references (e.g., CustomList<MyItem>)
            if node.type == "generic_type":
                # Only process if parent is not already handling this
                parent = node.parent
                if parent and parent.type in (
                    "object_creation_expression",
                    "superclass",
                    "super_interfaces",
                    "extends_interfaces",
                    "type_list",
                ):
                    # These are handled by their parent nodes
                    pass
                else:
                    process_generic_type_reference(node, scope or "", "type_annotation")

            # Type references
            if node.type == "type_identifier":
                # Avoid adding duplicate references for types already handled
                parent = node.parent
                if parent and parent.type in (
                    "generic_type",
                    "object_creation_expression",
                    "superclass",
                    "super_interfaces",
                    "extends_interfaces",
                    "type_list",
                ):
                    # These are handled by their parent nodes
                    pass
                else:
                    type_name = get_text(node)
                    if (
                        type_name not in JAVA_BUILTINS
                        and type_name not in JAVA_PRIMITIVE_TYPES
                    ):
                        add_reference(
                            {
                                "text": type_name,
                                "type": "type_annotation",
                                "source_line": node.start_point[0] + 1,
                                "source_column": node.start_point[1],
                                "scope": scope,
                            }
                        )

            # Field access
            if node.type == "field_access":
                # Get the object being accessed
                field_obj_node = node.child_by_field_name("object")
                if field_obj_node and field_obj_node.type == "identifier":
                    field_obj_name = get_text(field_obj_node)
                    if field_obj_name not in JAVA_BUILTINS and field_obj_name not in (
                        "this",
                        "super",
                    ):
                        add_reference(
                            {
                                "text": field_obj_name,
                                "type": "usage",
                                "source_line": field_obj_node.start_point[0] + 1,
                                "source_column": field_obj_node.start_point[1],
                                "scope": scope,
                            }
                        )
                # Get the field being accessed (but not if this is a method call)
                parent = node.parent
                is_method_call = (
                    parent is not None and parent.type == "method_invocation"
                )
                if not is_method_call:
                    field_node = node.child_by_field_name("field")
                    if field_node:
                        field_name = get_text(field_node)
                        if field_name not in JAVA_BUILTINS:
                            add_reference(
                                {
                                    "text": field_name,
                                    "type": "usage",
                                    "source_line": field_node.start_point[0] + 1,
                                    "source_column": field_node.start_point[1],
                                    "scope": scope,
                                }
                            )

            # Annotation usage (@Override, @Deprecated, etc.)
            if node.type in ("marker_annotation", "annotation"):
                for child in node.children:
                    if child.type == "identifier":
                        annotation_name = get_text(child)
                        if annotation_name not in JAVA_BUILTINS:
                            add_reference(
                                {
                                    "text": annotation_name,
                                    "type": "usage",
                                    "source_line": child.start_point[0] + 1,
                                    "source_column": child.start_point[1],
                                    "scope": scope,
                                }
                            )
                        break

            # Recurse into children
            for child in node.children:
                child_scope = scope
                # Update scope when entering class/interface/method bodies
                if node.type == "class_declaration":
                    for name_child in node.children:
                        if name_child.type == "identifier":
                            child_scope = (
                                f"{scope}.{get_text(name_child)}"
                                if scope
                                else get_text(name_child)
                            )
                            break
                elif node.type == "interface_declaration":
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
                            child_scope = (
                                f"{scope}.{get_text(name_child)}"
                                if scope
                                else get_text(name_child)
                            )
                            break

                extract_references(child, child_scope)

        def process_node(node: Node, scope: str | None = None) -> None:
            """Process a node and its children recursively."""
            if node.type == "class_declaration":
                process_class_declaration(node, scope)
            elif node.type == "interface_declaration":
                process_interface_declaration(node, scope)
            elif node.type == "enum_declaration":
                process_enum_declaration(node, scope)
            elif node.type == "annotation_type_declaration":
                process_annotation_type_declaration(node, scope)
            elif node.type == "record_declaration":
                process_record_declaration(node, scope)
            elif node.type == "program":
                # Process top-level declarations
                for child in node.children:
                    process_node(child, scope)

        # Process top-level nodes
        for child in root.children:
            process_node(child)

        # Extract references
        extract_references(root)

        return symbols, references
