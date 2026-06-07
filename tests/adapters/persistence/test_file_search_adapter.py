"""Integration tests for PostgresFileSearchRepository."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from inxr2.adapters.persistence.repositories.file_adapter import (
    PostgresFileRepository,
)
from inxr2.adapters.persistence.repositories.file_search_adapter import (
    PostgresFileSearchRepository,
)
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)

from .factories import CommitFactory, FileFactory, RepositoryFactory


@pytest.mark.asyncio
class TestPostgresFileSearchRepositorySearchByName:
    """Tests for search_by_name method."""

    async def test_search_by_name_returns_matching_files(
        self, db_session: AsyncSession
    ) -> None:
        """Test that search_by_name returns files matching the query."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        search_adapter = PostgresFileSearchRepository(db_session)

        repo = await repo_adapter.save(RepositoryFactory.create(name="search-repo"))
        assert repo.id is not None

        commit = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="a" * 40)
        )
        assert commit.id is not None

        # Create various files and link to commit
        for path, chash in [
            ("src/utils.py", "srch_utils_" + "0" * 29),
            ("src/main.py", "srch_main0" + "0" * 30),
            ("tests/test_utils.py", "srch_tutil" + "0" * 30),
            ("README.md", "srch_readm" + "0" * 30),
        ]:
            f = await file_adapter.save(
                FileFactory.create(repository_id=repo.id, path=path, content_hash=chash)
            )
            assert f.id is not None
            await file_adapter.link_file_to_commit(f.id, commit.id)

        # Search for "utils"
        results, total = await search_adapter.search_by_name("utils")

        assert len(results) == 2
        assert total == 2
        paths = {f.path for f in results}
        assert "src/utils.py" in paths
        assert "tests/test_utils.py" in paths

    async def test_search_by_name_is_case_insensitive(
        self, db_session: AsyncSession
    ) -> None:
        """Test that search_by_name is case-insensitive."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        search_adapter = PostgresFileSearchRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="case-insensitive-repo")
        )
        assert repo.id is not None

        commit = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="b" * 40)
        )
        assert commit.id is not None

        f = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/MyClass.py",
                content_hash="case_ins0" + "0" * 31,
            )
        )
        assert f.id is not None
        await file_adapter.link_file_to_commit(f.id, commit.id)

        # Search with different cases
        results_lower, _ = await search_adapter.search_by_name("myclass")
        results_upper, _ = await search_adapter.search_by_name("MYCLASS")
        results_mixed, _ = await search_adapter.search_by_name("MyClass")

        assert len(results_lower) == 1
        assert len(results_upper) == 1
        assert len(results_mixed) == 1

    async def test_search_by_name_filters_by_repository(
        self, db_session: AsyncSession
    ) -> None:
        """Test that search_by_name filters by repository_id."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        search_adapter = PostgresFileSearchRepository(db_session)

        repo1 = await repo_adapter.save(RepositoryFactory.create(name="repo1-search"))
        repo2 = await repo_adapter.save(RepositoryFactory.create(name="repo2-search"))
        assert repo1.id is not None
        assert repo2.id is not None

        commit1 = await commit_adapter.save(
            CommitFactory.create(repository_id=repo1.id, commit_hash="c" * 40)
        )
        commit2 = await commit_adapter.save(
            CommitFactory.create(repository_id=repo2.id, commit_hash="d" * 40)
        )
        assert commit1.id is not None
        assert commit2.id is not None

        f1 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo1.id,
                path="src/config.py",
                content_hash="repo1_cfg" + "0" * 31,
            )
        )
        assert f1.id is not None
        await file_adapter.link_file_to_commit(f1.id, commit1.id)

        f2 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo2.id,
                path="src/config.py",
                content_hash="repo2_cfg" + "0" * 31,
            )
        )
        assert f2.id is not None
        await file_adapter.link_file_to_commit(f2.id, commit2.id)

        # Search within repo1 only
        results, total = await search_adapter.search_by_name(
            "config", repository_id=repo1.id
        )

        assert len(results) == 1
        assert total == 1
        assert results[0].repository_id == repo1.id

    async def test_search_by_name_filters_by_commit(
        self, db_session: AsyncSession
    ) -> None:
        """Test that search_by_name filters by commit_id."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        search_adapter = PostgresFileSearchRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="commit-filter-search-repo")
        )
        assert repo.id is not None

        commit1 = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="e" * 40)
        )
        commit2 = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="f" * 40)
        )
        assert commit1.id is not None
        assert commit2.id is not None

        f1 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/app.py",
                content_hash="commit1ap" + "0" * 31,
            )
        )
        assert f1.id is not None
        await file_adapter.link_file_to_commit(f1.id, commit1.id)

        f2 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/app.py",
                content_hash="commit2ap" + "0" * 31,
            )
        )
        assert f2.id is not None
        await file_adapter.link_file_to_commit(f2.id, commit2.id)

        # Search within commit1 only
        results, total = await search_adapter.search_by_name(
            "app", commit_id=commit1.id
        )

        assert len(results) == 1
        assert total == 1
        assert results[0].id == f1.id

    async def test_search_by_name_filters_by_language(
        self, db_session: AsyncSession
    ) -> None:
        """Test that search_by_name filters by language."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        search_adapter = PostgresFileSearchRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="lang-filter-search-repo")
        )
        assert repo.id is not None

        commit = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="g" * 40)
        )
        assert commit.id is not None

        f_py = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/utils.py",
                content_hash="lang_py00" + "0" * 31,
                language="python",
            )
        )
        assert f_py.id is not None
        await file_adapter.link_file_to_commit(f_py.id, commit.id)

        f_ts = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/utils.ts",
                content_hash="lang_ts00" + "0" * 31,
                language="typescript",
            )
        )
        assert f_ts.id is not None
        await file_adapter.link_file_to_commit(f_ts.id, commit.id)

        # Search for Python files only
        results, _ = await search_adapter.search_by_name("utils", language="python")

        assert len(results) == 1
        assert results[0].path == "src/utils.py"

    async def test_search_by_name_respects_limit(
        self, db_session: AsyncSession
    ) -> None:
        """Test that search_by_name respects the limit parameter."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        search_adapter = PostgresFileSearchRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="limit-search-repo")
        )
        assert repo.id is not None

        commit = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="h" * 40)
        )
        assert commit.id is not None

        # Create many files
        for i in range(10):
            f = await file_adapter.save(
                FileFactory.create(
                    repository_id=repo.id,
                    path=f"src/test_{i}.py",
                    content_hash=f"limit_{i:04d}" + "0" * 30,
                )
            )
            assert f.id is not None
            await file_adapter.link_file_to_commit(f.id, commit.id)

        # Search with limit of 5
        results, total = await search_adapter.search_by_name("test", limit=5)

        assert len(results) == 5
        assert total == 10

    async def test_search_by_name_paginates_with_offset(
        self, db_session: AsyncSession
    ) -> None:
        """Test that offset produces disjoint pages with stable totals."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        search_adapter = PostgresFileSearchRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="offset-search-repo")
        )
        assert repo.id is not None

        commit = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="o" * 40)
        )
        assert commit.id is not None

        for i in range(10):
            f = await file_adapter.save(
                FileFactory.create(
                    repository_id=repo.id,
                    path=f"src/item_{i:02d}.py",
                    content_hash=f"offset{i:04d}" + "0" * 30,
                )
            )
            assert f.id is not None
            await file_adapter.link_file_to_commit(f.id, commit.id)

        page1, total1 = await search_adapter.search_by_name("item", limit=5, offset=0)
        page2, total2 = await search_adapter.search_by_name("item", limit=5, offset=5)

        assert total1 == 10
        assert total2 == 10
        assert len(page1) == 5
        assert len(page2) == 5
        # Pages are disjoint
        page1_ids = {f.id for f in page1}
        page2_ids = {f.id for f in page2}
        assert page1_ids.isdisjoint(page2_ids)

    async def test_search_by_name_orders_by_relevance(
        self, db_session: AsyncSession
    ) -> None:
        """Test that search_by_name orders results by relevance."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        search_adapter = PostgresFileSearchRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="relevance-search-repo")
        )
        assert repo.id is not None

        commit = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="i" * 40)
        )
        assert commit.id is not None

        # Create files with different matching patterns
        # Relevance scoring uses PostgreSQL regex (func.substring with pattern).
        for path, chash in [
            ("src/helpers/config_utils.py", "rel_cfgu0" + "0" * 31),
            ("src/config.py", "rel_cfg00" + "0" * 31),
            ("src/configuration.py", "rel_cfgn0" + "0" * 31),
        ]:
            f = await file_adapter.save(
                FileFactory.create(
                    repository_id=repo.id,
                    path=path,
                    content_hash=chash,
                )
            )
            assert f.id is not None
            await file_adapter.link_file_to_commit(f.id, commit.id)

        results, _ = await search_adapter.search_by_name("config")

        assert len(results) == 3
        # Exact match first, prefix second, contains last
        assert results[0].path == "src/config.py"
        assert results[1].path == "src/configuration.py"
        assert results[2].path == "src/helpers/config_utils.py"

    async def test_search_by_name_returns_empty_for_no_matches(
        self, db_session: AsyncSession
    ) -> None:
        """Test that search_by_name returns empty list when no matches found."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        search_adapter = PostgresFileSearchRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="no-match-search-repo")
        )
        assert repo.id is not None

        commit = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="j" * 40)
        )
        assert commit.id is not None

        f = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/main.py",
                content_hash="no_match0" + "0" * 31,
            )
        )
        assert f.id is not None
        await file_adapter.link_file_to_commit(f.id, commit.id)

        results, total = await search_adapter.search_by_name("nonexistent")

        assert results == []
        assert total == 0

    async def test_search_by_name_deduplicates_without_commit_id(
        self, db_session: AsyncSession
    ) -> None:
        """Test that search_by_name deduplicates by path when no commit_id is specified."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        search_adapter = PostgresFileSearchRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="dedup-search-repo")
        )
        assert repo.id is not None

        commit1 = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="k" * 40)
        )
        commit2 = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="l" * 40)
        )
        assert commit1.id is not None
        assert commit2.id is not None

        # Same file in two commits (different content versions)
        f1 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/service.py",
                content_hash="dedup_v10" + "0" * 31,
            )
        )
        assert f1.id is not None
        await file_adapter.link_file_to_commit(f1.id, commit1.id)

        f2 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/service.py",
                content_hash="dedup_v20" + "0" * 31,
            )
        )
        assert f2.id is not None
        await file_adapter.link_file_to_commit(f2.id, commit2.id)

        # Search without commit filter - should deduplicate
        results, total = await search_adapter.search_by_name(
            "service", repository_id=repo.id
        )

        # Should only return one result (deduplicated)
        assert len(results) == 1
        assert total == 1
        assert results[0].path == "src/service.py"

    async def test_search_by_name_cross_repo_same_path(
        self, db_session: AsyncSession
    ) -> None:
        """Test that cross-repo search returns one file per repo for identical paths.

        When searching without repository_id filter, files with the same path
        in different repositories should NOT be collapsed - each repo should
        have its own entry in the results.
        """
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        search_adapter = PostgresFileSearchRepository(db_session)

        # Create two repositories
        repo1 = await repo_adapter.save(
            RepositoryFactory.create(name="cross-repo-search-1")
        )
        repo2 = await repo_adapter.save(
            RepositoryFactory.create(name="cross-repo-search-2")
        )
        assert repo1.id is not None
        assert repo2.id is not None

        commit1 = await commit_adapter.save(
            CommitFactory.create(repository_id=repo1.id, commit_hash="m" * 40)
        )
        commit2 = await commit_adapter.save(
            CommitFactory.create(repository_id=repo2.id, commit_hash="n" * 40)
        )
        assert commit1.id is not None
        assert commit2.id is not None

        # Create files with identical paths in both repos
        f1 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo1.id,
                path="src/main.py",
                content_hash="cross_r10" + "0" * 31,
            )
        )
        assert f1.id is not None
        await file_adapter.link_file_to_commit(f1.id, commit1.id)

        f2 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo2.id,
                path="src/main.py",
                content_hash="cross_r20" + "0" * 31,
            )
        )
        assert f2.id is not None
        await file_adapter.link_file_to_commit(f2.id, commit2.id)

        # Search globally (no repository filter) - should return both files
        results, total = await search_adapter.search_by_name("main")

        # Should return 2 results - one from each repository
        assert len(results) == 2
        assert total == 2
        repo_ids = {r.repository_id for r in results}
        assert repo_ids == {repo1.id, repo2.id}


@pytest.mark.asyncio
class TestSearchByNameExtensions:
    """Extension-filter branch permutations for search_by_name."""

    async def _setup(self, db_session: AsyncSession) -> tuple[int, int]:
        from inxr2.domain.entities import File

        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

        repo = await repo_adapter.save(RepositoryFactory.create(name="ext-repo"))
        assert repo.id is not None
        commit = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="e" * 40)
        )
        assert commit.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, commit.id, "main")

        for path, ext, chash in [
            ("src/widget.py", ".py", "ext_py0000" + "0" * 30),
            ("src/widget.ts", ".ts", "ext_ts0000" + "0" * 30),
            ("widget_makefile", None, "ext_none00" + "0" * 30),
        ]:
            f = await file_adapter.save(
                File(
                    repository_id=repo.id,
                    path=path,
                    content_hash=chash,
                    size_bytes=10,
                    language="python",
                    extension=ext,
                )
            )
            assert f.id is not None
            await file_adapter.link_file_to_commit(f.id, commit.id)
        await db_session.commit()
        return repo.id, commit.id

    async def test_real_and_none_extensions(self, db_session: AsyncSession) -> None:
        repo_id, _ = await self._setup(db_session)
        adapter = PostgresFileSearchRepository(db_session)
        results, total = await adapter.search_by_name(
            "widget", repository_id=repo_id, extensions=[".py", "(none)"]
        )
        paths = {f.path for f in results}
        assert total == 2
        assert paths == {"src/widget.py", "widget_makefile"}

    async def test_only_none_extension(self, db_session: AsyncSession) -> None:
        repo_id, _ = await self._setup(db_session)
        adapter = PostgresFileSearchRepository(db_session)
        results, total = await adapter.search_by_name(
            "widget", repository_id=repo_id, extensions=["(none)"]
        )
        assert total == 1
        assert results[0].path == "widget_makefile"

    async def test_only_real_extensions(self, db_session: AsyncSession) -> None:
        repo_id, _ = await self._setup(db_session)
        adapter = PostgresFileSearchRepository(db_session)
        results, total = await adapter.search_by_name(
            "widget", repository_id=repo_id, extensions=[".ts"]
        )
        assert total == 1
        assert results[0].path == "src/widget.ts"


@pytest.mark.asyncio
class TestGetDistinctExtensions:
    """Branch permutations for get_distinct_extensions."""

    async def _setup(self, db_session: AsyncSession) -> tuple[int, int]:
        from inxr2.domain.entities import File

        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

        repo = await repo_adapter.save(RepositoryFactory.create(name="distinct-repo"))
        assert repo.id is not None
        commit = await commit_adapter.save(
            CommitFactory.create(repository_id=repo.id, commit_hash="d" * 40)
        )
        assert commit.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, commit.id, "main")

        for path, ext, chash in [
            ("a.py", ".py", "dist_py000" + "0" * 30),
            ("b.ts", ".ts", "dist_ts000" + "0" * 30),
            ("Makefile", None, "dist_none0" + "0" * 30),
        ]:
            f = await file_adapter.save(
                File(
                    repository_id=repo.id,
                    path=path,
                    content_hash=chash,
                    size_bytes=10,
                    language="python",
                    extension=ext,
                )
            )
            assert f.id is not None
            await file_adapter.link_file_to_commit(f.id, commit.id)
        await db_session.commit()
        return repo.id, commit.id

    async def test_by_repository_and_branch(self, db_session: AsyncSession) -> None:
        repo_id, _ = await self._setup(db_session)
        adapter = PostgresFileSearchRepository(db_session)
        exts = await adapter.get_distinct_extensions(
            repository_id=repo_id, branch="main"
        )
        # "(none)" sentinel is prepended because Makefile has no extension.
        assert exts[0] == "(none)"
        assert ".py" in exts and ".ts" in exts

    async def test_by_repository_without_branch(self, db_session: AsyncSession) -> None:
        repo_id, _ = await self._setup(db_session)
        adapter = PostgresFileSearchRepository(db_session)
        exts = await adapter.get_distinct_extensions(repository_id=repo_id)
        assert ".py" in exts and ".ts" in exts

    async def test_latest_scope(self, db_session: AsyncSession) -> None:
        repo_id, _ = await self._setup(db_session)
        adapter = PostgresFileSearchRepository(db_session)
        exts = await adapter.get_distinct_extensions(scope="latest")
        assert ".py" in exts and ".ts" in exts

    async def test_no_repo_no_scope(self, db_session: AsyncSession) -> None:
        repo_id, _ = await self._setup(db_session)
        adapter = PostgresFileSearchRepository(db_session)
        exts = await adapter.get_distinct_extensions()
        assert ".py" in exts and ".ts" in exts
