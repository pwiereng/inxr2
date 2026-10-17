"""Tests for FindDeadCodeUseCase (issue #548)."""

from datetime import datetime

import pytest

from inxr2.application.use_cases.symbols import (
    FindDeadCodeRequest,
    FindDeadCodeUseCase,
)
from inxr2.domain.entities import Commit, File, Reference, Symbol
from inxr2.domain.value_objects import CommitHash, ReferenceType, SymbolKind
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryReferenceRepository,
    InMemorySymbolRepository,
)


def _symbol(
    symbol_id: int,
    file_id: int,
    name: str,
    line: int = 1,
    kind: SymbolKind = SymbolKind.FUNCTION,
) -> Symbol:
    return Symbol(
        id=symbol_id,
        repository_id=1,
        file_id=file_id,
        name=name,
        kind=kind,
        start_line=line,
        start_column=0,
        end_line=line + 1,
        end_column=0,
    )


def _reference(file_id: int, text: str) -> Reference:
    return Reference(
        repository_id=1,
        source_file_id=file_id,
        source_line=1,
        source_column=0,
        source_end_column=len(text),
        reference_text=text,
        reference_type=ReferenceType.CALL,
    )


class TestFindDeadCodeUseCase:
    @pytest.fixture
    async def use_case(self) -> FindDeadCodeUseCase:
        commit_repo = InMemoryCommitRepository()
        commit_repo._commits[1] = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("abc123def456"),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        file_repo = InMemoryFileRepository(commit_repo=commit_repo)
        for file_id, path in ((1, "src/main.py"), (2, "src/utils.py")):
            file_repo.add(
                File(
                    id=file_id,
                    repository_id=1,
                    path=path,
                    content_hash=f"hash{file_id}",
                    size_bytes=100,
                    language="python",
                )
            )
        symbol_repo = InMemorySymbolRepository(file_repo=file_repo)
        await symbol_repo.save(_symbol(1, 1, "main"))
        await symbol_repo.save(_symbol(2, 2, "helper", line=3))
        await symbol_repo.save(_symbol(3, 2, "unused", line=9))
        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo, file_repo=file_repo, commit_repo=commit_repo
        )
        await ref_repo.save(_reference(1, "helper"))
        return FindDeadCodeUseCase(
            reference_repo=ref_repo, file_repo=file_repo, commit_repo=commit_repo
        )

    async def test_returns_unreferenced_symbols_with_paths_and_coverage(
        self, use_case: FindDeadCodeUseCase
    ) -> None:
        result = await use_case.execute(FindDeadCodeRequest(repository_id=1))

        assert [(s.symbol.name, s.file_path) for s in result.symbols] == [
            ("main", "src/main.py"),
            ("unused", "src/utils.py"),
        ]
        assert result.total == 2
        assert result.scanned == 3
        assert result.entry_points_excluded == 0

    async def test_pages_results(self, use_case: FindDeadCodeUseCase) -> None:
        result = await use_case.execute(
            FindDeadCodeRequest(repository_id=1, limit=1, offset=1)
        )

        assert [s.symbol.name for s in result.symbols] == ["unused"]
        assert result.total == 2
        assert (result.limit, result.offset) == (1, 1)

    async def test_unknown_commit_hash_raises(
        self, use_case: FindDeadCodeUseCase
    ) -> None:
        with pytest.raises(ValueError, match="not found"):
            await use_case.execute(
                FindDeadCodeRequest(repository_id=1, commit_hash="deadbeef")
            )

    async def test_commit_hash_scopes_to_that_commit(
        self, use_case: FindDeadCodeUseCase
    ) -> None:
        # No file is linked to commit abc123 → nothing in scope
        result = await use_case.execute(
            FindDeadCodeRequest(repository_id=1, commit_hash="abc123def456")
        )

        assert result.symbols == []
        assert result.scanned == 0


class TestFindDeadCodeFilters:
    """kind and branch reach the repository scan (PR #558 review)."""

    @pytest.fixture
    async def use_case(self) -> FindDeadCodeUseCase:
        """main has main.py + utils.py; feature's head has utils.py only."""
        commit_repo = InMemoryCommitRepository()
        for commit_id, branch in ((1, "main"), (2, "feature")):
            commit_repo._commits[commit_id] = Commit(
                id=commit_id,
                repository_id=1,
                commit_hash=CommitHash(f"{commit_id}" * 12),
                author_date=datetime(2025, 1, commit_id),
                commit_date=datetime(2025, 1, commit_id),
            )
            await commit_repo.link_commit_to_branch(1, commit_id, branch)
        file_repo = InMemoryFileRepository(commit_repo=commit_repo)
        for file_id, path in ((1, "src/main.py"), (2, "src/utils.py")):
            file_repo.add(
                File(
                    id=file_id,
                    repository_id=1,
                    path=path,
                    content_hash=f"hash{file_id}",
                    size_bytes=100,
                    language="python",
                )
            )
        await file_repo.link_file_to_commit(1, 1)
        await file_repo.link_file_to_commit(2, 1)
        await file_repo.link_file_to_commit(2, 2)
        symbol_repo = InMemorySymbolRepository(file_repo=file_repo)
        await symbol_repo.save(_symbol(1, 1, "main"))
        await symbol_repo.save(_symbol(2, 2, "helper", line=3))
        await symbol_repo.save(_symbol(3, 2, "Widget", line=9, kind=SymbolKind.CLASS))
        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo, file_repo=file_repo, commit_repo=commit_repo
        )
        await ref_repo.save(_reference(1, "helper"))
        return FindDeadCodeUseCase(
            reference_repo=ref_repo, file_repo=file_repo, commit_repo=commit_repo
        )

    async def test_kind_is_passed_to_the_scan(
        self, use_case: FindDeadCodeUseCase
    ) -> None:
        result = await use_case.execute(
            FindDeadCodeRequest(repository_id=1, kind="class")
        )

        assert [s.symbol.name for s in result.symbols] == ["Widget"]
        assert result.scanned == 1

    async def test_branch_is_passed_to_the_scan(
        self, use_case: FindDeadCodeUseCase
    ) -> None:
        on_main = await use_case.execute(FindDeadCodeRequest(repository_id=1))
        on_feature = await use_case.execute(
            FindDeadCodeRequest(repository_id=1, branch="feature")
        )

        assert [s.symbol.name for s in on_main.symbols] == ["main", "Widget"]
        # helper's only caller (main.py) is not on feature
        assert [s.symbol.name for s in on_feature.symbols] == ["helper", "Widget"]
