"""Domain-level constants for INXR2.

These constants represent business concepts and constraints that are
framework-agnostic.
"""


class DatabaseLimits:
    """Hard limits imposed by the database layer."""

    # PostgreSQL tsvector has a hard limit of 1,048,575 bytes on the generated
    # tsvector. We use a conservative input cap to account for positional data
    # and lexeme overhead that can exceed the raw input size.
    MAX_TSVECTOR_BYTES = 750_000

    # Maximum regex pattern length to prevent catastrophic backtracking (ReDoS).
    MAX_REGEX_LENGTH = 500


class QueryDefaults:
    """Default limits for database queries."""

    SYMBOL_SEARCH_LIMIT = 50
    REFERENCE_LIMIT = 100
    COMMIT_LIST_LIMIT = 100


class APILimits:
    """Input length limits enforced at the API boundary."""

    MAX_TEXT_QUERY_LENGTH = 500
    MAX_FILE_QUERY_LENGTH = 200


# Cross-language symbol kind aliases.
# Querying by a key also matches all values in its list.
# e.g. kind="interface" returns both interface and protocol symbols (Swift).
KIND_ALIASES: dict[str, list[str]] = {
    "interface": ["interface", "protocol"],
}


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
    "swift",
)
