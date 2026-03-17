"""Tests for Python language parser symbol extraction."""

import pytest

from inxr2.adapters.external.treesitter import TreeSitterService


@pytest.fixture
def parser_service() -> TreeSitterService:
    return TreeSitterService()


class TestModuleLevelConstants:
    """Tests for module-level constant symbol extraction."""

    @pytest.mark.asyncio
    async def test_captures_public_constant(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "MAX_RETRIES = 3\n"
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        names = [s["name"] for s in symbols]
        assert "MAX_RETRIES" in names
        const = next(s for s in symbols if s["name"] == "MAX_RETRIES")
        assert const["kind"] == "constant"

    @pytest.mark.asyncio
    async def test_captures_private_constant_with_underscore_prefix(
        self, parser_service: TreeSitterService
    ) -> None:
        """Regression test for issue #358: _UPPER_CASE constants not clickable."""
        code = "_STD_LIB_PREFIXES = ['os', 'sys']\n"
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        names = [s["name"] for s in symbols]
        assert "_STD_LIB_PREFIXES" in names
        const = next(s for s in symbols if s["name"] == "_STD_LIB_PREFIXES")
        assert const["kind"] == "constant"

    @pytest.mark.asyncio
    async def test_does_not_capture_lowercase_module_variable(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "logger = logging.getLogger(__name__)\n"
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        names = [s["name"] for s in symbols]
        assert "logger" not in names

    @pytest.mark.asyncio
    async def test_captures_multiple_constants_mixed(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """\
MAX_SIZE = 100
_INTERNAL_LIMIT = 50
some_variable = "hello"
"""
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        names = [s["name"] for s in symbols]
        assert "MAX_SIZE" in names
        assert "_INTERNAL_LIMIT" in names
        assert "some_variable" not in names


class TestPlainIdentifierReferences:
    """Tests for plain variable usage reference extraction."""

    @pytest.mark.asyncio
    async def test_captures_constant_used_in_membership_test(
        self, parser_service: TreeSitterService
    ) -> None:
        """Regression test for issue #358: usages of _UPPER_CASE constants not captured."""
        code = """\
_STD_LIB_PREFIXES = ['os', 'sys']

def is_std(name):
    return name in _STD_LIB_PREFIXES
"""
        _, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        ref_names = [r["text"] for r in references]
        assert "_STD_LIB_PREFIXES" in ref_names

    @pytest.mark.asyncio
    async def test_captures_constant_used_as_argument(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """\
MY_LIST = [1, 2, 3]

def process():
    result = sorted(MY_LIST)
    return result
"""
        _, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        ref_names = [r["text"] for r in references]
        assert "MY_LIST" in ref_names

    @pytest.mark.asyncio
    async def test_does_not_capture_write_target_as_reference(
        self, parser_service: TreeSitterService
    ) -> None:
        code = """\
MY_CONST = 42

def foo():
    MY_CONST = 99
"""
        _, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        # The reassignment inside foo is a write, not a usage reference
        usage_refs = [
            r
            for r in references
            if r["text"] == "MY_CONST" and r.get("type") == "usage"
        ]
        assert len(usage_refs) == 0

    @pytest.mark.asyncio
    async def test_does_not_duplicate_call_references(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "result = my_function()\n"
        _, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        call_refs = [r for r in references if r["text"] == "my_function"]
        # Should appear exactly once (as a call), not also as a plain usage
        assert len(call_refs) == 1
        assert call_refs[0]["type"] == "call"
