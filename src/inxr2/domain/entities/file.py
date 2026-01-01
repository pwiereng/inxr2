"""File entity - represents a source file."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class File:
    """
    A source code file at a specific commit.

    Attributes:
        id: Unique file identifier
        repository_id: Repository this file belongs to
        commit_hash: Commit hash where this version exists
        path: File path relative to repository root
        content_hash: SHA-256 hash of file content (for deduplication)
        language: Detected programming language
        content: File content (optional, may be loaded separately)

    TODO: Add size limits for content
    TODO: Add methods for language detection
    """

    id: str
    repository_id: str
    commit_hash: str
    path: Path
    content_hash: str
    language: str
    content: str | None = None
