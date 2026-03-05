"""Domain-level validation functions for business rules."""

import re


def validate_repo_name(name: str) -> None:
    """Validate a repository name against domain rules.

    Args:
        name: Repository name to validate

    Raises:
        ValueError: If the name is invalid
    """
    if not name or not name.strip():
        raise ValueError("Repository name cannot be empty")

    if not re.match(r"^[a-zA-Z0-9_.-]+$", name):
        raise ValueError(
            f"Invalid repository name '{name}': "
            "must contain only letters, numbers, underscores, hyphens, and dots"
        )

    if name.startswith(".") or name.endswith("."):
        raise ValueError(
            f"Invalid repository name '{name}': "
            "cannot be '.', '..', or start/end with a dot"
        )
