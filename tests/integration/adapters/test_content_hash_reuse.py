"""Integration tests for repository get_or_create race condition handling."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from inxr2.domain.entities import Repository


@pytest.mark.asyncio
class TestGetOrCreateRaceCondition:
    """Tests for get_or_create race condition handling."""

    async def test_get_or_create_handles_concurrent_calls(
        self, db_session: AsyncSession
    ) -> None:
        """Test that concurrent get_or_create calls don't fail.

        Simulates a race condition where multiple processes try to create
        the same repository simultaneously. Only one should succeed in creating,
        and all should return the same repository.
        """
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo_name = "concurrent-test-repo"

        # First call creates the repository
        repo1, created1 = await repo_adapter.get_or_create(
            name=repo_name,
            url="https://example.com/repo.git",
            description="Test repo",
        )

        assert created1 is True
        assert repo1.id is not None
        assert repo1.name == repo_name

        # Second call with same name should return existing
        repo2, created2 = await repo_adapter.get_or_create(
            name=repo_name,
            url="https://example.com/different.git",  # Different URL
            description="Different description",
        )

        assert created2 is False
        assert repo2.id == repo1.id
        assert repo2.name == repo_name
        # Should return original values, not the new ones
        assert repo2.url == "https://example.com/repo.git"

    async def test_get_or_create_returns_existing_on_find(
        self, db_session: AsyncSession
    ) -> None:
        """Test get_or_create returns existing repository when found."""
        repo_adapter = PostgresRepositoryAdapter(db_session)

        # First, create a repository directly
        repo = Repository(
            name="existing-repo",
            url="https://example.com/existing.git",
        )
        saved_repo = await repo_adapter.save(repo)
        assert saved_repo.id is not None

        # Now try get_or_create - should find existing
        found_repo, created = await repo_adapter.get_or_create(
            name="existing-repo",
            url="https://different-url.com/repo.git",
        )

        assert created is False
        assert found_repo.id == saved_repo.id
        assert found_repo.url == "https://example.com/existing.git"

    async def test_get_or_create_creates_when_not_found(
        self, db_session: AsyncSession
    ) -> None:
        """Test get_or_create creates new repository when not found."""
        repo_adapter = PostgresRepositoryAdapter(db_session)

        repo, created = await repo_adapter.get_or_create(
            name="new-unique-repo",
            url="https://example.com/new.git",
            description="A new repository",
            default_branch="main",
        )

        assert created is True
        assert repo.id is not None
        assert repo.name == "new-unique-repo"
        assert repo.url == "https://example.com/new.git"
        assert repo.description == "A new repository"
        assert repo.default_branch == "main"

        # Verify it was actually saved
        found = await repo_adapter.find_by_name("new-unique-repo")
        assert found is not None
        assert found.id == repo.id
