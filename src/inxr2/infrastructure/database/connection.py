"""Database connection management and session factory.

Provides async SQLAlchemy engine and session management for PostgreSQL.
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
            database_url: PostgreSQL connection URL (async format).
                         Defaults to DATABASE_URL environment variable.
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/inxr2_dev",
        )

        # Convert postgres:// to postgresql+asyncpg:// if needed
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace(
                "postgres://", "postgresql+asyncpg://", 1
            )
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )

        # Create async engine
        self.engine = create_async_engine(
            self.database_url,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",  # Log SQL queries
            pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
            pool_pre_ping=True,  # Verify connections before using
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
        PostgreSQL connection URL (async format)
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
