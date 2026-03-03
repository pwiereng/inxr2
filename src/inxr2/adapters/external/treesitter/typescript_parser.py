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

            # Extract this.property assignments in constructors
            if name == "constructor":
                _extract_constructor_properties(node, class_name)

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

        def _extract_constructor_properties(method_node: Node, class_name: str) -> None:
            """Extract this.x = ... assignments in a constructor as property symbols.

            Collects names of fields already declared in the class body to avoid
            duplicates, then walks the constructor body for assignment_expression
            nodes where the LHS is `this.<prop>`.
            """
            # Collect existing field names from the class body to avoid duplicates
            existing_fields: set[str] = set()
            class_body = method_node.parent  # class_body
            if class_body and class_body.type == "class_body":
                for member in class_body.children:
                    if member.type == "public_field_definition":
                        field_name = get_name_from_node(member)
                        if field_name:
                            existing_fields.add(field_name)

            seen_props: set[str] = set()

            def _visit_for_this_assignments(n: Node) -> None:
                if n.type == "assignment_expression":
                    left = n.child_by_field_name("left")
                    if left and left.type == "member_expression":
                        obj = left.child_by_field_name("object")
                        prop = left.child_by_field_name("property")
                        if (
                            obj
                            and prop
                            and obj.type == "this"
                            and prop.type == "property_identifier"
                        ):
                            prop_name = get_text(prop)
                            if (
                                prop_name
                                and prop_name not in existing_fields
                                and prop_name not in seen_props
                            ):
                                seen_props.add(prop_name)
                                symbols.append(
                                    self._make_symbol(
                                        prop_name, "property", prop, class_name
                                    )
                                )
                for child in n.children:
                    # Don't recurse into nested scopes where `this` is rebound
                    if child.type in (
                        "function_expression",
                        "function_declaration",
                        "class",
                        "class_declaration",
                        "method_definition",
                    ):
                        continue
                    _visit_for_this_assignments(child)

            # Find the statement_block (constructor body) and walk it
            for child in method_node.children:
                if child.type == "statement_block":
                    _visit_for_this_assignments(child)

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

                    # Check if it's an arrow function, class expression, etc.
                    value_node = child.child_by_field_name("value")
                    if value_node and value_node.type == "arrow_function":
                        symbols.append(self._make_symbol(var_name, "function", child))
                    elif value_node and value_node.type == "class":
                        # Class expression: const X = class { ... }
                        _process_class_expression(value_node, var_name)
                    elif re.match(r"^[A-Z][A-Z0-9_]*$", var_name):
                        # UPPER_CASE constant
                        symbols.append(self._make_symbol(var_name, "constant", child))

        def _process_class_expression(node: Node, name: str) -> None:
            """Process a class expression node, creating a class symbol and its members.

            Used for patterns like `const X = class { ... }` and
            `module.exports = class Foo { ... }`.
            """
            symbols.append(self._make_symbol(name, "class", node))
            for child in node.children:
                if child.type == "class_body":
                    for member in child.children:
                        if member.type == "method_definition":
                            process_method(member, name)
                        elif member.type == "public_field_definition":
                            process_field(member, name)

        def _class_expression_binding_name(node: Node) -> str | None:
            """Get the binding name for a class expression from its parent.

            Returns the variable name for `const X = class { ... }` or the
            export property for `exports.X = class { ... }`.
            """
            parent = node.parent
            if not parent:
                return None
            if parent.type == "variable_declarator":
                name_node = parent.child_by_field_name("name")
                if name_node:
                    return get_text(name_node)
            elif parent.type == "assignment_expression":
                left = parent.child_by_field_name("left")
                if left:
                    binding, is_prop = _get_export_binding_name(left)
                    if is_prop:
                        return binding
            return None

        def _get_export_binding_name(left: Node) -> tuple[str | None, bool]:
            """Get the binding name from a CommonJS export LHS.

            Returns (name, is_exports_prop):
              - module.exports → (None, False) — name comes from RHS
              - exports.Foo    → ("Foo", True) — name comes from LHS
              - foo.bar        → (None, False) — not an export, caller should skip
            """
            if left.type != "member_expression":
                return None, False
            obj = left.child_by_field_name("object")
            prop = left.child_by_field_name("property")
            if not obj or not prop:
                return None, False
            obj_name = get_text(obj)
            prop_name = get_text(prop)
            if obj_name == "module" and prop_name == "exports":
                return None, False
            if obj_name == "exports":
                return prop_name, True
            # Not a recognized export pattern (e.g. foo.bar = ...)
            return None, False

        def _is_export_pattern(left: Node) -> bool:
            """Check if LHS is module.exports or exports.<prop>."""
            if left.type != "member_expression":
                return False
            obj = left.child_by_field_name("object")
            prop = left.child_by_field_name("property")
            if not obj or not prop:
                return False
            obj_name = get_text(obj)
            prop_name = get_text(prop)
            return (obj_name == "module" and prop_name == "exports") or (
                obj_name == "exports"
            )

        def _process_assignment_expression(node: Node) -> None:
            """Process assignment expressions for module.exports/exports patterns.

            Handles:
              - module.exports = class Foo { ... }
              - exports.Foo = class Foo { ... }
              - module.exports = function foo() { ... }

            Ignores non-export assignments (e.g. foo.bar = class { ... }).
            """
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if not left or not right:
                return

            if not _is_export_pattern(left):
                return

            if right.type == "class":
                # For exports.Foo = class Bar { ... }, prefer LHS name "Foo".
                # For module.exports = class Bar { ... }, use RHS name "Bar".
                binding_name, is_exports_prop = _get_export_binding_name(left)
                if is_exports_prop:
                    class_name = binding_name
                else:
                    class_name = get_name_from_node(right)
                    if not class_name:
                        class_name = binding_name
                if class_name:
                    _process_class_expression(right, class_name)
            elif right.type == "function_expression":
                # Mirror class-expression handling: prefer LHS for exports.<prop>.
                binding_name, is_exports_prop = _get_export_binding_name(left)
                if is_exports_prop:
                    fn_name = binding_name
                else:
                    fn_name = get_name_from_node(right)
                    if not fn_name:
                        fn_name = binding_name
                if fn_name:
                    symbols.append(self._make_symbol(fn_name, "function", right))

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

            # CommonJS require() imports:
            #   const { A, B } = require('module')
            #   const x = require('module')
            if node.type in ("lexical_declaration", "variable_declaration"):
                for decl in node.children:
                    if decl.type != "variable_declarator":
                        continue
                    name_node = decl.child_by_field_name("name")
                    value_node = decl.child_by_field_name("value")
                    if not value_node or value_node.type != "call_expression":
                        continue
                    func_node = value_node.child_by_field_name("function")
                    if not func_node or get_text(func_node) != "require":
                        continue
                    # Extract module path from require('...')
                    args = value_node.child_by_field_name("arguments")
                    req_module: str | None = None
                    if args:
                        for arg in args.children:
                            if arg.type == "string":
                                req_module = get_text(arg).strip("'\"")
                                break
                    if name_node and name_node.type == "object_pattern":
                        # Destructured: const { A, B } = require('module')
                        for prop in name_node.children:
                            if prop.type == "shorthand_property_identifier_pattern":
                                binding_name = get_text(prop)
                                if binding_name:
                                    add_reference(
                                        self._make_reference(
                                            binding_name,
                                            "import",
                                            prop,
                                            from_module=req_module,
                                        )
                                    )
                            elif prop.type == "pair_pattern":
                                # { A: localA } — use the local binding name
                                # so later uses of localA resolve to the import
                                value = prop.child_by_field_name("value")
                                if value:
                                    val_name = get_text(value)
                                    if val_name:
                                        add_reference(
                                            self._make_reference(
                                                val_name,
                                                "import",
                                                value,
                                                from_module=req_module,
                                            )
                                        )
                    elif name_node and name_node.type == "identifier":
                        # Simple: const x = require('module')
                        binding_name = get_text(name_node)
                        if binding_name:
                            add_reference(
                                self._make_reference(
                                    binding_name,
                                    "import",
                                    name_node,
                                    from_module=req_module,
                                )
                            )

            # Bare identifier usage — identifiers not already covered by other
            # patterns (call targets, member access, imports, declarations, etc.)
            if node.type == "identifier":
                ident_name = get_text(node)
                # Filter out noise
                if len(ident_name) > 1 and ident_name not in TS_BUILTINS:
                    parent = node.parent
                    # Skip identifiers that are already handled by other patterns:
                    # - call_expression function target → handled as "call"
                    # - new_expression constructor → handled as "instantiation"
                    # - member_expression property → handled as "usage"
                    # - import nodes → handled as "import"
                    # - declarations (variable_declarator name, function name, etc.)
                    # - class/interface/enum/type declarations
                    # - formal_parameters / required_parameter / optional_parameter
                    # - shorthand_property_identifier_pattern (destructuring)
                    # - for..of / for..in variable bindings
                    skip_ident = False
                    if parent is not None:
                        # Declaration contexts — the identifier IS being declared
                        if parent.type in (
                            "variable_declarator",
                            "function_declaration",
                            "class_declaration",
                            "interface_declaration",
                            "enum_declaration",
                            "type_alias_declaration",
                            "import_specifier",
                            "import_clause",
                            "required_parameter",
                            "optional_parameter",
                            "formal_parameters",
                            "catch_clause",
                        ):
                            # In variable_declarator, skip identifiers in
                            # the name subtree (including destructuring patterns)
                            if parent.type == "variable_declarator":
                                name_child = parent.child_by_field_name("name")
                                skip_ident = name_child is not None and (
                                    name_child.id == node.id
                                )
                            else:
                                skip_ident = True
                        # Destructuring binding patterns inside variable_declarator
                        # name subtree (e.g., const { a, b } = obj or const [x] = arr)
                        elif parent.type in (
                            "object_pattern",
                            "array_pattern",
                        ):
                            # Walk ancestors to check if inside a binding context
                            ancestor = parent
                            while ancestor is not None:
                                if ancestor.type == "variable_declarator":
                                    name_child = ancestor.child_by_field_name("name")
                                    if name_child is not None:
                                        skip_ident = True
                                    break
                                if ancestor.type in (
                                    "required_parameter",
                                    "optional_parameter",
                                ):
                                    skip_ident = True
                                    break
                                ancestor = ancestor.parent
                        # Call target — already handled as "call"
                        elif parent.type == "call_expression":
                            func = parent.child_by_field_name("function")
                            skip_ident = func is not None and func.id == node.id
                        # new expression constructor — already handled
                        elif parent.type == "new_expression":
                            ctor = parent.child_by_field_name("constructor")
                            skip_ident = ctor is not None and ctor.id == node.id
                        # Member expression object — the object part (e.g.,
                        # `config` in `config.value`) is a bare usage, but
                        # the property part is handled by member_expression
                        elif parent.type == "member_expression":
                            prop = parent.child_by_field_name("property")
                            skip_ident = prop is not None and prop.id == node.id
                        # Property names in object literals — only skip key position
                        elif parent.type == "pair":
                            key_child = parent.child_by_field_name("key")
                            skip_ident = (
                                key_child is not None and key_child.id == node.id
                            )
                        elif parent.type == "property_assignment":
                            name_child = parent.child_by_field_name("name")
                            skip_ident = (
                                name_child is not None and name_child.id == node.id
                            )
                        # Method/field definitions (the name part)
                        elif parent.type in (
                            "method_definition",
                            "public_field_definition",
                        ):
                            skip_ident = True
                        # Destructuring binding patterns
                        elif parent.type in (
                            "shorthand_property_identifier_pattern",
                            "pair_pattern",
                        ):
                            skip_ident = True
                        # for..of / for..in loop variable binding (left position only)
                        elif parent.type in ("for_of_statement", "for_in_statement"):
                            left = parent.child_by_field_name("left")
                            skip_ident = left is not None and left.id == node.id
                        # Label identifiers
                        elif parent.type in (
                            "labeled_statement",
                            "break_statement",
                            "continue_statement",
                        ):
                            skip_ident = True
                    if not skip_ident:
                        add_reference(
                            self._make_reference(ident_name, "usage", node, scope)
                        )

            # Recurse
            for child in node.children:
                child_scope = scope
                if node.type in ("class_declaration", "class"):
                    if node.type == "class_declaration":
                        name = get_name_from_node(node)
                    else:
                        # Class expression — prefer the binding name so
                        # scope matches the indexed symbol name.
                        name = _class_expression_binding_name(node)
                        if not name:
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
            elif node.type == "expression_statement":
                # Handle module.exports = class ..., exports.X = class ..., etc.
                for child in node.children:
                    if child.type == "assignment_expression":
                        _process_assignment_expression(child)
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
