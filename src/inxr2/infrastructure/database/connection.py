"""Database connection management and session factory.

Provides async SQLAlchemy engine and session management for PostgreSQL.
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def normalize_database_url(url: str) -> str:
    """Convert postgres:// or postgresql:// to postgresql+asyncpg://.

    Leaves postgresql+asyncpg:// URLs unchanged.
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


class DatabaseConnection:
    """Manages database connection and session creation."""

    def __init__(
        self,
        database_url: str | None = None,
        *,
        echo: bool | None = None,
        pool_size: int | None = None,
        max_overflow: int | None = None,
    ):
        """
        Initialize database connection.

        Args:
            database_url: PostgreSQL connection URL (async format).
                         Defaults to DATABASE_URL environment variable.
            echo: Enable SQL echo logging. Defaults to SQL_ECHO env var.
            pool_size: Connection pool size. Defaults to DB_POOL_SIZE env var.
            max_overflow: Max pool overflow. Defaults to DB_MAX_OVERFLOW env var.
        """
        # Use provided URL or fall back to environment variable with default
        # os.getenv with a default value always returns str (never None)
        default_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/inxr2_dev"
        env_url = os.getenv("DATABASE_URL", default_url)
        self.database_url: str = normalize_database_url(database_url or env_url)

        # Resolve engine config: use explicit params or fall back to env vars
        resolved_echo = (
            echo
            if echo is not None
            else os.getenv("SQL_ECHO", "false").lower() == "true"
        )
        resolved_pool_size = (
            pool_size if pool_size is not None else int(os.getenv("DB_POOL_SIZE", "10"))
        )
        resolved_max_overflow = (
            max_overflow
            if max_overflow is not None
            else int(os.getenv("DB_MAX_OVERFLOW", "20"))
        )

        # Create async engine with connection pooling
        self.engine = create_async_engine(
            self.database_url,
            echo=resolved_echo,
            pool_size=resolved_pool_size,
            max_overflow=resolved_max_overflow,
            pool_pre_ping=True,
        )

        # Create session factory
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Don't expire objects after commit
        )

    async def close(self) -> None:
        """Close database connection and dispose engine."""
        await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Create a new database session (context manager).

        Usage:
            async with db.session() as session:
                # Use session
                await session.commit()
        """
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:  # Catch-all: rollback on any error
                await session.rollback()
                raise
            finally:
                await session.close()


# Global database connection instance
_db_connection: DatabaseConnection | None = None


def init_database(database_url: str | None = None) -> DatabaseConnection:
    """
    Initialize global database connection.

    Args:
        database_url: PostgreSQL connection URL

    Returns:
        DatabaseConnection instance
    """
    global _db_connection
    _db_connection = DatabaseConnection(database_url)
    return _db_connection


def get_database_connection() -> DatabaseConnection:
    """
    Get global database connection.

    Raises:
        RuntimeError: If database not initialized

    Returns:
        DatabaseConnection instance
    """
    if _db_connection is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db_connection


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injection function for FastAPI.

    Usage:
        @app.get("/api/example")
        async def example(session: AsyncSession = Depends(get_async_session)):
            # Use session
            pass
    """
    db = get_database_connection()
    async with db.session() as session:
        yield session


# Alias for consistency with route imports
get_db_session = get_async_session


def get_database_url() -> str:
    """
    Get the database URL from environment or default.

    Returns:
        Database connection URL (async format, PostgreSQL)
    """
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/inxr2_dev",
    )
    return normalize_database_url(url)
