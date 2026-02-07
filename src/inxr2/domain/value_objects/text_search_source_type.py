"""Text search source type enumeration."""

from enum import Enum


class TextSearchSourceType(str, Enum):
    """
    Type of source for searchable text content.

    Defines where searchable text was extracted from:
    - COMMENT: Inline or block comments
    - DOCSTRING: Function/class documentation strings
    - COMMIT_MESSAGE: Git commit messages
    - FILE_CONTENT: Content from non-code files (markdown, YAML, etc.)
    """

    COMMENT = "comment"
    DOCSTRING = "docstring"
    COMMIT_MESSAGE = "commit_message"
    FILE_CONTENT = "file_content"
