"""Shared validation functions for API routes."""

from pathlib import PurePosixPath

from fastapi import HTTPException

from inxr2.domain.services.validators import validate_repo_name as _validate_repo_name


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

    Delegates to the shared domain validator and wraps ValueError into HTTPException.

    Args:
        repo: Repository name to validate

    Returns:
        Validated repository name

    Raises:
        HTTPException: If repo name is invalid
    """
    try:
        _validate_repo_name(repo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return repo
