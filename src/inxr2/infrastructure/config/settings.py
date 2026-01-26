"""Application settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings.

    Settings are loaded from environment variables or .env file.

    TODO: Add all configuration options
    TODO: Add validation
    """

    # Database
    database_url: str = (
        "postgresql+asyncpg://inxr2_user:inxr2_dev_password@localhost/inxr2_dev"
    )

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # TODO: Add more settings:
    # - Indexing configuration
    # - Search limits
    # - Git repository cache location
    # - Tree-sitter grammar paths
    # - Logging configuration

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Global settings instance
settings = Settings()
