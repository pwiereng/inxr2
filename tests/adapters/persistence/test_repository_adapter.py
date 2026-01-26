"""Integration tests for PostgresRepositoryAdapter.

These tests use a real database (SQLite in-memory or test PostgreSQL).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)

from .factories import RepositoryFactory


@pytest.mark.asyncio
class TestPostgresRepositoryAdapter:
    """Integration tests for PostgresRepositoryAdapter."""

    async def test_save_new_repository_returns_entity_with_id(
        self, db_session: AsyncSession
    ) -> None:
        """Test saving a new repository generates an ID."""
        adapter = PostgresRepositoryAdapter(db_session)
        entity = RepositoryFactory.create(name="new-repo")

        # ID should be None before save
        assert entity.id is None

        saved = await adapter.save(entity)

        # ID should be assigned after save
        assert saved.id is not None
        assert saved.name == entity.name
        assert saved.url == entity.url

    async def test_find_by_id_returns_repository_when_exists(
        self, db_session: AsyncSession
    ) -> None:
        """Test finding a repository by ID."""
        adapter = PostgresRepositoryAdapter(db_session)

        # Create and save a repository
        entity = RepositoryFactory.create(name="find-by-id-repo")
        saved = await adapter.save(entity)
        assert saved.id is not None

        # Find by ID
        found = await adapter.find_by_id(saved.id)

        assert found is not None
        assert found.id == saved.id
        assert found.name == saved.name

    async def test_find_by_id_returns_none_when_not_exists(
        self, db_session: AsyncSession
    ) -> None:
        """Test finding a non-existent repository returns None."""
        adapter = PostgresRepositoryAdapter(db_session)

        found = await adapter.find_by_id(99999)

        assert found is None

    async def test_find_by_name_returns_repository_when_exists(
        self, db_session: AsyncSession
    ) -> None:
        """Test finding a repository by unique name."""
        adapter = PostgresRepositoryAdapter(db_session)

        # Create and save a repository
        entity = RepositoryFactory.create(name="unique-repo")
        await adapter.save(entity)

        # Find by name
        found = await adapter.find_by_name("unique-repo")

        assert found is not None
        assert found.name == "unique-repo"

    async def test_find_by_name_returns_none_when_not_exists(
        self, db_session: AsyncSession
    ) -> None:
        """Test finding a non-existent repository by name returns None."""
        adapter = PostgresRepositoryAdapter(db_session)

        found = await adapter.find_by_name("nonexistent-repo")

        assert found is None

    async def test_list_all_returns_empty_list_initially(
        self, db_session: AsyncSession
    ) -> None:
        """Test listing repositories when none exist."""
        adapter = PostgresRepositoryAdapter(db_session)

        repos = await adapter.list_all()

        assert repos == []

    async def test_list_all_returns_all_repositories(
        self, db_session: AsyncSession
    ) -> None:
        """Test listing all repositories."""
        adapter = PostgresRepositoryAdapter(db_session)

        # Create multiple repositories
        await adapter.save(RepositoryFactory.create(name="repo1"))
        await adapter.save(RepositoryFactory.create(name="repo2"))
        await adapter.save(RepositoryFactory.create(name="repo3"))

        repos = await adapter.list_all()

        assert len(repos) == 3
        repo_names = {repo.name for repo in repos}
        assert repo_names == {"repo1", "repo2", "repo3"}

    async def test_update_existing_repository(self, db_session: AsyncSession) -> None:
        """Test updating an existing repository."""
        adapter = PostgresRepositoryAdapter(db_session)

        # Create and save
        entity = RepositoryFactory.create(name="update-repo", description="Original")
        saved = await adapter.save(entity)
        assert saved.id is not None

        # Update (create new entity with same ID but different description)
        updated_entity = RepositoryFactory.create(
            id=saved.id,
            name="update-repo",
            description="Updated description",
        )
        updated = await adapter.save(updated_entity)

        # Verify update
        assert updated.id == saved.id
        assert updated.description == "Updated description"

        # Verify in database
        found = await adapter.find_by_id(saved.id)
        assert found is not None
        assert found.description == "Updated description"

    async def test_delete_existing_repository_returns_true(
        self, db_session: AsyncSession
    ) -> None:
        """Test deleting an existing repository."""
        adapter = PostgresRepositoryAdapter(db_session)

        # Create and save
        entity = RepositoryFactory.create(name="delete-repo")
        saved = await adapter.save(entity)
        assert saved.id is not None

        # Delete
        result = await adapter.delete(saved.id)

        assert result is True

        # Verify deleted
        found = await adapter.find_by_id(saved.id)
        assert found is None

    async def test_delete_nonexistent_repository_returns_false(
        self, db_session: AsyncSession
    ) -> None:
        """Test deleting a non-existent repository."""
        adapter = PostgresRepositoryAdapter(db_session)

        result = await adapter.delete(99999)

        assert result is False

    async def test_repository_config_jsonb_field_works(
        self, db_session: AsyncSession
    ) -> None:
        """Test that config JSONB field stores complex data."""
        adapter = PostgresRepositoryAdapter(db_session)

        config = {
            "branches": ["main", "develop", "feature/test"],
            "file_patterns": ["*.py", "*.java"],
            "max_file_size_kb": 1024,
        }
        entity = RepositoryFactory.create(name="config-repo", config=config)

        saved = await adapter.save(entity)
        assert saved.id is not None
        found = await adapter.find_by_id(saved.id)
        assert found is not None

        assert found.config == config
        assert found.config["branches"] == ["main", "develop", "feature/test"]
        assert found.config["max_file_size_kb"] == 1024

    async def test_concurrent_saves_work_correctly(
        self, db_session: AsyncSession
    ) -> None:
        """Test that multiple saves in same session work."""
        adapter = PostgresRepositoryAdapter(db_session)

        # Save multiple repositories in same session
        repo1 = await adapter.save(RepositoryFactory.create(name="concurrent1"))
        repo2 = await adapter.save(RepositoryFactory.create(name="concurrent2"))
        repo3 = await adapter.save(RepositoryFactory.create(name="concurrent3"))

        # All should have different IDs
        assert repo1.id != repo2.id
        assert repo2.id != repo3.id
        assert repo1.id != repo3.id

        # All should be findable
        found1 = await adapter.find_by_name("concurrent1")
        found2 = await adapter.find_by_name("concurrent2")
        found3 = await adapter.find_by_name("concurrent3")

        assert found1 is not None
        assert found2 is not None
        assert found3 is not None
