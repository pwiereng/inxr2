"""Integration tests for PostgresFileRepository."""

from datetime import datetime, timedelta

import pytest

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

    async def test_list_versions_by_path_returns_all_versions(self, db_session):
        """Test listing all versions of a file across commits."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

        # Create repository
        repo = await repo_adapter.save(RepositoryFactory.create(name="versions-repo"))

        # Create commits with different dates
        now = datetime.utcnow()
        commit1 = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="a" * 40,
                commit_date=now - timedelta(hours=2),
            )
        )
        await commit_adapter.link_commit_to_branch(repo.id, commit1.id, "main")

        commit2 = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="b" * 40,
                commit_date=now - timedelta(hours=1),
            )
        )
        await commit_adapter.link_commit_to_branch(repo.id, commit2.id, "main")

        commit3 = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="c" * 40,
                commit_date=now,
            )
        )
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

    async def test_list_versions_by_path_filters_by_branch(self, db_session):
        """Test that list_versions_by_path filters by branch."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="branch-versions-repo")
        )

        now = datetime.utcnow()
        # Create commits on different branches
        main_commit = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="d" * 40,
                commit_date=now - timedelta(hours=1),
            )
        )
        await commit_adapter.link_commit_to_branch(repo.id, main_commit.id, "main")

        feature_commit = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="e" * 40,
                commit_date=now,
            )
        )
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
        self, db_session
    ):
        """Test that filtering by non-existent branch returns empty list."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="empty-branch-repo")
        )

        commit = await commit_adapter.save(
            CommitFactory.create(
                repository_id=repo.id,
                commit_hash="f" * 40,
            )
        )
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

    async def test_list_versions_preserves_order_with_branch_filter(self, db_session):
        """Test that branch-filtered versions maintain correct ordering."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        commit_adapter = PostgresCommitRepository(db_session)
        file_adapter = PostgresFileRepository(db_session)

        repo = await repo_adapter.save(
            RepositoryFactory.create(name="order-branch-repo")
        )

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
            await commit_adapter.link_commit_to_branch(repo.id, commit.id, "main")
            commits.append(commit)

        # Create files in different order than commits
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=commits[1].id,
                path="src/order.py",
                content_hash="v2" + "0" * 38,
            )
        )
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=commits[0].id,
                path="src/order.py",
                content_hash="v1" + "0" * 38,
            )
        )
        await file_adapter.save(
            FileFactory.create(
                repository_id=repo.id,
                commit_id=commits[2].id,
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
