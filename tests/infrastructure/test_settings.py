"""Tests for application settings."""

import os
from unittest.mock import patch

from inxr2.infrastructure.config.settings import Settings


class TestSettings:
    """Tests for Settings class."""

    def test_default_database_url(self) -> None:
        """Settings should have a default database URL."""
        # Create settings without any env vars set
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert "postgresql" in settings.database_url
            assert "asyncpg" in settings.database_url

    def test_default_api_host(self) -> None:
        """Settings should have default API host of 0.0.0.0."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.api_host == "0.0.0.0"

    def test_default_api_port(self) -> None:
        """Settings should have default API port of 8000."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.api_port == 8000

    def test_database_url_from_environment(self) -> None:
        """Settings should load database URL from environment."""
        custom_url = "postgresql+asyncpg://user:pass@host:5432/db"
        with patch.dict(os.environ, {"DATABASE_URL": custom_url}, clear=True):
            settings = Settings()
            assert settings.database_url == custom_url

    def test_api_host_from_environment(self) -> None:
        """Settings should load API host from environment."""
        with patch.dict(os.environ, {"API_HOST": "127.0.0.1"}, clear=True):
            settings = Settings()
            assert settings.api_host == "127.0.0.1"

    def test_api_port_from_environment(self) -> None:
        """Settings should load API port from environment."""
        with patch.dict(os.environ, {"API_PORT": "9000"}, clear=True):
            settings = Settings()
            assert settings.api_port == 9000

    def test_api_port_type_conversion(self) -> None:
        """Settings should convert API port string to int."""
        with patch.dict(os.environ, {"API_PORT": "3000"}, clear=True):
            settings = Settings()
            assert isinstance(settings.api_port, int)
            assert settings.api_port == 3000
