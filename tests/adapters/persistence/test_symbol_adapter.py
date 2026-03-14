"""Integration tests for PostgresSymbolRepository."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from inxr2.adapters.persistence.repositories.file_adapter import (
    PostgresFileRepository,
)
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from inxr2.adapters.persistence.repositories.symbol_adapter import (
    PostgresSymbolRepository,
)
from inxr2.domain.value_objects import SymbolKind

from .factories import CommitFactory, FileFactory, RepositoryFactory, SymbolFactory


async def _setup_repo_commit_file(
    db_session: AsyncSession,
    repo_name: str,
    commit_hash: str = "a" * 40,
    file_path: str = "src/main.py",
    language: str = "python",
) -> tuple[int, int, int]:
    """Create a repo, commit, and file linked together. Returns (repo_id, commit_id, file_id)."""
    repo_adapter = PostgresRepositoryAdapter(db_session)
    repo = await repo_adapter.save(RepositoryFactory.create(name=repo_name))
    assert repo.id is not None

    commit_adapter = PostgresCommitRepository(db_session)
    commit = await commit_adapter.save(
        CommitFactory.create(repository_id=repo.id, commit_hash=commit_hash)
    )
    assert commit.id is not None

    # Link commit to branch for latest-file dedup to work
    await commit_adapter.link_commit_to_branch(repo.id, commit.id, "main")

    file_adapter = PostgresFileRepository(db_session)
    file = await file_adapter.save(
        FileFactory.create(
            repository_id=repo.id,
            path=file_path,
            language=language,
            content_hash=commit_hash,  # reuse hash for uniqueness
        )
    )
    assert file.id is not None
    await file_adapter.link_file_to_commit(file.id, commit.id)

    await db_session.commit()
    return repo.id, commit.id, file.id


async def _setup_two_commits(
    db_session: AsyncSession,
    repo_name: str,
) -> dict[str, int]:
    """Create repo with 2 commits, same file path at each.

    Returns dict with repo_id, commit1_id, commit2_id, file1_id, file2_id.
    Latest-file dedup should prefer file2 (newer commit).
    """
    repo_adapter = PostgresRepositoryAdapter(db_session)
    repo = await repo_adapter.save(RepositoryFactory.create(name=repo_name))
    assert repo.id is not None

    commit_adapter = PostgresCommitRepository(db_session)
    now = datetime.now(UTC).replace(tzinfo=None)

    commit1 = await commit_adapter.save(
        CommitFactory.create(
            repository_id=repo.id,
            commit_hash="a" * 40,
            commit_date=now - timedelta(hours=2),
        )
    )
    assert commit1.id is not None
    await commit_adapter.link_commit_to_branch(repo.id, commit1.id, "main")

    commit2 = await commit_adapter.save(
        CommitFactory.create(
            repository_id=repo.id,
            commit_hash="b" * 40,
            commit_date=now - timedelta(hours=1),
        )
    )
    assert commit2.id is not None
    await commit_adapter.link_commit_to_branch(repo.id, commit2.id, "main")

    file_adapter = PostgresFileRepository(db_session)
    file1 = await file_adapter.save(
        FileFactory.create(
            repository_id=repo.id, path="src/main.py", content_hash="c" * 40
        )
    )
    assert file1.id is not None
    await file_adapter.link_file_to_commit(file1.id, commit1.id)

    file2 = await file_adapter.save(
        FileFactory.create(
            repository_id=repo.id, path="src/main.py", content_hash="d" * 40
        )
    )
    assert file2.id is not None
    await file_adapter.link_file_to_commit(file2.id, commit2.id)

    await db_session.commit()

    return {
        "repo_id": repo.id,
        "commit1_id": commit1.id,
        "commit2_id": commit2.id,
        "file1_id": file1.id,
        "file2_id": file2.id,
    }


@pytest.mark.asyncio
class TestPostgresSymbolRepositorySave:
    """Tests for save, find_by_id, save_many, count, delete."""

    async def test_save_returns_entity_with_id(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(db_session, "sym-save-repo")
        adapter = PostgresSymbolRepository(db_session)

        saved = await adapter.save(
            SymbolFactory.create(file_id=file_id, repository_id=repo_id, name="foo")
        )

        assert saved.id is not None
        assert saved.name == "foo"
        assert saved.kind == SymbolKind.FUNCTION

    async def test_find_by_id_returns_saved_symbol(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(db_session, "sym-find-repo")
        adapter = PostgresSymbolRepository(db_session)
        saved = await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="bar",
                qualified_name="module.bar",
                kind=SymbolKind.CLASS,
                signature="class bar:",
                docstring="A test class",
            )
        )
        assert saved.id is not None

        found = await adapter.find_by_id(saved.id)

        assert found is not None
        assert found.name == "bar"
        assert found.qualified_name == "module.bar"
        assert found.kind == SymbolKind.CLASS
        assert found.signature == "class bar:"
        assert found.docstring == "A test class"

    async def test_find_by_id_returns_none_for_missing(
        self, db_session: AsyncSession
    ) -> None:
        adapter = PostgresSymbolRepository(db_session)
        assert await adapter.find_by_id(-1) is None

    async def test_save_many_bulk_creates_symbols(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(db_session, "sym-bulk-repo")
        adapter = PostgresSymbolRepository(db_session)

        symbols = [
            SymbolFactory.create(
                file_id=file_id, repository_id=repo_id, name=f"func_{i}"
            )
            for i in range(5)
        ]
        saved = await adapter.save_many(symbols)

        assert len(saved) == 5
        assert all(s.id is not None for s in saved)

    async def test_save_many_empty_list(self, db_session: AsyncSession) -> None:
        adapter = PostgresSymbolRepository(db_session)
        assert await adapter.save_many([]) == []

    async def test_count_by_repository(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "sym-count-repo"
        )
        adapter = PostgresSymbolRepository(db_session)
        await adapter.save_many(
            [
                SymbolFactory.create(
                    file_id=file_id, repository_id=repo_id, name=f"fn_{i}"
                )
                for i in range(3)
            ]
        )

        assert await adapter.count_by_repository(repo_id) == 3

    async def test_delete_by_file(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(db_session, "sym-del-repo")
        adapter = PostgresSymbolRepository(db_session)
        await adapter.save_many(
            [
                SymbolFactory.create(
                    file_id=file_id, repository_id=repo_id, name=f"d_{i}"
                )
                for i in range(4)
            ]
        )

        deleted = await adapter.delete_by_file(file_id)

        assert deleted == 4
        assert await adapter.count_by_repository(repo_id) == 0

    async def test_save_preserves_metadata(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(db_session, "sym-meta-repo")
        adapter = PostgresSymbolRepository(db_session)
        saved = await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="meta_fn",
                metadata={"language_specific": True, "visibility": "public"},
            )
        )
        assert saved.id is not None

        found = await adapter.find_by_id(saved.id)
        assert found is not None
        assert found.metadata == {"language_specific": True, "visibility": "public"}


@pytest.mark.asyncio
class TestPostgresSymbolRepositorySearchByName:
    """Tests for search_by_name with various filters."""

    async def test_basic_substring_search(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "sym-search-repo"
        )
        adapter = PostgresSymbolRepository(db_session)
        await adapter.save_many(
            [
                SymbolFactory.create(
                    file_id=file_id, repository_id=repo_id, name="calculate_total"
                ),
                SymbolFactory.create(
                    file_id=file_id,
                    repository_id=repo_id,
                    name="calculate_tax",
                    start_line=30,
                    end_line=40,
                ),
                SymbolFactory.create(
                    file_id=file_id,
                    repository_id=repo_id,
                    name="process_order",
                    start_line=50,
                    end_line=60,
                ),
            ]
        )

        results, _ = await adapter.search_by_name("calculate", repository_id=repo_id)

        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"calculate_total", "calculate_tax"}

    async def test_search_with_kind_filter(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(db_session, "sym-kind-repo")
        adapter = PostgresSymbolRepository(db_session)
        await adapter.save_many(
            [
                SymbolFactory.create(
                    file_id=file_id,
                    repository_id=repo_id,
                    name="MyClass",
                    kind=SymbolKind.CLASS,
                ),
                SymbolFactory.create(
                    file_id=file_id,
                    repository_id=repo_id,
                    name="my_function",
                    kind=SymbolKind.FUNCTION,
                    start_line=30,
                    end_line=40,
                ),
            ]
        )

        results, _ = await adapter.search_by_name(
            "my", repository_id=repo_id, kind="class", case_sensitive=False
        )

        assert len(results) == 1
        assert results[0].name == "MyClass"

    async def test_search_with_limit(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "sym-limit-repo"
        )
        adapter = PostgresSymbolRepository(db_session)
        await adapter.save_many(
            [
                SymbolFactory.create(
                    file_id=file_id,
                    repository_id=repo_id,
                    name=f"item_{i:02d}",
                    start_line=i * 10 + 1,
                    end_line=i * 10 + 9,
                )
                for i in range(10)
            ]
        )

        results, total = await adapter.search_by_name(
            "item", repository_id=repo_id, limit=3
        )

        assert len(results) == 3
        assert total == 10

    async def test_search_paginates_with_offset(self, db_session: AsyncSession) -> None:
        """Test that offset produces disjoint pages with stable totals."""
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "sym-offset-repo"
        )
        adapter = PostgresSymbolRepository(db_session)
        await adapter.save_many(
            [
                SymbolFactory.create(
                    file_id=file_id,
                    repository_id=repo_id,
                    name=f"item_{i:02d}",
                    start_line=i * 10 + 1,
                    end_line=i * 10 + 9,
                )
                for i in range(10)
            ]
        )

        page1, total1 = await adapter.search_by_name(
            "item", repository_id=repo_id, limit=5, offset=0
        )
        page2, total2 = await adapter.search_by_name(
            "item", repository_id=repo_id, limit=5, offset=5
        )

        assert total1 == 10
        assert total2 == 10
        assert len(page1) == 5
        assert len(page2) == 5
        # Pages are disjoint
        page1_ids = {s.id for s in page1}
        page2_ids = {s.id for s in page2}
        assert page1_ids.isdisjoint(page2_ids)

    async def test_search_case_insensitive(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(db_session, "sym-case-repo")
        adapter = PostgresSymbolRepository(db_session)
        await adapter.save(
            SymbolFactory.create(file_id=file_id, repository_id=repo_id, name="MyClass")
        )

        # Case sensitive (default) should not match
        results_cs, _ = await adapter.search_by_name(
            "myclass", repository_id=repo_id, case_sensitive=True
        )
        assert len(results_cs) == 0

        # Case insensitive should match
        results_ci, _ = await adapter.search_by_name(
            "myclass", repository_id=repo_id, case_sensitive=False
        )
        assert len(results_ci) == 1
        assert results_ci[0].name == "MyClass"

    async def test_search_returns_empty_for_no_match(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "sym-empty-repo"
        )
        adapter = PostgresSymbolRepository(db_session)
        await adapter.save(
            SymbolFactory.create(
                file_id=file_id, repository_id=repo_id, name="existing"
            )
        )

        results, total = await adapter.search_by_name(
            "nonexistent", repository_id=repo_id
        )
        assert results == []
        assert total == 0

    async def test_search_with_language_filter(self, db_session: AsyncSession) -> None:
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(RepositoryFactory.create(name="sym-lang-repo"))
        assert repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="a" * 40)
        )
        assert commit.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, commit.id, "main")

        file_adapter = PostgresFileRepository(db_session)
        py_file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/main.py",
                language="python",
                content_hash="c" * 40,
            )
        )
        assert py_file.id is not None
        await file_adapter.link_file_to_commit(py_file.id, commit.id)

        ts_file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/main.ts",
                language="typescript",
                content_hash="d" * 40,
            )
        )
        assert ts_file.id is not None
        await file_adapter.link_file_to_commit(ts_file.id, commit.id)

        await db_session.commit()

        adapter = PostgresSymbolRepository(db_session)
        await adapter.save_many(
            [
                SymbolFactory.create(
                    file_id=py_file.id,
                    repository_id=repo.id,
                    name="handler",
                ),
                SymbolFactory.create(
                    file_id=ts_file.id,
                    repository_id=repo.id,
                    name="handler",
                    start_line=20,
                ),
            ]
        )

        results, _ = await adapter.search_by_name(
            "handler", repository_id=repo.id, language="python"
        )

        assert len(results) == 1
        assert results[0].file_id == py_file.id

    async def test_search_top_level_only(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "sym-toplevel-repo"
        )
        adapter = PostgresSymbolRepository(db_session)

        parent = await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="MyClass",
                kind=SymbolKind.CLASS,
            )
        )
        assert parent.id is not None

        await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="my_method",
                kind=SymbolKind.METHOD,
                parent_symbol_id=parent.id,
                start_line=15,
            )
        )

        # top_level_only should exclude the nested method
        results, _ = await adapter.search_by_name(
            "my", repository_id=repo_id, top_level_only=True, case_sensitive=False
        )

        names = {r.name for r in results}
        assert "MyClass" in names
        assert "my_method" not in names

    async def test_search_with_namespace_parent_is_top_level(
        self, db_session: AsyncSession
    ) -> None:
        """Symbols whose parent is a namespace are considered top-level."""
        repo_id, _, file_id = await _setup_repo_commit_file(db_session, "sym-ns-repo")
        adapter = PostgresSymbolRepository(db_session)

        ns = await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="mymodule",
                kind=SymbolKind.NAMESPACE,
            )
        )
        assert ns.id is not None

        await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="ns_func",
                kind=SymbolKind.FUNCTION,
                parent_symbol_id=ns.id,
                start_line=20,
            )
        )

        results, _ = await adapter.search_by_name(
            "ns_func", repository_id=repo_id, top_level_only=True
        )

        assert len(results) == 1
        assert results[0].name == "ns_func"


@pytest.mark.asyncio
class TestPostgresSymbolRepositoryDedup:
    """Tests for latest-file-version dedup and time-travel."""

    async def test_search_returns_only_latest_file_version(
        self, db_session: AsyncSession
    ) -> None:
        data = await _setup_two_commits(db_session, "sym-dedup-repo")
        adapter = PostgresSymbolRepository(db_session)

        await adapter.save(
            SymbolFactory.create(
                file_id=data["file1_id"],
                repository_id=data["repo_id"],
                name="dedup_fn",
            )
        )
        await adapter.save(
            SymbolFactory.create(
                file_id=data["file2_id"],
                repository_id=data["repo_id"],
                name="dedup_fn",
                start_line=15,
            )
        )

        results, _ = await adapter.search_by_name(
            "dedup_fn", repository_id=data["repo_id"]
        )

        assert len(results) == 1
        assert results[0].file_id == data["file2_id"]

    async def test_search_with_commit_id_time_travel(
        self, db_session: AsyncSession
    ) -> None:
        data = await _setup_two_commits(db_session, "sym-travel-repo")
        adapter = PostgresSymbolRepository(db_session)

        await adapter.save(
            SymbolFactory.create(
                file_id=data["file1_id"],
                repository_id=data["repo_id"],
                name="travel_fn",
            )
        )
        await adapter.save(
            SymbolFactory.create(
                file_id=data["file2_id"],
                repository_id=data["repo_id"],
                name="travel_fn",
                start_line=15,
            )
        )

        # Time travel to commit1 should return only file1's symbol
        results, _ = await adapter.search_by_name(
            "travel_fn",
            repository_id=data["repo_id"],
            commit_id=data["commit1_id"],
        )

        assert len(results) == 1
        assert results[0].file_id == data["file1_id"]

    async def test_find_by_exact_name_dedup(self, db_session: AsyncSession) -> None:
        data = await _setup_two_commits(db_session, "sym-exact-dedup-repo")
        adapter = PostgresSymbolRepository(db_session)

        await adapter.save(
            SymbolFactory.create(
                file_id=data["file1_id"],
                repository_id=data["repo_id"],
                name="exact_fn",
            )
        )
        await adapter.save(
            SymbolFactory.create(
                file_id=data["file2_id"],
                repository_id=data["repo_id"],
                name="exact_fn",
                start_line=15,
            )
        )

        results = await adapter.find_by_exact_name(
            "exact_fn", repository_id=data["repo_id"]
        )

        assert len(results) == 1
        assert results[0].file_id == data["file2_id"]

    async def test_find_by_exact_name_with_commit_id(
        self, db_session: AsyncSession
    ) -> None:
        data = await _setup_two_commits(db_session, "sym-exact-tt-repo")
        adapter = PostgresSymbolRepository(db_session)

        await adapter.save(
            SymbolFactory.create(
                file_id=data["file1_id"],
                repository_id=data["repo_id"],
                name="tt_fn",
            )
        )
        await adapter.save(
            SymbolFactory.create(
                file_id=data["file2_id"],
                repository_id=data["repo_id"],
                name="tt_fn",
                start_line=15,
            )
        )

        results = await adapter.find_by_exact_name(
            "tt_fn",
            repository_id=data["repo_id"],
            commit_id=data["commit1_id"],
        )

        assert len(results) == 1
        assert results[0].file_id == data["file1_id"]


@pytest.mark.asyncio
class TestPostgresSymbolRepositoryLookups:
    """Tests for find_by_qualified_name, list_by_file, list_by_file_and_parent."""

    async def test_find_by_qualified_name(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "sym-qname-repo"
        )
        adapter = PostgresSymbolRepository(db_session)
        await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="MyClass",
                qualified_name="src.main.MyClass",
            )
        )
        await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="other_fn",
                qualified_name="src.main.other_fn",
                start_line=30,
                end_line=40,
            )
        )

        results = await adapter.find_by_qualified_name(repo_id, "src.main.MyClass")

        assert len(results) == 1
        assert results[0].name == "MyClass"

    async def test_list_by_file(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "sym-listfile-repo"
        )
        adapter = PostgresSymbolRepository(db_session)
        await adapter.save_many(
            [
                SymbolFactory.create(
                    file_id=file_id,
                    repository_id=repo_id,
                    name="first",
                    start_line=1,
                ),
                SymbolFactory.create(
                    file_id=file_id,
                    repository_id=repo_id,
                    name="second",
                    start_line=20,
                ),
            ]
        )

        results = await adapter.list_by_file(file_id)

        assert len(results) == 2
        # Should be ordered by start_line
        assert results[0].name == "first"
        assert results[1].name == "second"

    async def test_list_by_file_and_parent_root(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "sym-parent-root-repo"
        )
        adapter = PostgresSymbolRepository(db_session)

        parent = await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="ParentClass",
                kind=SymbolKind.CLASS,
            )
        )
        assert parent.id is not None
        await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="child_method",
                kind=SymbolKind.METHOD,
                parent_symbol_id=parent.id,
                start_line=15,
            )
        )

        # parent_symbol_id=None returns only root-level symbols
        results = await adapter.list_by_file_and_parent(file_id, parent_symbol_id=None)

        assert len(results) == 1
        assert results[0].name == "ParentClass"

    async def test_list_by_file_and_parent_children(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "sym-parent-child-repo"
        )
        adapter = PostgresSymbolRepository(db_session)

        parent = await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="TheClass",
                kind=SymbolKind.CLASS,
            )
        )
        assert parent.id is not None
        await adapter.save_many(
            [
                SymbolFactory.create(
                    file_id=file_id,
                    repository_id=repo_id,
                    name="method_a",
                    kind=SymbolKind.METHOD,
                    parent_symbol_id=parent.id,
                    start_line=15,
                ),
                SymbolFactory.create(
                    file_id=file_id,
                    repository_id=repo_id,
                    name="method_b",
                    kind=SymbolKind.METHOD,
                    parent_symbol_id=parent.id,
                    start_line=25,
                    end_line=35,
                ),
            ]
        )

        results = await adapter.list_by_file_and_parent(
            file_id, parent_symbol_id=parent.id
        )

        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"method_a", "method_b"}


@pytest.mark.asyncio
class TestPostgresSymbolRepositoryAggregation:
    """Tests for list_files_with_symbols, list_distinct_kinds, count_*_kinds_by_file."""

    async def test_list_files_with_symbols(self, db_session: AsyncSession) -> None:
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(RepositoryFactory.create(name="sym-files-repo"))
        assert repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="a" * 40)
        )
        assert commit.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, commit.id, "main")

        file_adapter = PostgresFileRepository(db_session)
        file1 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/a.py",
                content_hash="c" * 40,
                language="python",
            )
        )
        assert file1.id is not None
        await file_adapter.link_file_to_commit(file1.id, commit.id)

        file2 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/b.py",
                content_hash="d" * 40,
                language="python",
            )
        )
        assert file2.id is not None
        await file_adapter.link_file_to_commit(file2.id, commit.id)

        # File with no symbols
        file3 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/empty.py",
                content_hash="e" * 40,
                language="python",
            )
        )
        assert file3.id is not None
        await file_adapter.link_file_to_commit(file3.id, commit.id)

        await db_session.commit()

        sym_adapter = PostgresSymbolRepository(db_session)
        await sym_adapter.save_many(
            [
                SymbolFactory.create(
                    file_id=file1.id, repository_id=repo.id, name="fn1"
                ),
                SymbolFactory.create(
                    file_id=file1.id,
                    repository_id=repo.id,
                    name="fn2",
                    start_line=20,
                ),
                SymbolFactory.create(
                    file_id=file2.id, repository_id=repo.id, name="fn3"
                ),
            ]
        )

        results = await sym_adapter.list_files_with_symbols(repo.id)

        # file3 has no symbols, should not appear
        assert len(results) == 2
        paths = {r[1] for r in results}
        assert paths == {"src/a.py", "src/b.py"}
        # file1 has 2 symbols, file2 has 1
        counts = {r[1]: r[3] for r in results}
        assert counts["src/a.py"] == 2
        assert counts["src/b.py"] == 1

    async def test_list_distinct_kinds(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "sym-kinds-repo"
        )
        adapter = PostgresSymbolRepository(db_session)
        await adapter.save_many(
            [
                SymbolFactory.create(
                    file_id=file_id,
                    repository_id=repo_id,
                    name="fn",
                    kind=SymbolKind.FUNCTION,
                ),
                SymbolFactory.create(
                    file_id=file_id,
                    repository_id=repo_id,
                    name="cls",
                    kind=SymbolKind.CLASS,
                    start_line=20,
                ),
                SymbolFactory.create(
                    file_id=file_id,
                    repository_id=repo_id,
                    name="ns",
                    kind=SymbolKind.NAMESPACE,
                    start_line=30,
                    end_line=40,
                ),
            ]
        )

        kinds = await adapter.list_distinct_kinds(repo_id)

        # Namespace is excluded
        assert "namespace" not in kinds
        assert "function" in kinds
        assert "class" in kinds

    async def test_count_top_level_kinds_by_file(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "sym-toplvl-cnt-repo"
        )
        adapter = PostgresSymbolRepository(db_session)

        parent = await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="TopClass",
                kind=SymbolKind.CLASS,
            )
        )
        assert parent.id is not None
        await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="nested_method",
                kind=SymbolKind.METHOD,
                parent_symbol_id=parent.id,
                start_line=15,
            )
        )
        await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="top_fn",
                kind=SymbolKind.FUNCTION,
                start_line=30,
                end_line=40,
            )
        )

        counts = await adapter.count_top_level_kinds_by_file([file_id])

        assert file_id in counts
        # nested_method is not top-level
        assert counts[file_id].get("method", 0) == 0
        assert counts[file_id]["class"] == 1
        assert counts[file_id]["function"] == 1

    async def test_count_top_level_kinds_by_file_empty(
        self, db_session: AsyncSession
    ) -> None:
        adapter = PostgresSymbolRepository(db_session)
        assert await adapter.count_top_level_kinds_by_file([]) == {}

    async def test_count_kinds_by_file(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "sym-allkinds-repo"
        )
        adapter = PostgresSymbolRepository(db_session)

        parent = await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="TheClass",
                kind=SymbolKind.CLASS,
            )
        )
        assert parent.id is not None
        await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="the_method",
                kind=SymbolKind.METHOD,
                parent_symbol_id=parent.id,
                start_line=15,
            )
        )

        counts = await adapter.count_kinds_by_file([file_id])

        assert file_id in counts
        # count_kinds_by_file includes nested
        assert counts[file_id]["class"] == 1
        assert counts[file_id]["method"] == 1

    async def test_count_kinds_by_file_empty(self, db_session: AsyncSession) -> None:
        adapter = PostgresSymbolRepository(db_session)
        assert await adapter.count_kinds_by_file([]) == {}


@pytest.mark.asyncio
class TestPostgresSymbolRepositoryUpdateParent:
    """Tests for update_parent_symbol_ids."""

    async def test_update_parent_symbol_ids(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "sym-update-parent-repo"
        )
        adapter = PostgresSymbolRepository(db_session)

        parent = await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="Container",
                kind=SymbolKind.CLASS,
            )
        )
        assert parent.id is not None

        child = await adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="inner_fn",
                start_line=15,
            )
        )
        assert child.id is not None

        count = await adapter.update_parent_symbol_ids({child.id: parent.id})

        assert count == 1
        updated = await adapter.find_by_id(child.id)
        assert updated is not None
        assert updated.parent_symbol_id == parent.id

    async def test_update_parent_symbol_ids_empty(
        self, db_session: AsyncSession
    ) -> None:
        adapter = PostgresSymbolRepository(db_session)
        assert await adapter.update_parent_symbol_ids({}) == 0
