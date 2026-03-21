"""Tests for parser error handling and resilience.

Verifies that malformed AST nodes are skipped with warnings,
and partial results are returned instead of failing entirely.
"""

import logging
from typing import Any, cast
from unittest.mock import patch

import pytest
from tree_sitter import Node

from inxr2.adapters.external.treesitter import TreeSitterService
from inxr2.adapters.external.treesitter.base import BaseLanguageParser


class FakeNode:
    """Minimal fake Node for testing error handling."""

    def __init__(
        self,
        node_type: str = "comment",
        start_line: int = 1,
        start_column: int = 0,
        end_line: int = 1,
        end_column: int = 10,
        start_byte: int = 0,
        end_byte: int = 10,
        children: list[Any] | None = None,
        node_id: int = 0,
    ):
        self.type = node_type
        self.start_point = (start_line - 1, start_column)
        self.end_point = (end_line - 1, end_column)
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.children: list[Any] = children or []
        self.id = node_id


class ErrorOnSecondNodeParser(BaseLanguageParser):
    """Parser that raises on nodes at a specific line."""

    def __init__(self, error_line: int = 2):
        self._error_line = error_line

    @property
    def language_name(self) -> str:
        return "test"

    def extract(
        self, root: Any, content: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return [], []

    def _process_comment_node(self, node: Node, content: str) -> dict[str, Any] | None:
        if node.type == "comment":
            line = node.start_point[0] + 1
            if line == self._error_line:
                raise ValueError(f"Simulated error at line {line}")
            text = content[node.start_byte : node.end_byte]
            return {
                "content": text.lstrip("# "),
                "content_type": "single_line_comment",
                "source_line": line,
                "source_end_line": node.end_point[0] + 1,
            }
        return None


class TestBaseParserCommentErrorHandling:
    """Tests for per-node error handling in base extract_comments."""

    def test_skips_bad_node_returns_partial_results(self) -> None:
        """A malformed node is skipped; valid nodes before and after are kept."""
        parser = ErrorOnSecondNodeParser(error_line=2)

        good1 = FakeNode(
            node_type="comment",
            start_line=1,
            start_byte=0,
            end_byte=8,
        )
        bad = FakeNode(
            node_type="comment",
            start_line=2,
            start_byte=9,
            end_byte=20,
        )
        good2 = FakeNode(
            node_type="comment",
            start_line=3,
            start_byte=21,
            end_byte=30,
        )
        root = FakeNode(
            node_type="module",
            children=[good1, bad, good2],
        )

        content = "# first\n# bad node\n# third!!"
        comments = parser.extract_comments(cast(Node, root), content)

        assert len(comments) == 2
        assert comments[0]["source_line"] == 1
        assert comments[1]["source_line"] == 3

    def test_logs_warning_on_bad_node(self, caplog: pytest.LogCaptureFixture) -> None:
        """A warning is logged when a comment node raises an exception."""
        parser = ErrorOnSecondNodeParser(error_line=1)

        bad = FakeNode(
            node_type="comment",
            start_line=1,
            start_byte=0,
            end_byte=5,
        )
        root = FakeNode(node_type="module", children=[bad])

        with caplog.at_level(
            logging.WARNING, logger="inxr2.adapters.external.treesitter.base"
        ):
            parser.extract_comments(cast(Node, root), "# bad")

        assert len(caplog.records) == 1
        assert "Skipping comment node" in caplog.records[0].message
        assert "line 1" in caplog.records[0].message

    def test_children_still_visited_after_parent_error(self) -> None:
        """Children of a failing node are still visited."""
        parser = ErrorOnSecondNodeParser(error_line=1)

        child = FakeNode(
            node_type="comment",
            start_line=2,
            start_byte=6,
            end_byte=15,
        )
        # Parent is a non-comment container that has a comment child
        # The comment child at line 2 should still be processed
        bad_parent = FakeNode(
            node_type="comment",
            start_line=1,
            start_byte=0,
            end_byte=5,
            children=[child],
        )
        root = FakeNode(node_type="module", children=[bad_parent])

        content = "# bad\n# good!!!!!"
        comments = parser.extract_comments(cast(Node, root), content)

        # bad_parent at line 1 fails, but child at line 2 succeeds
        assert len(comments) == 1
        assert comments[0]["source_line"] == 2


class TestPythonParserCommentErrorHandling:
    """Tests for error handling in Python parser's extract_comments."""

    @pytest.fixture
    def service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_valid_comments_extracted_normally(
        self, service: TreeSitterService
    ) -> None:
        """Sanity check: normal comments are still extracted correctly."""
        code = "# first comment\nx = 1\n# second comment\n"
        comments = await service.extract_comments(code, "python", "test.py")

        contents = [c.content for c in comments]
        assert "first comment" in contents
        assert "second comment" in contents

    @pytest.mark.asyncio
    async def test_python_comment_error_logged_and_skipped(
        self, service: TreeSitterService, caplog: pytest.LogCaptureFixture
    ) -> None:
        """If _get_text raises inside Python visit_node, the node is skipped."""
        code = "# good comment\nx = 1\n"

        with caplog.at_level(
            logging.WARNING, logger="inxr2.adapters.external.treesitter.python_parser"
        ):
            # Patch _get_text to fail on a specific call
            service._ensure_initialized()
            original_get_text = service._language_parsers.get("python")
            assert original_get_text is not None
            original = original_get_text._get_text

            call_count = 0

            def failing_get_text(node: Any, content: str) -> str:
                nonlocal call_count
                call_count += 1
                if node.type == "comment":
                    raise RuntimeError("simulated parse error")
                return original(node, content)

            with patch.object(
                original_get_text, "_get_text", side_effect=failing_get_text
            ):
                comments = await service.extract_comments(code, "python", "test.py")

        # The comment node should have been skipped
        comment_contents = [
            c.content for c in comments if c.content_type == "single_line_comment"
        ]
        assert len(comment_contents) == 0
        assert any("Skipping comment node" in r.message for r in caplog.records)


class TestTreeSitterServiceErrorHandling:
    """Tests for service-level error handling around extraction calls."""

    @pytest.fixture
    def service(self) -> TreeSitterService:
        return TreeSitterService()

    @pytest.mark.asyncio
    async def test_parse_file_returns_empty_on_extraction_error(
        self, service: TreeSitterService, caplog: pytest.LogCaptureFixture
    ) -> None:
        """parse_file returns ([], []) when language_parser.extract raises."""
        service._ensure_initialized()
        py_parser = service._language_parsers.get("python")
        assert py_parser is not None

        with caplog.at_level(
            logging.ERROR, logger="inxr2.adapters.external.treesitter.service"
        ):
            with patch.object(py_parser, "extract", side_effect=RuntimeError("boom")):
                symbols, refs = await service.parse_file(
                    "def foo(): pass", "python", "test.py"
                )

        assert symbols == []
        assert refs == []
        assert any("Failed to extract symbols" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_extract_comments_returns_empty_on_extraction_error(
        self, service: TreeSitterService, caplog: pytest.LogCaptureFixture
    ) -> None:
        """extract_comments returns [] when language_parser.extract_comments raises."""
        service._ensure_initialized()
        py_parser = service._language_parsers.get("python")
        assert py_parser is not None

        with caplog.at_level(
            logging.ERROR, logger="inxr2.adapters.external.treesitter.service"
        ):
            with patch.object(
                py_parser, "extract_comments", side_effect=RuntimeError("boom")
            ):
                comments = await service.extract_comments(
                    "# hello", "python", "test.py"
                )

        assert comments == []
        assert any("Failed to extract comments" in r.message for r in caplog.records)
