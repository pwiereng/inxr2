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
        names = [s.name for s in symbols]
        assert "MAX_RETRIES" in names
        const = next(s for s in symbols if s.name == "MAX_RETRIES")
        assert const.kind == "constant"

    @pytest.mark.asyncio
    async def test_captures_private_constant_with_underscore_prefix(
        self, parser_service: TreeSitterService
    ) -> None:
        """Regression test for issue #358: _UPPER_CASE constants not clickable."""
        code = "_STD_LIB_PREFIXES = ['os', 'sys']\n"
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        names = [s.name for s in symbols]
        assert "_STD_LIB_PREFIXES" in names
        const = next(s for s in symbols if s.name == "_STD_LIB_PREFIXES")
        assert const.kind == "constant"

    @pytest.mark.asyncio
    async def test_does_not_capture_lowercase_module_variable(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "logger = logging.getLogger(__name__)\n"
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        names = [s.name for s in symbols]
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
        names = [s.name for s in symbols]
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
        ref_names = [r.reference_text for r in references]
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
        ref_names = [r.reference_text for r in references]
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
            if r.reference_text == "MY_CONST" and r.reference_type == "usage"
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
        call_refs = [r for r in references if r.reference_text == "my_function"]
        # Should appear exactly once (as a call), not also as a plain usage
        assert len(call_refs) == 1
        assert call_refs[0].reference_type == "call"

    @pytest.mark.asyncio
    async def test_does_not_duplicate_type_annotation_references(
        self, parser_service: TreeSitterService
    ) -> None:
        """Type annotation identifiers must not also emit a plain usage reference."""
        code = "def foo(x: MyType) -> ReturnType:\n    pass\n"
        _, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        my_type_refs = [r for r in references if r.reference_text == "MyType"]
        return_type_refs = [r for r in references if r.reference_text == "ReturnType"]
        # Each type name should appear exactly once, as type_annotation only
        assert len(my_type_refs) == 1
        assert my_type_refs[0].reference_type == "type_annotation"
        assert len(return_type_refs) == 1
        assert return_type_refs[0].reference_type == "type_annotation"

    @pytest.mark.asyncio
    async def test_does_not_capture_self_or_cls_as_usage(
        self, parser_service: TreeSitterService
    ) -> None:
        """self and cls must not emit plain usage references."""
        code = """\
class Foo:
    def method(self):
        do_something(self)
        return self

    @classmethod
    def create(cls):
        return cls
"""
        _, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        self_refs = [
            r for r in references if r.reference_text == "self" and r.reference_type == "usage"
        ]
        cls_refs = [
            r for r in references if r.reference_text == "cls" and r.reference_type == "usage"
        ]
        assert len(self_refs) == 0
        assert len(cls_refs) == 0

    @pytest.mark.asyncio
    async def test_does_not_capture_tuple_comprehension_loop_vars(
        self, parser_service: TreeSitterService
    ) -> None:
        """Tuple-unpacking comprehension loop variables must not be captured as usages."""
        code = """\
PAIRS = [(1, 2), (3, 4)]

def process():
    return [a + b for a, b in PAIRS]
"""
        _, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        # Lowercase loop variables (a, b) must not appear as usage refs at all —
        # the plain identifier handler only captures UPPER_CASE constant patterns.
        a_usage_refs = [
            r for r in references if r.reference_text == "a" and r.reference_type == "usage"
        ]
        b_usage_refs = [
            r for r in references if r.reference_text == "b" and r.reference_type == "usage"
        ]
        assert len(a_usage_refs) == 0
        assert len(b_usage_refs) == 0

    @pytest.mark.asyncio
    async def test_does_not_capture_local_variables_as_usage(
        self, parser_service: TreeSitterService
    ) -> None:
        """Regression test for #363: plain identifier handler must not capture
        local variables as usage refs.

        Before the fix, the handler emitted a usage ref for every identifier read
        (e.g. `result`, `item`, `config`) which flooded the reference table with
        unresolvable entries and dropped inxr/master resolution rate from 37.1% to 28.5%.
        Only UPPER_CASE constant-pattern names (e.g. MY_CONST, _STD_LIB_PREFIXES)
        should be emitted.
        """
        code = """\
def process(config):
    result = do_something(config)
    for item in result:
        process_item(item)
    return result
"""
        _, references = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        usage_names = {r.reference_text for r in references if r.reference_type == "usage"}
        assert "result" not in usage_names
        assert "item" not in usage_names
        assert "config" not in usage_names


class TestSymbolDocstrings:
    """Tests for docstring extraction onto symbol records (Issue #364)."""

    @pytest.mark.asyncio
    async def test_function_docstring_extracted(
        self, parser_service: TreeSitterService
    ) -> None:
        code = '''\
def greet(name):
    """Return a greeting for the given name."""
    return f"Hello, {name}"
'''
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        greet = next(s for s in symbols if s.name == "greet")
        assert greet.docstring == "Return a greeting for the given name."

    @pytest.mark.asyncio
    async def test_class_docstring_extracted(
        self, parser_service: TreeSitterService
    ) -> None:
        code = '''\
class MyClass:
    """A simple example class."""
    pass
'''
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        cls = next(s for s in symbols if s.name == "MyClass")
        assert cls.docstring == "A simple example class."

    @pytest.mark.asyncio
    async def test_method_docstring_extracted(
        self, parser_service: TreeSitterService
    ) -> None:
        code = '''\
class Greeter:
    def hello(self):
        """Say hello."""
        return "hello"
'''
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        method = next(s for s in symbols if s.name == "hello")
        assert method.docstring == "Say hello."

    @pytest.mark.asyncio
    async def test_no_docstring_symbol_has_none(
        self, parser_service: TreeSitterService
    ) -> None:
        code = "def no_doc():\n    return 42\n"
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        func = next(s for s in symbols if s.name == "no_doc")
        assert func.docstring is None

    @pytest.mark.asyncio
    async def test_multiline_docstring_extracted(
        self, parser_service: TreeSitterService
    ) -> None:
        code = '''\
def complex_func():
    """
    This is a longer docstring
    that spans multiple lines.
    """
    pass
'''
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        func = next(s for s in symbols if s.name == "complex_func")
        assert func.docstring is not None
        assert func.docstring is not None and "longer docstring" in func.docstring
        assert func.docstring is not None and "multiple lines" in func.docstring

    @pytest.mark.asyncio
    async def test_decorated_function_docstring_extracted(
        self, parser_service: TreeSitterService
    ) -> None:
        code = '''\
def decorator(f):
    return f

@decorator
def decorated():
    """Decorated function docstring."""
    pass
'''
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        func = next(s for s in symbols if s.name == "decorated")
        assert func.docstring == "Decorated function docstring."

    @pytest.mark.asyncio
    async def test_nested_function_docstring_extracted(
        self, parser_service: TreeSitterService
    ) -> None:
        code = '''\
def outer():
    """Outer docstring."""
    def inner():
        """Inner docstring."""
        pass
'''
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        inner = next(s for s in symbols if s.name == "inner")
        assert inner.docstring == "Inner docstring."

    @pytest.mark.asyncio
    async def test_docstring_still_in_text_contents(
        self, parser_service: TreeSitterService
    ) -> None:
        """Docstrings must remain in text_contents for full-text search."""
        code = '''\
def my_func():
    """This docstring should appear in comments too."""
    pass
'''
        symbols, _ = await parser_service.parse_file(
            content=code, language="python", file_path="test.py"
        )
        comments = await parser_service.extract_comments(
            content=code, language="python", file_path="test.py"
        )
        func = next(s for s in symbols if s.name == "my_func")
        assert func.docstring == "This docstring should appear in comments too."
        docstring_comments = [
            c for c in comments if c.content_type == "docstring"
        ]
        assert len(docstring_comments) == 1
        assert (
            "This docstring should appear in comments too."
            in docstring_comments[0].content
        )
