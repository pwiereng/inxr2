"""Domain-level validation functions for business rules."""

import re

_REPO_NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")


def validate_repo_name(name: str) -> None:
    """Validate a repository name against domain rules.

    Args:
        name: Repository name to validate

    Raises:
        ValueError: If the name is invalid
    """
    if not name or not name.strip():
        raise ValueError("Repository name cannot be empty")

    if not _REPO_NAME_RE.match(name):
        raise ValueError(
            f"Invalid repository name '{name}': "
            "must contain only letters, numbers, underscores, hyphens, and dots"
        )

    if name.startswith(".") or name.endswith("."):
        raise ValueError(
            f"Invalid repository name '{name}': cannot start or end with a dot"
        )
