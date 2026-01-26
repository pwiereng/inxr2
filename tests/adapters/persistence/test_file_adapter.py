"""Integration tests for PostgresFileRepository."""

from datetime import datetime, timedelta

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
        now = datetime.utcnow()
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
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=commit1.id,
                path="src/test.py",
                content_hash="h1" + "0" * 38,
            )
        )
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=commit2.id,
                path="src/test.py",
                content_hash="h2" + "0" * 38,
            )
        )
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=commit3.id,
                path="src/test.py",
                content_hash="h3" + "0" * 38,
            )
        )

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

        now = datetime.utcnow()
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
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=main_commit.id,
                path="src/app.py",
                content_hash="main" + "0" * 36,
            )
        )
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=feature_commit.id,
                path="src/app.py",
                content_hash="feat" + "0" * 36,
            )
        )

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

        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/file.py",
            )
        )

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

        now = datetime.utcnow()
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

        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=commit1_id,
                path="src/order.py",
                content_hash="v2" + "0" * 38,
            )
        )
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=commit0_id,
                path="src/order.py",
                content_hash="v1" + "0" * 38,
            )
        )
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=commit2_id,
                path="src/order.py",
                content_hash="v3" + "0" * 38,
            )
        )

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

        now = datetime.utcnow()

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
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=old_commit.id,
                path="src/file.py",
                content_hash="old_content" + "0" * 29,
            )
        )
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=new_commit.id,
                path="src/file.py",
                content_hash="new_content" + "0" * 29,
            )
        )

        # Create another_file.py only at old commit (file not modified)
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=old_commit.id,
                path="src/another_file.py",
                content_hash="unchanged" + "0" * 31,
            )
        )

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

        now = datetime.utcnow()

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
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=main_commit.id,
                path="src/main_only.py",
            )
        )
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=feature_commit.id,
                path="src/feature_only.py",
            )
        )

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

        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=commit.id,
                path="src/test.py",
            )
        )

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

        now = datetime.utcnow()

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
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=shared_commit.id,
                path="src/shared.py",
            )
        )

        # Both branches should see the file
        main_files = await file_adapter.list_latest_by_branch(repo.id, "main")
        feature_files = await file_adapter.list_latest_by_branch(repo.id, "feature")

        assert len(main_files) == 1
        assert len(feature_files) == 1
        assert main_files[0].path == "src/shared.py"
        assert feature_files[0].path == "src/shared.py"
