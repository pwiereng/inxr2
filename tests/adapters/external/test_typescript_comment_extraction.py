"""Tests for TypeScript/JavaScript comment extraction."""

import pytest

from inxr2.adapters.external.treesitter import TreeSitterService


class TestTypeScriptCommentExtraction:
    """Tests for extracting comments from TypeScript code."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_extract_single_line_comments(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test extracting single-line comments."""
        code = """
// This is a single-line comment
function hello() {
    // Comment inside function
    console.log("hello");
    const x = 42; // Comment after code
}
"""
        comments = await parser_service.extract_comments(
            content=code, language="typescript", file_path="test.ts"
        )

        # Should find 3 comments
        assert len(comments) == 3

        # First comment
        assert comments[0].content == "This is a single-line comment"
        assert comments[0].content_type == "single_line_comment"
        assert comments[0].source_line == 2

        # Second comment
        assert comments[1].content == "Comment inside function"
        assert comments[1].content_type == "single_line_comment"
        assert comments[1].source_line == 4

        # Third comment
        assert comments[2].content == "Comment after code"
        assert comments[2].content_type == "single_line_comment"
        assert comments[2].source_line == 6

    @pytest.mark.asyncio
    async def test_extract_multi_line_comments(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test extracting multi-line comments."""
        code = """
/*
 * This is a multi-line comment.
 * It spans multiple lines.
 */
function foo() {
    /* Inline block comment */
    return 42;
}
"""
        comments = await parser_service.extract_comments(
            content=code, language="typescript", file_path="test.ts"
        )

        # Should find 2 block comments
        block_comments = [c for c in comments if c.content_type == "block_comment"]
        assert len(block_comments) == 2

        # Multi-line block comment
        multi_line = [c for c in block_comments if "spans multiple lines" in c.content]
        assert len(multi_line) == 1
        assert multi_line[0].source_line == 2
        assert multi_line[0].source_end_line is not None
        assert multi_line[0].source_end_line >= 4

        # Inline block comment
        inline = [c for c in block_comments if "Inline block comment" in c.content]
        assert len(inline) == 1
        assert inline[0].source_line == 7

    @pytest.mark.asyncio
    async def test_extract_jsdoc_comments(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test extracting JSDoc comments."""
        code = """
/**
 * Function description.
 * @param x - The parameter
 * @returns The result
 */
function add(x: number): number {
    return x + 1;
}

/**
 * Class description.
 */
class MyClass {
    /** Property description. */
    value: number;
}
"""
        comments = await parser_service.extract_comments(
            content=code, language="typescript", file_path="test.ts"
        )

        # Should find 3 JSDoc comments
        jsdoc = [c for c in comments if c.content_type == "jsdoc_comment"]
        assert len(jsdoc) == 3

        # Function JSDoc
        func_doc = [c for c in jsdoc if "Function description" in c.content]
        assert len(func_doc) == 1
        assert "@param" in func_doc[0].content
        assert "@returns" in func_doc[0].content
        assert func_doc[0].source_line == 2

        # Class JSDoc
        class_doc = [c for c in jsdoc if "Class description" in c.content]
        assert len(class_doc) == 1
        assert class_doc[0].source_line == 11

        # Property JSDoc
        prop_doc = [c for c in jsdoc if "Property description" in c.content]
        assert len(prop_doc) == 1
        assert prop_doc[0].source_line == 15

    @pytest.mark.asyncio
    async def test_strip_comment_markers(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test that comment markers are stripped."""
        code = """
// Single line comment
/* Block comment */
/** JSDoc comment */
"""
        comments = await parser_service.extract_comments(
            content=code, language="typescript", file_path="test.ts"
        )

        # Comments should not contain //, /*, */, /**
        for comment in comments:
            assert not comment.content.startswith("//")
            assert not comment.content.startswith("/*")
            assert not comment.content.endswith("*/")
            assert not comment.content.startswith("/**")

    @pytest.mark.asyncio
    async def test_javascript_comments(self, parser_service: TreeSitterService) -> None:
        """Test that JavaScript comments are extracted the same way."""
        code = """
// JavaScript single-line comment
/* JavaScript block comment */
function hello() {
    return "hello";
}
"""
        comments = await parser_service.extract_comments(
            content=code, language="javascript", file_path="test.js"
        )

        # Should find 2 comments
        assert len(comments) == 2

        assert comments[0].content == "JavaScript single-line comment"
        assert comments[0].content_type == "single_line_comment"

        assert comments[1].content == "JavaScript block comment"
        assert comments[1].content_type == "block_comment"


class TestJavaCommentExtraction:
    """Tests for extracting comments from Java code."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_extract_java_comments(
        self, parser_service: TreeSitterService
    ) -> None:
        """Test extracting Java comments."""
        code = """
// Single-line comment
/*
 * Multi-line comment
 */
/**
 * Javadoc comment
 */
public class MyClass {
    public void method() {
        // Comment in method
    }
}
"""
        comments = await parser_service.extract_comments(
            content=code, language="java", file_path="Test.java"
        )

        # Should find at least 3 comments
        assert len(comments) >= 3

        # Single-line
        single_line = [c for c in comments if c.content_type == "single_line_comment"]
        assert len(single_line) >= 2

        # Block comments
        block = [
            c
            for c in comments
            if c.content_type in ("block_comment", "javadoc_comment")
        ]
        assert len(block) >= 2


class TestCCommentExtraction:
    """Tests for extracting comments from C code."""

    @pytest.fixture
    def parser_service(self) -> TreeSitterService:
        """Create a TreeSitterService instance."""
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_extract_c_comments(self, parser_service: TreeSitterService) -> None:
        """Test extracting C comments."""
        code = """
// C single-line comment
/*
 * C multi-line comment
 */
int main() {
    // Comment in function
    return 0;
}
"""
        comments = await parser_service.extract_comments(
            content=code, language="c", file_path="test.c"
        )

        # Should find at least 3 comments
        assert len(comments) >= 3

        # Single-line
        single_line = [c for c in comments if c.content_type == "single_line_comment"]
        assert len(single_line) >= 2

        # Block comment
        block = [c for c in comments if c.content_type == "block_comment"]
        assert len(block) >= 1
