"""Repository entity - represents a git repository."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Repository:
    """
    A git repository that is indexed by INXR2.

    Attributes:
        id: Unique identifier for this repository
        name: Human-readable name
        url: Git URL or local path
        config: JSONB configuration metadata

    TODO: Add validation for URL format
    TODO: Add methods for repository operations (if needed)
    """

    id: str
    name: str
    url: str
    config: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate repository entity."""
        # TODO: Add validation logic
        # - Validate name is non-empty
        # - Validate URL format (git:// or https:// or file://)
        # - Validate config schema if present
        pass
