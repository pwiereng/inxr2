"""Shared regex validation utilities for PostgreSQL regex search."""

import re

# Regex validation constants
MAX_REGEX_LENGTH = 500
# Patterns that can cause catastrophic backtracking (ReDoS)
DANGEROUS_REGEX_PATTERNS = [
    r"\(\.\*\)\+",  # (.*)+
    r"\(\.\+\)\+",  # (.+)+
    r"\([^)]*\+\)\+",  # (x+)+ pattern
    r"\([^)]*\*\)\+",  # (x*)+
    r"\([^)]*\+\)\*",  # (x+)*
    r"\([^)]*\*\)\*",  # (x*)*
]


def validate_regex_pattern(pattern: str) -> None:
    """
    Validate regex pattern for safety.

    Args:
        pattern: The regex pattern to validate

    Raises:
        ValueError: If pattern is invalid or potentially dangerous
    """
    # Check length
    if len(pattern) > MAX_REGEX_LENGTH:
        raise ValueError(
            f"Regex pattern too long: {len(pattern)} characters "
            f"(max {MAX_REGEX_LENGTH})"
        )

    # Check for dangerous patterns that can cause catastrophic backtracking
    for dangerous in DANGEROUS_REGEX_PATTERNS:
        if re.search(dangerous, pattern):
            raise ValueError(
                "Regex pattern contains potentially dangerous nested quantifiers "
                "that could cause performance issues"
            )

    # Try to compile the regex to catch syntax errors early
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}") from None


def translate_word_boundaries(pattern: str) -> str:
    r"""Translate \b (PCRE word boundary) to \y (PostgreSQL word boundary)."""
    return pattern.replace(r"\b", r"\y")
