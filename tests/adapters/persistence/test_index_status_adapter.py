"""Integration tests for PostgresIndexStatusRepository."""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.index_status_adapter import (
    PostgresIndexStatusRepository,
)
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from inxr2.domain.entities import IndexStatus

from .factories import RepositoryFactory


async def _make_repo(db_session: AsyncSession, name: str = "test-repo") -> int:
    """Create a repository and return its ID."""
    repo = await PostgresRepositoryAdapter(db_session).save(
        RepositoryFactory.create(name=name)
    )
    assert repo.id is not None
    await db_session.commit()
    return repo.id


def _status(repo_id: int, branch: str = "main", **kwargs: Any) -> IndexStatus:
    """Shorthand for constructing an IndexStatus."""
    return IndexStatus(
        repository_id=repo_id,
        branch=branch,
        **kwargs,
    )


@pytest.mark.asyncio
class TestSaveUpsert:
    """save() — insert vs update (upsert) behaviour."""

    async def test_insert_new_status(self, db_session: AsyncSession) -> None:
        repo_id = await _make_repo(db_session)
        adapter = PostgresIndexStatusRepository(db_session)

        saved = await adapter.save(_status(repo_id))
        assert saved.id is not None
        assert saved.repository_id == repo_id
        assert saved.branch == "main"
        assert saved.indexing_status == "pending"

    async def test_upsert_updates_existing_entry(
        self, db_session: AsyncSession
    ) -> None:
        """Saving a second time for same repo+branch updates rather than inserts."""
        repo_id = await _make_repo(db_session)
        adapter = PostgresIndexStatusRepository(db_session)

        first = await adapter.save(_status(repo_id, indexing_status="pending"))
        assert first.id is not None

        updated = await adapter.save(
            _status(repo_id, indexing_status="completed", total_commits_indexed=5)
        )
        assert updated.id == first.id
        assert updated.indexing_status == "completed"
        assert updated.total_commits_indexed == 5

    async def test_upsert_preserves_original_created_at(
        self, db_session: AsyncSession
    ) -> None:
        """Upsert must preserve created_at from the first insert."""
        repo_id = await _make_repo(db_session)
        adapter = PostgresIndexStatusRepository(db_session)

        first = await adapter.save(_status(repo_id))
        await db_session.commit()
        original_created_at = first.created_at

        second = await adapter.save(_status(repo_id, indexing_status="in_progress"))
        assert second.created_at == original_created_at

    async def test_different_branches_are_separate_entries(
        self, db_session: AsyncSession
    ) -> None:
        """main and develop branches are stored as separate rows."""
        repo_id = await _make_repo(db_session)
        adapter = PostgresIndexStatusRepository(db_session)

        main_status = await adapter.save(_status(repo_id, branch="main"))
        dev_status = await adapter.save(_status(repo_id, branch="develop"))

        assert main_status.id is not None
        assert dev_status.id is not None
        assert main_status.id != dev_status.id

    async def test_save_stores_all_fields(self, db_session: AsyncSession) -> None:
        repo_id = await _make_repo(db_session)
        adapter = PostgresIndexStatusRepository(db_session)

        saved = await adapter.save(
            _status(
                repo_id,
                indexing_status="completed",
                last_indexed_commit="a" * 40,
                oldest_indexed_commit="b" * 40,
                total_commits_indexed=10,
                total_files_indexed=200,
                total_symbols_indexed=1500,
                total_references_indexed=3000,
                last_indexing_duration_seconds=42.5,
                error_count=0,
                indexer_version="1.2.3",
            )
        )

        assert saved.last_indexed_commit == "a" * 40
        assert saved.oldest_indexed_commit == "b" * 40
        assert saved.total_commits_indexed == 10
        assert saved.total_files_indexed == 200
        assert saved.total_symbols_indexed == 1500
        assert saved.total_references_indexed == 3000
        assert saved.last_indexing_duration_seconds == pytest.approx(42.5)
        assert saved.indexer_version == "1.2.3"

    async def test_save_status_with_error_info(self, db_session: AsyncSession) -> None:
        repo_id = await _make_repo(db_session)
        adapter = PostgresIndexStatusRepository(db_session)

        saved = await adapter.save(
            _status(
                repo_id,
                indexing_status="failed",
                error_message="Connection timeout",
                error_count=3,
            )
        )

        assert saved.indexing_status == "failed"
        assert saved.error_message == "Connection timeout"
        assert saved.error_count == 3

    async def test_upsert_when_status_has_id_skips_lookup(
        self, db_session: AsyncSession
    ) -> None:
        """If status already has an ID, save() should update directly (no lookup)."""
        repo_id = await _make_repo(db_session)
        adapter = PostgresIndexStatusRepository(db_session)

        first = await adapter.save(_status(repo_id, indexing_status="pending"))
        assert first.id is not None

        # Provide status with explicit id — should update in place
        with_id = IndexStatus(
            id=first.id,
            repository_id=repo_id,
            branch="main",
            indexing_status="completed",
        )
        updated = await adapter.save(with_id)
        assert updated.id == first.id
        assert updated.indexing_status == "completed"


@pytest.mark.asyncio
class TestFindByRepositoryAndBranch:
    """find_by_repository_and_branch() correctness."""

    async def test_finds_existing_status(self, db_session: AsyncSession) -> None:
        repo_id = await _make_repo(db_session)
        adapter = PostgresIndexStatusRepository(db_session)

        await adapter.save(_status(repo_id, indexing_status="completed"))

        result = await adapter.find_by_repository_and_branch(repo_id, "main")
        assert result is not None
        assert result.repository_id == repo_id
        assert result.branch == "main"
        assert result.indexing_status == "completed"

    async def test_returns_none_for_unknown_repo(
        self, db_session: AsyncSession
    ) -> None:
        adapter = PostgresIndexStatusRepository(db_session)
        result = await adapter.find_by_repository_and_branch(999999, "main")
        assert result is None

    async def test_returns_none_for_unknown_branch(
        self, db_session: AsyncSession
    ) -> None:
        repo_id = await _make_repo(db_session)
        adapter = PostgresIndexStatusRepository(db_session)

        await adapter.save(_status(repo_id, branch="main"))

        result = await adapter.find_by_repository_and_branch(repo_id, "feature/xyz")
        assert result is None

    async def test_branch_match_is_exact(self, db_session: AsyncSession) -> None:
        """main must not match main-old or main2."""
        repo_id = await _make_repo(db_session)
        adapter = PostgresIndexStatusRepository(db_session)

        await adapter.save(_status(repo_id, branch="main"))
        await adapter.save(_status(repo_id, branch="main-old"))

        result = await adapter.find_by_repository_and_branch(repo_id, "main")
        assert result is not None
        assert result.branch == "main"

    async def test_does_not_return_status_from_other_repo(
        self, db_session: AsyncSession
    ) -> None:
        repo1_id = await _make_repo(db_session, "repo-1")
        repo2_id = await _make_repo(db_session, "repo-2")
        adapter = PostgresIndexStatusRepository(db_session)

        await adapter.save(_status(repo1_id, branch="main"))

        result = await adapter.find_by_repository_and_branch(repo2_id, "main")
        assert result is None


@pytest.mark.asyncio
class TestListByRepository:
    """list_by_repository() correctness."""

    async def test_returns_all_branches_for_repo(
        self, db_session: AsyncSession
    ) -> None:
        repo_id = await _make_repo(db_session)
        adapter = PostgresIndexStatusRepository(db_session)

        await adapter.save(_status(repo_id, branch="main"))
        await adapter.save(_status(repo_id, branch="develop"))
        await adapter.save(_status(repo_id, branch="feature/x"))

        results = await adapter.list_by_repository(repo_id)
        assert len(results) == 3
        branches = {r.branch for r in results}
        assert branches == {"main", "develop", "feature/x"}

    async def test_returns_empty_for_unknown_repo(
        self, db_session: AsyncSession
    ) -> None:
        adapter = PostgresIndexStatusRepository(db_session)
        results = await adapter.list_by_repository(999999)
        assert results == []

    async def test_returns_empty_when_no_branches_indexed(
        self, db_session: AsyncSession
    ) -> None:
        repo_id = await _make_repo(db_session)
        adapter = PostgresIndexStatusRepository(db_session)

        results = await adapter.list_by_repository(repo_id)
        assert results == []

    async def test_results_ordered_by_branch_name(
        self, db_session: AsyncSession
    ) -> None:
        repo_id = await _make_repo(db_session)
        adapter = PostgresIndexStatusRepository(db_session)

        await adapter.save(_status(repo_id, branch="z-branch"))
        await adapter.save(_status(repo_id, branch="a-branch"))
        await adapter.save(_status(repo_id, branch="m-branch"))

        results = await adapter.list_by_repository(repo_id)
        branch_names = [r.branch for r in results]
        assert branch_names == ["a-branch", "m-branch", "z-branch"]

    async def test_does_not_return_statuses_from_other_repo(
        self, db_session: AsyncSession
    ) -> None:
        repo1_id = await _make_repo(db_session, "repo-p")
        repo2_id = await _make_repo(db_session, "repo-q")
        adapter = PostgresIndexStatusRepository(db_session)

        await adapter.save(_status(repo1_id, branch="main"))
        await adapter.save(_status(repo2_id, branch="main"))
        await adapter.save(_status(repo2_id, branch="develop"))

        results = await adapter.list_by_repository(repo1_id)
        assert len(results) == 1
        assert results[0].repository_id == repo1_id
