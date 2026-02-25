"""Tests for status_command.show_overall_status."""

from datetime import datetime
from io import StringIO

import pytest
from rich.console import Console

from inxr2.adapters.cli.commands.status_command import _show_overall_status_async
from inxr2.domain.entities import IndexStatus, Repository
from tests.fixtures.test_doubles import (
    InMemoryIndexStatusRepository,
    InMemoryRepositoryRepository,
)


def _make_console() -> tuple[Console, StringIO]:
    """Create a Console that writes to a StringIO buffer."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    return console, buf


@pytest.mark.asyncio
async def test_no_repositories_shows_placeholder() -> None:
    """When no repos exist, show 'No repositories indexed' message."""
    console, buf = _make_console()
    repo_repo = InMemoryRepositoryRepository()
    idx_repo = InMemoryIndexStatusRepository()

    await _show_overall_status_async(
        console, repository_repo=repo_repo, index_status_repo=idx_repo
    )

    output = buf.getvalue()
    assert "No repositories indexed yet." in output
    assert "inxr2 index --config config.yaml" in output


@pytest.mark.asyncio
async def test_repo_with_no_index_status_shows_not_indexed() -> None:
    """A repo that has no index status rows shows 'Not indexed'."""
    console, buf = _make_console()
    repo_repo = InMemoryRepositoryRepository()
    idx_repo = InMemoryIndexStatusRepository()

    await repo_repo.save(Repository(name="my-repo", url="/path/to/my-repo"))

    await _show_overall_status_async(
        console, repository_repo=repo_repo, index_status_repo=idx_repo
    )

    output = buf.getvalue()
    assert "my-repo" in output
    assert "Not indexed" in output


@pytest.mark.asyncio
async def test_repo_with_completed_status_shows_counts() -> None:
    """A repo with a completed index status shows file/symbol/reference counts."""
    console, buf = _make_console()
    repo_repo = InMemoryRepositoryRepository()
    idx_repo = InMemoryIndexStatusRepository()

    repo = await repo_repo.save(Repository(name="test-repo", url="/path/to/test-repo"))
    assert repo.id is not None

    idx_repo.add(
        IndexStatus(
            id=1,
            repository_id=repo.id,
            branch="main",
            indexing_status="completed",
            last_indexed_at=datetime(2026, 2, 24, 10, 30),
            total_files_indexed=42,
            total_symbols_indexed=150,
            total_references_indexed=200,
        )
    )

    await _show_overall_status_async(
        console, repository_repo=repo_repo, index_status_repo=idx_repo
    )

    output = buf.getvalue()
    assert "test-repo" in output
    assert "main" in output
    assert "2026-02-24 10:30" in output
    assert "42" in output
    assert "150" in output
    assert "200" in output
    assert "Completed" in output


@pytest.mark.asyncio
async def test_repo_with_multiple_branches() -> None:
    """A repo indexed on two branches shows one row per branch."""
    console, buf = _make_console()
    repo_repo = InMemoryRepositoryRepository()
    idx_repo = InMemoryIndexStatusRepository()

    repo = await repo_repo.save(Repository(name="multi-branch", url="/path"))
    assert repo.id is not None

    idx_repo.add(
        IndexStatus(
            id=1,
            repository_id=repo.id,
            branch="main",
            indexing_status="completed",
            total_files_indexed=10,
            total_symbols_indexed=20,
            total_references_indexed=30,
        )
    )
    idx_repo.add(
        IndexStatus(
            id=2,
            repository_id=repo.id,
            branch="develop",
            indexing_status="in_progress",
            total_files_indexed=5,
            total_symbols_indexed=8,
            total_references_indexed=12,
        )
    )

    await _show_overall_status_async(
        console, repository_repo=repo_repo, index_status_repo=idx_repo
    )

    output = buf.getvalue()
    assert "main" in output
    assert "develop" in output
    assert "Completed" in output
    assert "In progress" in output


@pytest.mark.asyncio
async def test_failed_status_shows_failed() -> None:
    """A repo with failed indexing shows 'Failed' status."""
    console, buf = _make_console()
    repo_repo = InMemoryRepositoryRepository()
    idx_repo = InMemoryIndexStatusRepository()

    repo = await repo_repo.save(Repository(name="fail-repo", url="/path"))
    assert repo.id is not None

    idx_repo.add(
        IndexStatus(
            id=1,
            repository_id=repo.id,
            branch="main",
            indexing_status="failed",
            total_files_indexed=0,
            total_symbols_indexed=0,
            total_references_indexed=0,
        )
    )

    await _show_overall_status_async(
        console, repository_repo=repo_repo, index_status_repo=idx_repo
    )

    output = buf.getvalue()
    assert "Failed" in output
