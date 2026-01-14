"""Configuration value objects for INXR2."""

from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class RepositoryConfig(BaseModel):
    """Configuration for a single repository to index."""

    name: str = Field(..., description="Unique name for the repository")
    path: str | None = Field(
        default=None, description="Local filesystem path to the repository"
    )
    url: str | None = Field(
        default=None, description="Remote URL for cloning (Phase 1.9)"
    )
    branches: list[str] = Field(default=["main"], description="Branches to index")
    languages: list[str] = Field(
        default=["python", "typescript", "javascript"],
        description="Languages to extract symbols from",
    )
    exclude_patterns: list[str] = Field(
        default_factory=list,
        description="Glob patterns for files/directories to exclude",
    )

    @model_validator(mode="after")
    def validate_path_or_url(self) -> "RepositoryConfig":
        """Ensure either path or url is specified."""
        if not self.path and not self.url:
            raise ValueError("Either 'path' or 'url' must be specified")
        return self

    def get_resolved_path(self) -> Path | None:
        """Get the resolved path (with env vars expanded)."""
        if self.path:
            return Path(self.path).expanduser().resolve()
        return None


class IndexingConfig(BaseModel):
    """Configuration for indexing behavior."""

    incremental: bool = Field(
        default=True, description="Use incremental indexing when possible"
    )
    max_commit_history: int = Field(
        default=1000, description="Maximum number of commits to index per branch"
    )
    batch_size: int = Field(
        default=100, description="Number of files to process per batch"
    )


class ServerConfig(BaseModel):
    """Configuration for the web server."""

    host: str = Field(default="0.0.0.0", description="Host to bind to")
    port: int = Field(default=8000, description="Port to listen on")


class AppConfig(BaseModel):
    """Root configuration for INXR2."""

    repositories: list[RepositoryConfig] = Field(
        ..., description="List of repositories to index"
    )
    indexing: IndexingConfig = Field(
        default_factory=IndexingConfig, description="Indexing configuration"
    )
    server: ServerConfig = Field(
        default_factory=ServerConfig, description="Server configuration"
    )

    def get_repository(self, name: str) -> RepositoryConfig | None:
        """Get a repository by name."""
        for repo in self.repositories:
            if repo.name == name:
                return repo
        return None

    def get_repository_names(self) -> list[str]:
        """Get list of all repository names."""
        return [repo.name for repo in self.repositories]
