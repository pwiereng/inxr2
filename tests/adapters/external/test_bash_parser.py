"""Tests for Bash/Shell script language parser using Tree-sitter."""

import pytest

from inxr2.adapters.external.treesitter import TreeSitterService


class TestBashSupport:
    """Tests for Bash language support in TreeSitterService."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    def test_supports_bash(self, parser_service: TreeSitterService) -> None:
        """Test that Bash is supported case-insensitively."""
        assert parser_service.supports_language("bash")
        assert parser_service.supports_language("Bash")
        assert parser_service.supports_language("BASH")


class TestBashFunctionSymbols:
    """Tests for Bash function parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_function_keyword_definition(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing function with 'function' keyword."""
        code = """function greet() {
    echo "hello"
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        funcs = [s for s in symbols if s["kind"] == "function"]
        assert len(funcs) == 1
        assert funcs[0]["name"] == "greet"

    @pytest.mark.asyncio
    async def test_shorthand_function_definition(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing function with shorthand syntax."""
        code = """greet() {
    echo "hello"
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        funcs = [s for s in symbols if s["kind"] == "function"]
        assert len(funcs) == 1
        assert funcs[0]["name"] == "greet"

    @pytest.mark.asyncio
    async def test_multiple_functions(self, parser_service: TreeSitterService) -> None:
        """Test parsing multiple function definitions."""
        code = """function setup() {
    echo "setup"
}

teardown() {
    echo "teardown"
}

function run_tests() {
    echo "tests"
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        funcs = [s for s in symbols if s["kind"] == "function"]
        assert len(funcs) == 3
        names = {f["name"] for f in funcs}
        assert names == {"setup", "teardown", "run_tests"}

    @pytest.mark.asyncio
    async def test_function_has_end_line(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that function symbols include end_line for span tracking."""
        code = """function greet() {
    echo "line 1"
    echo "line 2"
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        funcs = [s for s in symbols if s["kind"] == "function"]
        assert len(funcs) == 1
        assert funcs[0]["start_line"] == 1
        assert funcs[0]["end_line"] == 4


class TestBashVariableSymbols:
    """Tests for Bash variable and constant parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_top_level_variable_assignment(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test parsing top-level variable assignments."""
        code = """MY_VAR="hello"
ANOTHER=42
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        variables = [s for s in symbols if s["kind"] == "variable"]
        names = {v["name"] for v in variables}
        assert "MY_VAR" in names
        assert "ANOTHER" in names

    @pytest.mark.asyncio
    async def test_readonly_is_constant(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that readonly declarations produce constant symbols."""
        code = "readonly MAX_RETRIES=3\n"
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        consts = [s for s in symbols if s["kind"] == "constant"]
        assert any(s["name"] == "MAX_RETRIES" for s in consts)

    @pytest.mark.asyncio
    async def test_export_variable(self, parser_service: TreeSitterService) -> None:
        """Test that export declarations produce variable symbols."""
        code = 'export PATH="/usr/bin:$PATH"\n'
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        variables = [s for s in symbols if s["name"] == "PATH"]
        assert len(variables) >= 1

    @pytest.mark.asyncio
    async def test_local_variable_in_function(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that local declarations inside functions are scoped."""
        code = """function greet() {
    local name="world"
    echo "$name"
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        locals_ = [
            s for s in symbols if s["kind"] == "variable" and s["name"] == "name"
        ]
        assert len(locals_) == 1
        assert locals_[0]["scope"] == "greet"

    @pytest.mark.asyncio
    async def test_declare_r_is_constant(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that declare -r produces a constant symbol."""
        code = "declare -r CONST_VAR=100\n"
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        consts = [s for s in symbols if s["kind"] == "constant"]
        assert any(s["name"] == "CONST_VAR" for s in consts)

    @pytest.mark.asyncio
    async def test_declare_x_is_variable(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that declare -x produces a variable symbol."""
        code = "declare -x EXPORTED=yes\n"
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        variables = [s for s in symbols if s["kind"] == "variable"]
        assert any(s["name"] == "EXPORTED" for s in variables)

    @pytest.mark.asyncio
    async def test_multi_variable_export(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that export A=1 B=2 captures both variables."""
        code = "export A=1 B=2\n"
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        names = {s["name"] for s in symbols if s["kind"] == "variable"}
        assert "A" in names
        assert "B" in names

    @pytest.mark.asyncio
    async def test_multi_variable_readonly(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that readonly X=1 Y=2 captures both as constants."""
        code = "readonly X=1 Y=2\n"
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        consts = {s["name"] for s in symbols if s["kind"] == "constant"}
        assert "X" in consts
        assert "Y" in consts

    @pytest.mark.asyncio
    async def test_bare_export(self, parser_service: TreeSitterService) -> None:
        """Test that bare export FOO (no assignment) produces a variable symbol."""
        code = "export FOO\n"
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        names = {s["name"] for s in symbols if s["kind"] == "variable"}
        assert "FOO" in names

    @pytest.mark.asyncio
    async def test_bare_readonly(self, parser_service: TreeSitterService) -> None:
        """Test that bare readonly BAR produces a constant symbol."""
        code = "readonly BAR\n"
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        consts = {s["name"] for s in symbols if s["kind"] == "constant"}
        assert "BAR" in consts

    @pytest.mark.asyncio
    async def test_declare_combined_flags_rx(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that declare -rx produces a constant (combined flag with r)."""
        code = "declare -rx COMBO=1\n"
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        consts = {s["name"] for s in symbols if s["kind"] == "constant"}
        assert "COMBO" in consts

    @pytest.mark.asyncio
    async def test_local_readonly_is_constant(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that local -r inside a function produces a constant."""
        code = """function init() {
    local -r CONST_VAL=42
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        consts = [s for s in symbols if s["kind"] == "constant"]
        assert any(s["name"] == "CONST_VAL" for s in consts)


class TestBashReferences:
    """Tests for Bash reference extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_variable_expansion_simple(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test $VAR reference extraction."""
        code = """MY_VAR="hello"
echo $MY_VAR
"""
        _, refs = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        usage = [r for r in refs if r["text"] == "MY_VAR" and r["type"] == "usage"]
        assert len(usage) >= 1

    @pytest.mark.asyncio
    async def test_variable_expansion_braces(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test ${VAR} reference extraction."""
        code = """MY_VAR="hello"
echo "${MY_VAR}"
"""
        _, refs = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        usage = [r for r in refs if r["text"] == "MY_VAR" and r["type"] == "usage"]
        assert len(usage) >= 1

    @pytest.mark.asyncio
    async def test_variable_expansion_with_default(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test ${VAR:-default} reference extraction."""
        code = 'echo "${MY_VAR:-fallback}"\n'
        _, refs = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        usage = [r for r in refs if r["text"] == "MY_VAR" and r["type"] == "usage"]
        assert len(usage) == 1

    @pytest.mark.asyncio
    async def test_function_call_reference(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that calling a function generates a call reference."""
        code = """function greet() { echo "hi"; }
greet
"""
        _, refs = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        calls = [r for r in refs if r["text"] == "greet" and r["type"] == "call"]
        assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_source_import(self, parser_service: TreeSitterService) -> None:
        """Test source and . commands generate import references."""
        code = """source ./lib.sh
. ./utils.sh
"""
        _, refs = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        imports = [r for r in refs if r["type"] == "import"]
        assert len(imports) == 2
        import_texts = {r["text"] for r in imports}
        assert "./lib.sh" in import_texts
        assert "./utils.sh" in import_texts

    @pytest.mark.asyncio
    async def test_special_variables_skipped(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that special variables ($@, $#, $?, etc.) don't generate refs."""
        code = """echo $1 $2 $@ $# $?
"""
        _, refs = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        # None of these should produce usage references
        special = [
            r
            for r in refs
            if r["text"] in ("1", "2", "@", "#", "?", "$") and r["type"] == "usage"
        ]
        assert len(special) == 0

    @pytest.mark.asyncio
    async def test_builtin_commands_skipped(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that builtin commands don't generate call references."""
        code = """echo "hello"
cd /tmp
pwd
"""
        _, refs = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        builtins = [
            r
            for r in refs
            if r["text"] in ("echo", "cd", "pwd") and r["type"] == "call"
        ]
        assert len(builtins) == 0

    @pytest.mark.asyncio
    async def test_non_builtin_command_generates_call(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that non-builtin commands generate call references."""
        code = """my_custom_func arg1 arg2
"""
        _, refs = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        calls = [
            r for r in refs if r["text"] == "my_custom_func" and r["type"] == "call"
        ]
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_reference_scope_inside_function(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that references inside functions have the function as scope."""
        code = """function setup() {
    echo $CONFIG_PATH
}
"""
        _, refs = await parser_service.parse_file(
            content=code, language="bash", file_path="test.sh"
        )
        config_refs = [
            r for r in refs if r["text"] == "CONFIG_PATH" and r["type"] == "usage"
        ]
        assert len(config_refs) == 1
        assert config_refs[0].get("scope") == "setup"


class TestBashComments:
    """Tests for Bash comment extraction."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_single_line_comment(self, parser_service: TreeSitterService) -> None:
        """Test extracting a single-line comment."""
        code = """# This is a comment
MY_VAR=1
"""
        comments = await parser_service.extract_comments(
            content=code, language="bash", file_path="test.sh"
        )
        assert len(comments) >= 1
        assert any(c["content"] == "This is a comment" for c in comments)

    @pytest.mark.asyncio
    async def test_shebang_extracted_as_comment(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that shebang line is extracted as a comment."""
        code = """#!/bin/bash
echo "hello"
"""
        comments = await parser_service.extract_comments(
            content=code, language="bash", file_path="test.sh"
        )
        shebang = [c for c in comments if "bin/bash" in c["content"]]
        assert len(shebang) == 1

    @pytest.mark.asyncio
    async def test_empty_comment_filtered(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that empty comments are filtered out."""
        code = """#
# Real comment
#
"""
        comments = await parser_service.extract_comments(
            content=code, language="bash", file_path="test.sh"
        )
        assert all(c["content"] for c in comments)


class TestBashComplexStructures:
    """Tests for complex Bash scripts with mixed constructs."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_full_script(self, parser_service: TreeSitterService) -> None:
        """Test parsing a complete bash script with multiple constructs."""
        code = """#!/bin/bash

# Configuration
readonly CONFIG_DIR="/etc/myapp"
export LOG_LEVEL="info"
VERSION="1.0.0"

function log() {
    local level="$1"
    local message="$2"
    echo "[$level] $message"
}

setup() {
    source ./config.sh
    log "info" "Setting up..."
}

setup
"""
        symbols, refs = await parser_service.parse_file(
            content=code, language="bash", file_path="deploy.sh"
        )

        # Check symbols
        funcs = [s for s in symbols if s["kind"] == "function"]
        assert len(funcs) == 2
        func_names = {f["name"] for f in funcs}
        assert func_names == {"log", "setup"}

        consts = [s for s in symbols if s["kind"] == "constant"]
        assert any(s["name"] == "CONFIG_DIR" for s in consts)

        variables = [s for s in symbols if s["kind"] == "variable"]
        var_names = {v["name"] for v in variables}
        assert "LOG_LEVEL" in var_names
        assert "VERSION" in var_names

        # Check references
        imports = [r for r in refs if r["type"] == "import"]
        assert any(r["text"] == "./config.sh" for r in imports)

        calls = [r for r in refs if r["type"] == "call"]
        call_names = {c["text"] for c in calls}
        assert "log" in call_names
        assert "setup" in call_names


class TestBashEdgeCases:
    """Tests for edge cases in Bash parsing."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_empty_file(self, parser_service: TreeSitterService) -> None:
        """Test parsing an empty file."""
        symbols, refs = await parser_service.parse_file(
            content="", language="bash", file_path="empty.sh"
        )
        assert symbols == []
        assert refs == []

    @pytest.mark.asyncio
    async def test_only_comments(self, parser_service: TreeSitterService) -> None:
        """Test parsing a file with only comments."""
        code = """#!/bin/bash
# Just a comment
# Another comment
"""
        symbols, refs = await parser_service.parse_file(
            content=code, language="bash", file_path="comments.sh"
        )
        assert symbols == []
        assert refs == []

    @pytest.mark.asyncio
    async def test_bash_extension(self, parser_service: TreeSitterService) -> None:
        """Test parsing with .bash extension."""
        code = """function hello() {
    echo "world"
}
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="bash", file_path="script.bash"
        )
        funcs = [s for s in symbols if s["kind"] == "function"]
        assert len(funcs) == 1
        assert funcs[0]["name"] == "hello"
