"""Database connection management and session factory.

Provides async SQLAlchemy engine and session management.
Supports PostgreSQL (production) and SQLite (testing).
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class DatabaseConnection:
    """Manages database connection and session creation."""

    def __init__(self, database_url: str | None = None):
        """
        Initialize database connection.

        Args:
            database_url: Database connection URL (async format).
                         Supports PostgreSQL and SQLite URLs.
                         Defaults to DATABASE_URL environment variable.
        """
        # Use provided URL or fall back to environment variable with default
        # os.getenv with a default value always returns str (never None)
        default_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/inxr2_dev"
        env_url = os.getenv("DATABASE_URL", default_url)
        self.database_url: str = database_url or env_url

        # Convert postgres:// to postgresql+asyncpg:// if needed
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace(
                "postgres://", "postgresql+asyncpg://", 1
            )
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )

        # Convert sqlite:// to sqlite+aiosqlite:// if needed
        # Note: sqlite+aiosqlite:/// doesn't match startswith("sqlite:///")
        # so no additional check is needed to prevent double conversion
        if self.database_url.startswith("sqlite:///"):
            self.database_url = self.database_url.replace(
                "sqlite:///", "sqlite+aiosqlite:///", 1
            )

        # Create async engine with appropriate settings for the database type
        engine_kwargs: dict[str, object] = {
            "echo": os.getenv("SQL_ECHO", "false").lower() == "true",  # Log SQL queries
        }

        # SQLite doesn't support connection pooling parameters
        if not self.database_url.startswith("sqlite"):
            engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "10"))
            engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "20"))
            engine_kwargs["pool_pre_ping"] = True  # Verify connections before using

        self.engine = create_async_engine(self.database_url, **engine_kwargs)

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
            except Exception:
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
        database_url: Database connection URL (PostgreSQL or SQLite)

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
        Database connection URL (async format, defaults to PostgreSQL)
    """
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/inxr2_dev",
    )

    # Convert postgres:// to postgresql+asyncpg:// if needed
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return url
