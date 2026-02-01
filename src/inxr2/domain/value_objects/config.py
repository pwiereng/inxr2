"""Configuration value objects for INXR2.

These are pure domain objects with no framework dependencies.
Validation is handled by the adapter layer (Pydantic models in adapters/config/).
"""

from dataclasses import dataclass, field
from pathlib import Path

from ..constants import DEFAULT_INDEXING_LANGUAGES


@dataclass(frozen=True)
class RepositoryConfig:
    """Configuration for a single repository to index."""

    name: str
    path: str | None = None
    url: str | None = None
    branches: tuple[str, ...] = ("main",)
    languages: tuple[str, ...] = DEFAULT_INDEXING_LANGUAGES
    exclude_patterns: tuple[str, ...] = ()

    def get_resolved_path(self) -> Path | None:
        """Get the resolved path (with env vars expanded)."""
        if self.path:
            return Path(self.path).expanduser().resolve()
        return None


@dataclass(frozen=True)
class IndexingConfig:
    """Configuration for indexing behavior."""

    incremental: bool = True
    max_commit_history: int = 1000
    batch_size: int = 100


@dataclass(frozen=True)
class ServerConfig:
    """Configuration for the web server."""

    host: str = "0.0.0.0"
    port: int = 8000


@dataclass(frozen=True)
class AppConfig:
    """Root configuration for INXR2."""

    repositories: tuple[RepositoryConfig, ...]
    indexing: IndexingConfig = field(default_factory=IndexingConfig)
    server: ServerConfig = field(default_factory=ServerConfig)

    def get_repository(self, name: str) -> RepositoryConfig | None:
        """Get a repository by name."""
        for repo in self.repositories:
            if repo.name == name:
                return repo
        return None

    def get_repository_names(self) -> list[str]:
        """Get list of all repository names."""
        return [repo.name for repo in self.repositories]
