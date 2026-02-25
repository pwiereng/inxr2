"""Tests for ResolveReferencesUseCase using dependency injection."""

from datetime import datetime

import pytest

from inxr2.application.use_cases.indexing import (
    ResolveReferencesRequest,
    ResolveReferencesUseCase,
)
from inxr2.domain.entities import Commit, File, Reference, Symbol
from inxr2.domain.value_objects import CommitHash, ReferenceType, SymbolKind
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryReferenceRepository,
    InMemorySymbolRepository,
)


class TestResolveReferencesUseCase:
    """Tests for ResolveReferencesUseCase."""

    @pytest.fixture
    def symbol_repo(self) -> InMemorySymbolRepository:
        """Create a symbol repository with test symbols."""
        repo = InMemorySymbolRepository()

        # Add test symbols
        repo.add(
            Symbol(
                id=1,
                file_id=1,
                repository_id=1,
                name="calculate_total",
                kind=SymbolKind.FUNCTION,
                start_line=10,
                start_column=0,
                end_line=15,
                end_column=0,
            )
        )
        repo.add(
            Symbol(
                id=2,
                file_id=1,
                repository_id=1,
                name="Calculator",
                kind=SymbolKind.CLASS,
                start_line=20,
                start_column=0,
                end_line=50,
                end_column=0,
            )
        )
        # Same-named symbol in a different file (file 2)
        repo.add(
            Symbol(
                id=3,
                file_id=2,
                repository_id=1,
                name="calculate_total",
                kind=SymbolKind.FUNCTION,
                start_line=10,
                start_column=0,
                end_line=15,
                end_column=0,
            )
        )

        return repo

    @pytest.fixture
    def reference_repo(
        self, symbol_repo: InMemorySymbolRepository
    ) -> InMemoryReferenceRepository:
        """Create a reference repository with test references."""
        repo = InMemoryReferenceRepository(symbol_repo=symbol_repo)

        # Unresolved reference to calculate_total (from file 2)
        repo.add(
            Reference(
                id=1,
                repository_id=1,
                source_file_id=2,
                source_line=5,
                source_column=10,
                source_end_column=25,
                reference_text="calculate_total",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,  # Unresolved
            )
        )
        # Unresolved reference to Calculator (from file 2)
        repo.add(
            Reference(
                id=2,
                repository_id=1,
                source_file_id=2,
                source_line=8,
                source_column=5,
                source_end_column=15,
                reference_text="Calculator",
                reference_type=ReferenceType.INSTANTIATION,
                target_symbol_id=None,  # Unresolved
            )
        )
        # Already resolved reference (should be skipped)
        repo.add(
            Reference(
                id=3,
                repository_id=1,
                source_file_id=2,
                source_line=10,
                source_column=0,
                source_end_column=15,
                reference_text="calculate_total",
                reference_type=ReferenceType.CALL,
                target_symbol_id=1,  # Already resolved
            )
        )
        # Unresolved reference to nonexistent symbol
        repo.add(
            Reference(
                id=4,
                repository_id=1,
                source_file_id=2,
                source_line=15,
                source_column=0,
                source_end_column=20,
                reference_text="nonexistent_func",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,  # Unresolved, no matching symbol
            )
        )
        # Reference from file 3 to calculate_total
        repo.add(
            Reference(
                id=5,
                repository_id=1,
                source_file_id=3,
                source_line=5,
                source_column=10,
                source_end_column=25,
                reference_text="calculate_total",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,  # Unresolved
            )
        )

        return repo

    @pytest.fixture
    def use_case(
        self, reference_repo: InMemoryReferenceRepository
    ) -> ResolveReferencesUseCase:
        """Create the use case with the fake repository."""
        return ResolveReferencesUseCase(reference_repository=reference_repo)

    @pytest.mark.asyncio
    async def test_resolve_references_across_repository(
        self,
        use_case: ResolveReferencesUseCase,
        reference_repo: InMemoryReferenceRepository,
    ) -> None:
        """Test resolving references across the repository."""
        # Arrange
        request = ResolveReferencesRequest(repository_id=1)

        # Act
        response = await use_case.execute(request)

        # Assert
        # Should resolve 3 references:
        # - ref 1: calculate_total -> symbol 3 (same file priority: ref is from file 2, symbol 3 is in file 2)
        # - ref 2: Calculator -> symbol 2
        # - ref 5: calculate_total -> symbol 1 (file 3 has no calculate_total, so picks by ID)
        # Should NOT resolve ref 4 (no matching symbol)
        # Should skip ref 3 (already resolved)
        assert response.resolved_count == 3

        # Verify ref 1 is now resolved to symbol 3 (same file as reference)
        ref1 = await reference_repo.find_by_id(1)
        assert ref1 is not None
        assert (
            ref1.target_symbol_id == 3
        )  # Same file priority: symbol 3 is in file 2, like ref 1

        # Verify ref 2 is now resolved
        ref2 = await reference_repo.find_by_id(2)
        assert ref2 is not None
        assert ref2.target_symbol_id == 2

        # Verify ref 4 is still unresolved
        ref4 = await reference_repo.find_by_id(4)
        assert ref4 is not None
        assert ref4.target_symbol_id is None

    @pytest.mark.asyncio
    async def test_resolve_references_matches_by_file(
        self,
        use_case: ResolveReferencesUseCase,
        reference_repo: InMemoryReferenceRepository,
    ) -> None:
        """Test that references resolve to symbols in the same file when possible."""
        # Arrange
        request = ResolveReferencesRequest(repository_id=1)

        # Act
        response = await use_case.execute(request)

        # Assert
        # Should resolve 3 references:
        # - ref 1: calculate_total -> symbol 3 (same file priority: ref is from file 2, symbol 3 is in file 2)
        # - ref 2: Calculator -> symbol 2
        # - ref 5: calculate_total -> symbol 1 (file 3 has no calculate_total, so picks by ID)
        # Should NOT resolve ref 4 (no matching symbol)
        # Should skip ref 3 (already resolved)
        assert response.resolved_count == 3

        # Verify ref 5 is resolved to a matching symbol
        ref5 = await reference_repo.find_by_id(5)
        assert ref5 is not None
        assert ref5.target_symbol_id is not None

    @pytest.mark.asyncio
    async def test_resolve_references_for_different_repository(
        self,
        use_case: ResolveReferencesUseCase,
        reference_repo: InMemoryReferenceRepository,
    ) -> None:
        """Test that only references in specified repository are resolved."""
        # Arrange - request for repository that doesn't exist
        request = ResolveReferencesRequest(repository_id=999)

        # Act
        response = await use_case.execute(request)

        # Assert - no references should be resolved
        assert response.resolved_count == 0

    @pytest.mark.asyncio
    async def test_resolve_references_skips_already_resolved(
        self,
        use_case: ResolveReferencesUseCase,
        reference_repo: InMemoryReferenceRepository,
    ) -> None:
        """Test that already resolved references are not counted again."""
        # Arrange
        request = ResolveReferencesRequest(repository_id=1)

        # Act - resolve twice
        response1 = await use_case.execute(request)
        response2 = await use_case.execute(request)

        # Assert
        assert response1.resolved_count == 3
        assert response2.resolved_count == 0  # All already resolved

    @pytest.mark.asyncio
    async def test_resolve_references_empty_repository(
        self, symbol_repo: InMemorySymbolRepository
    ) -> None:
        """Test resolving references when there are no references."""
        # Arrange
        empty_ref_repo = InMemoryReferenceRepository(symbol_repo=symbol_repo)
        use_case = ResolveReferencesUseCase(reference_repository=empty_ref_repo)
        request = ResolveReferencesRequest(repository_id=1)

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response.resolved_count == 0


class TestDeterministicResolution:
    """Tests for deterministic resolution with same-file, same-language priority."""

    @pytest.fixture
    def file_repo(self) -> "InMemoryFileRepository":
        """Create a file repository with test files."""
        from tests.fixtures.test_doubles import InMemoryFileRepository

        repo = InMemoryFileRepository()

        # File 1: Python file
        repo.add(
            File(
                id=1,
                repository_id=1,
                path="src/main.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            )
        )
        # File 2: Another Python file
        repo.add(
            File(
                id=2,
                repository_id=1,
                path="src/utils.py",
                content_hash="hash2",
                size_bytes=100,
                language="python",
            )
        )
        # File 3: TypeScript file
        repo.add(
            File(
                id=3,
                repository_id=1,
                path="src/app.ts",
                content_hash="hash3",
                size_bytes=100,
                language="typescript",
            )
        )
        return repo

    @pytest.fixture
    def symbol_repo_with_duplicates(self) -> InMemorySymbolRepository:
        """Create a symbol repository with multiple symbols having the same name."""
        repo = InMemorySymbolRepository()

        # Three symbols all named "Config" in different files
        repo.add(
            Symbol(
                id=1,
                file_id=1,  # Python file (main.py)
                repository_id=1,
                name="Config",
                kind=SymbolKind.CLASS,
                start_line=10,
                start_column=0,
                end_line=20,
                end_column=0,
            )
        )
        repo.add(
            Symbol(
                id=2,
                file_id=2,  # Python file (utils.py)
                repository_id=1,
                name="Config",
                kind=SymbolKind.CLASS,
                start_line=5,
                start_column=0,
                end_line=15,
                end_column=0,
            )
        )
        repo.add(
            Symbol(
                id=3,
                file_id=3,  # TypeScript file (app.ts)
                repository_id=1,
                name="Config",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        return repo

    @pytest.mark.asyncio
    async def test_same_file_priority(
        self,
        symbol_repo_with_duplicates: InMemorySymbolRepository,
        file_repo: "InMemoryFileRepository",
    ) -> None:
        """Test that references resolve to symbols in the same file first."""
        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo_with_duplicates,
            file_repo=file_repo,
        )

        # Reference to "Config" from main.py (file_id=1)
        ref_repo.add(
            Reference(
                id=1,
                repository_id=1,
                source_file_id=1,  # From main.py
                source_line=25,
                source_column=0,
                source_end_column=6,
                reference_text="Config",
                reference_type=ReferenceType.TYPE_ANNOTATION,
                target_symbol_id=None,
            )
        )

        use_case = ResolveReferencesUseCase(reference_repository=ref_repo)
        request = ResolveReferencesRequest(repository_id=1)

        await use_case.execute(request)

        # Should resolve to symbol 1 (in same file: main.py)
        ref = await ref_repo.find_by_id(1)
        assert ref is not None
        assert ref.target_symbol_id == 1  # Same file priority

    @pytest.mark.asyncio
    async def test_same_language_priority(
        self,
        file_repo: "InMemoryFileRepository",
    ) -> None:
        """Test that references resolve to same-language symbols over lower IDs."""
        # Config in app.ts (TypeScript, lower ID=1) and main.py (Python, higher ID=3)
        # Reference from utils.py (Python) should prefer Python symbol despite higher ID
        symbol_repo = InMemorySymbolRepository()
        symbol_repo.add(
            Symbol(
                id=1,
                file_id=3,  # TypeScript file (app.ts) — lower ID
                repository_id=1,
                name="Config",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        symbol_repo.add(
            Symbol(
                id=3,
                file_id=1,  # Python file (main.py) — higher ID
                repository_id=1,
                name="Config",
                kind=SymbolKind.CLASS,
                start_line=10,
                start_column=0,
                end_line=20,
                end_column=0,
            )
        )

        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
        )

        # Reference to "Config" from utils.py (file_id=2, Python)
        # No Config in utils.py, so should prefer Python symbol (id=3) over TS (id=1)
        ref_repo.add(
            Reference(
                id=1,
                repository_id=1,
                source_file_id=2,  # From utils.py (Python)
                source_line=20,
                source_column=0,
                source_end_column=6,
                reference_text="Config",
                reference_type=ReferenceType.TYPE_ANNOTATION,
                target_symbol_id=None,
            )
        )

        use_case = ResolveReferencesUseCase(reference_repository=ref_repo)
        request = ResolveReferencesRequest(repository_id=1)

        await use_case.execute(request)

        # Should resolve to symbol 3 (Python, same language as source file)
        # even though symbol 1 (TypeScript) has lower ID
        ref = await ref_repo.find_by_id(1)
        assert ref is not None
        assert ref.target_symbol_id == 3  # Same language priority over ID

    @pytest.mark.asyncio
    async def test_cross_language_falls_back_to_id(
        self,
        file_repo: "InMemoryFileRepository",
    ) -> None:
        """Test resolution falls back to symbol ID when no same-language match."""
        symbol_repo = InMemorySymbolRepository()

        # Only TypeScript symbols, but reference from Python
        symbol_repo.add(
            Symbol(
                id=10,
                file_id=3,  # TypeScript
                repository_id=1,
                name="Helper",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )
        symbol_repo.add(
            Symbol(
                id=5,  # Lower ID
                file_id=3,  # TypeScript
                repository_id=1,
                name="Helper",
                kind=SymbolKind.CLASS,
                start_line=20,
                start_column=0,
                end_line=30,
                end_column=0,
            )
        )

        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
        )

        # Reference from Python file to TypeScript symbol
        ref_repo.add(
            Reference(
                id=1,
                repository_id=1,
                source_file_id=1,  # From main.py (Python)
                source_line=5,
                source_column=0,
                source_end_column=6,
                reference_text="Helper",
                reference_type=ReferenceType.TYPE_ANNOTATION,
                target_symbol_id=None,
            )
        )

        use_case = ResolveReferencesUseCase(reference_repository=ref_repo)
        request = ResolveReferencesRequest(repository_id=1)

        await use_case.execute(request)

        # Should resolve to symbol 5 (lower ID = deterministic tiebreaker)
        ref = await ref_repo.find_by_id(1)
        assert ref is not None
        assert ref.target_symbol_id == 5

    @pytest.mark.asyncio
    async def test_resolution_is_deterministic(
        self,
        symbol_repo_with_duplicates: InMemorySymbolRepository,
        file_repo: "InMemoryFileRepository",
    ) -> None:
        """Test that resolution produces the same result every time."""
        results = []

        for _ in range(5):
            ref_repo = InMemoryReferenceRepository(
                symbol_repo=symbol_repo_with_duplicates,
                file_repo=file_repo,
            )

            ref_repo.add(
                Reference(
                    id=1,
                    repository_id=1,
                    source_file_id=1,
                    source_line=25,
                    source_column=0,
                    source_end_column=6,
                    reference_text="Config",
                    reference_type=ReferenceType.TYPE_ANNOTATION,
                    target_symbol_id=None,
                )
            )

            use_case = ResolveReferencesUseCase(reference_repository=ref_repo)
            request = ResolveReferencesRequest(repository_id=1)

            await use_case.execute(request)

            ref = await ref_repo.find_by_id(1)
            assert ref is not None
            results.append(ref.target_symbol_id)

        # All results should be the same
        assert len(set(results)) == 1, f"Resolution was not deterministic: {results}"


class TestBranchScopedResolution:
    """Tests for branch-scoped reference resolution via use case."""

    @pytest.mark.asyncio
    async def test_branch_param_does_not_restrict_resolution(self) -> None:
        """Branch parameter is accepted but all refs are resolved regardless."""
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository(commit_repo=commit_repo)
        symbol_repo = InMemorySymbolRepository(file_repo=file_repo)
        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
        )

        # Set up two branches with commits
        commit_repo.add(
            Commit(
                id=1,
                repository_id=1,
                commit_hash=CommitHash("main" + "0" * 36),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        await commit_repo.link_commit_to_branch(1, 1, "main")

        commit_repo.add(
            Commit(
                id=2,
                repository_id=1,
                commit_hash=CommitHash("feat" + "0" * 36),
                author_date=datetime(2025, 1, 2),
                commit_date=datetime(2025, 1, 2),
            )
        )
        await commit_repo.link_commit_to_branch(1, 2, "feature")

        # File on main
        file_repo.add(
            File(
                id=1,
                repository_id=1,
                path="src/main_mod.py",
                content_hash="hash_main",
                size_bytes=100,
                language="python",
            )
        )
        await file_repo.link_file_to_commit(1, 1)

        # File on feature
        file_repo.add(
            File(
                id=2,
                repository_id=1,
                path="src/feat_mod.py",
                content_hash="hash_feat",
                size_bytes=100,
                language="python",
            )
        )
        await file_repo.link_file_to_commit(2, 2)

        # Symbols
        symbol_repo.add(
            Symbol(
                id=1,
                file_id=1,
                repository_id=1,
                name="MainFunc",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )
        symbol_repo.add(
            Symbol(
                id=2,
                file_id=2,
                repository_id=1,
                name="FeatFunc",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )

        # Reference on main
        ref_repo.add(
            Reference(
                id=1,
                repository_id=1,
                source_file_id=1,
                source_line=10,
                source_column=0,
                source_end_column=8,
                reference_text="MainFunc",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )
        # Reference on feature
        ref_repo.add(
            Reference(
                id=2,
                repository_id=1,
                source_file_id=2,
                source_line=10,
                source_column=0,
                source_end_column=8,
                reference_text="FeatFunc",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )

        # Resolve with branch="main" via use case — all refs resolved
        use_case = ResolveReferencesUseCase(reference_repository=ref_repo)
        response = await use_case.execute(
            ResolveReferencesRequest(repository_id=1, branch="main")
        )

        # Both refs resolved (no source-file filter, repo-wide symbol pool)
        assert response.resolved_count == 2

        main_ref = await ref_repo.find_by_id(1)
        assert main_ref is not None
        assert main_ref.target_symbol_id == 1

        feat_ref = await ref_repo.find_by_id(2)
        assert feat_ref is not None
        assert feat_ref.target_symbol_id == 2

    @pytest.mark.asyncio
    async def test_branch_none_resolves_all_refs(self) -> None:
        """When branch is None, all refs are resolved (backward compat)."""
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository(commit_repo=commit_repo)
        symbol_repo = InMemorySymbolRepository(file_repo=file_repo)
        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
        )

        # Same setup as above but resolve with branch=None
        commit_repo.add(
            Commit(
                id=1,
                repository_id=1,
                commit_hash=CommitHash("main" + "0" * 36),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        await commit_repo.link_commit_to_branch(1, 1, "main")

        commit_repo.add(
            Commit(
                id=2,
                repository_id=1,
                commit_hash=CommitHash("feat" + "0" * 36),
                author_date=datetime(2025, 1, 2),
                commit_date=datetime(2025, 1, 2),
            )
        )
        await commit_repo.link_commit_to_branch(1, 2, "feature")

        file_repo.add(
            File(
                id=1,
                repository_id=1,
                path="src/main_mod.py",
                content_hash="hash_main",
                size_bytes=100,
                language="python",
            )
        )
        await file_repo.link_file_to_commit(1, 1)

        file_repo.add(
            File(
                id=2,
                repository_id=1,
                path="src/feat_mod.py",
                content_hash="hash_feat",
                size_bytes=100,
                language="python",
            )
        )
        await file_repo.link_file_to_commit(2, 2)

        symbol_repo.add(
            Symbol(
                id=1,
                file_id=1,
                repository_id=1,
                name="MainFunc",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )
        symbol_repo.add(
            Symbol(
                id=2,
                file_id=2,
                repository_id=1,
                name="FeatFunc",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )

        ref_repo.add(
            Reference(
                id=1,
                repository_id=1,
                source_file_id=1,
                source_line=10,
                source_column=0,
                source_end_column=8,
                reference_text="MainFunc",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )
        ref_repo.add(
            Reference(
                id=2,
                repository_id=1,
                source_file_id=2,
                source_line=10,
                source_column=0,
                source_end_column=8,
                reference_text="FeatFunc",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )

        # Resolve with branch=None (default)
        use_case = ResolveReferencesUseCase(reference_repository=ref_repo)
        response = await use_case.execute(
            ResolveReferencesRequest(repository_id=1, branch=None)
        )

        # Both refs resolved
        assert response.resolved_count == 2

    @pytest.mark.asyncio
    async def test_execute_with_progress_accepts_branch(self) -> None:
        """execute_with_progress accepts branch parameter."""
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository(commit_repo=commit_repo)
        symbol_repo = InMemorySymbolRepository(file_repo=file_repo)
        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
        )

        # Minimal setup: one branch with one file+symbol+ref
        commit_repo.add(
            Commit(
                id=1,
                repository_id=1,
                commit_hash=CommitHash("main" + "0" * 36),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        await commit_repo.link_commit_to_branch(1, 1, "main")

        file_repo.add(
            File(
                id=1,
                repository_id=1,
                path="src/mod.py",
                content_hash="hash1",
                size_bytes=100,
                language="python",
            )
        )
        await file_repo.link_file_to_commit(1, 1)

        symbol_repo.add(
            Symbol(
                id=1,
                file_id=1,
                repository_id=1,
                name="Func",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )

        ref_repo.add(
            Reference(
                id=1,
                repository_id=1,
                source_file_id=1,
                source_line=10,
                source_column=0,
                source_end_column=4,
                reference_text="Func",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )

        use_case = ResolveReferencesUseCase(reference_repository=ref_repo)
        response = await use_case.execute_with_progress(
            ResolveReferencesRequest(repository_id=1, branch="main"),
            batch_size=100,
        )

        assert response.resolved_count == 1

    @pytest.mark.asyncio
    async def test_branch_param_uses_repo_wide_symbols(self) -> None:
        """References on a branch resolve to symbols from files outside that branch.

        Regression test for issue #98: symbol pool must be repo-wide, not
        branch-scoped, when resolving branch-scoped references.
        """
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository(commit_repo=commit_repo)
        symbol_repo = InMemorySymbolRepository(file_repo=file_repo)
        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
        )

        # Main branch commit
        commit_repo.add(
            Commit(
                id=1,
                repository_id=1,
                commit_hash=CommitHash("main" + "0" * 36),
                author_date=datetime(2025, 1, 2),
                commit_date=datetime(2025, 1, 2),
            )
        )
        await commit_repo.link_commit_to_branch(1, 1, "main")

        # Feature branch commit (NOT on main)
        commit_repo.add(
            Commit(
                id=2,
                repository_id=1,
                commit_hash=CommitHash("feat" + "0" * 36),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        await commit_repo.link_commit_to_branch(1, 2, "feature")

        # File on main with a reference to "HTTPException"
        file_repo.add(
            File(
                id=1,
                repository_id=1,
                path="src/api.py",
                content_hash="hash_api",
                size_bytes=200,
                language="python",
            )
        )
        await file_repo.link_file_to_commit(1, 1)

        # File on feature with the target symbol (NOT on main)
        file_repo.add(
            File(
                id=2,
                repository_id=1,
                path="lib/exceptions.py",
                content_hash="hash_exc",
                size_bytes=100,
                language="python",
            )
        )
        await file_repo.link_file_to_commit(2, 2)

        # Symbol only on the feature branch's file
        symbol_repo.add(
            Symbol(
                id=1,
                file_id=2,
                repository_id=1,
                name="HTTPException",
                kind=SymbolKind.CLASS,
                start_line=1,
                start_column=0,
                end_line=10,
                end_column=0,
            )
        )

        # Reference on main to HTTPException
        ref_repo.add(
            Reference(
                id=1,
                repository_id=1,
                source_file_id=1,
                source_line=5,
                source_column=10,
                source_end_column=23,
                reference_text="HTTPException",
                reference_type=ReferenceType.USAGE,
                target_symbol_id=None,
            )
        )

        # Resolve scoped to "main" — should find HTTPException from repo-wide pool
        use_case = ResolveReferencesUseCase(reference_repository=ref_repo)
        response = await use_case.execute(
            ResolveReferencesRequest(repository_id=1, branch="main")
        )

        assert response.resolved_count == 1
        ref = await ref_repo.find_by_id(1)
        assert ref is not None
        assert ref.target_symbol_id == 1


class TestStaleFileVersionResolution:
    """Regression test for issue #129: resolution skips stale file versions.

    When incremental indexing accumulates multiple file versions for the
    same path, only references from the latest version should be resolved.
    References from superseded file versions are never shown in the UI and
    processing them wastes time (17m vs 2m on real data).
    """

    @pytest.mark.asyncio
    async def test_only_latest_file_version_refs_resolved(self) -> None:
        """References from old file versions should NOT be resolved."""
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository(commit_repo=commit_repo)
        symbol_repo = InMemorySymbolRepository(file_repo=file_repo)
        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
        )

        # Two commits: older and newer
        commit_repo.add(
            Commit(
                id=1,
                repository_id=1,
                commit_hash=CommitHash("old0" + "0" * 36),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        await commit_repo.link_commit_to_branch(1, 1, "main")

        commit_repo.add(
            Commit(
                id=2,
                repository_id=1,
                commit_hash=CommitHash("new0" + "0" * 36),
                author_date=datetime(2025, 1, 2),
                commit_date=datetime(2025, 1, 2),
            )
        )
        await commit_repo.link_commit_to_branch(1, 2, "main")

        # Two file versions for the SAME path (simulating incremental indexing)
        file_repo.add(
            File(
                id=1,
                repository_id=1,
                path="src/mod.py",
                content_hash="old_hash",
                size_bytes=100,
                language="python",
            )
        )
        await file_repo.link_file_to_commit(1, 1)  # old version

        file_repo.add(
            File(
                id=2,
                repository_id=1,
                path="src/mod.py",
                content_hash="new_hash",
                size_bytes=150,
                language="python",
            )
        )
        await file_repo.link_file_to_commit(2, 2)  # latest version

        # Symbol in the latest file version
        symbol_repo.add(
            Symbol(
                id=1,
                file_id=2,
                repository_id=1,
                name="my_func",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )

        # Reference in the OLD file version (should NOT be resolved)
        ref_repo.add(
            Reference(
                id=1,
                repository_id=1,
                source_file_id=1,  # old file version
                source_line=10,
                source_column=0,
                source_end_column=7,
                reference_text="my_func",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )

        # Reference in the LATEST file version (should be resolved)
        ref_repo.add(
            Reference(
                id=2,
                repository_id=1,
                source_file_id=2,  # latest file version
                source_line=10,
                source_column=0,
                source_end_column=7,
                reference_text="my_func",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )

        use_case = ResolveReferencesUseCase(reference_repository=ref_repo)
        response = await use_case.execute(
            ResolveReferencesRequest(repository_id=1)
        )

        # Only 1 resolved: the reference from the latest file version
        assert response.resolved_count == 1

        # Old file version ref stays unresolved
        old_ref = await ref_repo.find_by_id(1)
        assert old_ref is not None
        assert old_ref.target_symbol_id is None

        # Latest file version ref is resolved
        new_ref = await ref_repo.find_by_id(2)
        assert new_ref is not None
        assert new_ref.target_symbol_id == 1

    @pytest.mark.asyncio
    async def test_count_unresolved_excludes_stale_files(self) -> None:
        """count_unresolved_references should only count refs from latest files."""
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository(commit_repo=commit_repo)
        symbol_repo = InMemorySymbolRepository(file_repo=file_repo)
        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo,
            file_repo=file_repo,
            commit_repo=commit_repo,
        )

        # Two commits
        commit_repo.add(
            Commit(
                id=1,
                repository_id=1,
                commit_hash=CommitHash("old0" + "0" * 36),
                author_date=datetime(2025, 1, 1),
                commit_date=datetime(2025, 1, 1),
            )
        )
        await commit_repo.link_commit_to_branch(1, 1, "main")

        commit_repo.add(
            Commit(
                id=2,
                repository_id=1,
                commit_hash=CommitHash("new0" + "0" * 36),
                author_date=datetime(2025, 1, 2),
                commit_date=datetime(2025, 1, 2),
            )
        )
        await commit_repo.link_commit_to_branch(1, 2, "main")

        # Two versions of same file
        file_repo.add(
            File(
                id=1,
                repository_id=1,
                path="src/mod.py",
                content_hash="old_hash",
                size_bytes=100,
                language="python",
            )
        )
        await file_repo.link_file_to_commit(1, 1)

        file_repo.add(
            File(
                id=2,
                repository_id=1,
                path="src/mod.py",
                content_hash="new_hash",
                size_bytes=150,
                language="python",
            )
        )
        await file_repo.link_file_to_commit(2, 2)

        # Unresolved refs in both old and new file versions
        ref_repo.add(
            Reference(
                id=1,
                repository_id=1,
                source_file_id=1,  # old
                source_line=5,
                source_column=0,
                source_end_column=7,
                reference_text="some_func",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )
        ref_repo.add(
            Reference(
                id=2,
                repository_id=1,
                source_file_id=2,  # latest
                source_line=5,
                source_column=0,
                source_end_column=7,
                reference_text="some_func",
                reference_type=ReferenceType.CALL,
                target_symbol_id=None,
            )
        )

        # Should only count the ref from the latest file version
        count = await ref_repo.count_unresolved_references(repository_id=1)
        assert count == 1
