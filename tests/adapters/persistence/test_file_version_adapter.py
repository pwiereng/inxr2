"""Integration tests for PostgresFileVersionRepository."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from inxr2.adapters.persistence.repositories.file_adapter import (
    PostgresFileRepository,
)
from inxr2.adapters.persistence.repositories.file_version_adapter import (
    PostgresFileVersionRepository,
)
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)

from .factories import CommitFactory, FileFactory, RepositoryFactory


@pytest.mark.asyncio
class TestPostgresFileVersionRepositoryVersions:
    """Tests for file version listing with branch filtering."""

    async def test_list_versions_by_path_returns_all_versions(
        self, db_session: AsyncSession
    ) -> None:
        """Test listing all versions of a file across commits."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        version_adapter = PostgresFileVersionRepository(db_session)

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
        versions = await version_adapter.list_versions_by_path(repo.id, "src/test.py")

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
        version_adapter = PostgresFileVersionRepository(db_session)

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
        all_versions = await version_adapter.list_versions_by_path(
            repo.id, "src/app.py"
        )
        assert len(all_versions) == 2

        # List only main branch versions
        main_versions = await version_adapter.list_versions_by_path(
            repo.id, "src/app.py", branch="main"
        )
        assert len(main_versions) == 1
        assert main_versions[0].content_hash == "main" + "0" * 36

        # List only feature branch versions
        feature_versions = await version_adapter.list_versions_by_path(
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
        version_adapter = PostgresFileVersionRepository(db_session)

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
        versions = await version_adapter.list_versions_by_path(
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
        version_adapter = PostgresFileVersionRepository(db_session)

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
        versions = await version_adapter.list_versions_by_path(
            repo.id, "src/order.py", branch="main"
        )

        assert len(versions) == 3
        assert versions[0].content_hash == "v3" + "0" * 38  # newest
        assert versions[1].content_hash == "v2" + "0" * 38
        assert versions[2].content_hash == "v1" + "0" * 38  # oldest


@pytest.mark.asyncio
class TestPostgresFileVersionRepositoryLatestByBranch:
    """Tests for list_latest_by_branch method."""

    async def test_list_latest_by_branch_returns_latest_version_of_each_file(
        self, db_session: AsyncSession
    ) -> None:
        """Test that list_latest_by_branch returns only the most recent version of each file."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        version_adapter = PostgresFileVersionRepository(db_session)

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
        files = await version_adapter.list_latest_by_branch(repo.id, "main")

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
        version_adapter = PostgresFileVersionRepository(db_session)

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
        main_files = await version_adapter.list_latest_by_branch(repo.id, "main")
        assert len(main_files) == 1
        assert main_files[0].path == "src/main_only.py"

        # Get files on feature branch
        feature_files = await version_adapter.list_latest_by_branch(repo.id, "feature")
        assert len(feature_files) == 1
        assert feature_files[0].path == "src/feature_only.py"

    async def test_list_latest_by_branch_returns_empty_for_unknown_branch(
        self, db_session: AsyncSession
    ) -> None:
        """Test that list_latest_by_branch returns empty list for non-existent branch."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        version_adapter = PostgresFileVersionRepository(db_session)

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
        files = await version_adapter.list_latest_by_branch(repo.id, "nonexistent")
        assert files == []

    async def test_list_latest_by_branch_handles_shared_commits(
        self, db_session: AsyncSession
    ) -> None:
        """Test that files from commits shared between branches are included correctly."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        version_adapter = PostgresFileVersionRepository(db_session)

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
        main_files = await version_adapter.list_latest_by_branch(repo.id, "main")
        feature_files = await version_adapter.list_latest_by_branch(repo.id, "feature")

        assert len(main_files) == 1
        assert len(feature_files) == 1
        assert main_files[0].path == "src/shared.py"
        assert feature_files[0].path == "src/shared.py"


@pytest.mark.asyncio
class TestFileVersionDedupByContentHash:
    """Regression tests: dedup by content_hash should return distinct content hashes."""

    async def test_same_hash_across_three_commits_returns_one_version(
        self, db_session: AsyncSession
    ) -> None:
        """One file row linked to 3 commits → 1 deduped version for that content hash."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        version_adapter = PostgresFileVersionRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="dedup-oldest-repo")
        )
        assert repo.id is not None

        now = datetime.now(UTC).replace(tzinfo=None)

        # 3 commits at different dates
        c1 = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="1" * 40,
                commit_date=now - timedelta(days=30),
            )
        )
        assert c1.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, c1.id, "main")

        c2 = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="2" * 40,
                commit_date=now - timedelta(days=15),
            )
        )
        assert c2.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, c2.id, "main")

        c3 = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="3" * 40,
                commit_date=now,
            )
        )
        assert c3.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, c3.id, "main")

        # One file row (same content_hash) linked to all 3 commits
        f = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="docs/schema.md",
                content_hash="same" + "0" * 36,
            )
        )
        assert f.id is not None
        await file_adapter.link_file_to_commit(f.id, c1.id)
        await file_adapter.link_file_to_commit(f.id, c2.id)
        await file_adapter.link_file_to_commit(f.id, c3.id)

        versions = await version_adapter.list_versions_by_path(
            repo.id, "docs/schema.md", branch="main"
        )

        # Should deduplicate to 1 version
        assert len(versions) == 1
        assert versions[0].content_hash == "same" + "0" * 36

    async def test_two_hashes_returns_two_versions_oldest_first_hash(
        self, db_session: AsyncSession
    ) -> None:
        """2 commits with hash A, then 1 commit with hash B → 2 versions.
        Hash A version should be linked to the oldest commit."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)
        version_adapter = PostgresFileVersionRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="dedup-two-hash-repo")
        )
        assert repo.id is not None

        now = datetime.now(UTC).replace(tzinfo=None)

        # 3 commits
        c1 = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="a1" + "0" * 38,
                commit_date=now - timedelta(days=30),
            )
        )
        assert c1.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, c1.id, "main")

        c2 = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="a2" + "0" * 38,
                commit_date=now - timedelta(days=15),
            )
        )
        assert c2.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, c2.id, "main")

        c3 = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="a3" + "0" * 38,
                commit_date=now,
            )
        )
        assert c3.id is not None
        await commit_adapter.link_commit_to_branch(repo.id, c3.id, "main")

        # File with hash_a linked to c1 and c2 (unchanged across those)
        fa = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="docs/readme.md",
                content_hash="hash_a" + "0" * 34,
            )
        )
        assert fa.id is not None
        await file_adapter.link_file_to_commit(fa.id, c1.id)
        await file_adapter.link_file_to_commit(fa.id, c2.id)

        # File with hash_b linked to c3 (content changed)
        fb = await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                path="docs/readme.md",
                content_hash="hash_b" + "0" * 34,
            )
        )
        assert fb.id is not None
        await file_adapter.link_file_to_commit(fb.id, c3.id)

        versions = await version_adapter.list_versions_by_path(
            repo.id, "docs/readme.md", branch="main"
        )

        # Should return 2 versions (newest content first)
        assert len(versions) == 2
        assert versions[0].content_hash == "hash_b" + "0" * 34  # newer content
        assert versions[1].content_hash == "hash_a" + "0" * 34  # older content
