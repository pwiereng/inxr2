"""Search scope value object for controlling cross-repository search behavior."""

from enum import StrEnum


class SearchScope(StrEnum):
    """Scope for cross-repository search.

    Controls which commits are searched when no repository is specified:
    - LATEST: HEAD of each repo's default branch (current code)
    - ALL_BRANCHES: HEAD of every indexed branch (future)
    - ALL_HISTORY: Every indexed commit (future)
    """

    LATEST = "latest"
    ALL_BRANCHES = "all_branches"
    ALL_HISTORY = "all_history"
