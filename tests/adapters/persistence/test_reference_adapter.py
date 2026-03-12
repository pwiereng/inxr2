"""Integration tests for PostgresReferenceRepository."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from inxr2.adapters.persistence.repositories.file_adapter import (
    PostgresFileRepository,
)
from inxr2.adapters.persistence.repositories.reference_adapter import (
    PostgresReferenceRepository,
)
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from inxr2.adapters.persistence.repositories.symbol_adapter import (
    PostgresSymbolRepository,
)
from inxr2.domain.value_objects import ReferenceType

from .factories import (
    CommitFactory,
    FileFactory,
    ReferenceFactory,
    RepositoryFactory,
    SymbolFactory,
)


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
    await commit_adapter.link_commit_to_branch(repo.id, commit.id, "main")

    file_adapter = PostgresFileRepository(db_session)
    file = await file_adapter.save(
        FileFactory.create(
            repository_id=repo.id,
            path=file_path,
            language=language,
            content_hash=commit_hash,
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
class TestPostgresReferenceRepositorySave:
    """Tests for save, find_by_id, save_many, count, delete."""

    async def test_save_returns_entity_with_id(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(db_session, "ref-save-repo")
        adapter = PostgresReferenceRepository(db_session)

        saved = await adapter.save(
            ReferenceFactory.create(
                repository_id=repo_id,
                source_file_id=file_id,
                reference_text="some_func",
            )
        )

        assert saved.id is not None
        assert saved.reference_text == "some_func"
        assert saved.reference_type == ReferenceType.CALL

    async def test_find_by_id_returns_saved_reference(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(db_session, "ref-find-repo")
        adapter = PostgresReferenceRepository(db_session)
        saved = await adapter.save(
            ReferenceFactory.create(
                repository_id=repo_id,
                source_file_id=file_id,
                reference_text="my_import",
                reference_type=ReferenceType.IMPORT,
                is_definition=True,
                resolution_confidence=0.8,
            )
        )
        assert saved.id is not None

        found = await adapter.find_by_id(saved.id)

        assert found is not None
        assert found.reference_text == "my_import"
        assert found.reference_type == ReferenceType.IMPORT
        assert found.is_definition is True
        assert found.resolution_confidence == pytest.approx(0.8)

    async def test_find_by_id_returns_none_for_missing(
        self, db_session: AsyncSession
    ) -> None:
        adapter = PostgresReferenceRepository(db_session)
        assert await adapter.find_by_id(-1) is None

    async def test_save_many_bulk_creates_references(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(db_session, "ref-bulk-repo")
        adapter = PostgresReferenceRepository(db_session)

        refs = [
            ReferenceFactory.create(
                repository_id=repo_id,
                source_file_id=file_id,
                reference_text=f"func_{i}",
                source_line=i + 1,
            )
            for i in range(5)
        ]
        saved = await adapter.save_many(refs)

        assert len(saved) == 5
        assert all(r.id is not None for r in saved)

    async def test_save_many_empty_list(self, db_session: AsyncSession) -> None:
        adapter = PostgresReferenceRepository(db_session)
        assert await adapter.save_many([]) == []

    async def test_count_by_repository(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "ref-count-repo"
        )
        adapter = PostgresReferenceRepository(db_session)
        await adapter.save_many(
            [
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text=f"r_{i}",
                    source_line=i + 1,
                )
                for i in range(3)
            ]
        )

        assert await adapter.count_by_repository(repo_id) == 3

    async def test_delete_by_file(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(db_session, "ref-del-repo")
        adapter = PostgresReferenceRepository(db_session)
        await adapter.save_many(
            [
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text=f"del_{i}",
                    source_line=i + 1,
                )
                for i in range(4)
            ]
        )

        deleted = await adapter.delete_by_file(file_id)

        assert deleted == 4
        assert await adapter.count_by_repository(repo_id) == 0

    async def test_save_preserves_metadata(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(db_session, "ref-meta-repo")
        adapter = PostgresReferenceRepository(db_session)
        saved = await adapter.save(
            ReferenceFactory.create(
                repository_id=repo_id,
                source_file_id=file_id,
                reference_text="meta_ref",
                metadata={"import_path": "pkg.module"},
            )
        )
        assert saved.id is not None

        found = await adapter.find_by_id(saved.id)
        assert found is not None
        assert found.metadata == {"import_path": "pkg.module"}


@pytest.mark.asyncio
class TestPostgresReferenceRepositoryListByFile:
    """Tests for list_by_file."""

    async def test_list_by_file_returns_references_ordered(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "ref-listfile-repo"
        )
        adapter = PostgresReferenceRepository(db_session)
        await adapter.save_many(
            [
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text="second",
                    source_line=20,
                ),
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text="first",
                    source_line=5,
                ),
            ]
        )

        results = await adapter.list_by_file(file_id)

        assert len(results) == 2
        # Ordered by source_line
        assert results[0].reference_text == "first"
        assert results[1].reference_text == "second"

    async def test_list_by_file_empty(self, db_session: AsyncSession) -> None:
        adapter = PostgresReferenceRepository(db_session)
        results = await adapter.list_by_file(-1)
        assert results == []


@pytest.mark.asyncio
class TestPostgresReferenceRepositoryFindReferencesToSymbol:
    """Tests for find_references_to_symbol with dedup and time-travel."""

    async def test_find_references_to_symbol_basic(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "ref-tosym-repo"
        )
        sym_adapter = PostgresSymbolRepository(db_session)
        target = await sym_adapter.save(
            SymbolFactory.create(
                file_id=file_id, repository_id=repo_id, name="target_fn"
            )
        )
        assert target.id is not None

        ref_adapter = PostgresReferenceRepository(db_session)
        await ref_adapter.save_many(
            [
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text="target_fn",
                    target_symbol_id=target.id,
                    source_line=30,
                ),
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text="target_fn",
                    target_symbol_id=target.id,
                    source_line=50,
                ),
            ]
        )

        results = await ref_adapter.find_references_to_symbol(
            target.id, repository_id=repo_id
        )

        assert len(results) == 2
        assert all(r.target_symbol_id == target.id for r in results)

    async def test_find_references_to_symbol_with_commit_id(
        self, db_session: AsyncSession
    ) -> None:
        """Time-travel: only return references from files at that commit."""
        data = await _setup_two_commits(db_session, "ref-tosym-tt-repo")

        sym_adapter = PostgresSymbolRepository(db_session)
        target = await sym_adapter.save(
            SymbolFactory.create(
                file_id=data["file2_id"],
                repository_id=data["repo_id"],
                name="sym",
            )
        )
        assert target.id is not None

        ref_adapter = PostgresReferenceRepository(db_session)
        # Reference in file1 (commit1)
        await ref_adapter.save(
            ReferenceFactory.create(
                repository_id=data["repo_id"],
                source_file_id=data["file1_id"],
                reference_text="sym",
                target_symbol_id=target.id,
                source_line=10,
            )
        )
        # Reference in file2 (commit2)
        await ref_adapter.save(
            ReferenceFactory.create(
                repository_id=data["repo_id"],
                source_file_id=data["file2_id"],
                reference_text="sym",
                target_symbol_id=target.id,
                source_line=10,
            )
        )

        # Time travel to commit1 should only return file1's reference
        results = await ref_adapter.find_references_to_symbol(
            target.id, commit_id=data["commit1_id"]
        )

        assert len(results) == 1
        assert results[0].source_file_id == data["file1_id"]

    async def test_find_references_to_symbol_dedup_latest(
        self, db_session: AsyncSession
    ) -> None:
        """Without commit_id, returns only refs from latest file version."""
        data = await _setup_two_commits(db_session, "ref-tosym-dedup-repo")

        sym_adapter = PostgresSymbolRepository(db_session)
        target = await sym_adapter.save(
            SymbolFactory.create(
                file_id=data["file2_id"],
                repository_id=data["repo_id"],
                name="sym",
            )
        )
        assert target.id is not None

        ref_adapter = PostgresReferenceRepository(db_session)
        await ref_adapter.save(
            ReferenceFactory.create(
                repository_id=data["repo_id"],
                source_file_id=data["file1_id"],
                reference_text="sym",
                target_symbol_id=target.id,
                source_line=10,
            )
        )
        await ref_adapter.save(
            ReferenceFactory.create(
                repository_id=data["repo_id"],
                source_file_id=data["file2_id"],
                reference_text="sym",
                target_symbol_id=target.id,
                source_line=10,
            )
        )

        results = await ref_adapter.find_references_to_symbol(
            target.id, repository_id=data["repo_id"]
        )

        assert len(results) == 1
        assert results[0].source_file_id == data["file2_id"]


@pytest.mark.asyncio
class TestPostgresReferenceRepositoryFindByText:
    """Tests for find_references_by_text with dedup and time-travel."""

    async def test_find_references_by_text_basic(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "ref-bytext-repo"
        )
        adapter = PostgresReferenceRepository(db_session)
        await adapter.save_many(
            [
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text="calculate",
                    source_line=5,
                ),
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text="calculate",
                    source_line=15,
                ),
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text="other",
                    source_line=25,
                ),
            ]
        )

        results = await adapter.find_references_by_text("calculate", repo_id)

        assert len(results) == 2
        assert all(r.reference_text == "calculate" for r in results)

    async def test_find_references_by_text_with_commit_id(
        self, db_session: AsyncSession
    ) -> None:
        data = await _setup_two_commits(db_session, "ref-bytext-tt-repo")
        adapter = PostgresReferenceRepository(db_session)

        await adapter.save(
            ReferenceFactory.create(
                repository_id=data["repo_id"],
                source_file_id=data["file1_id"],
                reference_text="lookup",
                source_line=10,
            )
        )
        await adapter.save(
            ReferenceFactory.create(
                repository_id=data["repo_id"],
                source_file_id=data["file2_id"],
                reference_text="lookup",
                source_line=10,
            )
        )

        results = await adapter.find_references_by_text(
            "lookup", data["repo_id"], commit_id=data["commit1_id"]
        )

        assert len(results) == 1
        assert results[0].source_file_id == data["file1_id"]

    async def test_find_references_by_text_dedup_latest(
        self, db_session: AsyncSession
    ) -> None:
        data = await _setup_two_commits(db_session, "ref-bytext-dedup-repo")
        adapter = PostgresReferenceRepository(db_session)

        await adapter.save(
            ReferenceFactory.create(
                repository_id=data["repo_id"],
                source_file_id=data["file1_id"],
                reference_text="lookup",
                source_line=10,
            )
        )
        await adapter.save(
            ReferenceFactory.create(
                repository_id=data["repo_id"],
                source_file_id=data["file2_id"],
                reference_text="lookup",
                source_line=10,
            )
        )

        results = await adapter.find_references_by_text("lookup", data["repo_id"])

        assert len(results) == 1
        assert results[0].source_file_id == data["file2_id"]


@pytest.mark.asyncio
class TestPostgresReferenceRepositorySearchByText:
    """Tests for search_by_text with pagination and filters."""

    async def test_search_by_text_basic(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "ref-search-repo"
        )
        adapter = PostgresReferenceRepository(db_session)
        await adapter.save_many(
            [
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text="calculate_total",
                    source_line=5,
                ),
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text="calculate_tax",
                    source_line=10,
                ),
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text="process_order",
                    source_line=15,
                ),
            ]
        )

        results, total = await adapter.search_by_text(
            "calculate", repository_id=repo_id
        )

        assert total == 2
        assert len(results) == 2
        texts = {r.reference_text for r in results}
        assert texts == {"calculate_total", "calculate_tax"}

    async def test_search_by_text_pagination(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "ref-paginate-repo"
        )
        adapter = PostgresReferenceRepository(db_session)
        await adapter.save_many(
            [
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text=f"item_{i:02d}",
                    source_line=i + 1,
                )
                for i in range(10)
            ]
        )

        page1, total = await adapter.search_by_text(
            "item", repository_id=repo_id, limit=3, offset=0
        )
        page2, total2 = await adapter.search_by_text(
            "item", repository_id=repo_id, limit=3, offset=3
        )

        assert total == 10
        assert total2 == 10
        assert len(page1) == 3
        assert len(page2) == 3
        # Pages should not overlap
        page1_texts = {r.reference_text for r in page1}
        page2_texts = {r.reference_text for r in page2}
        assert page1_texts.isdisjoint(page2_texts)

    async def test_search_by_text_case_insensitive(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(db_session, "ref-case-repo")
        adapter = PostgresReferenceRepository(db_session)
        await adapter.save(
            ReferenceFactory.create(
                repository_id=repo_id,
                source_file_id=file_id,
                reference_text="MyClass",
            )
        )

        results_cs, _ = await adapter.search_by_text(
            "myclass", repository_id=repo_id, case_sensitive=True
        )
        results_ci, _ = await adapter.search_by_text(
            "myclass", repository_id=repo_id, case_sensitive=False
        )

        assert len(results_cs) == 0
        assert len(results_ci) == 1

    async def test_search_by_text_no_matches(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "ref-nomatch-repo"
        )
        adapter = PostgresReferenceRepository(db_session)
        await adapter.save(
            ReferenceFactory.create(
                repository_id=repo_id,
                source_file_id=file_id,
                reference_text="existing",
            )
        )

        results, total = await adapter.search_by_text(
            "nonexistent", repository_id=repo_id
        )

        assert total == 0
        assert results == []


@pytest.mark.asyncio
class TestPostgresReferenceRepositoryResolution:
    """Tests for the 3-pass reference resolution algorithm."""

    async def test_count_unresolved_references(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "ref-unresolved-repo"
        )
        ref_adapter = PostgresReferenceRepository(db_session)
        await ref_adapter.save_many(
            [
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text="unresolved1",
                    target_symbol_id=None,
                    source_line=1,
                ),
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text="unresolved2",
                    target_symbol_id=None,
                    source_line=2,
                ),
            ]
        )

        count = await ref_adapter.count_unresolved_references(repo_id)
        assert count == 2

    async def test_resolve_same_file_pass1(self, db_session: AsyncSession) -> None:
        """Pass 1: Reference resolved to symbol in the same file."""
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "ref-resolve-p1-repo"
        )
        sym_adapter = PostgresSymbolRepository(db_session)
        symbol = await sym_adapter.save(
            SymbolFactory.create(
                file_id=file_id, repository_id=repo_id, name="local_fn"
            )
        )
        assert symbol.id is not None

        ref_adapter = PostgresReferenceRepository(db_session)
        ref = await ref_adapter.save(
            ReferenceFactory.create(
                repository_id=repo_id,
                source_file_id=file_id,
                reference_text="local_fn",
                target_symbol_id=None,
            )
        )
        assert ref.id is not None

        resolved_count = await ref_adapter.resolve_unlinked_references(repo_id)

        assert resolved_count >= 1
        updated = await ref_adapter.find_by_id(ref.id)
        assert updated is not None
        assert updated.target_symbol_id == symbol.id

    async def test_resolve_same_language_pass2(self, db_session: AsyncSession) -> None:
        """Pass 2: Reference resolved to symbol in different file, same language."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            RepositoryFactory.create(name="ref-resolve-p2-repo")
        )
        assert repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="a" * 40)
        )
        assert commit.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, commit.id, "main")

        file_adapter = PostgresFileRepository(db_session)
        source_file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/caller.py",
                content_hash="c" * 40,
                language="python",
            )
        )
        assert source_file.id is not None
        await file_adapter.link_file_to_commit(source_file.id, commit.id)

        target_file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/callee.py",
                content_hash="d" * 40,
                language="python",
            )
        )
        assert target_file.id is not None
        await file_adapter.link_file_to_commit(target_file.id, commit.id)
        await db_session.commit()

        sym_adapter = PostgresSymbolRepository(db_session)
        symbol = await sym_adapter.save(
            SymbolFactory.create(
                file_id=target_file.id,
                repository_id=repo.id,
                name="cross_file_fn",
            )
        )
        assert symbol.id is not None

        ref_adapter = PostgresReferenceRepository(db_session)
        ref = await ref_adapter.save(
            ReferenceFactory.create(
                repository_id=repo.id,
                source_file_id=source_file.id,
                reference_text="cross_file_fn",
                target_symbol_id=None,
            )
        )
        assert ref.id is not None

        resolved_count = await ref_adapter.resolve_unlinked_references(repo.id)

        assert resolved_count >= 1
        updated = await ref_adapter.find_by_id(ref.id)
        assert updated is not None
        assert updated.target_symbol_id == symbol.id

    async def test_resolve_global_pass3(self, db_session: AsyncSession) -> None:
        """Pass 3: Reference resolved to symbol in different language file."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            RepositoryFactory.create(name="ref-resolve-p3-repo")
        )
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
                content_hash="c" * 40,
                language="python",
            )
        )
        assert py_file.id is not None
        await file_adapter.link_file_to_commit(py_file.id, commit.id)

        ts_file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/main.ts",
                content_hash="d" * 40,
                language="typescript",
            )
        )
        assert ts_file.id is not None
        await file_adapter.link_file_to_commit(ts_file.id, commit.id)
        await db_session.commit()

        sym_adapter = PostgresSymbolRepository(db_session)
        symbol = await sym_adapter.save(
            SymbolFactory.create(
                file_id=ts_file.id,
                repository_id=repo.id,
                name="cross_lang_fn",
            )
        )
        assert symbol.id is not None

        ref_adapter = PostgresReferenceRepository(db_session)
        ref = await ref_adapter.save(
            ReferenceFactory.create(
                repository_id=repo.id,
                source_file_id=py_file.id,
                reference_text="cross_lang_fn",
                target_symbol_id=None,
            )
        )
        assert ref.id is not None

        resolved_count = await ref_adapter.resolve_unlinked_references(repo.id)

        assert resolved_count >= 1
        updated = await ref_adapter.find_by_id(ref.id)
        assert updated is not None
        assert updated.target_symbol_id == symbol.id

    async def test_resolve_prefers_same_file_over_cross_file(
        self, db_session: AsyncSession
    ) -> None:
        """Pass 1 (same-file) takes priority over Pass 2 (same-language)."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            RepositoryFactory.create(name="ref-resolve-priority-repo")
        )
        assert repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="a" * 40)
        )
        assert commit.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, commit.id, "main")

        file_adapter = PostgresFileRepository(db_session)
        file_a = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/a.py",
                content_hash="c" * 40,
                language="python",
            )
        )
        assert file_a.id is not None
        await file_adapter.link_file_to_commit(file_a.id, commit.id)

        file_b = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/b.py",
                content_hash="d" * 40,
                language="python",
            )
        )
        assert file_b.id is not None
        await file_adapter.link_file_to_commit(file_b.id, commit.id)
        await db_session.commit()

        sym_adapter = PostgresSymbolRepository(db_session)
        local_sym = await sym_adapter.save(
            SymbolFactory.create(
                file_id=file_a.id,
                repository_id=repo.id,
                name="shared_name",
            )
        )
        assert local_sym.id is not None
        remote_sym = await sym_adapter.save(
            SymbolFactory.create(
                file_id=file_b.id,
                repository_id=repo.id,
                name="shared_name",
                start_line=20,
            )
        )
        assert remote_sym.id is not None

        ref_adapter = PostgresReferenceRepository(db_session)
        ref = await ref_adapter.save(
            ReferenceFactory.create(
                repository_id=repo.id,
                source_file_id=file_a.id,
                reference_text="shared_name",
                target_symbol_id=None,
            )
        )
        assert ref.id is not None

        await ref_adapter.resolve_unlinked_references(repo.id)

        updated = await ref_adapter.find_by_id(ref.id)
        assert updated is not None
        # Should resolve to the symbol in the same file (pass 1 priority)
        assert updated.target_symbol_id == local_sym.id

    async def test_resolve_batch_respects_batch_size(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "ref-batch-repo"
        )
        sym_adapter = PostgresSymbolRepository(db_session)

        # Create symbols for each reference to match
        for i in range(5):
            await sym_adapter.save(
                SymbolFactory.create(
                    file_id=file_id,
                    repository_id=repo_id,
                    name=f"batch_fn_{i}",
                    start_line=(i + 1) * 10,
                    end_line=(i + 1) * 10 + 8,
                )
            )

        ref_adapter = PostgresReferenceRepository(db_session)
        await ref_adapter.save_many(
            [
                ReferenceFactory.create(
                    repository_id=repo_id,
                    source_file_id=file_id,
                    reference_text=f"batch_fn_{i}",
                    target_symbol_id=None,
                    source_line=100 + i,
                )
                for i in range(5)
            ]
        )

        # Resolve with small batch size
        resolved = await ref_adapter.resolve_references_batch(repo_id, batch_size=2)

        # batch_size=2 limits total resolved across all 3 passes
        assert resolved <= 2

    async def test_resolve_already_resolved_not_changed(
        self, db_session: AsyncSession
    ) -> None:
        """References with target_symbol_id already set are not modified."""
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "ref-already-resolved-repo"
        )
        sym_adapter = PostgresSymbolRepository(db_session)
        original_target = await sym_adapter.save(
            SymbolFactory.create(
                file_id=file_id, repository_id=repo_id, name="original"
            )
        )
        assert original_target.id is not None

        other_sym = await sym_adapter.save(
            SymbolFactory.create(
                file_id=file_id,
                repository_id=repo_id,
                name="already_linked",
                start_line=30,
                end_line=40,
            )
        )
        assert other_sym.id is not None

        ref_adapter = PostgresReferenceRepository(db_session)
        ref = await ref_adapter.save(
            ReferenceFactory.create(
                repository_id=repo_id,
                source_file_id=file_id,
                reference_text="already_linked",
                target_symbol_id=original_target.id,  # Already resolved
            )
        )
        assert ref.id is not None

        resolved_count = await ref_adapter.resolve_unlinked_references(repo_id)

        # Should not re-resolve already resolved references
        assert resolved_count == 0
        updated = await ref_adapter.find_by_id(ref.id)
        assert updated is not None
        assert updated.target_symbol_id == original_target.id

    async def test_resolve_no_matching_symbol(self, db_session: AsyncSession) -> None:
        """Reference with no matching symbol stays unresolved."""
        repo_id, _, file_id = await _setup_repo_commit_file(
            db_session, "ref-no-match-repo"
        )
        ref_adapter = PostgresReferenceRepository(db_session)
        ref = await ref_adapter.save(
            ReferenceFactory.create(
                repository_id=repo_id,
                source_file_id=file_id,
                reference_text="no_such_symbol",
                target_symbol_id=None,
            )
        )
        assert ref.id is not None

        resolved_count = await ref_adapter.resolve_unlinked_references(repo_id)

        assert resolved_count == 0
        updated = await ref_adapter.find_by_id(ref.id)
        assert updated is not None
        assert updated.target_symbol_id is None

    async def test_prepare_resolution_is_idempotent(
        self, db_session: AsyncSession
    ) -> None:
        """Calling prepare_resolution multiple times does not error."""
        repo_id, _, _ = await _setup_repo_commit_file(db_session, "ref-prep-idem-repo")
        ref_adapter = PostgresReferenceRepository(db_session)

        await ref_adapter.prepare_resolution(repo_id)
        await ref_adapter.prepare_resolution(repo_id)
        # Should not raise
