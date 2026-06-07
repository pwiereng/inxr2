"""Integration tests for PostgresCommitRepository."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def test_save_new_commit_returns_entity_with_id(
        self, db_session: AsyncSession
    ) -> None:
        """Test saving a new commit generates an ID."""
        # First create a repository
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            RepositoryFactory.create(name="commit-test-repo")
        )
        assert repo.id is not None

        adapter = PostgresCommitRepository(db_session)
        commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="a" * 40,
        )

        saved = await adapter.save(commit)

        assert saved.id is not None
        assert saved.commit_hash.value == "a" * 40

    async def test_find_by_hash_returns_commit(self, db_session: AsyncSession) -> None:
        """Test finding a commit by hash."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(RepositoryFactory.create(name="find-hash-repo"))
        assert repo.id is not None

        adapter = PostgresCommitRepository(db_session)
        commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="b" * 40,
        )
        await adapter.save(commit)

        found = await adapter.find_by_hash(repo.id, "b" * 40)

        assert found is not None
        assert found.commit_hash.value == "b" * 40

    async def test_link_commit_to_branch_creates_association(
        self, db_session: AsyncSession
    ) -> None:
        """Test that link_commit_to_branch creates a branch-commit association."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            RepositoryFactory.create(name="link-branch-repo")
        )
        assert repo.id is not None

        adapter = PostgresCommitRepository(db_session)
        commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="c" * 40,
        )
        saved = await adapter.save(commit)
        assert saved.id is not None

        # Link to a branch
        await adapter.link_commit_to_branch(repo.id, saved.id, "main")

        # Verify via get_branches_for_commit
        branches = await adapter.get_branches_for_commit(saved.id)
        assert "main" in branches

    async def test_link_commit_to_multiple_branches(
        self, db_session: AsyncSession
    ) -> None:
        """Test that a commit can be linked to multiple branches."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            RepositoryFactory.create(name="multi-branch-repo")
        )
        assert repo.id is not None

        adapter = PostgresCommitRepository(db_session)
        commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="d" * 40,
        )
        saved = await adapter.save(commit)
        assert saved.id is not None

        # Link to multiple branches
        await adapter.link_commit_to_branches(repo.id, saved.id, ["main", "develop"])

        # Verify both branches
        branches = await adapter.get_branches_for_commit(saved.id)
        assert set(branches) == {"main", "develop"}

    async def test_find_latest_by_branch_returns_latest_commit(
        self, db_session: AsyncSession
    ) -> None:
        """Test that find_latest_by_branch returns the most recent commit."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            RepositoryFactory.create(name="latest-branch-repo")
        )
        assert repo.id is not None

        adapter = PostgresCommitRepository(db_session)

        # Create commits with different dates
        now = datetime.now(UTC).replace(tzinfo=None)
        older_commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="c" * 40,
            commit_date=now - timedelta(hours=2),
        )
        newer_commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="d" * 40,
            commit_date=now - timedelta(hours=1),
        )
        newest_commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="e" * 40,
            commit_date=now,
        )

        saved_older = await adapter.save(older_commit)
        assert saved_older.id is not None
        saved_newer = await adapter.save(newer_commit)
        assert saved_newer.id is not None
        saved_newest = await adapter.save(newest_commit)
        assert saved_newest.id is not None

        # Link all commits to main branch
        await adapter.link_commit_to_branch(repo.id, saved_older.id, "main")
        await adapter.link_commit_to_branch(repo.id, saved_newer.id, "main")
        await adapter.link_commit_to_branch(repo.id, saved_newest.id, "main")

        # Find latest by branch
        latest = await adapter.find_latest_by_branch(repo.id, "main")

        assert latest is not None
        assert latest.commit_hash.value == "e" * 40

    async def test_find_latest_by_branch_filters_by_branch(
        self, db_session: AsyncSession
    ) -> None:
        """Test that find_latest_by_branch only considers commits from specified branch."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            RepositoryFactory.create(name="branch-filter-repo")
        )
        assert repo.id is not None

        adapter = PostgresCommitRepository(db_session)

        now = datetime.now(UTC).replace(tzinfo=None)
        # Main branch has older commit
        main_commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="f" * 40,
            commit_date=now - timedelta(hours=2),
        )
        # Feature branch has newer commit
        feature_commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="1" * 40,
            commit_date=now,
        )

        saved_main = await adapter.save(main_commit)
        assert saved_main.id is not None
        saved_feature = await adapter.save(feature_commit)
        assert saved_feature.id is not None

        # Link to respective branches
        await adapter.link_commit_to_branch(repo.id, saved_main.id, "main")
        await adapter.link_commit_to_branch(repo.id, saved_feature.id, "feature")

        # Latest for main should be main_commit even though feature is newer
        latest_main = await adapter.find_latest_by_branch(repo.id, "main")
        latest_feature = await adapter.find_latest_by_branch(repo.id, "feature")

        assert latest_main is not None
        assert latest_main.commit_hash.value == "f" * 40
        assert latest_feature is not None
        assert latest_feature.commit_hash.value == "1" * 40

    async def test_find_latest_by_branch_returns_none_for_unknown_branch(
        self, db_session: AsyncSession
    ) -> None:
        """Test that find_latest_by_branch returns None for non-existent branch."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(RepositoryFactory.create(name="no-branch-repo"))
        assert repo.id is not None

        adapter = PostgresCommitRepository(db_session)

        commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="2" * 40,
        )
        saved = await adapter.save(commit)
        assert saved.id is not None
        await adapter.link_commit_to_branch(repo.id, saved.id, "main")

        # Try to find non-existent branch
        result = await adapter.find_latest_by_branch(repo.id, "nonexistent")

        assert result is None

    async def test_list_by_repository_filters_by_branch(
        self, db_session: AsyncSession
    ) -> None:
        """Test that list_by_repository can filter by branch."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            RepositoryFactory.create(name="list-branch-repo")
        )
        assert repo.id is not None

        adapter = PostgresCommitRepository(db_session)

        main_commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="3" * 40,
        )
        develop_commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="4" * 40,
        )

        saved_main = await adapter.save(main_commit)
        assert saved_main.id is not None
        saved_develop = await adapter.save(develop_commit)
        assert saved_develop.id is not None

        # Link to respective branches
        await adapter.link_commit_to_branch(repo.id, saved_main.id, "main")
        await adapter.link_commit_to_branch(repo.id, saved_develop.id, "develop")

        # List all commits
        all_commits = await adapter.list_by_repository(repo.id)
        assert len(all_commits) == 2

        # List only main branch
        main_commits = await adapter.list_by_repository(repo.id, branch="main")
        assert len(main_commits) == 1
        assert main_commits[0].commit_hash.value == "3" * 40

        # List only develop branch
        develop_commits = await adapter.list_by_repository(repo.id, branch="develop")
        assert len(develop_commits) == 1
        assert develop_commits[0].commit_hash.value == "4" * 40

    async def test_commit_on_multiple_branches_appears_in_both(
        self, db_session: AsyncSession
    ) -> None:
        """Test that a commit linked to multiple branches appears when filtering by either."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            RepositoryFactory.create(name="shared-commit-repo")
        )
        assert repo.id is not None

        adapter = PostgresCommitRepository(db_session)

        # Create a shared commit (like a merge base)
        shared_commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="5" * 40,
        )
        saved_shared = await adapter.save(shared_commit)
        assert saved_shared.id is not None

        # Link to both main and feature branches
        await adapter.link_commit_to_branches(
            repo.id, saved_shared.id, ["main", "feature"]
        )

        # Should appear in both branch listings
        main_commits = await adapter.list_by_repository(repo.id, branch="main")
        feature_commits = await adapter.list_by_repository(repo.id, branch="feature")

        assert len(main_commits) == 1
        assert len(feature_commits) == 1
        assert main_commits[0].commit_hash.value == "5" * 40
        assert feature_commits[0].commit_hash.value == "5" * 40

    async def test_link_commit_to_branch_is_idempotent(
        self, db_session: AsyncSession
    ) -> None:
        """Test that linking the same commit to the same branch multiple times is idempotent."""
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            RepositoryFactory.create(name="idempotent-link-repo")
        )
        assert repo.id is not None

        adapter = PostgresCommitRepository(db_session)

        commit = CommitFactory.create(
            repository_id=repo.id,
            commit_hash="6" * 40,
        )
        saved = await adapter.save(commit)
        assert saved.id is not None

        # Link multiple times
        await adapter.link_commit_to_branch(repo.id, saved.id, "main")
        await adapter.link_commit_to_branch(repo.id, saved.id, "main")
        await adapter.link_commit_to_branch(repo.id, saved.id, "main")

        # Should still only have one association
        branches = await adapter.get_branches_for_commit(saved.id)
        assert branches == ["main"]


@pytest.mark.asyncio
class TestPostgresCommitRepositoryBranchCoverage:
    """Targeted branch coverage for edge cases."""

    async def _repo(self, db_session: AsyncSession, name: str) -> int:
        repo = await PostgresRepositoryAdapter(db_session).save(
            RepositoryFactory.create(name=name)
        )
        assert repo.id is not None
        return repo.id

    async def test_save_many_with_existing_id_merges(
        self, db_session: AsyncSession
    ) -> None:
        repo_id = await self._repo(db_session, "cm-merge")
        adapter = PostgresCommitRepository(db_session)
        saved = await adapter.save(
            CommitFactory.create(repository_id=repo_id, commit_hash="a" * 40)
        )
        assert saved.id is not None
        # save_many with a commit that already has an id → merge path.
        result = await adapter.save_many([saved])
        assert result[0].id == saved.id

    async def test_find_by_ids_empty_returns_empty(
        self, db_session: AsyncSession
    ) -> None:
        adapter = PostgresCommitRepository(db_session)
        assert await adapter.find_by_ids([]) == []

    async def test_find_by_hash_short_prefix(self, db_session: AsyncSession) -> None:
        repo_id = await self._repo(db_session, "cm-shorthash")
        adapter = PostgresCommitRepository(db_session)
        full = "abcdef" + "0" * 34
        await adapter.save(
            CommitFactory.create(repository_id=repo_id, commit_hash=full)
        )
        await db_session.commit()
        # short (prefix) hash → startswith matching branch.
        found = await adapter.find_by_hash(repo_id, "abcdef")
        assert found is not None
        assert found.commit_hash.value == full

    async def test_link_commit_to_branches_empty_is_noop(
        self, db_session: AsyncSession
    ) -> None:
        repo_id = await self._repo(db_session, "cm-emptybranches")
        adapter = PostgresCommitRepository(db_session)
        commit = await adapter.save(
            CommitFactory.create(repository_id=repo_id, commit_hash="b" * 40)
        )
        assert commit.id is not None
        # Empty branch list → early return, no rows created.
        await adapter.link_commit_to_branches(repo_id, commit.id, [])
        assert await adapter.get_branches_for_commit(commit.id) == []

    async def test_link_commit_to_branches_skips_existing(
        self, db_session: AsyncSession
    ) -> None:
        repo_id = await self._repo(db_session, "cm-multibranch")
        adapter = PostgresCommitRepository(db_session)
        commit = await adapter.save(
            CommitFactory.create(repository_id=repo_id, commit_hash="c" * 40)
        )
        assert commit.id is not None
        await adapter.link_commit_to_branch(repo_id, commit.id, "main")
        # "main" already linked; only "dev" is newly inserted.
        await adapter.link_commit_to_branches(repo_id, commit.id, ["main", "dev"])
        branches = set(await adapter.get_branches_for_commit(commit.id))
        assert branches == {"main", "dev"}

    async def test_get_branches_for_commits_empty(
        self, db_session: AsyncSession
    ) -> None:
        adapter = PostgresCommitRepository(db_session)
        assert await adapter.get_branches_for_commits([]) == {}

    async def test_get_branches_for_commits_groups(
        self, db_session: AsyncSession
    ) -> None:
        repo_id = await self._repo(db_session, "cm-grouping")
        adapter = PostgresCommitRepository(db_session)
        commit = await adapter.save(
            CommitFactory.create(repository_id=repo_id, commit_hash="d" * 40)
        )
        assert commit.id is not None
        await adapter.link_commit_to_branches(repo_id, commit.id, ["main", "release"])
        result = await adapter.get_branches_for_commits([commit.id])
        assert set(result[commit.id]) == {"main", "release"}
