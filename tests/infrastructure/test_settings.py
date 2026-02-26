"""Tests for application settings."""

from inxr2.infrastructure.config.settings import Settings


class TestSettings:
    """Tests for Settings class."""

    def test_database_url_can_be_configured(self) -> None:
        """Settings should accept a database URL."""
        custom_url = "postgresql+asyncpg://user:pass@host:5432/db"
        settings = Settings(database_url=custom_url)
        assert settings.database_url == custom_url

    def test_api_host_can_be_configured(self) -> None:
        """Settings should accept an API host."""
        settings = Settings(api_host="127.0.0.1")
        assert settings.api_host == "127.0.0.1"

    def test_api_port_can_be_configured(self) -> None:
        """Settings should accept an API port."""
        settings = Settings(api_port=9000)
        assert settings.api_port == 9000

    def test_api_port_type_coercion(self) -> None:
        """Settings should coerce API port string to int."""
        settings = Settings(api_port="3000")  # type: ignore[arg-type]
        assert isinstance(settings.api_port, int)
        assert settings.api_port == 3000

    def test_default_values(self) -> None:
        """Settings should have sensible defaults."""
        settings = Settings()
        assert "postgresql" in settings.database_url
        assert settings.api_host == "0.0.0.0"
        assert isinstance(settings.api_port, int)
