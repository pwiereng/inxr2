"""Commit hash value object."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CommitHash:
    """
    Git commit SHA-1 hash.

    Attributes:
        value: 40-character hexadecimal SHA-1 hash

    TODO: Add validation for SHA-1 format
    TODO: Add short hash method (7 chars)
    """

    value: str

    def __post_init__(self) -> None:
        """Validate commit hash format."""
        # TODO: Validate 40-character hex string
        # if not re.match(r'^[0-9a-f]{40}$', self.value):
        #     raise ValueError(f"Invalid commit hash: {self.value}")
        pass

    def short(self) -> str:
        """Return short version of hash (7 chars)."""
        # TODO: Implement
        return self.value[:7]
