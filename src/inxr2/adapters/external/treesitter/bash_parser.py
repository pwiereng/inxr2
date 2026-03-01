"""Bash/Shell script language parser using Tree-sitter."""

from typing import Any

from tree_sitter import Node

from .base import BaseLanguageParser
from .builtins import _load

BASH_BUILTINS = _load("bash.json", "builtins")

# Special variable names that should not generate references.
# Positional params ($1, $2, ...) are filtered by checking str.isdigit().
_SPECIAL_VARS = {"@", "#", "?", "$", "!", "*", "-", "_", "0"}


class BashParser(BaseLanguageParser):
    """Parser for Bash/Shell source code using Tree-sitter."""

    @property
    def language_name(self) -> str:
        return "bash"

    def extract(
        self,
        root: Node,
        content: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract symbols and references from Bash AST."""
        symbols: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []

        def get_text(node: Node) -> str:
            return self._get_text(node, content)

        def add_reference(ref: dict[str, Any]) -> None:
            self._add_reference(ref, references)

        def is_builtin(name: str) -> bool:
            return name in BASH_BUILTINS

        # ---- Symbol extraction helpers ----

        def process_function(node: Node) -> None:
            """Process a function_definition node."""
            func_name = None
            name_node = None

            for child in node.children:
                if child.type == "word":
                    func_name = get_text(child)
                    name_node = child
                    break

            if not func_name:
                return

            symbols.append(
                self._make_symbol(
                    func_name,
                    "function",
                    name_node or node,
                    None,
                    end_line=node.end_point[0] + 1,
                    end_column=node.end_point[1],
                )
            )

        def process_variable_assignment(node: Node, scope: str | None) -> None:
            """Process a top-level variable_assignment node."""
            for child in node.children:
                if child.type == "variable_name":
                    var_name = get_text(child)
                    symbols.append(
                        self._make_symbol(var_name, "variable", child, scope)
                    )
                    return

        def _resolve_decl_kind(keyword: str | None, has_readonly_flag: bool) -> str:
            """Determine symbol kind for a declaration."""
            if keyword == "readonly" or has_readonly_flag:
                return "constant"
            return "variable"

        def process_declaration(node: Node, scope: str | None) -> None:
            """Process a declaration_command (export, readonly, local, declare)."""
            keyword = None
            has_readonly_flag = False

            for child in node.children:
                if child.type in ("export", "readonly", "local", "declare"):
                    keyword = child.type
                elif child.type == "word":
                    word_text = get_text(child)
                    # Check for flags containing -r (readonly), e.g. -r, -rx, -ar
                    if word_text.startswith("-") and "r" in word_text[1:]:
                        has_readonly_flag = True
                elif child.type == "variable_name":
                    # Bare declaration (e.g. "export FOO", "readonly BAR")
                    kind = _resolve_decl_kind(keyword, has_readonly_flag)
                    var_name = get_text(child)
                    symbols.append(self._make_symbol(var_name, kind, child, scope))
                elif child.type == "variable_assignment":
                    kind = _resolve_decl_kind(keyword, has_readonly_flag)
                    for vc in child.children:
                        if vc.type == "variable_name":
                            var_name = get_text(vc)
                            symbols.append(self._make_symbol(var_name, kind, vc, scope))
                            break

        # ---- Reference extraction ----

        def extract_references(node: Node, scope: str | None = None) -> None:
            """Recursively extract references from the AST."""
            if node.type == "simple_expansion":
                _process_simple_expansion(node, scope)
                return

            if node.type == "expansion":
                _process_expansion(node, scope)
                return

            if node.type == "command":
                _process_command(node, scope)
                # Still recurse into command children for variable refs
                for child in node.children:
                    if child.type != "command_name":
                        extract_references(child, scope)
                return

            # Update scope when entering a function body
            child_scope = scope
            if node.type == "function_definition":
                for child in node.children:
                    if child.type == "word":
                        func_name = get_text(child)
                        child_scope = func_name
                        break

            for child in node.children:
                extract_references(child, child_scope)

        def _process_simple_expansion(node: Node, scope: str | None) -> None:
            """Handle $VAR references (simple_expansion nodes)."""
            for child in node.children:
                if child.type == "special_variable_name":
                    # Skip $@, $#, $?, $$, $!, $*, $-, $_
                    return
                if child.type == "variable_name":
                    var_name = get_text(child)
                    # Skip positional parameters ($0, $1, $2, ...)
                    if var_name.isdigit() or var_name in _SPECIAL_VARS:
                        return
                    add_reference(self._make_reference(var_name, "usage", child, scope))
                    return

        def _process_expansion(node: Node, scope: str | None) -> None:
            """Handle ${VAR} and ${VAR:-default} references (expansion nodes)."""
            for child in node.children:
                if child.type == "variable_name":
                    var_name = get_text(child)
                    if var_name.isdigit() or var_name in _SPECIAL_VARS:
                        return
                    add_reference(self._make_reference(var_name, "usage", child, scope))
                    return
                if child.type == "special_variable_name":
                    return

        def _process_command(node: Node, scope: str | None) -> None:
            """Handle command nodes for call and import references."""
            cmd_name = None
            cmd_name_node = None

            for child in node.children:
                if child.type == "command_name":
                    for wc in child.children:
                        if wc.type == "word":
                            cmd_name = get_text(wc)
                            cmd_name_node = wc
                            break
                    break

            if not cmd_name or not cmd_name_node:
                return

            # source ./file.sh or . ./file.sh → import reference
            if cmd_name in ("source", "."):
                _process_source_import(node, cmd_name_node, scope)
                return

            # Skip builtins
            if is_builtin(cmd_name):
                return

            # Regular command call
            add_reference(self._make_reference(cmd_name, "call", cmd_name_node, scope))

        def _process_source_import(
            node: Node, cmd_node: Node, scope: str | None
        ) -> None:
            """Extract import reference from source/. commands."""
            for child in node.children:
                if child.type == "word" and child is not cmd_node:
                    # The first word child that isn't the command name is the path
                    import_path = get_text(child)
                    add_reference(
                        self._make_reference(import_path, "import", child, scope)
                    )
                    return
                if child.type == "string":
                    # source "path/to/file.sh"
                    for sc in child.children:
                        if sc.type == "string_content":
                            import_path = get_text(sc)
                            add_reference(
                                self._make_reference(import_path, "import", sc, scope)
                            )
                            return

        # ---- Main processing ----

        # First pass: extract symbols from top-level and function bodies
        for child in root.children:
            if child.type == "function_definition":
                process_function(child)
                # Also extract local declarations inside the function body
                _extract_function_locals(child, symbols, content)
            elif child.type == "variable_assignment":
                process_variable_assignment(child, None)
            elif child.type == "declaration_command":
                process_declaration(child, None)

        # Second pass: extract references
        extract_references(root)

        return symbols, references

    def _process_comment_node(self, node: Node, content: str) -> dict[str, Any] | None:
        """Classify and clean a Bash comment node."""
        if node.type == "comment":
            text = self._get_text(node, content)
            if text.startswith("#"):
                cleaned = text[1:].strip()
                if not cleaned:
                    return None
                return {
                    "content": cleaned,
                    "content_type": "single_line_comment",
                    "source_line": node.start_point[0] + 1,
                    "source_end_line": node.end_point[0] + 1,
                }
        return None


def _extract_function_locals(
    func_node: Node,
    symbols: list[dict[str, Any]],
    content: str,
) -> None:
    """Walk a function body to extract local/declare variable declarations."""
    parser = BashParser()

    for child in func_node.children:
        if child.type == "compound_statement":
            _walk_for_locals(child, func_node, symbols, parser, content)


def _walk_for_locals(
    node: Node,
    func_node: Node,
    symbols: list[dict[str, Any]],
    parser: BashParser,
    content: str,
) -> None:
    """Recursively walk a function body for local/declare declarations."""
    # Determine function name for scope
    func_name = None
    for child in func_node.children:
        if child.type == "word":
            func_name = parser._get_text(child, content)
            break

    for child in node.children:
        if child.type == "declaration_command":
            has_readonly_flag = False
            for dc in child.children:
                if dc.type in ("local", "declare"):
                    pass  # recognised keyword, no action needed
                elif dc.type == "word":
                    word_text = parser._get_text(dc, content)
                    if word_text.startswith("-") and "r" in word_text[1:]:
                        has_readonly_flag = True
                elif dc.type == "variable_assignment":
                    kind = "constant" if has_readonly_flag else "variable"
                    for vc in dc.children:
                        if vc.type == "variable_name":
                            var_name = parser._get_text(vc, content)
                            symbols.append(
                                parser._make_symbol(var_name, kind, vc, func_name)
                            )
                            break
        # Recurse into nested blocks (if/for/while inside function)
        elif child.type in (
            "if_statement",
            "for_statement",
            "while_statement",
            "case_statement",
            "compound_statement",
        ):
            _walk_for_locals(child, func_node, symbols, parser, content)
