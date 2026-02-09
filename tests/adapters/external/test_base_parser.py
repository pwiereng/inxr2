"""Tests for base tree-sitter parser helper methods."""

from typing import Any, cast

import pytest
from tree_sitter import Node

from inxr2.adapters.external.treesitter.base import BaseLanguageParser


class FakeNode:
    """Minimal fake Node for testing without tree-sitter dependencies."""

    def __init__(
        self,
        start_line: int,
        start_column: int,
        end_line: int,
        end_column: int,
        start_byte: int = 0,
        end_byte: int = 10,
    ):
        self.start_point = (start_line - 1, start_column)  # tree-sitter uses 0-indexed
        self.end_point = (end_line - 1, end_column)
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.children: list[Any] = []


class ConcreteParser(BaseLanguageParser):
    """Minimal concrete implementation for testing base class methods."""

    @property
    def language_name(self) -> str:
        return "test"

    def extract(
        self, root: Any, content: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Not needed for base method testing."""
        return [], []


class TestMakeSymbol:
    """Tests for _make_symbol helper method."""

    @pytest.fixture
    def parser(self) -> ConcreteParser:
        """Create a parser instance."""
        return ConcreteParser()

    def test_make_symbol_without_scope(self, parser: ConcreteParser) -> None:
        """Test that symbol without scope has no qualified_name key."""
        node = FakeNode(start_line=10, start_column=4, end_line=15, end_column=8)
        result = parser._make_symbol(name="foo", kind="function", node=cast(Node, node))

        assert result["name"] == "foo"
        assert result["kind"] == "function"
        assert result["start_line"] == 10
        assert result["start_column"] == 4
        assert result["end_line"] == 15
        assert result["end_column"] == 8
        assert result["scope"] is None
        assert "qualified_name" not in result

    def test_make_symbol_with_scope(self, parser: ConcreteParser) -> None:
        """Test that symbol with scope auto-generates qualified_name."""
        node = FakeNode(start_line=20, start_column=8, end_line=25, end_column=12)
        result = parser._make_symbol(
            name="bar", kind="method", node=cast(Node, node), scope="MyClass"
        )

        assert result["name"] == "bar"
        assert result["kind"] == "method"
        assert result["scope"] == "MyClass"
        assert result["qualified_name"] == "MyClass.bar"

    def test_make_symbol_with_extra_override(self, parser: ConcreteParser) -> None:
        """Test that **extra overrides any field including location."""
        node = FakeNode(start_line=30, start_column=0, end_line=35, end_column=10)
        result = parser._make_symbol(
            name="baz",
            kind="class",
            node=cast(Node, node),
            scope="Module",
            end_line=999,  # Override location
            metadata={"custom": "value"},
        )

        assert result["name"] == "baz"
        assert result["kind"] == "class"
        assert result["start_line"] == 30
        assert result["end_line"] == 999  # Overridden
        assert result["scope"] == "Module"
        assert result["qualified_name"] == "Module.baz"
        assert result["metadata"] == {"custom": "value"}

    def test_make_symbol_empty_scope_does_not_create_qualified_name(
        self, parser: ConcreteParser
    ) -> None:
        """Test that empty string scope does not generate qualified_name."""
        node = FakeNode(start_line=5, start_column=2, end_line=6, end_column=3)
        result = parser._make_symbol(
            name="test", kind="var", node=cast(Node, node), scope=""
        )

        assert result["name"] == "test"
        assert result["scope"] == ""
        # Empty string is falsy, so no qualified_name
        assert "qualified_name" not in result


class TestMakeReference:
    """Tests for _make_reference helper method."""

    @pytest.fixture
    def parser(self) -> ConcreteParser:
        """Create a parser instance."""
        return ConcreteParser()

    def test_make_reference_without_scope(self, parser: ConcreteParser) -> None:
        """Test that reference without scope has no scope key."""
        node = FakeNode(start_line=42, start_column=10, end_line=42, end_column=15)
        result = parser._make_reference(
            text="identifier", ref_type="usage", node=cast(Node, node)
        )

        assert result["text"] == "identifier"
        assert result["type"] == "usage"
        assert result["source_line"] == 42
        assert result["source_column"] == 10
        assert "scope" not in result

    def test_make_reference_with_none_scope_does_not_add_scope_key(
        self, parser: ConcreteParser
    ) -> None:
        """Test that explicit scope=None does not add scope key."""
        node = FakeNode(start_line=50, start_column=5, end_line=50, end_column=10)
        result = parser._make_reference(
            text="variable", ref_type="call", node=cast(Node, node), scope=None
        )

        assert result["text"] == "variable"
        assert result["type"] == "call"
        assert "scope" not in result

    def test_make_reference_with_scope(self, parser: ConcreteParser) -> None:
        """Test that reference with scope includes scope key."""
        node = FakeNode(start_line=100, start_column=20, end_line=100, end_column=25)
        result = parser._make_reference(
            text="method",
            ref_type="call",
            node=cast(Node, node),
            scope="MyClass.myMethod",
        )

        assert result["text"] == "method"
        assert result["type"] == "call"
        assert result["scope"] == "MyClass.myMethod"

    def test_make_reference_with_empty_string_scope(
        self, parser: ConcreteParser
    ) -> None:
        """Test that empty string scope is included (empty string is not None)."""
        node = FakeNode(start_line=75, start_column=12, end_line=75, end_column=18)
        result = parser._make_reference(
            text="func", ref_type="usage", node=cast(Node, node), scope=""
        )

        assert result["text"] == "func"
        assert result["scope"] == ""  # Empty string is included

    def test_make_reference_with_extra_fields(self, parser: ConcreteParser) -> None:
        """Test that **extra overrides/adds fields."""
        node = FakeNode(start_line=200, start_column=0, end_line=200, end_column=5)
        result = parser._make_reference(
            text="import",
            ref_type="import",
            node=cast(Node, node),
            scope="module",
            from_module="./utils",
            source_line=999,  # Override
        )

        assert result["text"] == "import"
        assert result["type"] == "import"
        assert result["scope"] == "module"
        assert result["from_module"] == "./utils"
        assert result["source_line"] == 999  # Overridden


class TestAddReference:
    """Tests for _add_reference helper method."""

    @pytest.fixture
    def parser(self) -> ConcreteParser:
        """Create a parser instance."""
        return ConcreteParser()

    def test_add_reference_with_valid_text(self, parser: ConcreteParser) -> None:
        """Test that reference with valid text is added."""
        references: list[dict[str, Any]] = []
        ref = {"text": "identifier", "type": "usage", "source_line": 10}
        parser._add_reference(ref, references)

        assert len(references) == 1
        assert references[0]["text"] == "identifier"

    def test_add_reference_empty_string_not_added(self, parser: ConcreteParser) -> None:
        """Test that reference with empty string text is not added."""
        references: list[dict[str, Any]] = []
        ref = {"text": "", "type": "usage", "source_line": 10}
        parser._add_reference(ref, references)

        assert len(references) == 0

    def test_add_reference_whitespace_only_not_added(
        self, parser: ConcreteParser
    ) -> None:
        """Test that reference with whitespace-only text is not added."""
        references: list[dict[str, Any]] = []
        ref = {"text": "   \t\n  ", "type": "usage", "source_line": 10}
        parser._add_reference(ref, references)

        assert len(references) == 0

    def test_add_reference_missing_text_key_not_added(
        self, parser: ConcreteParser
    ) -> None:
        """Test that reference without text key is not added."""
        references: list[dict[str, Any]] = []
        ref = {"type": "usage", "source_line": 10}  # No "text" key
        parser._add_reference(ref, references)

        assert len(references) == 0

    def test_add_reference_preserves_multiple_valid_references(
        self, parser: ConcreteParser
    ) -> None:
        """Test that multiple valid references are all added."""
        references: list[dict[str, Any]] = []
        parser._add_reference({"text": "first", "type": "call"}, references)
        parser._add_reference({"text": "second", "type": "usage"}, references)
        parser._add_reference({"text": "", "type": "call"}, references)  # Skipped
        parser._add_reference({"text": "third", "type": "import"}, references)

        assert len(references) == 3
        assert [r["text"] for r in references] == ["first", "second", "third"]


class TestStripBlockComment:
    """Tests for _strip_block_comment helper method."""

    @pytest.fixture
    def parser(self) -> ConcreteParser:
        """Create a parser instance."""
        return ConcreteParser()

    def test_strip_simple_block_comment(self, parser: ConcreteParser) -> None:
        """Test stripping /* simple */ comment."""
        result = parser._strip_block_comment("/* simple */")
        assert result == "simple"

    def test_strip_javadoc_comment(self, parser: ConcreteParser) -> None:
        """Test stripping /** javadoc */ comment."""
        result = parser._strip_block_comment("/** javadoc */")
        assert result == "javadoc"

    def test_strip_multiline_comment_with_star_prefixes(
        self, parser: ConcreteParser
    ) -> None:
        """Test stripping multi-line comment with * prefixes."""
        comment = """/**
 * This is a multi-line comment
 * with star prefixes
 * on each line
 */"""
        result = parser._strip_block_comment(comment)
        expected = "This is a multi-line comment\nwith star prefixes\non each line"
        assert result == expected

    def test_strip_unclosed_block_comment(self, parser: ConcreteParser) -> None:
        """Test stripping unclosed /* comment without */."""
        result = parser._strip_block_comment("/* unclosed comment")
        assert result == "unclosed comment"

    def test_strip_unclosed_javadoc_comment(self, parser: ConcreteParser) -> None:
        """Test stripping unclosed /** comment without */."""
        result = parser._strip_block_comment("/** unclosed javadoc")
        assert result == "unclosed javadoc"

    def test_strip_empty_comment(self, parser: ConcreteParser) -> None:
        """Test stripping empty /* */ comment."""
        result = parser._strip_block_comment("/* */")
        assert result == ""

    def test_strip_empty_javadoc_comment(self, parser: ConcreteParser) -> None:
        """Test stripping empty /** */ comment."""
        result = parser._strip_block_comment("/** */")
        assert result == ""

    def test_strip_comment_with_no_star_prefixes(self, parser: ConcreteParser) -> None:
        """Test stripping multi-line comment without star prefixes."""
        comment = """/*
This line has no star
Neither does this one
*/"""
        result = parser._strip_block_comment(comment)
        expected = "This line has no star\nNeither does this one"
        assert result == expected

    def test_strip_comment_preserves_content_after_stars(
        self, parser: ConcreteParser
    ) -> None:
        """Test that content after * prefixes is preserved correctly."""
        comment = """/**
 * First line
 *Second line without space
 *   Third line with extra spaces
 */"""
        result = parser._strip_block_comment(comment)
        expected = "First line\nSecond line without space\nThird line with extra spaces"
        assert result == expected


class TestProcessCommentNode:
    """Tests for _process_comment_node default behavior."""

    @pytest.fixture
    def parser(self) -> ConcreteParser:
        """Create a parser instance."""
        return ConcreteParser()

    def test_process_comment_node_returns_none_by_default(
        self, parser: ConcreteParser
    ) -> None:
        """Test that default implementation returns None."""
        node = FakeNode(start_line=1, start_column=0, end_line=1, end_column=10)
        result = parser._process_comment_node(cast(Node, node), "// comment")
        assert result is None


class TestExtractComments:
    """Tests for extract_comments template method."""

    def test_extract_comments_walks_tree(self) -> None:
        """Test that extract_comments walks the tree and delegates to _process_comment_node."""

        # Create custom parser that tracks what it processes
        class TrackingParser(ConcreteParser):
            def __init__(self) -> None:
                super().__init__()
                self.processed_nodes: list[Any] = []

            def _process_comment_node(
                self, node: Any, content: str
            ) -> dict[str, Any] | None:
                self.processed_nodes.append(node)
                # Return a comment dict for nodes with text "comment"
                text = content[node.start_byte : node.end_byte]
                if "comment" in text:
                    return {
                        "content": text,
                        "content_type": "test_comment",
                        "source_line": node.start_point[0] + 1,
                        "source_end_line": node.end_point[0] + 1,
                    }
                return None

        parser = TrackingParser()

        # Create a tree structure
        root = FakeNode(
            start_line=1,
            start_column=0,
            end_line=10,
            end_column=0,
            start_byte=0,
            end_byte=50,
        )
        child1 = FakeNode(
            start_line=2,
            start_column=0,
            end_line=2,
            end_column=10,
            start_byte=10,
            end_byte=20,
        )
        child2 = FakeNode(
            start_line=3,
            start_column=0,
            end_line=3,
            end_column=10,
            start_byte=20,
            end_byte=40,
        )
        grandchild = FakeNode(
            start_line=4,
            start_column=0,
            end_line=4,
            end_column=10,
            start_byte=30,
            end_byte=40,
        )

        root.children = [child1, child2]
        child2.children = [grandchild]

        content = "root text\ncomment here\nmore text\ncomment again\n"

        comments = parser.extract_comments(cast(Node, root), content)

        # Should have visited all nodes
        assert len(parser.processed_nodes) == 4
        assert root in parser.processed_nodes
        assert child1 in parser.processed_nodes
        assert child2 in parser.processed_nodes
        assert grandchild in parser.processed_nodes

        # Should have extracted comments from nodes containing "comment"
        assert len(comments) >= 1

    def test_extract_comments_returns_empty_list_when_no_comments(self) -> None:
        """Test that extract_comments returns empty list when _process_comment_node returns None."""
        parser = ConcreteParser()  # Default returns None

        root = FakeNode(start_line=1, start_column=0, end_line=1, end_column=10)
        child = FakeNode(start_line=2, start_column=0, end_line=2, end_column=10)
        root.children = [child]

        comments = parser.extract_comments(cast(Node, root), "some content")

        assert len(comments) == 0

    def test_extract_comments_collects_all_returned_dicts(self) -> None:
        """Test that extract_comments collects all non-None results."""

        class CommentReturningParser(ConcreteParser):
            def _process_comment_node(
                self, node: Any, content: str
            ) -> dict[str, Any] | None:
                # Return comment dict for every node
                return {
                    "content": f"comment at line {node.start_point[0] + 1}",
                    "content_type": "test",
                    "source_line": node.start_point[0] + 1,
                    "source_end_line": node.end_point[0] + 1,
                }

        parser = CommentReturningParser()

        root = FakeNode(start_line=1, start_column=0, end_line=10, end_column=0)
        child1 = FakeNode(start_line=2, start_column=0, end_line=2, end_column=10)
        child2 = FakeNode(start_line=3, start_column=0, end_line=3, end_column=10)
        root.children = [child1, child2]

        comments = parser.extract_comments(cast(Node, root), "content")

        # Should have collected comments from root + 2 children
        assert len(comments) == 3
        assert all(c["content_type"] == "test" for c in comments)


class TestNodeLocation:
    """Tests for _node_location helper method."""

    @pytest.fixture
    def parser(self) -> ConcreteParser:
        """Create a parser instance."""
        return ConcreteParser()

    def test_node_location_converts_to_1_indexed(self, parser: ConcreteParser) -> None:
        """Test that _node_location converts tree-sitter 0-indexed to 1-indexed."""
        node = FakeNode(start_line=10, start_column=5, end_line=15, end_column=20)
        location = parser._node_location(cast(Node, node))

        assert location["start_line"] == 10
        assert location["start_column"] == 5
        assert location["end_line"] == 15
        assert location["end_column"] == 20

    def test_node_location_handles_single_line(self, parser: ConcreteParser) -> None:
        """Test _node_location for single-line node."""
        node = FakeNode(start_line=42, start_column=8, end_line=42, end_column=15)
        location = parser._node_location(cast(Node, node))

        assert location["start_line"] == 42
        assert location["end_line"] == 42
        assert location["start_column"] == 8
        assert location["end_column"] == 15


class TestGetText:
    """Tests for _get_text helper method."""

    @pytest.fixture
    def parser(self) -> ConcreteParser:
        """Create a parser instance."""
        return ConcreteParser()

    def test_get_text_extracts_correct_slice(self, parser: ConcreteParser) -> None:
        """Test that _get_text extracts correct content slice."""
        content = "def foo():\n    pass\n"
        node = FakeNode(
            start_line=1,
            start_column=4,
            end_line=1,
            end_column=7,
            start_byte=4,
            end_byte=7,
        )

        text = parser._get_text(cast(Node, node), content)
        assert text == "foo"

    def test_get_text_multiline_content(self, parser: ConcreteParser) -> None:
        """Test _get_text with multi-line content."""
        content = "function hello() {\n  console.log('hi');\n}"
        node = FakeNode(
            start_line=1,
            start_column=9,
            end_line=1,
            end_column=14,
            start_byte=9,
            end_byte=14,
        )

        text = parser._get_text(cast(Node, node), content)
        assert text == "hello"
