"""Test fixtures for CLI tests with database isolation."""

import asyncio
import os
from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner
from sqlalchemy.ext.asyncio import create_async_engine

from inxr2.adapters.persistence.models import Base


@pytest.fixture
def cli_test_db(tmp_path: Path) -> Generator[str, None, None]:
    """Create an isolated SQLite database for CLI tests.

    This fixture creates a temporary file-based SQLite database with the
    full schema, suitable for CLI integration tests that need database
    access without touching the live PostgreSQL database.

    Yields:
        The DATABASE_URL string for the test database.
    """
    db_path = tmp_path / "cli_test.db"
    db_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"

    async def setup_db() -> None:
        """Create all tables in the test database."""
        engine = create_async_engine(db_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    # Run async setup synchronously using asyncio.run()
    asyncio.run(setup_db())

    yield db_url

    # Cleanup is automatic via tmp_path fixture


@pytest.fixture
def isolated_cli_runner(
    cli_test_db: str, tmp_path: Path
) -> Generator[CliRunner, None, None]:
    """Create a CliRunner that uses an isolated test database.

    This fixture provides a Click CliRunner configured to use a temporary
    SQLite database instead of the live PostgreSQL database. Use this for
    any CLI tests that invoke commands which access the database.

    Also changes CWD to tmp_path so that side-effect files (e.g. index.log
    from _write_csv_log) don't pollute the workspace.

    Args:
        cli_test_db: The test database URL from cli_test_db fixture.
        tmp_path: Temporary directory for test artifacts.

    Yields:
        A CliRunner with DATABASE_URL set to the test database.
    """
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        yield CliRunner(env={"DATABASE_URL": cli_test_db})
    finally:
        os.chdir(original_cwd)
