"""Tests for PostgresTextSearch."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories import (
    PostgresCommitRepository,
    PostgresFileRepository,
    PostgresTextContentRepository,
    PostgresTextSearch,
)
from inxr2.application.ports.services import TextSearchQuery
from inxr2.domain.entities import Commit, File, Repository, TextContent
from inxr2.domain.value_objects import QueryMode, TextSearchSourceType

from .factories import FileFactory


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


@pytest.mark.asyncio
async def test_search_commit_filter_for_file_derived_content(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_second_commit: Commit,
    test_file: File,
) -> None:
    """File-derived content (NULL commit_id) is filtered via commit_files join.

    Regression test for issue #330: file-derived text_contents have commit_id=NULL
    but link to files via source_file_id. The commit filter must join through
    commit_files to determine which file version was present at a given commit.
    """
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_second_commit.id is not None
    assert test_file.id is not None

    file_repo = PostgresFileRepository(db_session)
    repo = PostgresTextContentRepository(db_session)
    search = PostgresTextSearch(db_session)

    # Create a second file version linked only to the second commit
    second_file = await file_repo.save(
        FileFactory.create(
            repository_id=test_repository.id,
            path="src/other.py",
        )
    )
    assert second_file.id is not None
    await file_repo.link_file_to_commit(second_file.id, test_second_commit.id)

    # File-derived content (commit_id=None) for each file version
    await repo.save(
        TextContent(
            repository_id=test_repository.id,
            commit_id=None,
            source_type=TextSearchSourceType.DOCSTRING.value,
            source_file_id=test_file.id,
            source_line=1,
            content="Docstring in first commit file",
            language="python",
            content_type="docstring",
        )
    )
    await repo.save(
        TextContent(
            repository_id=test_repository.id,
            commit_id=None,
            source_type=TextSearchSourceType.DOCSTRING.value,
            source_file_id=second_file.id,
            source_line=1,
            content="Docstring in second commit file",
            language="python",
            content_type="docstring",
        )
    )
    await db_session.commit()

    # Filter to first commit — should only find the first file's docstring
    query = TextSearchQuery(
        query="Docstring",
        mode=QueryMode.REGEX.value,
        repository_id=test_repository.id,
        commit_id=test_commit.id,
    )
    results, total = await search.search(query)

    assert total == 1
    assert results[0].text_content.content == "Docstring in first commit file"

    # Filter to second commit — should only find the second file's docstring
    query2 = TextSearchQuery(
        query="Docstring",
        mode=QueryMode.REGEX.value,
        repository_id=test_repository.id,
        commit_id=test_second_commit.id,
    )
    results2, total2 = await search.search(query2)

    assert total2 == 1
    assert results2[0].text_content.content == "Docstring in second commit file"


@pytest.mark.asyncio
async def test_keyword_search_returns_headline(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test that keyword mode returns a ts_headline with <mark> tags."""
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_file.id is not None

    repo = PostgresTextContentRepository(db_session)
    search = PostgresTextSearch(db_session)

    await repo.save(
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            source_type=TextSearchSourceType.COMMENT.value,
            source_file_id=test_file.id,
            source_line=1,
            content="Initialize the rich console for output",
            language="python",
        )
    )
    await db_session.commit()

    query = TextSearchQuery(
        query="console",
        mode=QueryMode.KEYWORD.value,
        repository_id=test_repository.id,
    )
    results, total = await search.search(query)

    assert total == 1
    assert results[0].headline is not None
    assert "<mark>" in results[0].headline
    assert "</mark>" in results[0].headline


@pytest.mark.asyncio
async def test_phrase_search_returns_headline(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test that phrase mode returns a ts_headline with <mark> tags."""
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_file.id is not None

    repo = PostgresTextContentRepository(db_session)
    search = PostgresTextSearch(db_session)

    await repo.save(
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            source_type=TextSearchSourceType.COMMENT.value,
            source_file_id=test_file.id,
            source_line=1,
            content="Initialize the rich console for output",
            language="python",
        )
    )
    await db_session.commit()

    query = TextSearchQuery(
        query="rich console",
        mode=QueryMode.PHRASE.value,
        repository_id=test_repository.id,
    )
    results, total = await search.search(query)

    assert total == 1
    assert results[0].headline is not None
    assert "<mark>" in results[0].headline


@pytest.mark.asyncio
async def test_regex_search_returns_no_headline(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test that regex mode returns headline=None (no ts_headline for regex)."""
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_file.id is not None

    repo = PostgresTextContentRepository(db_session)
    search = PostgresTextSearch(db_session)

    await repo.save(
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            source_type=TextSearchSourceType.COMMENT.value,
            source_file_id=test_file.id,
            source_line=1,
            content="Initialize the rich console for output",
            language="python",
        )
    )
    await db_session.commit()

    query = TextSearchQuery(
        query="console",
        mode=QueryMode.REGEX.value,
        repository_id=test_repository.id,
    )
    results, total = await search.search(query)

    assert total == 1
    assert results[0].headline is None


@pytest.mark.asyncio
async def test_headline_shows_stemmed_match(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test that ts_headline marks the actual stemmed word, not the query word.

    This is the core problem being solved: searching "initialize" should mark
    "Initial" in the headline because PostgreSQL stems both to the same root.
    """
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_file.id is not None

    repo = PostgresTextContentRepository(db_session)
    search = PostgresTextSearch(db_session)

    await repo.save(
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            source_type=TextSearchSourceType.COMMENT.value,
            source_file_id=test_file.id,
            source_line=1,
            content="Initial setup of the database connection pool",
            language="python",
        )
    )
    await db_session.commit()

    query = TextSearchQuery(
        query="initialize",
        mode=QueryMode.KEYWORD.value,
        repository_id=test_repository.id,
    )
    results, total = await search.search(query)

    assert total == 1
    assert results[0].headline is not None
    # ts_headline should mark "Initial" — the actual word in the content
    assert "<mark>Initial</mark>" in results[0].headline


@pytest.mark.asyncio
async def test_search_branch_filter_finds_file_based_content(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test branch filter finds comments/docstrings that have NULL commit_id.

    File-derived text content (comments, docstrings, file_content) stores
    source_file_id but not commit_id. Branch filtering must join through
    commit_files to reach branch_commits.
    """
    assert test_repository.id is not None
    assert test_commit.id is not None
    assert test_file.id is not None

    commit_repo = PostgresCommitRepository(db_session)
    text_repo = PostgresTextContentRepository(db_session)
    search = PostgresTextSearch(db_session)

    # Link commit to branch "main"
    await commit_repo.link_commit_to_branch(test_repository.id, test_commit.id, "main")

    # Create comment with NULL commit_id (file-derived, as real indexing does)
    await text_repo.save(
        TextContent(
            repository_id=test_repository.id,
            commit_id=None,
            source_type=TextSearchSourceType.COMMENT.value,
            source_file_id=test_file.id,
            source_line=10,
            content="Initialize rich console for output",
            language="python",
        )
    )
    await db_session.commit()

    # Search with branch filter — should find the comment
    query = TextSearchQuery(
        query="console",
        mode=QueryMode.KEYWORD.value,
        repository_id=test_repository.id,
        branch="main",
    )
    results, total = await search.search(query)

    assert total >= 1
    assert any(
        r.text_content.content == "Initialize rich console for output" for r in results
    )

    # Search with non-existent branch — should find nothing
    query_other = TextSearchQuery(
        query="console",
        mode=QueryMode.KEYWORD.value,
        repository_id=test_repository.id,
        branch="nonexistent-branch",
    )
    results_other, total_other = await search.search(query_other)

    assert total_other == 0


@pytest.mark.asyncio
async def test_search_branch_filter_finds_commit_messages(
    db_session: AsyncSession,
    test_repository: Repository,
    test_commit: Commit,
    test_file: File,
) -> None:
    """Test branch filter finds commit messages that have commit_id but NULL source_file_id."""
    assert test_repository.id is not None
    assert test_commit.id is not None

    commit_repo = PostgresCommitRepository(db_session)
    text_repo = PostgresTextContentRepository(db_session)
    search = PostgresTextSearch(db_session)

    # Link commit to branch "main"
    await commit_repo.link_commit_to_branch(test_repository.id, test_commit.id, "main")

    # Create commit message with commit_id but NULL source_file_id
    await text_repo.save(
        TextContent(
            repository_id=test_repository.id,
            commit_id=test_commit.id,
            source_type=TextSearchSourceType.COMMIT_MESSAGE.value,
            source_file_id=None,
            source_line=None,
            content="feat: Add console logging support",
            language=None,
        )
    )
    await db_session.commit()

    # Search with branch filter — should find the commit message
    query = TextSearchQuery(
        query="console",
        mode=QueryMode.KEYWORD.value,
        repository_id=test_repository.id,
        branch="main",
    )
    results, total = await search.search(query)

    assert total >= 1
    assert any(
        r.text_content.source_type == TextSearchSourceType.COMMIT_MESSAGE.value
        for r in results
    )
