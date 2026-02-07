"""Tests for Python comment extraction."""

import pytest

from inxr2.adapters.external.treesitter import TreeSitterService


class TestPythonCommentExtraction:
    """Tests for extracting comments from Python code."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_extract_inline_comment(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test extracting inline comments."""
        code = """
# This is a module-level comment
def hello():
    # This is an inline comment
    print("hello")
    x = 42  # Comment after code
"""
        comments = await parser_service.extract_comments(
            content=code, language="python", file_path="test.py"
        )

        # Should find 3 comments
        assert len(comments) == 3

        # First comment - module level
        assert comments[0]["content"] == "This is a module-level comment"
        assert comments[0]["content_type"] == "inline_comment"
        assert comments[0]["source_line"] == 2

        # Second comment - inside function
        assert comments[1]["content"] == "This is an inline comment"
        assert comments[1]["content_type"] == "inline_comment"
        assert comments[1]["source_line"] == 4

        # Third comment - after code
        assert comments[2]["content"] == "Comment after code"
        assert comments[2]["content_type"] == "inline_comment"
        assert comments[2]["source_line"] == 6

    @pytest.mark.asyncio
    async def test_extract_docstrings(self, parser_service: TreeSitterService) -> None:
        """Test extracting docstrings."""
        code = '''
"""Module docstring."""

def function_with_docstring():
    """Function docstring."""
    pass

class MyClass:
    """Class docstring."""

    def method(self):
        """Method docstring."""
        pass
'''
        comments = await parser_service.extract_comments(
            content=code, language="python", file_path="test.py"
        )

        # Should find 4 docstrings
        docstrings = [c for c in comments if c["content_type"] == "docstring"]
        assert len(docstrings) == 4

        # Module docstring
        module_doc = [c for c in docstrings if c["content"] == "Module docstring."]
        assert len(module_doc) == 1
        assert module_doc[0]["source_line"] == 2

        # Function docstring
        func_doc = [c for c in docstrings if c["content"] == "Function docstring."]
        assert len(func_doc) == 1
        assert func_doc[0]["source_line"] == 5

        # Class docstring
        class_doc = [c for c in docstrings if c["content"] == "Class docstring."]
        assert len(class_doc) == 1
        assert class_doc[0]["source_line"] == 9

        # Method docstring
        method_doc = [c for c in docstrings if c["content"] == "Method docstring."]
        assert len(method_doc) == 1
        assert method_doc[0]["source_line"] == 12

    @pytest.mark.asyncio
    async def test_extract_multiline_comments(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test extracting multi-line comments."""
        code = """
# Line 1
# Line 2
# Line 3

def foo():
    # Multi-line comment
    # in a function
    pass
"""
        comments = await parser_service.extract_comments(
            content=code, language="python", file_path="test.py"
        )

        # Each line is a separate inline comment
        assert len(comments) >= 5

        inline = [c for c in comments if c["content_type"] == "inline_comment"]
        assert len(inline) >= 5

    @pytest.mark.asyncio
    async def test_strip_comment_markers(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that comment markers are stripped."""
        code = '''
# This is a comment
"""This is a docstring"""
'''
        comments = await parser_service.extract_comments(
            content=code, language="python", file_path="test.py"
        )

        # Comments should not contain # or """
        for comment in comments:
            assert not comment["content"].startswith("#")
            assert not comment["content"].startswith('"""')
            assert not comment["content"].endswith('"""')
            assert not comment["content"].startswith("'''")
            assert not comment["content"].endswith("'''")

    @pytest.mark.asyncio
    async def test_skip_shebangs(self, parser_service: TreeSitterService) -> None:
        """Test that shebangs are not extracted as comments."""
        code = """#!/usr/bin/env python
# This is a real comment
def foo():
    pass
"""
        comments = await parser_service.extract_comments(
            content=code, language="python", file_path="test.py"
        )

        # Should only find the real comment, not the shebang
        assert len(comments) == 1
        assert comments[0]["content"] == "This is a real comment"

    @pytest.mark.asyncio
    async def test_skip_encoding_declarations(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that encoding declarations are not extracted."""
        code = """# -*- coding: utf-8 -*-
# This is a real comment
def foo():
    pass
"""
        comments = await parser_service.extract_comments(
            content=code, language="python", file_path="test.py"
        )

        # Should skip encoding declaration
        encoding_comments = [
            c for c in comments if "coding" in c["content"] and "utf-8" in c["content"]
        ]
        assert len(encoding_comments) == 0

    @pytest.mark.asyncio
    async def test_multiline_docstring(self, parser_service: TreeSitterService) -> None:
        """Test extracting multi-line docstrings."""
        code = '''
def complex_function():
    """
    This is a multi-line docstring.

    It has multiple paragraphs.
    And even blank lines.
    """
    pass
'''
        comments = await parser_service.extract_comments(
            content=code, language="python", file_path="test.py"
        )

        docstrings = [c for c in comments if c["content_type"] == "docstring"]
        assert len(docstrings) == 1

        # Should capture full docstring
        content = docstrings[0]["content"]
        assert "multi-line docstring" in content
        assert "multiple paragraphs" in content

        # Should have start and end lines
        assert docstrings[0]["source_line"] == 3
        assert docstrings[0]["source_end_line"] >= 7

    @pytest.mark.asyncio
    async def test_string_not_first_statement_is_not_docstring(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that a string after other statements is NOT a docstring.

        This is a regression test for a bug where any string expression in a
        function/class was incorrectly extracted as a docstring.
        """
        code = '''
def foo():
    x = 1
    """This is NOT a docstring - it comes after a statement"""
    return x

class Bar:
    y = 2
    """Also NOT a docstring"""
    pass
'''
        comments = await parser_service.extract_comments(
            content=code, language="python", file_path="test.py"
        )

        # Should NOT find any docstrings since neither string is first
        docstrings = [c for c in comments if c["content_type"] == "docstring"]
        assert len(docstrings) == 0

    @pytest.mark.asyncio
    async def test_real_docstring_is_extracted(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that actual docstrings (first statements) are still extracted."""
        code = '''
def foo():
    """This IS a docstring - first statement."""
    x = 1
    return x

class Bar:
    """This IS a class docstring."""
    y = 2
'''
        comments = await parser_service.extract_comments(
            content=code, language="python", file_path="test.py"
        )

        docstrings = [c for c in comments if c["content_type"] == "docstring"]
        assert len(docstrings) == 2

        # Verify content
        assert any("This IS a docstring" in d["content"] for d in docstrings)
        assert any("This IS a class docstring" in d["content"] for d in docstrings)
