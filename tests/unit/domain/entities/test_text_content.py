"""Tests for TextContent domain entity."""

from datetime import datetime

import pytest

from inxr2.domain.entities.text_content import TextContent


class TestTextContent:
    """Test TextContent entity creation and validation."""

    def test_text_content_creation_with_required_fields(self) -> None:
        """Test creating TextContent with required fields only."""
        text_content = TextContent(
            repository_id=1,
            commit_id=10,
            source_type="comment",
            content="TODO: refactor this function",
            source_file_id=5,
            source_line=42,
        )

        assert text_content.repository_id == 1
        assert text_content.commit_id == 10
        assert text_content.source_type == "comment"
        assert text_content.content == "TODO: refactor this function"
        assert text_content.source_file_id == 5
        assert text_content.source_line == 42
        assert text_content.id is None
        assert text_content.source_end_line is None
        assert text_content.language is None
        assert text_content.content_type is None
        assert text_content.indexed_at is None

    def test_text_content_creation_with_all_fields(self) -> None:
        """Test creating TextContent with all fields."""
        now = datetime.now()
        text_content = TextContent(
            id=100,
            repository_id=1,
            commit_id=10,
            source_type="docstring",
            source_file_id=5,
            source_line=10,
            source_end_line=15,
            content='"""Calculate the total amount."""',
            language="python",
            content_type="docstring",
            indexed_at=now,
        )

        assert text_content.id == 100
        assert text_content.repository_id == 1
        assert text_content.commit_id == 10
        assert text_content.source_type == "docstring"
        assert text_content.source_file_id == 5
        assert text_content.source_line == 10
        assert text_content.source_end_line == 15
        assert text_content.content == '"""Calculate the total amount."""'
        assert text_content.language == "python"
        assert text_content.content_type == "docstring"
        assert text_content.indexed_at == now

    def test_text_content_commit_message_without_file(self) -> None:
        """Test creating TextContent for commit message (no file_id)."""
        text_content = TextContent(
            repository_id=1,
            commit_id=10,
            source_type="commit_message",
            content="fix: resolve null pointer in parser",
            source_file_id=None,
            source_line=None,
        )

        assert text_content.source_type == "commit_message"
        assert text_content.source_file_id is None
        assert text_content.source_line is None
        assert text_content.content == "fix: resolve null pointer in parser"

    def test_text_content_empty_content_raises_error(self) -> None:
        """Test that empty content raises ValueError."""
        with pytest.raises(ValueError, match="Content cannot be empty"):
            TextContent(
                repository_id=1,
                commit_id=10,
                source_type="comment",
                content="",
                source_file_id=5,
                source_line=42,
            )

    def test_text_content_whitespace_only_content_raises_error(self) -> None:
        """Test that whitespace-only content raises ValueError."""
        with pytest.raises(ValueError, match="Content cannot be empty"):
            TextContent(
                repository_id=1,
                commit_id=10,
                source_type="comment",
                content="   \n\t  ",
                source_file_id=5,
                source_line=42,
            )

    def test_text_content_negative_source_line_raises_error(self) -> None:
        """Test that negative source line raises ValueError."""
        with pytest.raises(ValueError, match="Source line must be >= 1"):
            TextContent(
                repository_id=1,
                commit_id=10,
                source_type="comment",
                content="TODO: fix this",
                source_file_id=5,
                source_line=0,
            )

    def test_text_content_end_line_before_start_line_raises_error(self) -> None:
        """Test that end_line < start_line raises ValueError."""
        with pytest.raises(
            ValueError, match="Source end line.*cannot be before source line"
        ):
            TextContent(
                repository_id=1,
                commit_id=10,
                source_type="docstring",
                content="Multi-line docstring",
                source_file_id=5,
                source_line=10,
                source_end_line=5,
            )

    def test_text_content_immutability(self) -> None:
        """Test that TextContent is immutable (frozen dataclass)."""
        text_content = TextContent(
            repository_id=1,
            commit_id=10,
            source_type="comment",
            content="TODO: fix this",
            source_file_id=5,
            source_line=42,
        )

        # Frozen dataclass should prevent modification
        with pytest.raises((AttributeError, TypeError)):
            text_content.content = "Changed"  # type: ignore
