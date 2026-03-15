"""Tests for InMemoryFileRenameRepository (fake)."""

import pytest

from inxr2.domain.entities import FileRename
from tests.fixtures.test_doubles import InMemoryFileRenameRepository


@pytest.fixture
def repo() -> InMemoryFileRenameRepository:
    return InMemoryFileRenameRepository()


class TestInMemoryFileRenameRepository:
    """Tests for the in-memory fake file rename repository."""

    @pytest.mark.asyncio
    async def test_save_renames_assigns_ids(
        self, repo: InMemoryFileRenameRepository
    ) -> None:
        renames = [
            FileRename(
                repository_id=1,
                commit_id=10,
                old_path="a.py",
                new_path="b.py",
                similarity=90,
            ),
            FileRename(
                repository_id=1,
                commit_id=10,
                old_path="c.py",
                new_path="d.py",
                similarity=80,
            ),
        ]
        saved = await repo.save_renames(renames)
        assert len(saved) == 2
        assert saved[0].id == 1
        assert saved[1].id == 2
        assert saved[0].old_path == "a.py"
        assert saved[1].old_path == "c.py"

    @pytest.mark.asyncio
    async def test_save_empty_list(self, repo: InMemoryFileRenameRepository) -> None:
        saved = await repo.save_renames([])
        assert saved == []

    @pytest.mark.asyncio
    async def test_get_renames_for_commit(
        self, repo: InMemoryFileRenameRepository
    ) -> None:
        await repo.save_renames(
            [
                FileRename(
                    repository_id=1,
                    commit_id=10,
                    old_path="a.py",
                    new_path="b.py",
                    similarity=90,
                ),
                FileRename(
                    repository_id=1,
                    commit_id=10,
                    old_path="x.py",
                    new_path="y.py",
                    similarity=80,
                ),
                FileRename(
                    repository_id=1,
                    commit_id=20,
                    old_path="m.py",
                    new_path="n.py",
                    similarity=70,
                ),
            ]
        )

        renames = await repo.get_renames_for_commit(10)
        assert len(renames) == 2
        # Sorted by old_path
        assert renames[0].old_path == "a.py"
        assert renames[1].old_path == "x.py"

    @pytest.mark.asyncio
    async def test_get_renames_for_commit_empty(
        self, repo: InMemoryFileRenameRepository
    ) -> None:
        renames = await repo.get_renames_for_commit(999)
        assert renames == []

    @pytest.mark.asyncio
    async def test_get_file_history_by_old_path(
        self, repo: InMemoryFileRenameRepository
    ) -> None:
        await repo.save_renames(
            [
                FileRename(
                    repository_id=1,
                    commit_id=10,
                    old_path="src/a.py",
                    new_path="src/b.py",
                    similarity=90,
                ),
                FileRename(
                    repository_id=1,
                    commit_id=20,
                    old_path="src/b.py",
                    new_path="src/c.py",
                    similarity=85,
                ),
            ]
        )

        # Searching for src/a.py should find the first rename
        history = await repo.get_file_history(repository_id=1, file_path="src/a.py")
        assert len(history) == 1
        assert history[0].old_path == "src/a.py"

    @pytest.mark.asyncio
    async def test_get_file_history_by_new_path(
        self, repo: InMemoryFileRenameRepository
    ) -> None:
        await repo.save_renames(
            [
                FileRename(
                    repository_id=1,
                    commit_id=10,
                    old_path="src/a.py",
                    new_path="src/b.py",
                    similarity=90,
                ),
                FileRename(
                    repository_id=1,
                    commit_id=20,
                    old_path="src/b.py",
                    new_path="src/c.py",
                    similarity=85,
                ),
            ]
        )

        # Searching for src/b.py should find both renames
        history = await repo.get_file_history(repository_id=1, file_path="src/b.py")
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_get_file_history_filters_by_repository(
        self, repo: InMemoryFileRenameRepository
    ) -> None:
        await repo.save_renames(
            [
                FileRename(
                    repository_id=1,
                    commit_id=10,
                    old_path="a.py",
                    new_path="b.py",
                    similarity=90,
                ),
                FileRename(
                    repository_id=2,
                    commit_id=20,
                    old_path="a.py",
                    new_path="c.py",
                    similarity=80,
                ),
            ]
        )

        history = await repo.get_file_history(repository_id=1, file_path="a.py")
        assert len(history) == 1
        assert history[0].new_path == "b.py"

    @pytest.mark.asyncio
    async def test_count_by_repository(
        self, repo: InMemoryFileRenameRepository
    ) -> None:
        await repo.save_renames(
            [
                FileRename(
                    repository_id=1,
                    commit_id=10,
                    old_path="a.py",
                    new_path="b.py",
                    similarity=90,
                ),
                FileRename(
                    repository_id=1,
                    commit_id=20,
                    old_path="c.py",
                    new_path="d.py",
                    similarity=80,
                ),
                FileRename(
                    repository_id=2,
                    commit_id=30,
                    old_path="e.py",
                    new_path="f.py",
                    similarity=70,
                ),
            ]
        )

        assert await repo.count_by_repository(1) == 2
        assert await repo.count_by_repository(2) == 1
        assert await repo.count_by_repository(999) == 0

    @pytest.mark.asyncio
    async def test_delete_by_repository(
        self, repo: InMemoryFileRenameRepository
    ) -> None:
        await repo.save_renames(
            [
                FileRename(
                    repository_id=1,
                    commit_id=10,
                    old_path="a.py",
                    new_path="b.py",
                    similarity=90,
                ),
                FileRename(
                    repository_id=1,
                    commit_id=20,
                    old_path="c.py",
                    new_path="d.py",
                    similarity=80,
                ),
                FileRename(
                    repository_id=2,
                    commit_id=30,
                    old_path="e.py",
                    new_path="f.py",
                    similarity=70,
                ),
            ]
        )

        deleted = await repo.delete_by_repository(1)
        assert deleted == 2
        assert await repo.count_by_repository(1) == 0
        assert await repo.count_by_repository(2) == 1
