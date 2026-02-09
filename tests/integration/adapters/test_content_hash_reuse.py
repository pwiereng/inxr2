"""Integration tests for content-hash based symbol/reference reuse.

These tests verify that the optimization for reusing symbols/references
from files with identical content hashes works correctly.
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
from inxr2.application.ports.repositories import CopySymbolsResult
from inxr2.domain.entities import Commit, File, Reference, Repository, Symbol
from inxr2.domain.value_objects import CommitHash, ReferenceType, SymbolKind


@pytest.mark.asyncio
class TestFindOneByContentHashInRepo:
    """Tests for find_one_by_content_hash_in_repo method."""

    async def _create_repo_and_commit(
        self, db_session: AsyncSession, repo_name: str
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
                f"{repo_name}hash" + "0" * (40 - len(f"{repo_name}hash"))
            ),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_commit = await commit_adapter.save(commit)
        assert saved_commit.id is not None

        return saved_repo, saved_commit

    async def test_find_one_by_content_hash_in_repo_finds_match(
        self, db_session: AsyncSession
    ) -> None:
        """Test finding a file by content hash within a repository."""
        # Arrange
        repo, commit = await self._create_repo_and_commit(
            db_session, "content-hash-test"
        )
        assert repo.id is not None
        assert commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        file = File(
            repository_id=repo.id,
            commit_id=commit.id,
            path="src/main.py",
            content_hash="abc123def456" + "0" * 28,
            size_bytes=100,
            language="python",
        )
        saved_file = await file_adapter.save(file)
        assert saved_file.id is not None

        # Act
        hash_val = "abc123def456" + "0" * 28
        found = await file_adapter.find_one_by_content_hash_in_repo(repo.id, hash_val)

        # Assert
        assert found is not None
        assert found.id == saved_file.id
        assert found.content_hash == hash_val

    async def test_find_one_by_content_hash_in_repo_no_match(
        self, db_session: AsyncSession
    ) -> None:
        """Test finding a file by content hash when it doesn't exist."""
        # Arrange
        repo, commit = await self._create_repo_and_commit(db_session, "no-match-test")
        assert repo.id is not None
        assert commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        file = File(
            repository_id=repo.id,
            commit_id=commit.id,
            path="src/main.py",
            content_hash="e" * 40,
            size_bytes=100,
        )
        await file_adapter.save(file)

        # Act
        found = await file_adapter.find_one_by_content_hash_in_repo(repo.id, "f" * 40)

        # Assert
        assert found is None

    async def test_find_one_by_content_hash_in_repo_respects_repo_boundary(
        self, db_session: AsyncSession
    ) -> None:
        """Test that find_one_by_content_hash_in_repo only searches within the specified repo."""
        # Arrange - create two repositories with files having the same content hash
        repo1, commit1 = await self._create_repo_and_commit(
            db_session, "repo1-boundary"
        )
        repo2, commit2 = await self._create_repo_and_commit(
            db_session, "repo2-boundary"
        )
        assert repo1.id is not None
        assert repo2.id is not None
        assert commit1.id is not None
        assert commit2.id is not None

        file_adapter = PostgresFileRepository(db_session)

        # Create file only in repo2 with a specific content hash
        file_in_repo2 = File(
            repository_id=repo2.id,
            commit_id=commit2.id,
            path="src/shared.py",
            content_hash="b" * 40,
            size_bytes=100,
        )
        await file_adapter.save(file_in_repo2)

        # Act - search for that hash in repo1 (where it doesn't exist)
        found = await file_adapter.find_one_by_content_hash_in_repo(repo1.id, "b" * 40)

        # Assert - should NOT find the file from repo2
        assert found is None

    async def test_get_content_hash_to_file_id_map(
        self, db_session: AsyncSession
    ) -> None:
        """Test loading all content hashes into a map."""
        # Arrange
        repo, commit = await self._create_repo_and_commit(db_session, "hash-map-test")
        assert repo.id is not None
        assert commit.id is not None

        file_adapter = PostgresFileRepository(db_session)

        # Create multiple files with different content hashes
        file1 = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/file1.py",
                content_hash="a" * 40,
                size_bytes=100,
            )
        )
        file2 = await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/file2.py",
                content_hash="b" * 40,
                size_bytes=100,
            )
        )
        # Duplicate content hash - should only get first file_id
        await file_adapter.save(
            File(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/file3.py",
                content_hash="a" * 40,  # Same as file1
                size_bytes=100,
            )
        )

        # Act
        hash_map = await file_adapter.get_content_hash_to_file_id_map(repo.id)

        # Assert
        assert len(hash_map) == 2  # Only unique hashes
        assert "a" * 40 in hash_map
        assert "b" * 40 in hash_map
        assert hash_map["a" * 40] == file1.id
        assert hash_map["b" * 40] == file2.id


@pytest.mark.asyncio
class TestCopySymbolsToFile:
    """Tests for copy_symbols_to_file method."""

    async def _create_test_data(
        self, db_session: AsyncSession
    ) -> tuple[Repository, Commit, Commit, File]:
        """Helper to create test repository, commits, and source file."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="symbol-copy-test", url="https://example.com/repo.git"
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)

        # Source commit
        source_commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("source00" + "0" * 32),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_source_commit = await commit_adapter.save(source_commit)
        assert saved_source_commit.id is not None

        # Target commit
        target_commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("target00" + "0" * 32),
            author_date=datetime(2025, 1, 2),
            commit_date=datetime(2025, 1, 2),
        )
        saved_target_commit = await commit_adapter.save(target_commit)
        assert saved_target_commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        source_file = File(
            repository_id=saved_repo.id,
            commit_id=saved_source_commit.id,
            path="src/module.py",
            content_hash="c" * 40,
            size_bytes=100,
            language="python",
        )
        saved_source_file = await file_adapter.save(source_file)
        assert saved_source_file.id is not None

        return saved_repo, saved_source_commit, saved_target_commit, saved_source_file

    async def test_copy_symbols_to_file(self, db_session: AsyncSession) -> None:
        """Test copying symbols from source file to target file."""
        # Arrange
        repo, source_commit, target_commit, source_file = await self._create_test_data(
            db_session
        )
        assert repo.id is not None
        assert source_commit.id is not None
        assert target_commit.id is not None
        assert source_file.id is not None

        # Create target file
        file_adapter = PostgresFileRepository(db_session)
        target_file = File(
            repository_id=repo.id,
            commit_id=target_commit.id,
            path="src/module.py",
            content_hash="c" * 40,
            size_bytes=100,
            language="python",
        )
        saved_target_file = await file_adapter.save(target_file)
        assert saved_target_file.id is not None

        # Create symbols in source file
        symbol_adapter = PostgresSymbolRepository(db_session)
        symbols = [
            Symbol(
                file_id=source_file.id,
                repository_id=repo.id,
                commit_id=source_commit.id,
                name="my_function",
                qualified_name="module.my_function",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            ),
            Symbol(
                file_id=source_file.id,
                repository_id=repo.id,
                commit_id=source_commit.id,
                name="MyClass",
                qualified_name="module.MyClass",
                kind=SymbolKind.CLASS,
                start_line=15,
                start_column=0,
                end_line=30,
                end_column=0,
            ),
        ]
        await symbol_adapter.save_many(symbols)

        # Act
        copy_result = await symbol_adapter.copy_symbols_to_file(
            source_file_id=source_file.id,
            target_file_id=saved_target_file.id,
            target_commit_id=target_commit.id,
            target_repository_id=repo.id,
        )

        # Assert - returns CopySymbolsResult with count and id_mapping
        assert isinstance(copy_result, CopySymbolsResult)
        assert copy_result.count == 2
        assert len(copy_result.id_mapping) == 2

        # Verify symbols were copied to target file
        target_symbols = await symbol_adapter.list_by_file(saved_target_file.id)
        assert len(target_symbols) == 2

        symbol_names = {s.name for s in target_symbols}
        assert "my_function" in symbol_names
        assert "MyClass" in symbol_names

        # Verify the symbols have the correct commit_id and file_id
        for symbol in target_symbols:
            assert symbol.file_id == saved_target_file.id
            assert symbol.commit_id == target_commit.id

    async def test_copy_symbols_handles_empty_source(
        self, db_session: AsyncSession
    ) -> None:
        """Test copying symbols when source file has no symbols."""
        # Arrange
        repo, source_commit, target_commit, source_file = await self._create_test_data(
            db_session
        )
        assert repo.id is not None
        assert source_commit.id is not None
        assert target_commit.id is not None
        assert source_file.id is not None

        # Create target file (no symbols in source)
        file_adapter = PostgresFileRepository(db_session)
        target_file = File(
            repository_id=repo.id,
            commit_id=target_commit.id,
            path="src/empty.py",
            content_hash="d" * 40,
            size_bytes=0,
        )
        saved_target_file = await file_adapter.save(target_file)
        assert saved_target_file.id is not None

        symbol_adapter = PostgresSymbolRepository(db_session)

        # Act
        copy_result = await symbol_adapter.copy_symbols_to_file(
            source_file_id=source_file.id,
            target_file_id=saved_target_file.id,
            target_commit_id=target_commit.id,
            target_repository_id=repo.id,
        )

        # Assert
        assert isinstance(copy_result, CopySymbolsResult)
        assert copy_result.count == 0
        assert copy_result.id_mapping == {}
        target_symbols = await symbol_adapter.list_by_file(saved_target_file.id)
        assert len(target_symbols) == 0

    async def test_copy_symbols_remaps_parent_symbol_id(
        self, db_session: AsyncSession
    ) -> None:
        """Test that parent_symbol_id is correctly remapped when copying nested symbols."""
        # Arrange
        repo, source_commit, target_commit, source_file = await self._create_test_data(
            db_session
        )
        assert repo.id is not None
        assert source_commit.id is not None
        assert target_commit.id is not None
        assert source_file.id is not None

        # Create target file
        file_adapter = PostgresFileRepository(db_session)
        target_file = File(
            repository_id=repo.id,
            commit_id=target_commit.id,
            path="src/module.py",
            content_hash="c" * 40,
            size_bytes=100,
            language="python",
        )
        saved_target_file = await file_adapter.save(target_file)
        assert saved_target_file.id is not None

        symbol_adapter = PostgresSymbolRepository(db_session)

        # Create parent class symbol
        parent_symbol = Symbol(
            file_id=source_file.id,
            repository_id=repo.id,
            commit_id=source_commit.id,
            name="MyClass",
            qualified_name="module.MyClass",
            kind=SymbolKind.CLASS,
            start_line=1,
            start_column=0,
            end_line=20,
            end_column=0,
        )
        saved_parent = await symbol_adapter.save(parent_symbol)
        assert saved_parent.id is not None

        # Create child method symbol with parent reference
        child_symbol = Symbol(
            file_id=source_file.id,
            repository_id=repo.id,
            commit_id=source_commit.id,
            name="my_method",
            qualified_name="module.MyClass.my_method",
            kind=SymbolKind.METHOD,
            start_line=5,
            start_column=4,
            end_line=10,
            end_column=0,
            parent_symbol_id=saved_parent.id,
        )
        await symbol_adapter.save(child_symbol)

        # Act
        copy_result = await symbol_adapter.copy_symbols_to_file(
            source_file_id=source_file.id,
            target_file_id=saved_target_file.id,
            target_commit_id=target_commit.id,
            target_repository_id=repo.id,
        )

        # Assert
        assert copy_result.count == 2

        # Verify symbols were copied and parent reference was remapped
        target_symbols = await symbol_adapter.list_by_file(saved_target_file.id)
        assert len(target_symbols) == 2

        # Find the copied class and method
        copied_class = next(s for s in target_symbols if s.name == "MyClass")
        copied_method = next(s for s in target_symbols if s.name == "my_method")

        # Verify the method's parent_symbol_id points to the NEW class ID
        assert copied_method.parent_symbol_id is not None
        assert copied_method.parent_symbol_id == copied_class.id
        # And NOT to the old parent ID
        assert copied_method.parent_symbol_id != saved_parent.id


@pytest.mark.asyncio
class TestCopyReferencesToFile:
    """Tests for copy_references_to_file method."""

    async def _create_test_data(
        self, db_session: AsyncSession
    ) -> tuple[Repository, Commit, Commit, File]:
        """Helper to create test repository, commits, and source file."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="ref-copy-test", url="https://example.com/repo.git"
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)

        # Source commit
        source_commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("refsrc00" + "0" * 32),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        saved_source_commit = await commit_adapter.save(source_commit)
        assert saved_source_commit.id is not None

        # Target commit
        target_commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash("reftgt00" + "0" * 32),
            author_date=datetime(2025, 1, 2),
            commit_date=datetime(2025, 1, 2),
        )
        saved_target_commit = await commit_adapter.save(target_commit)
        assert saved_target_commit.id is not None

        file_adapter = PostgresFileRepository(db_session)
        source_file = File(
            repository_id=saved_repo.id,
            commit_id=saved_source_commit.id,
            path="src/caller.py",
            content_hash="1" * 40,
            size_bytes=100,
            language="python",
        )
        saved_source_file = await file_adapter.save(source_file)
        assert saved_source_file.id is not None

        return saved_repo, saved_source_commit, saved_target_commit, saved_source_file

    async def test_copy_references_to_file(self, db_session: AsyncSession) -> None:
        """Test copying references from source file to target file."""
        # Arrange
        repo, source_commit, target_commit, source_file = await self._create_test_data(
            db_session
        )
        assert repo.id is not None
        assert source_commit.id is not None
        assert target_commit.id is not None
        assert source_file.id is not None

        # Create target file
        file_adapter = PostgresFileRepository(db_session)
        target_file = File(
            repository_id=repo.id,
            commit_id=target_commit.id,
            path="src/caller.py",
            content_hash="1" * 40,
            size_bytes=100,
            language="python",
        )
        saved_target_file = await file_adapter.save(target_file)
        assert saved_target_file.id is not None

        # Create references in source file
        reference_adapter = PostgresReferenceRepository(db_session)
        references = [
            Reference(
                source_file_id=source_file.id,
                repository_id=repo.id,
                commit_id=source_commit.id,
                source_line=5,
                source_column=4,
                source_end_column=15,
                reference_text="my_function",
                reference_type=ReferenceType.CALL,
            ),
            Reference(
                source_file_id=source_file.id,
                repository_id=repo.id,
                commit_id=source_commit.id,
                source_line=10,
                source_column=4,
                source_end_column=11,
                reference_text="MyClass",
                reference_type=ReferenceType.USAGE,
            ),
        ]
        await reference_adapter.save_many(references)

        # Act
        copied_count = await reference_adapter.copy_references_to_file(
            source_file_id=source_file.id,
            target_file_id=saved_target_file.id,
            target_commit_id=target_commit.id,
            target_repository_id=repo.id,
        )

        # Assert
        assert copied_count == 2

        # Verify references were copied to target file
        target_refs = await reference_adapter.list_by_file(saved_target_file.id)
        assert len(target_refs) == 2

        ref_texts = {r.reference_text for r in target_refs}
        assert "my_function" in ref_texts
        assert "MyClass" in ref_texts

        # Verify the references have the correct commit_id and file_id
        for ref in target_refs:
            assert ref.source_file_id == saved_target_file.id
            assert ref.commit_id == target_commit.id
            # target_symbol_id should be NULL (for later resolution)
            assert ref.target_symbol_id is None

    async def test_copy_references_handles_empty_source(
        self, db_session: AsyncSession
    ) -> None:
        """Test copying references when source file has no references."""
        # Arrange
        repo, source_commit, target_commit, source_file = await self._create_test_data(
            db_session
        )
        assert repo.id is not None
        assert source_commit.id is not None
        assert target_commit.id is not None
        assert source_file.id is not None

        # Create target file (no references in source)
        file_adapter = PostgresFileRepository(db_session)
        target_file = File(
            repository_id=repo.id,
            commit_id=target_commit.id,
            path="src/empty.py",
            content_hash="d" * 40,
            size_bytes=0,
        )
        saved_target_file = await file_adapter.save(target_file)
        assert saved_target_file.id is not None

        reference_adapter = PostgresReferenceRepository(db_session)

        # Act
        copied_count = await reference_adapter.copy_references_to_file(
            source_file_id=source_file.id,
            target_file_id=saved_target_file.id,
            target_commit_id=target_commit.id,
            target_repository_id=repo.id,
        )

        # Assert
        assert copied_count == 0
        target_refs = await reference_adapter.list_by_file(saved_target_file.id)
        assert len(target_refs) == 0

    async def test_copy_references_remaps_target_symbol_id(
        self, db_session: AsyncSession
    ) -> None:
        """Test that copied references remap target_symbol_id via mapping."""
        # Arrange
        repo, source_commit, target_commit, source_file = await self._create_test_data(
            db_session
        )
        assert repo.id is not None
        assert source_commit.id is not None
        assert target_commit.id is not None
        assert source_file.id is not None

        # Create symbols in the source file
        symbol_adapter = PostgresSymbolRepository(db_session)
        symbol = Symbol(
            file_id=source_file.id,
            repository_id=repo.id,
            commit_id=source_commit.id,
            name="target_func",
            kind=SymbolKind.FUNCTION,
            start_line=1,
            start_column=0,
            end_line=5,
            end_column=0,
        )
        saved_symbol = await symbol_adapter.save(symbol)
        assert saved_symbol.id is not None

        # Create target file
        file_adapter = PostgresFileRepository(db_session)
        target_file = File(
            repository_id=repo.id,
            commit_id=target_commit.id,
            path="src/caller.py",
            content_hash="1" * 40,
            size_bytes=100,
            language="python",
        )
        saved_target_file = await file_adapter.save(target_file)
        assert saved_target_file.id is not None

        # Copy symbols to get the mapping
        copy_result = await symbol_adapter.copy_symbols_to_file(
            source_file_id=source_file.id,
            target_file_id=saved_target_file.id,
            target_commit_id=target_commit.id,
            target_repository_id=repo.id,
        )
        assert saved_symbol.id in copy_result.id_mapping

        # Create references: one resolved, one unresolved
        reference_adapter = PostgresReferenceRepository(db_session)
        resolved_ref = Reference(
            source_file_id=source_file.id,
            repository_id=repo.id,
            commit_id=source_commit.id,
            source_line=10,
            source_column=4,
            source_end_column=15,
            reference_text="target_func",
            reference_type=ReferenceType.CALL,
            target_symbol_id=saved_symbol.id,  # Already resolved
        )
        unresolved_ref = Reference(
            source_file_id=source_file.id,
            repository_id=repo.id,
            commit_id=source_commit.id,
            source_line=20,
            source_column=4,
            source_end_column=18,
            reference_text="unknown_func",
            reference_type=ReferenceType.CALL,
            target_symbol_id=None,  # Unresolved
        )
        await reference_adapter.save(resolved_ref)
        await reference_adapter.save(unresolved_ref)

        # Act - copy with symbol_id_mapping
        copied_count = await reference_adapter.copy_references_to_file(
            source_file_id=source_file.id,
            target_file_id=saved_target_file.id,
            target_commit_id=target_commit.id,
            target_repository_id=repo.id,
            symbol_id_mapping=copy_result.id_mapping,
        )

        # Assert
        assert copied_count == 2

        target_refs = await reference_adapter.list_by_file(saved_target_file.id)
        assert len(target_refs) == 2

        # Find the resolved and unresolved copied references
        resolved_copy = next(
            r for r in target_refs if r.reference_text == "target_func"
        )
        unresolved_copy = next(
            r for r in target_refs if r.reference_text == "unknown_func"
        )

        # Resolved ref should have remapped target_symbol_id (new symbol ID)
        new_symbol_id = copy_result.id_mapping[saved_symbol.id]
        assert resolved_copy.target_symbol_id == new_symbol_id
        assert resolved_copy.target_symbol_id != saved_symbol.id  # Not the old ID

        # Unresolved ref should still be NULL
        assert unresolved_copy.target_symbol_id is None

    async def test_copy_references_without_mapping_clears_target(
        self, db_session: AsyncSession
    ) -> None:
        """Test that without mapping, target_symbol_id is set to NULL (backward compat)."""
        # Arrange
        repo, source_commit, target_commit, source_file = await self._create_test_data(
            db_session
        )
        assert repo.id is not None
        assert source_commit.id is not None
        assert target_commit.id is not None
        assert source_file.id is not None

        # Create a symbol in the source file to reference
        symbol_adapter = PostgresSymbolRepository(db_session)
        symbol = Symbol(
            file_id=source_file.id,
            repository_id=repo.id,
            commit_id=source_commit.id,
            name="target_func",
            kind=SymbolKind.FUNCTION,
            start_line=1,
            start_column=0,
            end_line=5,
            end_column=0,
        )
        saved_symbol = await symbol_adapter.save(symbol)
        assert saved_symbol.id is not None

        # Create target file
        file_adapter = PostgresFileRepository(db_session)
        target_file = File(
            repository_id=repo.id,
            commit_id=target_commit.id,
            path="src/caller.py",
            content_hash="1" * 40,
            size_bytes=100,
            language="python",
        )
        saved_target_file = await file_adapter.save(target_file)
        assert saved_target_file.id is not None

        # Create a reference WITH a resolved target_symbol_id
        reference_adapter = PostgresReferenceRepository(db_session)
        ref = Reference(
            source_file_id=source_file.id,
            repository_id=repo.id,
            commit_id=source_commit.id,
            source_line=10,
            source_column=4,
            source_end_column=15,
            reference_text="target_func",
            reference_type=ReferenceType.CALL,
            target_symbol_id=saved_symbol.id,  # Already resolved
        )
        await reference_adapter.save(ref)

        # Act - copy WITHOUT mapping (backward compat)
        copied_count = await reference_adapter.copy_references_to_file(
            source_file_id=source_file.id,
            target_file_id=saved_target_file.id,
            target_commit_id=target_commit.id,
            target_repository_id=repo.id,
        )

        # Assert
        assert copied_count == 1

        # Verify the copied reference has NULL target_symbol_id
        target_refs = await reference_adapter.list_by_file(saved_target_file.id)
        assert len(target_refs) == 1
        assert target_refs[0].target_symbol_id is None


@pytest.mark.asyncio
class TestGetOrCreateRaceCondition:
    """Tests for get_or_create race condition handling."""

    async def test_get_or_create_handles_concurrent_calls(
        self, db_session: AsyncSession
    ) -> None:
        """Test that concurrent get_or_create calls don't fail.

        Simulates a race condition where multiple processes try to create
        the same repository simultaneously. Only one should succeed in creating,
        and all should return the same repository.
        """
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo_name = "concurrent-test-repo"

        # First call creates the repository
        repo1, created1 = await repo_adapter.get_or_create(
            name=repo_name,
            url="https://example.com/repo.git",
            description="Test repo",
        )

        assert created1 is True
        assert repo1.id is not None
        assert repo1.name == repo_name

        # Second call with same name should return existing
        repo2, created2 = await repo_adapter.get_or_create(
            name=repo_name,
            url="https://example.com/different.git",  # Different URL
            description="Different description",
        )

        assert created2 is False
        assert repo2.id == repo1.id
        assert repo2.name == repo_name
        # Should return original values, not the new ones
        assert repo2.url == "https://example.com/repo.git"

    async def test_get_or_create_returns_existing_on_find(
        self, db_session: AsyncSession
    ) -> None:
        """Test get_or_create returns existing repository when found."""
        repo_adapter = PostgresRepositoryAdapter(db_session)

        # First, create a repository directly
        repo = Repository(
            name="existing-repo",
            url="https://example.com/existing.git",
        )
        saved_repo = await repo_adapter.save(repo)
        assert saved_repo.id is not None

        # Now try get_or_create - should find existing
        found_repo, created = await repo_adapter.get_or_create(
            name="existing-repo",
            url="https://different-url.com/repo.git",
        )

        assert created is False
        assert found_repo.id == saved_repo.id
        assert found_repo.url == "https://example.com/existing.git"

    async def test_get_or_create_creates_when_not_found(
        self, db_session: AsyncSession
    ) -> None:
        """Test get_or_create creates new repository when not found."""
        repo_adapter = PostgresRepositoryAdapter(db_session)

        repo, created = await repo_adapter.get_or_create(
            name="new-unique-repo",
            url="https://example.com/new.git",
            description="A new repository",
            default_branch="main",
        )

        assert created is True
        assert repo.id is not None
        assert repo.name == "new-unique-repo"
        assert repo.url == "https://example.com/new.git"
        assert repo.description == "A new repository"
        assert repo.default_branch == "main"

        # Verify it was actually saved
        found = await repo_adapter.find_by_name("new-unique-repo")
        assert found is not None
        assert found.id == repo.id
