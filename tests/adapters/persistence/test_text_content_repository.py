"""Tests for PostgresTextContentRepository."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories import PostgresTextContentRepository
from inxr2.domain.entities import Commit, File, Repository, TextContent
from inxr2.domain.value_objects import TextSearchSourceType


@pytest.mark.asyncio
async def test_save_text_content(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test saving a text content entry."""
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_file.id is not None

    repo = PostgresTextContentRepository(db_session)

    text_content = TextContent(
        repository_id=test_repository.id,
        commit_id=test_commit.id,
        source_type=TextSearchSourceType.COMMENT.value,
        source_file_id=test_file.id,
        source_line=10,
        source_end_line=10,
        content="TODO: refactor this function",
        language="python",
        content_type="single_line_comment",
    )

    saved = await repo.save(text_content)

    assert saved.id is not None
    assert saved.repository_id == test_repository.id
    assert saved.commit_id == test_commit.id
    assert saved.source_type == TextSearchSourceType.COMMENT.value
    assert saved.content == "TODO: refactor this function"
    assert saved.source_line == 10
    assert saved.indexed_at is not None


@pytest.mark.asyncio
async def test_save_batch(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test batch saving text contents."""
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_file.id is not None

    repo = PostgresTextContentRepository(db_session)

    text_contents = [
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            source_type=TextSearchSourceType.COMMENT.value,
            source_file_id=test_file.id,
            source_line=i,
            content=f"Comment {i}",
            language="python",
        )
        for i in range(1, 6)
    ]

    saved = await repo.save_batch(text_contents)

    assert len(saved) == 5
    assert all(tc.id is not None for tc in saved)
    assert all(tc.repository_id == test_repository.id for tc in saved)


@pytest.mark.asyncio
async def test_delete_by_commit(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test deleting text contents by commit."""
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_file.id is not None

    repo = PostgresTextContentRepository(db_session)

    # Create some text contents
    text_contents = [
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            source_type=TextSearchSourceType.COMMENT.value,
            source_file_id=test_file.id,
            source_line=i,
            content=f"Comment {i}",
            language="python",
        )
        for i in range(1, 4)
    ]
    await repo.save_batch(text_contents)

    # Delete by commit
    deleted_count = await repo.delete_by_commit(test_commit.id)

    assert deleted_count == 3


@pytest.mark.asyncio
async def test_delete_by_file(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test deleting text contents by file."""
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_file.id is not None

    repo = PostgresTextContentRepository(db_session)

    # Create some text contents
    text_contents = [
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            source_type=TextSearchSourceType.COMMENT.value,
            source_file_id=test_file.id,
            source_line=i,
            content=f"Comment {i}",
            language="python",
        )
        for i in range(1, 4)
    ]
    await repo.save_batch(text_contents)

    # Delete by file
    deleted_count = await repo.delete_by_file(test_file.id)

    assert deleted_count == 3


@pytest.mark.asyncio
async def test_save_commit_message_without_file(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
) -> None:
    """Test saving commit message text content (no file)."""
    assert test_repository.id is not None
    assert test_commit.id is not None

    repo = PostgresTextContentRepository(db_session)

    text_content = TextContent(
        repository_id=test_repository.id,
        commit_id=test_commit.id,
        source_type=TextSearchSourceType.COMMIT_MESSAGE.value,
        source_file_id=None,  # Commit messages don't have file
        source_line=None,
        content="fix: resolve database connection issue",
        language=None,
        content_type="commit_message",
    )

    saved = await repo.save(text_content)

    assert saved.id is not None
    assert saved.source_file_id is None
    assert saved.source_line is None
    assert saved.content == "fix: resolve database connection issue"
