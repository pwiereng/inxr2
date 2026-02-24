"""Tests for GetAllRepositoryStatsUseCase."""

from datetime import datetime

import pytest

from inxr2.application.use_cases.repositories import GetAllRepositoryStatsUseCase
from inxr2.domain.entities import Commit, File, Reference, Repository, Symbol
from inxr2.domain.value_objects import CommitHash, ReferenceType, SymbolKind
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryFileVersionRepository,
    InMemoryReferenceRepository,
    InMemoryRepositoryRepository,
    InMemorySymbolRepository,
)


class TestGetAllRepositoryStatsUseCase:
    """Tests for batch repository stats retrieval."""

    @pytest.mark.asyncio
    async def test_returns_stats_for_all_repositories(self) -> None:
        """Should return one stats entry per repository."""
        repo_repo = InMemoryRepositoryRepository()
        repo_repo.add(Repository(id=1, name="repo-a", url="/a", default_branch="main"))
        repo_repo.add(Repository(id=2, name="repo-b", url="/b", default_branch="main"))

        commit_repo = InMemoryCommitRepository()
        c1 = Commit(
            id=1,
            repository_id=1,
            commit_hash=CommitHash("a" * 40),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        commit_repo.add(c1)
        commit_repo._branch_commits[(1, "main", 1)] = True

        c2 = Commit(
            id=2,
            repository_id=2,
            commit_hash=CommitHash("b" * 40),
            author_date=datetime(2025, 2, 1),
            commit_date=datetime(2025, 2, 1),
        )
        commit_repo.add(c2)
        commit_repo._branch_commits[(2, "main", 2)] = True

        file_repo = InMemoryFileRepository(commit_repo=commit_repo)
        # _commit_files tuples are (commit_id, file_id)
        file_repo.add(
            File(
                id=1,
                repository_id=1,
                path="main.py",
                content_hash="h1",
                size_bytes=100,
                language="Python",
                line_count=50,
            )
        )
        file_repo._commit_files.add((1, 1))
        file_repo.add(
            File(
                id=2,
                repository_id=2,
                path="app.ts",
                content_hash="h2",
                size_bytes=200,
                language="TypeScript",
                line_count=80,
            )
        )
        file_repo._commit_files.add((2, 2))

        symbol_repo = InMemorySymbolRepository()
        symbol_repo.add(
            Symbol(
                id=1,
                file_id=1,
                repository_id=1,
                name="func",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )

        reference_repo = InMemoryReferenceRepository()
        reference_repo.add(
            Reference(
                id=1,
                repository_id=1,
                source_file_id=1,
                source_line=3,
                source_column=0,
                source_end_column=4,
                reference_text="func",
                reference_type=ReferenceType.CALL,
                target_symbol_id=1,
            )
        )

        file_version_repo = InMemoryFileVersionRepository(file_repo)
        use_case = GetAllRepositoryStatsUseCase(
            repository_repo=repo_repo,
            file_repo=file_repo,
            file_version_repo=file_version_repo,
            symbol_repo=symbol_repo,
            reference_repo=reference_repo,
            commit_repo=commit_repo,
        )

        result = await use_case.execute()

        assert len(result) == 2
        by_id = {s.repository_id: s for s in result}
        assert by_id[1].name == "repo-a"
        assert by_id[1].total_files == 1
        assert by_id[1].total_symbols == 1
        assert by_id[1].total_lines == 50
        assert by_id[1].total_references_resolved == 1
        assert by_id[1].commit_date_earliest == datetime(2025, 1, 1)

        assert by_id[2].name == "repo-b"
        assert by_id[2].total_files == 1
        assert by_id[2].total_lines == 80

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_repositories(self) -> None:
        """Should return empty list when there are no repositories."""
        file_repo = InMemoryFileRepository()
        file_version_repo = InMemoryFileVersionRepository(file_repo)
        use_case = GetAllRepositoryStatsUseCase(
            repository_repo=InMemoryRepositoryRepository(),
            file_repo=file_repo,
            file_version_repo=file_version_repo,
            symbol_repo=InMemorySymbolRepository(),
            reference_repo=InMemoryReferenceRepository(),
            commit_repo=InMemoryCommitRepository(),
        )

        result = await use_case.execute()

        assert result == []

    @pytest.mark.asyncio
    async def test_each_stat_has_all_new_fields(self) -> None:
        """Each stats result should contain all expected fields."""
        repo_repo = InMemoryRepositoryRepository()
        repo_repo.add(Repository(id=1, name="repo-x", url="/x", default_branch="main"))

        file_repo = InMemoryFileRepository()
        file_version_repo = InMemoryFileVersionRepository(file_repo)
        use_case = GetAllRepositoryStatsUseCase(
            repository_repo=repo_repo,
            file_repo=file_repo,
            file_version_repo=file_version_repo,
            symbol_repo=InMemorySymbolRepository(),
            reference_repo=InMemoryReferenceRepository(),
            commit_repo=InMemoryCommitRepository(),
        )

        result = await use_case.execute()

        assert len(result) == 1
        stats = result[0]
        assert stats.total_lines == 0
        assert stats.total_references_resolved == 0
        assert stats.total_references_unresolved == 0
        assert stats.commit_date_earliest is None
        assert stats.commit_date_latest is None
