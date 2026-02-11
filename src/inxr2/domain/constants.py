"""Domain-level constants for INXR2.

These constants represent business concepts and constraints that are
framework-agnostic.
"""

# Languages with full tree-sitter parser support for symbol extraction
# This should be kept in sync with TreeSitterService.SUPPORTED_LANGUAGES
SUPPORTED_LANGUAGES_WITH_PARSERS = (
    "python",
    "typescript",
    "javascript",
    "c",
    "java",
    "csharp",
)

# Default languages to index when not specified in config
DEFAULT_INDEXING_LANGUAGES = (
    "python",
    "typescript",
    "javascript",
)
