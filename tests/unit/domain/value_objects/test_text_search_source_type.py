"""Tests for TextSearchSourceType value object."""

from inxr2.domain.value_objects.text_search_source_type import TextSearchSourceType


class TestTextSearchSourceType:
    """Test TextSearchSourceType enumeration."""

    def test_all_source_types_defined(self) -> None:
        """Test that all expected source types are defined."""
        assert TextSearchSourceType.COMMENT.value == "comment"
        assert TextSearchSourceType.DOCSTRING.value == "docstring"
        assert TextSearchSourceType.COMMIT_MESSAGE.value == "commit_message"
        assert TextSearchSourceType.FILE_CONTENT.value == "file_content"

    def test_source_type_is_string_enum(self) -> None:
        """Test that source types are string values."""
        assert isinstance(TextSearchSourceType.COMMENT.value, str)
        assert isinstance(TextSearchSourceType.DOCSTRING, str)

    def test_source_type_equality(self) -> None:
        """Test source type equality comparisons."""
        assert TextSearchSourceType.COMMENT.value == "comment"
        assert TextSearchSourceType.DOCSTRING.value == "docstring"
        assert TextSearchSourceType.COMMIT_MESSAGE.value == "commit_message"
        assert TextSearchSourceType.FILE_CONTENT.value == "file_content"

    def test_source_type_from_string(self) -> None:
        """Test creating source type from string value."""
        assert TextSearchSourceType("comment") == TextSearchSourceType.COMMENT
        assert TextSearchSourceType("docstring") == TextSearchSourceType.DOCSTRING
        assert (
            TextSearchSourceType("commit_message")
            == TextSearchSourceType.COMMIT_MESSAGE
        )
        assert TextSearchSourceType("file_content") == TextSearchSourceType.FILE_CONTENT
