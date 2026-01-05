"""Unit tests for entity-to-model mappers."""

from datetime import datetime

import pytest

from inxr2.adapters.persistence.mappers import (
    CommitMapper,
    FileMapper,
    RepositoryMapper,
    SymbolMapper,
)
from inxr2.domain.value_objects import CommitHash, SymbolKind

from .factories import CommitFactory, FileFactory, RepositoryFactory, SymbolFactory


class TestRepositoryMapper:
    """Test RepositoryMapper bidirectional conversion."""

    def test_to_model_converts_entity_to_orm_model(self):
        """Test converting Repository entity to RepositoryModel."""
        entity = RepositoryFactory.create(
            name="test-repo",
            url="https://github.com/test/repo.git",
            description="Test repository",
        )

        model = RepositoryMapper.to_model(entity)

        assert model.name == entity.name
        assert model.url == entity.url
        assert model.description == entity.description
        assert model.default_branch == entity.default_branch
        assert model.config == entity.config

    def test_to_domain_converts_orm_model_to_entity(self):
        """Test converting RepositoryModel to Repository entity."""
        from inxr2.adapters.persistence.models import RepositoryModel

        model = RepositoryModel(
            id=1,
            name="test-repo",
            url="https://github.com/test/repo.git",
            description="Test repository",
            default_branch="main",
            config={"key": "value"},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        entity = RepositoryMapper.to_domain(model)

        assert entity.id == model.id
        assert entity.name == model.name
        assert entity.url == model.url
        assert entity.description == model.description
        assert entity.default_branch == model.default_branch
        assert entity.config == model.config

    def test_round_trip_conversion_preserves_data(self):
        """Test that entity -> model -> entity preserves all data."""
        original = RepositoryFactory.create(
            id=1,
            name="test-repo",
            url="https://github.com/test/repo.git",
            config={"branches": ["main", "dev"]},
        )

        model = RepositoryMapper.to_model(original)
        restored = RepositoryMapper.to_domain(model)

        assert restored.name == original.name
        assert restored.url == original.url
        assert restored.config == original.config


class TestCommitMapper:
    """Test CommitMapper bidirectional conversion."""

    def test_to_model_converts_entity_to_orm_model(self):
        """Test converting Commit entity to CommitModel."""
        entity = CommitFactory.create(
            repository_id=1,
            commit_hash="a" * 40,
            author_name="Test Author",
            message="Test commit",
        )

        model = CommitMapper.to_model(entity)

        assert model.repository_id == entity.repository_id
        assert model.commit_hash == entity.commit_hash.value
        assert model.author_name == entity.author_name
        assert model.message == entity.message

    def test_to_domain_converts_orm_model_to_entity(self):
        """Test converting CommitModel to Commit entity."""
        from inxr2.adapters.persistence.models import CommitModel

        model = CommitModel(
            id=1,
            repository_id=1,
            commit_hash="a" * 40,
            short_hash="aaaaaaa",
            author_name="Test Author",
            author_email="author@test.com",
            committer_name="Test Committer",
            committer_email="committer@test.com",
            author_date=datetime.utcnow(),
            commit_date=datetime.utcnow(),
            message="Test commit",
            branch="main",
        )

        entity = CommitMapper.to_domain(model)

        assert entity.id == model.id
        assert entity.repository_id == model.repository_id
        assert entity.commit_hash.value == model.commit_hash
        assert entity.author_name == model.author_name
        assert entity.message == model.message

    def test_commit_hash_value_object_handled_correctly(self):
        """Test that CommitHash value object is properly converted."""
        entity = CommitFactory.create(commit_hash="abc123" + "0" * 34)

        model = CommitMapper.to_model(entity)

        assert model.commit_hash == entity.commit_hash.value
        assert len(model.commit_hash) == 40


class TestFileMapper:
    """Test FileMapper bidirectional conversion."""

    def test_to_model_converts_entity_to_orm_model(self):
        """Test converting File entity to FileModel."""
        entity = FileFactory.create(
            repository_id=1,
            commit_id=1,
            path="src/test.py",
            content_hash="b" * 40,
            size_bytes=1024,
        )

        model = FileMapper.to_model(entity)

        assert model.repository_id == entity.repository_id
        assert model.commit_id == entity.commit_id
        assert model.path == entity.path
        assert model.content_hash == entity.content_hash
        assert model.size_bytes == entity.size_bytes

    def test_to_domain_converts_orm_model_to_entity(self):
        """Test converting FileModel to File entity."""
        from inxr2.adapters.persistence.models import FileModel

        model = FileModel(
            id=1,
            repository_id=1,
            commit_id=1,
            path="src/test.py",
            content_hash="b" * 40,
            size_bytes=1024,
            language="python",
            encoding="utf-8",
            is_binary=False,
            line_count=50,
        )

        entity = FileMapper.to_domain(model)

        assert entity.id == model.id
        assert entity.path == model.path
        assert entity.content_hash == model.content_hash
        assert entity.language == model.language


class TestSymbolMapper:
    """Test SymbolMapper bidirectional conversion."""

    def test_to_model_converts_entity_to_orm_model(self):
        """Test converting Symbol entity to SymbolModel."""
        entity = SymbolFactory.create(
            file_id=1,
            repository_id=1,
            commit_id=1,
            name="test_function",
            kind=SymbolKind.FUNCTION,
            start_line=10,
            end_line=20,
        )

        model = SymbolMapper.to_model(entity)

        assert model.file_id == entity.file_id
        assert model.name == entity.name
        assert model.kind == entity.kind.value
        assert model.start_line == entity.start_line
        assert model.end_line == entity.end_line

    def test_to_domain_converts_orm_model_to_entity(self):
        """Test converting SymbolModel to Symbol entity."""
        from inxr2.adapters.persistence.models import SymbolModel

        model = SymbolModel(
            id=1,
            file_id=1,
            repository_id=1,
            commit_id=1,
            name="test_function",
            kind="function",
            start_line=10,
            start_column=0,
            end_line=20,
            end_column=0,
        )

        entity = SymbolMapper.to_domain(model)

        assert entity.id == model.id
        assert entity.name == model.name
        assert entity.kind == SymbolKind.FUNCTION
        assert entity.start_line == model.start_line

    def test_symbol_kind_enum_handled_correctly(self):
        """Test that SymbolKind enum is properly converted."""
        entity = SymbolFactory.create(kind=SymbolKind.CLASS)

        model = SymbolMapper.to_model(entity)

        assert model.kind == "class"
        assert isinstance(model.kind, str)

        restored = SymbolMapper.to_domain(model)
        assert restored.kind == SymbolKind.CLASS
        assert isinstance(restored.kind, SymbolKind)

    def test_metadata_field_renamed_to_extra_metadata(self):
        """Test that metadata field is correctly mapped to extra_metadata."""
        entity = SymbolFactory.create(
            metadata={"decorators": ["@property"], "is_async": True}
        )

        model = SymbolMapper.to_model(entity)

        assert model.extra_metadata == entity.metadata
        assert model.extra_metadata["decorators"] == ["@property"]
