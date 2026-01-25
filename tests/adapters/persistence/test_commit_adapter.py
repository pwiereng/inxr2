"""Integration tests for PostgresCommitRepository."""

from datetime import datetime, timedelta

import pytest

from inxr2.adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)

from .factories import CommitFactory, RepositoryFactory


@pytest.mark.asyncio
class TestPostgresCommitRepository:
    """Integration tests for PostgresCommitRepository."""

    async def test_save_new_commit_returns_entity_with_id(self, db_session):
        """Test saving a new commit generates an ID."""
        # First create a repository
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            RepositoryFactory.create(name="commit-test-repo")
        )

        adapter = PostgresCommitRepository(db_session)
        commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="a" * 40,
            branch="main",
        )

        saved = await adapter.save(commit)

        assert saved.id is not None
        assert saved.commit_hash.value == "a" * 40
        assert saved.branch == "main"

    async def test_find_by_hash_returns_commit(self, db_session):
        """Test finding a commit by hash."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(RepositoryFactory.create(name="find-hash-repo"))

        adapter = PostgresCommitRepository(db_session)
        commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="b" * 40,
            branch="main",
        )
        await adapter.save(commit)

        found = await adapter.find_by_hash(repo.id, "b" * 40)

        assert found is not None
        assert found.commit_hash.value == "b" * 40

    async def test_find_latest_by_branch_returns_latest_commit(self, db_session):
        """Test that find_latest_by_branch returns the most recent commit."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            RepositoryFactory.create(name="latest-branch-repo")
        )

        adapter = PostgresCommitRepository(db_session)

        # Create commits with different dates
        now = datetime.utcnow()
        older_commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="c" * 40,
            branch="main",
            commit_date=now - timedelta(hours=2),
        )
        newer_commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="d" * 40,
            branch="main",
            commit_date=now - timedelta(hours=1),
        )
        newest_commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="e" * 40,
            branch="main",
            commit_date=now,
        )

        await adapter.save(older_commit)
        await adapter.save(newer_commit)
        await adapter.save(newest_commit)

        # Find latest by branch
        latest = await adapter.find_latest_by_branch(repo.id, "main")

        assert latest is not None
        assert latest.commit_hash.value == "e" * 40

    async def test_find_latest_by_branch_filters_by_branch(self, db_session):
        """Test that find_latest_by_branch only considers commits from specified branch."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            RepositoryFactory.create(name="branch-filter-repo")
        )

        adapter = PostgresCommitRepository(db_session)

        now = datetime.utcnow()
        # Main branch has older commit
        main_commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="f" * 40,
            branch="main",
            commit_date=now - timedelta(hours=2),
        )
        # Feature branch has newer commit
        feature_commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="1" * 40,
            branch="feature",
            commit_date=now,
        )

        await adapter.save(main_commit)
        await adapter.save(feature_commit)

        # Latest for main should be main_commit even though feature is newer
        latest_main = await adapter.find_latest_by_branch(repo.id, "main")
        latest_feature = await adapter.find_latest_by_branch(repo.id, "feature")

        assert latest_main is not None
        assert latest_main.commit_hash.value == "f" * 40
        assert latest_feature is not None
        assert latest_feature.commit_hash.value == "1" * 40

    async def test_find_latest_by_branch_returns_none_for_unknown_branch(
        self, db_session
    ):
        """Test that find_latest_by_branch returns None for non-existent branch."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(RepositoryFactory.create(name="no-branch-repo"))

        adapter = PostgresCommitRepository(db_session)

        commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="2" * 40,
            branch="main",
        )
        await adapter.save(commit)

        # Try to find non-existent branch
        result = await adapter.find_latest_by_branch(repo.id, "nonexistent")

        assert result is None

    async def test_list_by_repository_filters_by_branch(self, db_session):
        """Test that list_by_repository can filter by branch."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            RepositoryFactory.create(name="list-branch-repo")
        )

        adapter = PostgresCommitRepository(db_session)

        main_commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="3" * 40,
            branch="main",
        )
        develop_commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="4" * 40,
            branch="develop",
        )

        await adapter.save(main_commit)
        await adapter.save(develop_commit)

        # List all commits
        all_commits = await adapter.list_by_repository(repo.id)
        assert len(all_commits) == 2

        # List only main branch
        main_commits = await adapter.list_by_repository(repo.id, branch="main")
        assert len(main_commits) == 1
        assert main_commits[0].branch == "main"

        # List only develop branch
        develop_commits = await adapter.list_by_repository(repo.id, branch="develop")
        assert len(develop_commits) == 1
        assert develop_commits[0].branch == "develop"
