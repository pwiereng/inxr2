"""Tests for PostgresTextSearch."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories import (
    PostgresTextContentRepository,
    PostgresTextSearch,
)
from inxr2.application.ports.services import TextSearchQuery
from inxr2.domain.entities import Commit, File, Repository, TextContent
from inxr2.domain.value_objects import QueryMode, TextSearchSourceType


@pytest.mark.asyncio
async def test_search_empty_query_raises_error(db_session: AsyncSession) -> None:
    """Test that empty query raises ValueError."""
    search = PostgresTextSearch(db_session)

    query = TextSearchQuery(query="")

    with pytest.raises(ValueError, match="Search query cannot be empty"):
        await search.search(query)


@pytest.mark.asyncio
async def test_search_with_repository_filter(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test search filtered by repository."""
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_file.id is not None

    repo = PostgresTextContentRepository(db_session)
    search = PostgresTextSearch(db_session)

    # Create test text content
    text_content = TextContent(
        repository_id=test_repository.id,
        commit_id=test_commit.id,
        source_type=TextSearchSourceType.COMMENT.value,
        source_file_id=test_file.id,
        source_line=10,
        content="TODO refactor this code",
        language="python",
    )
    await repo.save(text_content)
    await db_session.commit()

    # Search in regex mode (regex mode)
    query = TextSearchQuery(
        query="TODO",
        mode=QueryMode.REGEX.value,
        repository_id=test_repository.id,
    )

    results, total = await search.search(query)

    assert total == 1
    assert len(results) == 1
    assert results[0].text_content.content == "TODO refactor this code"


@pytest.mark.asyncio
async def test_search_regex_mode(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test regex search mode."""
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_file.id is not None

    repo = PostgresTextContentRepository(db_session)
    search = PostgresTextSearch(db_session)

    # Create test text contents
    text_contents = [
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            source_type=TextSearchSourceType.COMMENT.value,
            source_file_id=test_file.id,
            source_line=i,
            content=content,
            language="python",
        )
        for i, content in enumerate(
            [
                "TODO: fix bug",
                "FIXME: handle edge case",
                "NOTE: this is important",
                "Just a regular comment",
            ],
            start=1,
        )
    ]
    await repo.save_batch(text_contents)
    await db_session.commit()

    # Search for comments starting with uppercase words (TODO, FIXME, NOTE)
    query = TextSearchQuery(
        query="^[A-Z]+:",  # Regex pattern
        mode=QueryMode.REGEX.value,
        repository_id=test_repository.id,
    )

    results, total = await search.search(query)

    assert total == 3
    assert len(results) == 3
    assert all(":" in r.text_content.content for r in results)


@pytest.mark.asyncio
async def test_search_with_source_type_filter(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test search filtered by source type."""
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_file.id is not None

    repo = PostgresTextContentRepository(db_session)
    search = PostgresTextSearch(db_session)

    # Create mixed source types
    text_contents = [
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            source_type=TextSearchSourceType.COMMENT.value,
            source_file_id=test_file.id,
            source_line=1,
            content="A comment with keyword",
            language="python",
        ),
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            source_type=TextSearchSourceType.DOCSTRING.value,
            source_file_id=test_file.id,
            source_line=5,
            content="A docstring with keyword",
            language="python",
        ),
    ]
    await repo.save_batch(text_contents)
    await db_session.commit()

    # Search only in comments
    query = TextSearchQuery(
        query="keyword",
        mode=QueryMode.REGEX.value,
        repository_id=test_repository.id,
        source_types=[TextSearchSourceType.COMMENT.value],
    )

    results, total = await search.search(query)

    assert total == 1
    assert results[0].text_content.source_type == TextSearchSourceType.COMMENT.value


@pytest.mark.asyncio
async def test_search_with_language_filter(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test search filtered by language."""
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_file.id is not None

    repo = PostgresTextContentRepository(db_session)
    search = PostgresTextSearch(db_session)

    # Create content in different languages
    text_contents = [
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            source_type=TextSearchSourceType.COMMENT.value,
            source_file_id=test_file.id,
            source_line=i,
            content=f"Comment {i}",
            language=lang,
        )
        for i, lang in enumerate(["python", "typescript", "python"], start=1)
    ]
    await repo.save_batch(text_contents)
    await db_session.commit()

    # Search only Python files
    query = TextSearchQuery(
        query="Comment",
        mode=QueryMode.REGEX.value,
        repository_id=test_repository.id,
        languages=["python"],
    )

    results, total = await search.search(query)

    assert total == 2
    assert all(r.text_content.language == "python" for r in results)


@pytest.mark.asyncio
async def test_search_pagination(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test search pagination."""
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_file.id is not None

    repo = PostgresTextContentRepository(db_session)
    search = PostgresTextSearch(db_session)

    # Create 10 text contents
    text_contents = [
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            source_type=TextSearchSourceType.COMMENT.value,
            source_file_id=test_file.id,
            source_line=i,
            content=f"Test comment {i}",
            language="python",
        )
        for i in range(1, 11)
    ]
    await repo.save_batch(text_contents)
    await db_session.commit()

    # First page
    query1 = TextSearchQuery(
        query="Test",
        mode=QueryMode.REGEX.value,
        repository_id=test_repository.id,
        limit=5,
        offset=0,
    )
    results1, total1 = await search.search(query1)

    assert total1 == 10
    assert len(results1) == 5

    # Second page
    query2 = TextSearchQuery(
        query="Test",
        mode=QueryMode.REGEX.value,
        repository_id=test_repository.id,
        limit=5,
        offset=5,
    )
    results2, total2 = await search.search(query2)

    assert total2 == 10
    assert len(results2) == 5

    # No overlap
    ids1 = {r.text_content.id for r in results1}
    ids2 = {r.text_content.id for r in results2}
    assert len(ids1 & ids2) == 0


@pytest.mark.asyncio
async def test_search_pagination_deterministic_with_tied_ranks(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test pagination is deterministic when multiple rows have the same rank.

    Without a tiebreaker (e.g., id), rows with identical ts_rank scores can
    shuffle across pages, causing duplicates on one page and missing results
    on another.
    """
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_file.id is not None

    repo = PostgresTextContentRepository(db_session)
    search = PostgresTextSearch(db_session)

    # Create 10 text contents with identical keyword content so they all
    # get the same ts_rank score
    text_contents = [
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            source_type=TextSearchSourceType.COMMENT.value,
            source_file_id=test_file.id,
            source_line=i,
            content=f"identical keyword line {i}",
            language="python",
        )
        for i in range(1, 11)
    ]
    await repo.save_batch(text_contents)
    await db_session.commit()

    # Fetch page 1
    query1 = TextSearchQuery(
        query="identical keyword",
        mode=QueryMode.KEYWORD.value,
        repository_id=test_repository.id,
        limit=5,
        offset=0,
    )
    results1, total1 = await search.search(query1)

    # Fetch page 2
    query2 = TextSearchQuery(
        query="identical keyword",
        mode=QueryMode.KEYWORD.value,
        repository_id=test_repository.id,
        limit=5,
        offset=5,
    )
    results2, total2 = await search.search(query2)

    assert total1 == 10
    assert total2 == 10
    assert len(results1) == 5
    assert len(results2) == 5

    # No overlap between pages - this would fail without a tiebreaker
    ids1 = {r.text_content.id for r in results1}
    ids2 = {r.text_content.id for r in results2}
    assert (
        len(ids1 & ids2) == 0
    ), f"Pages overlap: {ids1 & ids2} - pagination is non-deterministic"


@pytest.mark.asyncio
async def test_search_with_commit_filter(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_second_commit: Commit,
    test_file: File,
) -> None:
    """Test search filtered by specific commit (time travel)."""
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_second_commit.id is not None
    assert test_file.id is not None

    repo = PostgresTextContentRepository(db_session)
    search = PostgresTextSearch(db_session)

    # Create content in different commits
    await repo.save(
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            source_type=TextSearchSourceType.COMMENT.value,
            source_file_id=test_file.id,
            source_line=1,
            content="Old comment",
            language="python",
        )
    )
    await repo.save(
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_second_commit.id,
            source_type=TextSearchSourceType.COMMENT.value,
            source_file_id=test_file.id,
            source_line=1,
            content="New comment",
            language="python",
        )
    )
    await db_session.commit()

    # Search only in first commit
    query = TextSearchQuery(
        query="comment",
        mode=QueryMode.REGEX.value,
        repository_id=test_repository.id,
        commit_id=test_commit.id,
    )

    results, total = await search.search(query)

    assert total == 1
    assert results[0].text_content.content == "Old comment"
