"""Shared fixtures for API integration tests."""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.infrastructure.database import get_database_connection, get_db_session
from inxr2.infrastructure.fastapi.app import create_app


@pytest_asyncio.fixture
async def test_app(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[FastAPI, None]:
    """Create a FastAPI app with the database session overridden to the test session.

    ``create_app()`` calls ``init_database()``, which builds a fresh async engine
    (and asyncpg connection pool) and installs it as the process-wide connection,
    orphaning whichever one was there before. Since every test here builds its own
    app, the engine must be disposed on teardown — otherwise each test leaves a
    live pool behind for the garbage collector, surfacing as ``ResourceWarning:
    unclosed connection`` / ``unclosed transport`` at interpreter shutdown.

    The connection is captured immediately after ``create_app()`` rather than read
    back at teardown, so disposal always targets this app's engine.

    The DB-backed HTTP query log is disabled first. Overriding ``get_db_session``
    does not reach it: ``create_app()`` wires ``HttpLoggingMiddleware`` with a
    factory that calls ``get_database_connection()`` directly, so every request to
    an /api/* path would INSERT a query_log row over the process-wide
    ``DATABASE_URL`` connection — the *dev* database — outside this test's isolated
    session. CLAUDE.md: tests must never touch the live database. The flag is read
    at import time into a module global, so the attribute has to be patched, and it
    has to happen before ``create_app()`` reads it.
    """
    monkeypatch.setattr(
        "inxr2.infrastructure.fastapi.app._LOG_HTTP_REQUESTS", False, raising=True
    )

    app = create_app()
    db_connection = get_database_connection()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db

    try:
        yield app
    finally:
        await db_connection.close()
