"""Tests for database connection management."""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

import inxr2.infrastructure.database.connection as conn_module
from inxr2.infrastructure.database.connection import (
    DatabaseConnection,
    get_database_connection,
    get_database_url,
    init_database,
    normalize_database_url,
)


class TestNormalizeDatabaseUrl:
    """Tests for URL normalization helper."""

    def test_converts_postgres_url(self) -> None:
        """normalize_database_url should convert postgres:// to postgresql+asyncpg://."""
        result = normalize_database_url("postgres://user:pass@host:5432/db")
        assert result == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_converts_postgresql_url(self) -> None:
        """normalize_database_url should convert postgresql:// to postgresql+asyncpg://."""
        result = normalize_database_url("postgresql://user:pass@host:5432/db")
        assert result == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_preserves_asyncpg_url(self) -> None:
        """normalize_database_url should preserve postgresql+asyncpg:// URLs."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        assert normalize_database_url(url) == url


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

    def test_default_url_is_valid_postgresql(self) -> None:
        """DatabaseConnection with no args should produce a valid async URL."""
        conn = DatabaseConnection()
        assert "postgresql" in conn.database_url
        assert "asyncpg" in conn.database_url


class TestGetDatabaseUrl:
    """Tests for get_database_url function."""

    def test_returns_valid_async_url(self) -> None:
        """get_database_url should return a postgresql+asyncpg:// URL."""
        result = get_database_url()
        assert "postgresql+asyncpg" in result


class TestInitAndGetDatabaseConnection:
    """Tests for init_database and get_database_connection functions."""

    def test_get_database_connection_raises_when_not_initialized(self) -> None:
        """get_database_connection should raise RuntimeError when not initialized."""
        # Reset global state
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

    def test_default_echo_is_false(self) -> None:
        """DatabaseConnection should have SQL echo disabled by default."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        conn = DatabaseConnection(url)
        assert conn.engine.echo is False

    def test_explicit_echo_enabled(self) -> None:
        """DatabaseConnection should enable SQL echo when passed explicitly."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        conn = DatabaseConnection(url, echo=True)
        assert conn.engine.echo is True

    def test_explicit_echo_disabled(self) -> None:
        """DatabaseConnection should disable SQL echo when passed explicitly."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        conn = DatabaseConnection(url, echo=False)
        assert conn.engine.echo is False

    def test_explicit_pool_size(self) -> None:
        """DatabaseConnection should accept explicit pool size."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        conn = DatabaseConnection(url, pool_size=5)
        assert conn.engine is not None

    def test_default_pool_creates_engine(self) -> None:
        """DatabaseConnection with default pool config should create a valid engine."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        conn = DatabaseConnection(url)
        assert conn.engine is not None
