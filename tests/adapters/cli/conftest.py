"""Test fixtures for CLI tests with database isolation.

CLI commands create their own DatabaseConnection and manage their own
sessions/commits, so the savepoint pattern used in adapter tests doesn't
apply here. Instead, we create tables before each test and truncate all
tables after.
"""

import asyncio
import os
from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from inxr2.adapters.persistence.models import Base

# PostgreSQL test database URL — use non-asyncpg prefix since
# DatabaseConnection auto-converts postgresql:// → postgresql+asyncpg://
_raw_url = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://inxr2_user:inxr2_dev_password@localhost:5432/inxr2_test",
)
# Strip asyncpg driver if present so DatabaseConnection can do its own conversion
CLI_TEST_DB_URL = _raw_url.replace("+asyncpg", "")

# asyncpg variant for direct engine operations in fixtures
if CLI_TEST_DB_URL.startswith("postgresql://"):
    _ASYNC_URL = CLI_TEST_DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    _ASYNC_URL = CLI_TEST_DB_URL


def _assert_test_database(url: str) -> None:
    """Safety guard: refuse to operate on a non-test database."""
    db_name = url.rsplit("/", 1)[-1].split("?")[0]
    if not db_name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run tests against database '{db_name}' — "
            "TEST_DATABASE_URL must point to a database ending with '_test'."
        )


@pytest.fixture
def cli_test_db() -> Generator[str, None, None]:
    """Provide an isolated PostgreSQL test database for CLI tests.

    Creates all tables before the test and truncates them after.
    Yields a DATABASE_URL suitable for DatabaseConnection (postgresql:// prefix).
    """

    async def setup_db() -> None:
        engine = create_async_engine(_ASYNC_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def teardown_db() -> None:
        engine = create_async_engine(_ASYNC_URL, echo=False)
        async with engine.begin() as conn:
            # Truncate all tables in dependency-safe order
            await conn.execute(
                text(
                    "TRUNCATE TABLE "
                    'text_contents, "references", symbols, files, '
                    "index_status, branch_commits, commits, repositories "
                    "CASCADE"
                )
            )
        await engine.dispose()

    _assert_test_database(CLI_TEST_DB_URL)
    asyncio.run(setup_db())

    yield CLI_TEST_DB_URL

    asyncio.run(teardown_db())


@pytest.fixture
def isolated_cli_runner(
    cli_test_db: str, tmp_path: Path
) -> Generator[CliRunner, None, None]:
    """Create a CliRunner that uses an isolated test database.

    Provides a Click CliRunner configured to use the PostgreSQL test
    database. Also changes CWD to tmp_path so that side-effect files
    (e.g. index.log from _write_csv_log) don't pollute the workspace.

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
