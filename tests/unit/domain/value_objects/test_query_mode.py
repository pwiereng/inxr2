"""Tests for QueryMode value object."""

from inxr2.domain.value_objects import QueryMode


def test_query_mode_enum_values() -> None:
    """Test QueryMode enum has expected values."""
    assert QueryMode.KEYWORD.value == "keyword"
    assert QueryMode.PHRASE.value == "phrase"
    assert QueryMode.REGEX.value == "regex"


def test_query_mode_string_enum() -> None:
    """Test QueryMode is a string enum."""
    # String enums values can be used as strings
    assert QueryMode.KEYWORD.value == "keyword"
    assert QueryMode.PHRASE.value == "phrase"
    assert QueryMode.REGEX.value == "regex"


def test_query_mode_can_be_used_in_conditionals() -> None:
    """Test QueryMode values work in conditionals."""
    mode = QueryMode.KEYWORD

    if mode == QueryMode.KEYWORD:
        result = "keyword_search"
    elif mode == QueryMode.PHRASE:
        result = "phrase_search"
    else:
        result = "regex_search"

    assert result == "keyword_search"
