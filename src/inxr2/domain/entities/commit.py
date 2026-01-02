"""Commit entity - represents a git commit."""

from dataclasses import dataclass
from datetime import datetime

from ..value_objects.commit_hash import CommitHash


@dataclass(frozen=True)
class Commit:
    """
    A git commit snapshot.

    Attributes:
        hash: Commit hash (SHA-1)
        repository_id: ID of repository this commit belongs to
        branch: Branch name
        timestamp: Commit timestamp
        author: Author name
        message: Commit message
        parent_hashes: Parent commit hashes for graph traversal

    TODO: Add methods for commit comparison
    """

    hash: CommitHash
    repository_id: str
    branch: str
    timestamp: datetime
    author: str
    message: str
    parent_hashes: list[CommitHash] | None = None
