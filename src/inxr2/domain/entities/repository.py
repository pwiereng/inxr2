"""Repository entity - represents a git repository."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Repository:
    """
    A git repository that is indexed by INXR2.

    Domain entity (framework-agnostic). Separate from SQLAlchemy ORM model.

    Attributes:
        name: Unique human-readable name (e.g., 'linux-kernel')
        url: Git repository URL (https:// or ssh://)
        id: Database ID (None for new entities)
        description: Optional description
        default_branch: Default branch to index (usually 'main' or 'master')
        config: JSONB configuration metadata (branches, patterns, etc.)
        created_at: When repository was added
        updated_at: Last update timestamp
    """

    name: str
    url: str
    id: int | None = None
    description: str | None = None
    default_branch: str = "main"
    config: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate repository entity."""
        if not self.name:
            raise ValueError("Repository name cannot be empty")
        if not self.url:
            raise ValueError("Repository URL cannot be empty")
        # Name validation: alphanumeric, underscores, hyphens, and dots
        import re

        if not re.match(r"^[a-zA-Z0-9_.-]+$", self.name):
            raise ValueError(
                f"Invalid repository name '{self.name}': "
                "must contain only letters, numbers, underscores, hyphens, and dots"
            )
        if (
            self.name in (".", "..")
            or self.name.startswith(".")
            or self.name.endswith(".")
        ):
            raise ValueError(
                f"Invalid repository name '{self.name}': "
                "cannot be '.', '..', or start/end with a dot"
            )
