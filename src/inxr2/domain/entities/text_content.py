"""TextContent entity - represents searchable text extracted from code."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TextContent:
    """
    Searchable text content extracted from various sources.

    Domain entity (framework-agnostic). Separate from SQLAlchemy ORM model.

    This entity stores extracted text for full-text search:
    - Comments and docstrings from code files
    - Commit messages
    - Content from non-code files (markdown, YAML, etc.)

    Attributes:
        repository_id: Repository this content belongs to
        commit_id: Commit ID where this content exists
        source_type: Type of source (comment, docstring, commit_message, file_content)
        content: The extracted text content (NOT raw file lines)
        source_file_id: File this content came from (None for commit messages)
        source_line: Starting line number for navigation (None for commit messages)
        id: Database ID (None for new entities)
        source_end_line: Ending line number (for multi-line content)
        language: Programming language (python, typescript, markdown, etc.)
        content_type: Specific content type (inline_comment, block_comment, docstring, etc.)
        indexed_at: When this content was indexed
    """

    repository_id: int
    commit_id: int
    source_type: str
    content: str
    source_file_id: int | None
    source_line: int | None
    id: int | None = None
    source_end_line: int | None = None
    language: str | None = None
    content_type: str | None = None
    indexed_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate text content entity."""
        # Content validation
        if not self.content or not self.content.strip():
            raise ValueError("Content cannot be empty")

        # Line number validation (only if provided)
        if self.source_line is not None and self.source_line < 1:
            raise ValueError(f"Source line must be >= 1: {self.source_line}")

        # End line validation
        if (
            self.source_line is not None
            and self.source_end_line is not None
            and self.source_end_line < self.source_line
        ):
            raise ValueError(
                f"Source end line ({self.source_end_line}) cannot be before "
                f"source line ({self.source_line})"
            )
