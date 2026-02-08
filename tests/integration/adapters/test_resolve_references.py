"""Integration tests for resolve_references_batch against the database.

These tests verify that reference resolution correctly prioritizes:
1. Same-file symbols (preferred)
2. Lowest symbol ID (deterministic tiebreaker)

They also verify batching, already-resolved skipping, and non-matching handling.
"""

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from inxr2.adapters.persistence.repositories.file_adapter import PostgresFileRepository
from inxr2.adapters.persistence.repositories.reference_adapter import (
    PostgresReferenceRepository,
)
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from inxr2.adapters.persistence.repositories.symbol_adapter import (
    PostgresSymbolRepository,
)
from inxr2.domain.entities import Commit, File, Reference, Repository, Symbol
from inxr2.domain.value_objects import CommitHash, ReferenceType, SymbolKind


@pytest.mark.asyncio
class TestResolveReferencesBatch:
    """Tests for resolve_references_batch method against the database."""

    async def _create_repo_and_commit(
        self,
        db_session: AsyncSession,
        repo_name: str = "resolve-test",
        commit_hash_prefix: str = "abc",
    ) -> tuple[Repository, Commit]:
        """Helper to create a repository and commit."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name=repo_name, url=f"https://example.com/{repo_name}.git"
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash(
                commit_hash_prefix + "0" * (40 - len(commit_hash_prefix))
            ),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit = await commit_adapter.save(commit)
        assert saved_commit.id is not None

        return saved_repo, saved_commit

    async def test_same_file_priority(self, db_session: AsyncSession) -> None:
        """Reference resolves to symbol in the same file over other files."""
        repo, commit = await self._create_repo_and_commit(db_session)
        assert repo.id is not None
        assert commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        symbol_adapter = PostgresSymbolRepository(db_session)
        ref_adapter = PostgresReferenceRepository(db_session)

        # Create two files
        file_a = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/file_a.py",
                content_hash="hash_a",
                size_bytes=100,
                language="python",
            )
        )
        file_b = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/file_b.py",
                content_hash="hash_b",
                size_bytes=100,
                language="python",
            )
        )
        assert file_a.id is not None
        assert file_b.id is not None

        # Create "Config" symbol in both files
        sym_a = await symbol_adapter.save(
            Symbol(
                file_id=file_a.id,
                repository_id=repo.id,
                commit_id=commit.id,
                name="Config",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        sym_b = await symbol_adapter.save(
            Symbol(
                file_id=file_b.id,
                repository_id=repo.id,
                commit_id=commit.id,
                name="Config",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        assert sym_a.id is not None
        assert sym_b.id is not None

        # Reference to "Config" FROM file_b — should resolve to sym_b (same file)
        ref = await ref_adapter.save(
            Reference(
                source_file_id=file_b.id,
                repository_id=repo.id,
                commit_id=commit.id,
                source_line=15,
                source_column=0,
                source_end_column=6,
                reference_text="Config",
                reference_type=ReferenceType.USAGE,
                target_symbol_id=None,
            )
        )
        assert ref.id is not None

        # Act
        resolved = await ref_adapter.resolve_references_batch(
            repository_id=repo.id, batch_size=100
        )

        # Assert
        assert resolved == 1
        updated_ref = await ref_adapter.find_by_id(ref.id)
        assert updated_ref is not None
        assert updated_ref.target_symbol_id == sym_b.id  # Same file priority

    async def test_same_language_priority(self, db_session: AsyncSession) -> None:
        """Cross-file reference resolves to same-language symbol over lower ID."""
        repo, commit = await self._create_repo_and_commit(
            db_session, "lang-priority-test", "lpt"
        )
        assert repo.id is not None
        assert commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        symbol_adapter = PostgresSymbolRepository(db_session)
        ref_adapter = PostgresReferenceRepository(db_session)

        # Create Python source file, Python target file, and TypeScript file
        py_source = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/utils.py",
                content_hash="hash_py_src",
                size_bytes=100,
                language="python",
            )
        )
        py_target = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/models.py",
                content_hash="hash_py_tgt",
                size_bytes=100,
                language="python",
            )
        )
        ts_file = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="frontend/api.ts",
                content_hash="hash_ts",
                size_bytes=100,
                language="typescript",
            )
        )
        assert py_source.id is not None
        assert py_target.id is not None
        assert ts_file.id is not None

        # "Config" in TypeScript (will get lower symbol ID) and Python
        sym_ts = await symbol_adapter.save(
            Symbol(
                file_id=ts_file.id,
                repository_id=repo.id,
                commit_id=commit.id,
                name="Config",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        sym_py = await symbol_adapter.save(
            Symbol(
                file_id=py_target.id,
                repository_id=repo.id,
                commit_id=commit.id,
                name="Config",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        assert sym_ts.id is not None
        assert sym_py.id is not None
        # TypeScript symbol has lower ID (inserted first)
        assert sym_ts.id < sym_py.id

        # Reference to "Config" from Python source (no same-file match)
        ref = await ref_adapter.save(
            Reference(
                source_file_id=py_source.id,
                repository_id=repo.id,
                commit_id=commit.id,
                source_line=5,
                source_column=0,
                source_end_column=6,
                reference_text="Config",
                reference_type=ReferenceType.USAGE,
                target_symbol_id=None,
            )
        )
        assert ref.id is not None

        # Act
        resolved = await ref_adapter.resolve_references_batch(
            repository_id=repo.id, batch_size=100
        )

        # Assert — should resolve to Python symbol (same language), not TS (lower ID)
        assert resolved == 1
        updated_ref = await ref_adapter.find_by_id(ref.id)
        assert updated_ref is not None
        assert updated_ref.target_symbol_id == sym_py.id  # Same language wins

    async def test_cross_file_falls_back_to_lowest_id(
        self, db_session: AsyncSession
    ) -> None:
        """When no same-file match, resolves to lowest symbol ID."""
        repo, commit = await self._create_repo_and_commit(
            db_session, "lowest-id-test", "def"
        )
        assert repo.id is not None
        assert commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        symbol_adapter = PostgresSymbolRepository(db_session)
        ref_adapter = PostgresReferenceRepository(db_session)

        # Create three files
        file_src = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/source.py",
                content_hash="hash_src",
                size_bytes=100,
                language="python",
            )
        )
        file_x = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/module_x.py",
                content_hash="hash_x",
                size_bytes=100,
                language="python",
            )
        )
        file_y = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/module_y.py",
                content_hash="hash_y",
                size_bytes=100,
                language="python",
            )
        )
        assert file_src.id is not None
        assert file_x.id is not None
        assert file_y.id is not None

        # Create "Helper" in file_x and file_y (NOT in file_src)
        sym_x = await symbol_adapter.save(
            Symbol(
                file_id=file_x.id,
                repository_id=repo.id,
                commit_id=commit.id,
                name="Helper",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        sym_y = await symbol_adapter.save(
            Symbol(
                file_id=file_y.id,
                repository_id=repo.id,
                commit_id=commit.id,
                name="Helper",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        assert sym_x.id is not None
        assert sym_y.id is not None

        # Reference to "Helper" from file_src (no same-file match)
        ref = await ref_adapter.save(
            Reference(
                source_file_id=file_src.id,
                repository_id=repo.id,
                commit_id=commit.id,
                source_line=5,
                source_column=0,
                source_end_column=6,
                reference_text="Helper",
                reference_type=ReferenceType.USAGE,
                target_symbol_id=None,
            )
        )
        assert ref.id is not None

        # Act
        resolved = await ref_adapter.resolve_references_batch(
            repository_id=repo.id, batch_size=100
        )

        # Assert — should resolve to whichever has lowest ID
        assert resolved == 1
        updated_ref = await ref_adapter.find_by_id(ref.id)
        assert updated_ref is not None
        expected_id = min(sym_x.id, sym_y.id)
        assert updated_ref.target_symbol_id == expected_id

    async def test_skips_already_resolved(self, db_session: AsyncSession) -> None:
        """Already-resolved references are not touched."""
        repo, commit = await self._create_repo_and_commit(
            db_session, "skip-test", "ghi"
        )
        assert repo.id is not None
        assert commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        symbol_adapter = PostgresSymbolRepository(db_session)
        ref_adapter = PostgresReferenceRepository(db_session)

        file = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/main.py",
                content_hash="hash_main",
                size_bytes=100,
                language="python",
            )
        )
        assert file.id is not None

        sym = await symbol_adapter.save(
            Symbol(
                file_id=file.id,
                repository_id=repo.id,
                commit_id=commit.id,
                name="func",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )
        assert sym.id is not None

        # Already-resolved reference
        ref = await ref_adapter.save(
            Reference(
                source_file_id=file.id,
                repository_id=repo.id,
                commit_id=commit.id,
                source_line=10,
                source_column=0,
                source_end_column=4,
                reference_text="func",
                reference_type=ReferenceType.CALL,
                target_symbol_id=sym.id,  # Already resolved
            )
        )
        assert ref.id is not None

        # Act
        resolved = await ref_adapter.resolve_references_batch(
            repository_id=repo.id, batch_size=100
        )

        # Assert — nothing to resolve
        assert resolved == 0

    async def test_nonmatching_references_remain_null(
        self, db_session: AsyncSession
    ) -> None:
        """References with no matching symbol stay unresolved."""
        repo, commit = await self._create_repo_and_commit(
            db_session, "nomatch-test", "jkl"
        )
        assert repo.id is not None
        assert commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        ref_adapter = PostgresReferenceRepository(db_session)

        file = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/main.py",
                content_hash="hash_main2",
                size_bytes=100,
                language="python",
            )
        )
        assert file.id is not None

        # Reference to symbol that doesn't exist
        ref = await ref_adapter.save(
            Reference(
                source_file_id=file.id,
                repository_id=repo.id,
                commit_id=commit.id,
                source_line=5,
                source_column=0,
                source_end_column=20,
                reference_text="nonexistent_function",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )
        assert ref.id is not None

        # Act
        resolved = await ref_adapter.resolve_references_batch(
            repository_id=repo.id, batch_size=100
        )

        # Assert
        assert resolved == 0
        updated_ref = await ref_adapter.find_by_id(ref.id)
        assert updated_ref is not None
        assert updated_ref.target_symbol_id is None

    async def test_unresolvable_refs_do_not_block_resolvable_ones(
        self, db_session: AsyncSession
    ) -> None:
        """Resolvable refs are found even when many unresolvable refs exist.

        Regression test: if the batch selection picks refs that have no
        matching symbol (builtins like str, int), it must skip them and
        still resolve the refs that DO have matching symbols.
        """
        repo, commit = await self._create_repo_and_commit(
            db_session, "unresolvable-test", "pqr"
        )
        assert repo.id is not None
        assert commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        symbol_adapter = PostgresSymbolRepository(db_session)
        ref_adapter = PostgresReferenceRepository(db_session)

        file = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/main.py",
                content_hash="hash_unresolvable",
                size_bytes=100,
                language="python",
            )
        )
        assert file.id is not None

        # One symbol that can be resolved
        sym = await symbol_adapter.save(
            Symbol(
                file_id=file.id,
                repository_id=repo.id,
                commit_id=commit.id,
                name="my_function",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )
        assert sym.id is not None

        # Create many unresolvable refs (no matching symbol) BEFORE the resolvable one
        unresolvable_input = []
        for i, name in enumerate(
            ["str", "int", "print", "len", "dict", "list", "None", "True", "bool"]
        ):
            unresolvable_input.append(
                Reference(
                    source_file_id=file.id,
                    repository_id=repo.id,
                    commit_id=commit.id,
                    source_line=i + 10,
                    source_column=0,
                    source_end_column=len(name),
                    reference_text=name,
                    reference_type=ReferenceType.USAGE,
                    target_symbol_id=None,
                )
            )
        unresolvable_refs = await ref_adapter.save_many(unresolvable_input)

        # Create one resolvable ref (inserted AFTER the unresolvable ones)
        resolvable_ref = await ref_adapter.save(
            Reference(
                source_file_id=file.id,
                repository_id=repo.id,
                commit_id=commit.id,
                source_line=30,
                source_column=0,
                source_end_column=11,
                reference_text="my_function",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )
        assert resolvable_ref.id is not None

        # Act — with a small batch_size that's smaller than the number of
        # unresolvable refs, the resolvable ref must still be found
        total_resolved = 0
        for _ in range(20):  # Safety limit
            resolved = await ref_adapter.resolve_references_batch(
                repository_id=repo.id, batch_size=5
            )
            total_resolved += resolved
            if resolved == 0:
                break

        # Assert — the resolvable ref must have been resolved
        assert total_resolved == 1
        updated_ref = await ref_adapter.find_by_id(resolvable_ref.id)
        assert updated_ref is not None
        assert updated_ref.target_symbol_id == sym.id

        # Unresolvable refs remain NULL
        for uref in unresolvable_refs:
            assert uref.id is not None
            found = await ref_adapter.find_by_id(uref.id)
            assert found is not None
            assert found.target_symbol_id is None

    async def test_batching_processes_subset(self, db_session: AsyncSession) -> None:
        """With batch_size=1, only one reference is resolved per call."""
        repo, commit = await self._create_repo_and_commit(
            db_session, "batch-test", "mno"
        )
        assert repo.id is not None
        assert commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        symbol_adapter = PostgresSymbolRepository(db_session)
        ref_adapter = PostgresReferenceRepository(db_session)

        file = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/main.py",
                content_hash="hash_batch",
                size_bytes=100,
                language="python",
            )
        )
        assert file.id is not None

        sym_a = await symbol_adapter.save(
            Symbol(
                file_id=file.id,
                repository_id=repo.id,
                commit_id=commit.id,
                name="func_a",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )
        sym_b = await symbol_adapter.save(
            Symbol(
                file_id=file.id,
                repository_id=repo.id,
                commit_id=commit.id,
                name="func_b",
                kind=SymbolKind.FUNCTION,
                start_line=10,
                start_column=0,
                end_line=15,
                end_column=0,
            )
        )
        assert sym_a.id is not None
        assert sym_b.id is not None

        # Two unresolved references
        ref1 = await ref_adapter.save(
            Reference(
                source_file_id=file.id,
                repository_id=repo.id,
                commit_id=commit.id,
                source_line=20,
                source_column=0,
                source_end_column=6,
                reference_text="func_a",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )
        ref2 = await ref_adapter.save(
            Reference(
                source_file_id=file.id,
                repository_id=repo.id,
                commit_id=commit.id,
                source_line=25,
                source_column=0,
                source_end_column=6,
                reference_text="func_b",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )
        assert ref1.id is not None
        assert ref2.id is not None

        # Act — batch_size=1, should only resolve one
        resolved_first = await ref_adapter.resolve_references_batch(
            repository_id=repo.id, batch_size=1
        )
        assert resolved_first == 1

        # Second call resolves the other
        resolved_second = await ref_adapter.resolve_references_batch(
            repository_id=repo.id, batch_size=1
        )
        assert resolved_second == 1

        # Third call finds nothing left
        resolved_third = await ref_adapter.resolve_references_batch(
            repository_id=repo.id, batch_size=1
        )
        assert resolved_third == 0

    async def test_commit_aware_mode(self, db_session: AsyncSession) -> None:
        """In commit-aware mode, references only resolve to symbols from same commit."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="commit-aware-test", url="https://example.com/ca.git"
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit1 = await commit_adapter.save(
            Commit(
                repository_id=saved_repo.id,
                commit_hash=CommitHash("c1" + "0" * 38),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        commit2 = await commit_adapter.save(
            Commit(
                repository_id=saved_repo.id,
                commit_hash=CommitHash("c2" + "0" * 38),
                author_date=datetime(2025, 1, 2),
                commit_date=datetime(2025, 1, 2),
            )
        )
        assert commit1.id is not None
        assert commit2.id is not None

        file_adapter = PostgresFileRepository(db_session)
        symbol_adapter = PostgresSymbolRepository(db_session)
        ref_adapter = PostgresReferenceRepository(db_session)

        # File and symbol in commit 1
        file1 = await file_adapter.save(
            File(
                repository_id=saved_repo.id,
                commit_id=commit1.id,
                path="src/main.py",
                content_hash="hash_c1",
                size_bytes=100,
                language="python",
            )
        )
        assert file1.id is not None

        sym1 = await symbol_adapter.save(
            Symbol(
                file_id=file1.id,
                repository_id=saved_repo.id,
                commit_id=commit1.id,
                name="process",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )
        assert sym1.id is not None

        # File and symbol in commit 2
        file2 = await file_adapter.save(
            File(
                repository_id=saved_repo.id,
                commit_id=commit2.id,
                path="src/main.py",
                content_hash="hash_c2",
                size_bytes=100,
                language="python",
            )
        )
        assert file2.id is not None

        sym2 = await symbol_adapter.save(
            Symbol(
                file_id=file2.id,
                repository_id=saved_repo.id,
                commit_id=commit2.id,
                name="process",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )
        assert sym2.id is not None

        # Reference in commit 2 — should only resolve to sym2
        ref = await ref_adapter.save(
            Reference(
                source_file_id=file2.id,
                repository_id=saved_repo.id,
                commit_id=commit2.id,
                source_line=10,
                source_column=0,
                source_end_column=7,
                reference_text="process",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )
        assert ref.id is not None

        # Act
        resolved = await ref_adapter.resolve_references_batch(
            repository_id=saved_repo.id, batch_size=100, commit_aware=True
        )

        # Assert — resolved to commit2 symbol, not commit1
        assert resolved == 1
        updated_ref = await ref_adapter.find_by_id(ref.id)
        assert updated_ref is not None
        assert updated_ref.target_symbol_id == sym2.id

    async def test_commit_aware_does_not_cross_commits(
        self, db_session: AsyncSession
    ) -> None:
        """In commit-aware mode, reference in commit2 does not resolve to symbol in commit1."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="cross-commit-test", url="https://example.com/crosscommit.git"
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit1 = await commit_adapter.save(
            Commit(
                repository_id=saved_repo.id,
                commit_hash=CommitHash("cc1" + "0" * 37),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        commit2 = await commit_adapter.save(
            Commit(
                repository_id=saved_repo.id,
                commit_hash=CommitHash("cc2" + "0" * 37),
                author_date=datetime(2025, 1, 2),
                commit_date=datetime(2025, 1, 2),
            )
        )
        assert commit1.id is not None
        assert commit2.id is not None

        file_adapter = PostgresFileRepository(db_session)
        symbol_adapter = PostgresSymbolRepository(db_session)
        ref_adapter = PostgresReferenceRepository(db_session)

        # File and symbol "process" in commit1
        file1 = await file_adapter.save(
            File(
                repository_id=saved_repo.id,
                commit_id=commit1.id,
                path="src/utils.py",
                content_hash="hash_utils_c1",
                size_bytes=100,
                language="python",
            )
        )
        assert file1.id is not None

        sym1 = await symbol_adapter.save(
            Symbol(
                file_id=file1.id,
                repository_id=saved_repo.id,
                commit_id=commit1.id,
                name="process",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )
        assert sym1.id is not None

        # Different file in commit2 with reference to "process"
        file2 = await file_adapter.save(
            File(
                repository_id=saved_repo.id,
                commit_id=commit2.id,
                path="src/main.py",
                content_hash="hash_main_c2",
                size_bytes=100,
                language="python",
            )
        )
        assert file2.id is not None

        ref = await ref_adapter.save(
            Reference(
                source_file_id=file2.id,
                repository_id=saved_repo.id,
                commit_id=commit2.id,
                source_line=10,
                source_column=0,
                source_end_column=7,
                reference_text="process",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )
        assert ref.id is not None

        # Act — commit-aware mode should NOT resolve (no "process" in commit2)
        resolved_commit_aware = await ref_adapter.resolve_references_batch(
            repository_id=saved_repo.id, batch_size=100, commit_aware=True
        )

        # Assert — NOT resolved (no matching symbol in same commit)
        assert resolved_commit_aware == 0
        updated_ref = await ref_adapter.find_by_id(ref.id)
        assert updated_ref is not None
        assert updated_ref.target_symbol_id is None

        # Act — cross-commit mode (default) SHOULD resolve to commit1 symbol
        resolved_cross_commit = await ref_adapter.resolve_references_batch(
            repository_id=saved_repo.id, batch_size=100, commit_aware=False
        )

        # Assert — resolved to the commit1 symbol
        assert resolved_cross_commit == 1
        updated_ref = await ref_adapter.find_by_id(ref.id)
        assert updated_ref is not None
        assert updated_ref.target_symbol_id == sym1.id

    async def test_commit_aware_cross_file_resolution(
        self, db_session: AsyncSession
    ) -> None:
        """In commit-aware mode, cross-file resolution works within same commit."""
        repo, commit = await self._create_repo_and_commit(
            db_session, "cross-file-test", "xf"
        )
        assert repo.id is not None
        assert commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        symbol_adapter = PostgresSymbolRepository(db_session)
        ref_adapter = PostgresReferenceRepository(db_session)

        # File A with reference to "Logger"
        file_a = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/file_a.py",
                content_hash="hash_file_a",
                size_bytes=100,
                language="python",
            )
        )
        assert file_a.id is not None

        # File B with symbol "Logger"
        file_b = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/file_b.py",
                content_hash="hash_file_b",
                size_bytes=100,
                language="python",
            )
        )
        assert file_b.id is not None

        sym_logger = await symbol_adapter.save(
            Symbol(
                file_id=file_b.id,
                repository_id=repo.id,
                commit_id=commit.id,
                name="Logger",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        assert sym_logger.id is not None

        # Reference to "Logger" in file_a
        ref = await ref_adapter.save(
            Reference(
                source_file_id=file_a.id,
                repository_id=repo.id,
                commit_id=commit.id,
                source_line=5,
                source_column=0,
                source_end_column=6,
                reference_text="Logger",
                reference_type=ReferenceType.USAGE,
                target_symbol_id=None,
            )
        )
        assert ref.id is not None

        # Act — commit-aware mode with cross-file resolution
        resolved = await ref_adapter.resolve_references_batch(
            repository_id=repo.id, batch_size=100, commit_aware=True
        )

        # Assert — resolved to symbol in file_b (same commit, different file)
        assert resolved == 1
        updated_ref = await ref_adapter.find_by_id(ref.id)
        assert updated_ref is not None
        assert updated_ref.target_symbol_id == sym_logger.id
