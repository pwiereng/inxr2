"""Pydantic models for configuration validation.

These models handle validation and parsing of configuration files.
After validation, they are converted to domain value objects.
"""

from pydantic import BaseModel, Field, model_validator

from ...domain.value_objects import (
    AppConfig,
    IndexingConfig,
    RepositoryConfig,
    ServerConfig,
)


class RepositoryConfigModel(BaseModel):
    """Pydantic model for repository configuration validation."""

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
    def validate_path_or_url(self) -> "RepositoryConfigModel":
        """Ensure either path or url is specified."""
        if not self.path and not self.url:
            raise ValueError("Either 'path' or 'url' must be specified")
        return self

    def to_domain(self) -> RepositoryConfig:
        """Convert to domain value object."""
        return RepositoryConfig(
            name=self.name,
            path=self.path,
            url=self.url,
            branches=tuple(self.branches),
            languages=tuple(self.languages),
            exclude_patterns=tuple(self.exclude_patterns),
        )


class IndexingConfigModel(BaseModel):
    """Pydantic model for indexing configuration validation."""

    incremental: bool = Field(
        default=True, description="Use incremental indexing when possible"
    )
    max_commit_history: int = Field(
        default=1000, description="Maximum number of commits to index per branch"
    )
    batch_size: int = Field(
        default=100, description="Number of files to process per batch"
    )

    def to_domain(self) -> IndexingConfig:
        """Convert to domain value object."""
        return IndexingConfig(
            incremental=self.incremental,
            max_commit_history=self.max_commit_history,
            batch_size=self.batch_size,
        )


class ServerConfigModel(BaseModel):
    """Pydantic model for server configuration validation."""

    host: str = Field(default="0.0.0.0", description="Host to bind to")
    port: int = Field(default=8000, description="Port to listen on")

    def to_domain(self) -> ServerConfig:
        """Convert to domain value object."""
        return ServerConfig(
            host=self.host,
            port=self.port,
        )


class AppConfigModel(BaseModel):
    """Pydantic model for root configuration validation."""

    repositories: list[RepositoryConfigModel] = Field(
        ..., description="List of repositories to index"
    )
    indexing: IndexingConfigModel = Field(
        default_factory=IndexingConfigModel, description="Indexing configuration"
    )
    server: ServerConfigModel = Field(
        default_factory=ServerConfigModel, description="Server configuration"
    )

    def to_domain(self) -> AppConfig:
        """Convert to domain value object."""
        return AppConfig(
            repositories=tuple(repo.to_domain() for repo in self.repositories),
            indexing=self.indexing.to_domain(),
            server=self.server.to_domain(),
        )
