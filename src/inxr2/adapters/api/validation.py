"""Shared validation functions for API routes."""

import re
from pathlib import PurePosixPath

from fastapi import HTTPException


def validate_path(path: str) -> str:
    """Validate and normalize a file path to prevent path traversal attacks.

    Args:
        path: The file path to validate

    Returns:
        Normalized path string

    Raises:
        HTTPException: If path is invalid or contains traversal attempts
    """
    # Reject empty paths
    if not path or not path.strip():
        raise HTTPException(status_code=400, detail="Path cannot be empty")

    # Reject absolute paths
    if path.startswith("/") or path.startswith("\\"):
        raise HTTPException(status_code=400, detail="Absolute paths are not allowed")

    # Normalize the path and check for traversal
    normalized = PurePosixPath(path)

    # Check each part for ".."
    for part in normalized.parts:
        if part == "..":
            raise HTTPException(
                status_code=400, detail="Path traversal (..) is not allowed"
            )

    return str(normalized)


def validate_repo_name(repo: str) -> str:
    """Validate repository name format.

    Args:
        repo: Repository name to validate

    Returns:
        Validated repository name

    Raises:
        HTTPException: If repo name is invalid
    """
    if not repo or not repo.strip():
        raise HTTPException(status_code=400, detail="Repository name cannot be empty")

    # Allow only safe characters for repository names:
    # - a-zA-Z0-9_ (alphanumeric and underscore)
    # - hyphen (-)
    # - dot (.) for repo names like "my.repo"
    # This prevents injection of path separators, spaces, or special chars
    if not re.match(r"^[a-zA-Z0-9_.-]+$", repo):
        raise HTTPException(
            status_code=400,
            detail="Repository name contains invalid characters",
        )

    # Reject problematic dot patterns
    if repo in (".", "..") or repo.startswith(".") or repo.endswith("."):
        raise HTTPException(
            status_code=400,
            detail="Repository name cannot be '.', '..', or start/end with a dot",
        )

    return repo
