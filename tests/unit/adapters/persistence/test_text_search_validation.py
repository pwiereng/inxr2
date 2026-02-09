"""Unit tests for text search validation functions.

These tests verify the regex validation logic without requiring PostgreSQL.
"""

import pytest

from inxr2.adapters.persistence.repositories.postgres_text_search import (
    _validate_regex_pattern,
)


class TestRegexValidation:
    """Tests for regex pattern validation."""

    def test_valid_simple_pattern(self) -> None:
        """Test that simple patterns pass validation."""
        # Should not raise
        _validate_regex_pattern("TODO")
        _validate_regex_pattern("fix.*bug")
        _validate_regex_pattern("^[A-Z]+:")
        _validate_regex_pattern(r"\d{3}-\d{4}")

    def test_pattern_too_long(self) -> None:
        """Test that overly long patterns are rejected."""
        long_pattern = "a" * 501
        with pytest.raises(ValueError, match="too long"):
            _validate_regex_pattern(long_pattern)

    def test_pattern_at_max_length(self) -> None:
        """Test that patterns at exactly max length are accepted."""
        max_pattern = "a" * 500
        # Should not raise
        _validate_regex_pattern(max_pattern)

    def test_dangerous_pattern_star_plus(self) -> None:
        """Test that (.*)+  pattern is rejected (catastrophic backtracking)."""
        with pytest.raises(ValueError, match="dangerous nested quantifiers"):
            _validate_regex_pattern("(.*)+")

    def test_dangerous_pattern_plus_plus(self) -> None:
        """Test that (.+)+ pattern is rejected."""
        with pytest.raises(ValueError, match="dangerous nested quantifiers"):
            _validate_regex_pattern("(.+)+")

    def test_dangerous_pattern_nested_quantifiers(self) -> None:
        """Test that (a+)+ pattern is rejected."""
        with pytest.raises(ValueError, match="dangerous nested quantifiers"):
            _validate_regex_pattern("(a+)+")

    def test_dangerous_pattern_star_star(self) -> None:
        """Test that (a*)* pattern is rejected."""
        with pytest.raises(ValueError, match="dangerous nested quantifiers"):
            _validate_regex_pattern("(a*)*")

    def test_invalid_regex_syntax(self) -> None:
        """Test that invalid regex syntax is rejected."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            _validate_regex_pattern("[unclosed")

        with pytest.raises(ValueError, match="Invalid regex pattern"):
            _validate_regex_pattern("(unmatched")

        with pytest.raises(ValueError, match="Invalid regex pattern"):
            _validate_regex_pattern("*invalid")

    def test_special_characters_in_pattern(self) -> None:
        """Test that special characters are allowed when valid."""
        # These are valid regex patterns with special chars
        _validate_regex_pattern("TODO: fix this")
        _validate_regex_pattern("bug!")
        _validate_regex_pattern(r"\(important\)")
        _validate_regex_pattern("user:password")

    def test_safe_nested_groups(self) -> None:
        """Test that safe nested groups are allowed."""
        # Non-catastrophic nested patterns
        _validate_regex_pattern("((a)(b))")
        _validate_regex_pattern("(a|b)+")  # Alternation is fine
        _validate_regex_pattern("(a{1,3})+")  # Bounded quantifier is fine
