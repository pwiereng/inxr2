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
    "cpp",
    "java",
    "csharp",
    "go",
    "ruby",
    "bash",
)
