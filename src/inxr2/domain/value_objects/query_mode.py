"""Query mode enumeration for text search."""

from enum import Enum


class QueryMode(str, Enum):
    """
    Query mode for text search operations.

    Defines how the search query should be interpreted:
    - KEYWORD: Full-text search using tsvector (default)
    - PHRASE: Exact phrase matching
    - REGEX: PostgreSQL regex matching (bypasses tsvector)
    """

    KEYWORD = "keyword"
    PHRASE = "phrase"
    REGEX = "regex"
