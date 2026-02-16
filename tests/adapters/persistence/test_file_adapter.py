"""Integration tests for PostgresFileRepository."""

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

from .factories import CommitFactory, FileFactory, RepositoryFactory


@pytest.mark.asyncio
class TestPostgresFileRepositoryVersions:
    """Tests for file version listing with branch filtering."""

    async def test_list_versions_by_path_returns_all_versions(
        self, db_session: AsyncSession
    ) -> None:
        """Test listing all versions of a file across commits."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

        # Create repository
        repo = await repo_adapter.save(RepositoryFactory.create(name="versions-repo"))
        assert repo.id is not None

        # Create commits with different dates
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

        commit3 = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="c" * 40,
                commit_date=now,
            )
        )
        assert commit3.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, commit3.id, "main")

        # Create file at each commit
        f1 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/test.py",
                content_hash="h1" + "0" * 38,
            )
        )
        assert f1.id is not None
        await file_adapter.link_file_to_commit(f1.id, commit1.id)

        f2 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/test.py",
                content_hash="h2" + "0" * 38,
            )
        )
        assert f2.id is not None
        await file_adapter.link_file_to_commit(f2.id, commit2.id)

        f3 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/test.py",
                content_hash="h3" + "0" * 38,
            )
        )
        assert f3.id is not None
        await file_adapter.link_file_to_commit(f3.id, commit3.id)

        # List all versions
        versions = await file_adapter.list_versions_by_path(repo.id, "src/test.py")

        assert len(versions) == 3
        # Should be ordered by commit date descending (newest first)
        assert versions[0].content_hash == "h3" + "0" * 38
        assert versions[1].content_hash == "h2" + "0" * 38
        assert versions[2].content_hash == "h1" + "0" * 38

    async def test_list_versions_by_path_filters_by_branch(
        self, db_session: AsyncSession
    ) -> None:
        """Test that list_versions_by_path filters by branch."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="branch-versions-repo")
        )
        assert repo.id is not None

        now = datetime.now(UTC).replace(tzinfo=None)
        # Create commits on different branches
        main_commit = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="d" * 40,
                commit_date=now - timedelta(hours=1),
            )
        )
        assert main_commit.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, main_commit.id, "main")

        feature_commit = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="e" * 40,
                commit_date=now,
            )
        )
        assert feature_commit.id is not None
        await commit_adapter.link_commit_to_branch(
            repo.id, feature_commit.id, "feature"
        )

        # Create same file on both branches
        main_file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/app.py",
                content_hash="main" + "0" * 36,
            )
        )
        assert main_file.id is not None
        await file_adapter.link_file_to_commit(main_file.id, main_commit.id)

        feat_file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/app.py",
                content_hash="feat" + "0" * 36,
            )
        )
        assert feat_file.id is not None
        await file_adapter.link_file_to_commit(feat_file.id, feature_commit.id)

        # List all versions (no branch filter)
        all_versions = await file_adapter.list_versions_by_path(repo.id, "src/app.py")
        assert len(all_versions) == 2

        # List only main branch versions
        main_versions = await file_adapter.list_versions_by_path(
            repo.id, "src/app.py", branch="main"
        )
        assert len(main_versions) == 1
        assert main_versions[0].content_hash == "main" + "0" * 36

        # List only feature branch versions
        feature_versions = await file_adapter.list_versions_by_path(
            repo.id, "src/app.py", branch="feature"
        )
        assert len(feature_versions) == 1
        assert feature_versions[0].content_hash == "feat" + "0" * 36

    async def test_list_versions_by_path_returns_empty_for_unknown_branch(
        self, db_session: AsyncSession
    ) -> None:
        """Test that filtering by non-existent branch returns empty list."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="empty-branch-repo")
        )
        assert repo.id is not None

        commit = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="f" * 40,
            )
        )
        assert commit.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, commit.id, "main")

        file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/file.py",
            )
        )
        assert file.id is not None
        await file_adapter.link_file_to_commit(file.id, commit.id)

        # Filter by non-existent branch
        versions = await file_adapter.list_versions_by_path(
            repo.id, "src/file.py", branch="nonexistent"
        )

        assert versions == []

    async def test_list_versions_preserves_order_with_branch_filter(
        self, db_session: AsyncSession
    ) -> None:
        """Test that branch-filtered versions maintain correct ordering."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="order-branch-repo")
        )
        assert repo.id is not None

        now = datetime.now(UTC).replace(tzinfo=None)
        # Create multiple commits on main branch
        commits = []
        for i in range(3):
            commit = await commit_adapter.save(
                CommitFactory.create(
                    repository_id=repo.id,
                    commit_hash=str(i) * 40,
                    commit_date=now - timedelta(hours=3 - i),
                )
            )
            assert commit.id is not None
            await commit_adapter.link_commit_to_branch(repo.id, commit.id, "main")
            commits.append(commit)

        # Create files in different order than commits
        # Extract commit IDs with assertions for type narrowing
        commit0_id = commits[0].id
        commit1_id = commits[1].id
        commit2_id = commits[2].id
        assert commit0_id is not None
        assert commit1_id is not None
        assert commit2_id is not None

        fv2 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/order.py",
                content_hash="v2" + "0" * 38,
            )
        )
        assert fv2.id is not None
        await file_adapter.link_file_to_commit(fv2.id, commit1_id)

        fv1 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/order.py",
                content_hash="v1" + "0" * 38,
            )
        )
        assert fv1.id is not None
        await file_adapter.link_file_to_commit(fv1.id, commit0_id)

        fv3 = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/order.py",
                content_hash="v3" + "0" * 38,
            )
        )
        assert fv3.id is not None
        await file_adapter.link_file_to_commit(fv3.id, commit2_id)

        # Versions should be ordered by commit date (newest first)
        versions = await file_adapter.list_versions_by_path(
            repo.id, "src/order.py", branch="main"
        )

        assert len(versions) == 3
        assert versions[0].content_hash == "v3" + "0" * 38  # newest
        assert versions[1].content_hash == "v2" + "0" * 38
        assert versions[2].content_hash == "v1" + "0" * 38  # oldest


@pytest.mark.asyncio
class TestPostgresFileRepositoryLatestByBranch:
    """Tests for list_latest_by_branch method."""

    async def test_list_latest_by_branch_returns_latest_version_of_each_file(
        self, db_session: AsyncSession
    ) -> None:
        """Test that list_latest_by_branch returns only the most recent version of each file."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="latest-by-branch-repo")
        )
        assert repo.id is not None

        now = datetime.now(UTC).replace(tzinfo=None)

        # Create commits at different times
        old_commit = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="old" + "0" * 37,
                commit_date=now - timedelta(hours=2),
            )
        )
        assert old_commit.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, old_commit.id, "main")

        new_commit = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="new" + "0" * 37,
                commit_date=now,
            )
        )
        assert new_commit.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, new_commit.id, "main")

        # Create file.py at both commits (file modified)
        old_file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/file.py",
                content_hash="old_content" + "0" * 29,
            )
        )
        assert old_file.id is not None
        await file_adapter.link_file_to_commit(old_file.id, old_commit.id)

        new_file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/file.py",
                content_hash="new_content" + "0" * 29,
            )
        )
        assert new_file.id is not None
        await file_adapter.link_file_to_commit(new_file.id, new_commit.id)

        # Create another_file.py at both commits (unchanged across commits)
        # In full-snapshot indexing, every commit links to all files in the tree
        another_file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/another_file.py",
                content_hash="unchanged" + "0" * 31,
            )
        )
        assert another_file.id is not None
        await file_adapter.link_file_to_commit(another_file.id, old_commit.id)
        await file_adapter.link_file_to_commit(another_file.id, new_commit.id)

        # Get latest files on main branch
        files = await file_adapter.list_latest_by_branch(repo.id, "main")

        # Should have 2 files (latest version of each)
        assert len(files) == 2

        # Sort by path for predictable assertions
        files_by_path = {f.path: f for f in files}

        # file.py should have the newer content
        assert files_by_path["src/file.py"].content_hash == "new_content" + "0" * 29

        # another_file.py should still be present (from old commit)
        assert (
            files_by_path["src/another_file.py"].content_hash == "unchanged" + "0" * 31
        )

    async def test_list_latest_by_branch_filters_by_branch(
        self, db_session: AsyncSession
    ) -> None:
        """Test that list_latest_by_branch only returns files from the specified branch."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="branch-filter-repo")
        )
        assert repo.id is not None

        now = datetime.now(UTC).replace(tzinfo=None)

        # Create commit on main branch
        main_commit = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="main" + "0" * 36,
                commit_date=now,
            )
        )
        assert main_commit.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, main_commit.id, "main")

        # Create commit on feature branch
        feature_commit = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="feat" + "0" * 36,
                commit_date=now,
            )
        )
        assert feature_commit.id is not None
        await commit_adapter.link_commit_to_branch(
            repo.id, feature_commit.id, "feature"
        )

        # Create files on each branch
        main_file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/main_only.py",
                content_hash="main_only" + "0" * 31,
            )
        )
        assert main_file.id is not None
        await file_adapter.link_file_to_commit(main_file.id, main_commit.id)

        feature_file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/feature_only.py",
                content_hash="feat_only" + "0" * 31,
            )
        )
        assert feature_file.id is not None
        await file_adapter.link_file_to_commit(feature_file.id, feature_commit.id)

        # Get files on main branch
        main_files = await file_adapter.list_latest_by_branch(repo.id, "main")
        assert len(main_files) == 1
        assert main_files[0].path == "src/main_only.py"

        # Get files on feature branch
        feature_files = await file_adapter.list_latest_by_branch(repo.id, "feature")
        assert len(feature_files) == 1
        assert feature_files[0].path == "src/feature_only.py"

    async def test_list_latest_by_branch_returns_empty_for_unknown_branch(
        self, db_session: AsyncSession
    ) -> None:
        """Test that list_latest_by_branch returns empty list for non-existent branch."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="unknown-branch-repo")
        )
        assert repo.id is not None

        commit = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="test" + "0" * 36,
            )
        )
        assert commit.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, commit.id, "main")

        file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/test.py",
                content_hash="unknown_br" + "0" * 30,
            )
        )
        assert file.id is not None
        await file_adapter.link_file_to_commit(file.id, commit.id)

        # Get files on non-existent branch
        files = await file_adapter.list_latest_by_branch(repo.id, "nonexistent")
        assert files == []

    async def test_list_latest_by_branch_handles_shared_commits(
        self, db_session: AsyncSession
    ) -> None:
        """Test that files from commits shared between branches are included correctly."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="shared-commit-repo")
        )
        assert repo.id is not None

        now = datetime.now(UTC).replace(tzinfo=None)

        # Create a commit that's on both branches (like a merge base)
        shared_commit = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="shared" + "0" * 34,
                commit_date=now - timedelta(hours=1),
            )
        )
        assert shared_commit.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, shared_commit.id, "main")
        await commit_adapter.link_commit_to_branch(repo.id, shared_commit.id, "feature")

        # Create a file at the shared commit
        shared_file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="src/shared.py",
                content_hash="shared_f" + "0" * 32,
            )
        )
        assert shared_file.id is not None
        await file_adapter.link_file_to_commit(shared_file.id, shared_commit.id)

        # Both branches should see the file
        main_files = await file_adapter.list_latest_by_branch(repo.id, "main")
        feature_files = await file_adapter.list_latest_by_branch(repo.id, "feature")

        assert len(main_files) == 1
        assert len(feature_files) == 1
        assert main_files[0].path == "src/shared.py"
        assert feature_files[0].path == "src/shared.py"


@pytest.mark.asyncio
class TestPostgresFileRepositorySearchByName:
    """Tests for search_by_name method."""

    async def test_search_by_name_returns_matching_files(
        self, db_session: AsyncSession
    ) -> None:
        """Test that search_by_name returns files matching the query."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

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
        results = await file_adapter.search_by_name("utils")

        assert len(results) == 2
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
        results_lower = await file_adapter.search_by_name("myclass")
        results_upper = await file_adapter.search_by_name("MYCLASS")
        results_mixed = await file_adapter.search_by_name("MyClass")

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
        results = await file_adapter.search_by_name("config", repository_id=repo1.id)

        assert len(results) == 1
        assert results[0].repository_id == repo1.id

    async def test_search_by_name_filters_by_commit(
        self, db_session: AsyncSession
    ) -> None:
        """Test that search_by_name filters by commit_id."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

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
        results = await file_adapter.search_by_name("app", commit_id=commit1.id)

        assert len(results) == 1
        assert results[0].id == f1.id

    async def test_search_by_name_filters_by_language(
        self, db_session: AsyncSession
    ) -> None:
        """Test that search_by_name filters by language."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

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
        results = await file_adapter.search_by_name("utils", language="python")

        assert len(results) == 1
        assert results[0].path == "src/utils.py"

    async def test_search_by_name_respects_limit(
        self, db_session: AsyncSession
    ) -> None:
        """Test that search_by_name respects the limit parameter."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

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
        results = await file_adapter.search_by_name("test", limit=5)

        assert len(results) == 5

    async def test_search_by_name_orders_by_relevance(
        self, db_session: AsyncSession
    ) -> None:
        """Test that search_by_name orders results by relevance."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

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

        results = await file_adapter.search_by_name("config")

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

        results = await file_adapter.search_by_name("nonexistent")

        assert results == []

    async def test_search_by_name_deduplicates_without_commit_id(
        self, db_session: AsyncSession
    ) -> None:
        """Test that search_by_name deduplicates by path when no commit_id is specified."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

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
        results = await file_adapter.search_by_name("service", repository_id=repo.id)

        # Should only return one result (deduplicated)
        assert len(results) == 1
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
        results = await file_adapter.search_by_name("main")

        # Should return 2 results - one from each repository
        assert len(results) == 2
        repo_ids = {r.repository_id for r in results}
        assert repo_ids == {repo1.id, repo2.id}
