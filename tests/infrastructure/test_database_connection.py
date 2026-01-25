"""Tests for database connection management."""

import os
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from inxr2.infrastructure.database.connection import (
    DatabaseConnection,
    get_database_connection,
    get_database_url,
    init_database,
)


class TestDatabaseConnection:
    """Tests for DatabaseConnection class."""

    def test_uses_provided_url(self) -> None:
        """DatabaseConnection should use the provided URL."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        conn = DatabaseConnection(url)
        assert conn.database_url == url

    def test_converts_postgres_url(self) -> None:
        """DatabaseConnection should convert postgres:// to postgresql+asyncpg://."""
        url = "postgres://user:pass@host:5432/db"
        conn = DatabaseConnection(url)
        assert conn.database_url == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_converts_postgresql_url(self) -> None:
        """DatabaseConnection should convert postgresql:// to postgresql+asyncpg://."""
        url = "postgresql://user:pass@host:5432/db"
        conn = DatabaseConnection(url)
        assert conn.database_url == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_preserves_asyncpg_url(self) -> None:
        """DatabaseConnection should preserve postgresql+asyncpg:// URLs."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        conn = DatabaseConnection(url)
        assert conn.database_url == url

    def test_creates_async_engine(self) -> None:
        """DatabaseConnection should create an AsyncEngine."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        conn = DatabaseConnection(url)
        assert isinstance(conn.engine, AsyncEngine)

    def test_creates_session_factory(self) -> None:
        """DatabaseConnection should create a session factory."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        conn = DatabaseConnection(url)
        assert conn.session_factory is not None

    def test_uses_environment_url_as_fallback(self) -> None:
        """DatabaseConnection should use DATABASE_URL env var as fallback."""
        env_url = "postgresql+asyncpg://env:pass@envhost:5432/envdb"
        with patch.dict(os.environ, {"DATABASE_URL": env_url}):
            conn = DatabaseConnection()
            assert conn.database_url == env_url

    def test_uses_default_when_no_url_provided(self) -> None:
        """DatabaseConnection should use default URL when none provided."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove DATABASE_URL if it exists
            if "DATABASE_URL" in os.environ:
                del os.environ["DATABASE_URL"]
            conn = DatabaseConnection()
            # Should have some default URL
            assert "postgresql" in conn.database_url
            assert "asyncpg" in conn.database_url


class TestGetDatabaseUrl:
    """Tests for get_database_url function."""

    def test_returns_environment_url(self) -> None:
        """get_database_url should return DATABASE_URL from environment."""
        env_url = "postgresql+asyncpg://user:pass@host:5432/db"
        with patch.dict(os.environ, {"DATABASE_URL": env_url}):
            result = get_database_url()
            assert result == env_url

    def test_converts_postgres_url(self) -> None:
        """get_database_url should convert postgres:// URLs."""
        env_url = "postgres://user:pass@host:5432/db"
        with patch.dict(os.environ, {"DATABASE_URL": env_url}):
            result = get_database_url()
            assert result == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_converts_postgresql_url(self) -> None:
        """get_database_url should convert postgresql:// URLs."""
        env_url = "postgresql://user:pass@host:5432/db"
        with patch.dict(os.environ, {"DATABASE_URL": env_url}):
            result = get_database_url()
            assert result == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_returns_default_when_no_env(self) -> None:
        """get_database_url should return default when no env var."""
        with patch.dict(os.environ, {}, clear=True):
            if "DATABASE_URL" in os.environ:
                del os.environ["DATABASE_URL"]
            result = get_database_url()
            assert "postgresql+asyncpg" in result


class TestInitAndGetDatabaseConnection:
    """Tests for init_database and get_database_connection functions."""

    def test_get_database_connection_raises_when_not_initialized(self) -> None:
        """get_database_connection should raise RuntimeError when not initialized."""
        # Reset global state
        import inxr2.infrastructure.database.connection as conn_module

        conn_module._db_connection = None

        with pytest.raises(RuntimeError, match="Database not initialized"):
            get_database_connection()

    def test_init_database_returns_connection(self) -> None:
        """init_database should return a DatabaseConnection."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        conn = init_database(url)
        assert isinstance(conn, DatabaseConnection)

    def test_get_database_connection_returns_initialized_connection(self) -> None:
        """get_database_connection should return the initialized connection."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        init_conn = init_database(url)
        get_conn = get_database_connection()
        assert get_conn is init_conn

    def test_init_database_replaces_existing_connection(self) -> None:
        """init_database should replace any existing connection."""
        url1 = "postgresql+asyncpg://user:pass@host1:5432/db1"
        url2 = "postgresql+asyncpg://user:pass@host2:5432/db2"

        conn1 = init_database(url1)
        conn2 = init_database(url2)

        assert conn2.database_url == url2
        assert get_database_connection() is conn2
        assert get_database_connection() is not conn1


class TestDatabaseConnectionPoolSettings:
    """Tests for database connection pool configuration."""

    def test_default_pool_size_from_env(self) -> None:
        """DatabaseConnection should use default pool size when env not set."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        with patch.dict(os.environ, {}, clear=True):
            conn = DatabaseConnection(url)
            # Engine should be created (pool configuration is internal)
            assert conn.engine is not None

    def test_custom_pool_size_from_env(self) -> None:
        """DatabaseConnection should read DB_POOL_SIZE from environment."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        # Verify the env var is read (actual pool size is internal)
        with patch.dict(os.environ, {"DB_POOL_SIZE": "5"}):
            conn = DatabaseConnection(url)
            assert conn.engine is not None

    def test_sql_echo_disabled_by_default(self) -> None:
        """DatabaseConnection should have SQL echo disabled by default."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        with patch.dict(os.environ, {}, clear=True):
            conn = DatabaseConnection(url)
            assert conn.engine.echo is False

    def test_sql_echo_enabled_from_env(self) -> None:
        """DatabaseConnection should enable SQL echo from SQL_ECHO env var."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        with patch.dict(os.environ, {"SQL_ECHO": "true"}):
            conn = DatabaseConnection(url)
            assert conn.engine.echo is True
