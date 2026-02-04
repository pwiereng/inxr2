"""Tests for TextContentMapper."""

from datetime import datetime

from inxr2.adapters.persistence.mappers import TextContentMapper
from inxr2.adapters.persistence.models.text_content import TextContentModel
from inxr2.domain.entities.text_content import TextContent


class TestTextContentMapper:
    """Test TextContentMapper bidirectional conversion."""

    def test_to_domain_with_all_fields(self) -> None:
        """Test converting ORM model to domain entity with all fields."""
        now = datetime.now()
        model = TextContentModel(
            id=1,
            repository_id=10,
            commit_id=100,
            source_type="docstring",
            source_file_id=50,
            source_line=10,
            source_end_line=15,
            content='"""Calculate total amount."""',
            language="python",
            content_type="docstring",
            indexed_at=now,
        )

        entity = TextContentMapper.to_domain(model)

        assert isinstance(entity, TextContent)
        assert entity.id == 1
        assert entity.repository_id == 10
        assert entity.commit_id == 100
        assert entity.source_type == "docstring"
        assert entity.source_file_id == 50
        assert entity.source_line == 10
        assert entity.source_end_line == 15
        assert entity.content == '"""Calculate total amount."""'
        assert entity.language == "python"
        assert entity.content_type == "docstring"
        assert entity.indexed_at == now

    def test_to_domain_commit_message(self) -> None:
        """Test converting commit message (no file_id) to domain."""
        model = TextContentModel(
            id=2,
            repository_id=10,
            commit_id=100,
            source_type="commit_message",
            source_file_id=None,
            source_line=None,
            content="fix: resolve null pointer",
            language=None,
            content_type=None,
        )

        entity = TextContentMapper.to_domain(model)

        assert entity.source_type == "commit_message"
        assert entity.source_file_id is None
        assert entity.source_line is None
        assert entity.content == "fix: resolve null pointer"

    def test_to_model_with_all_fields(self) -> None:
        """Test converting domain entity to ORM model with all fields."""
        now = datetime.now()
        entity = TextContent(
            id=1,
            repository_id=10,
            commit_id=100,
            source_type="comment",
            source_file_id=50,
            source_line=42,
            source_end_line=42,
            content="TODO: refactor this",
            language="python",
            content_type="inline_comment",
            indexed_at=now,
        )

        model = TextContentMapper.to_model(entity)

        assert isinstance(model, TextContentModel)
        assert model.id == 1
        assert model.repository_id == 10
        assert model.commit_id == 100
        assert model.source_type == "comment"
        assert model.source_file_id == 50
        assert model.source_line == 42
        assert model.source_end_line == 42
        assert model.content == "TODO: refactor this"
        assert model.language == "python"
        assert model.content_type == "inline_comment"
        assert model.indexed_at == now

    def test_to_model_sets_indexed_at_if_none(self) -> None:
        """Test that to_model sets indexed_at if not provided."""
        entity = TextContent(
            repository_id=10,
            commit_id=100,
            source_type="comment",
            source_file_id=50,
            source_line=42,
            content="TODO: fix",
            indexed_at=None,
        )

        model = TextContentMapper.to_model(entity)

        assert model.indexed_at is not None
        assert isinstance(model.indexed_at, datetime)

    def test_roundtrip_conversion(self) -> None:
        """Test that converting domain -> model -> domain preserves data."""
        now = datetime.now()
        original_entity = TextContent(
            id=1,
            repository_id=10,
            commit_id=100,
            source_type="docstring",
            source_file_id=50,
            source_line=10,
            source_end_line=15,
            content='"""Test docstring"""',
            language="python",
            content_type="docstring",
            indexed_at=now,
        )

        model = TextContentMapper.to_model(original_entity)
        roundtrip_entity = TextContentMapper.to_domain(model)

        assert roundtrip_entity.id == original_entity.id
        assert roundtrip_entity.repository_id == original_entity.repository_id
        assert roundtrip_entity.commit_id == original_entity.commit_id
        assert roundtrip_entity.source_type == original_entity.source_type
        assert roundtrip_entity.source_file_id == original_entity.source_file_id
        assert roundtrip_entity.source_line == original_entity.source_line
        assert roundtrip_entity.source_end_line == original_entity.source_end_line
        assert roundtrip_entity.content == original_entity.content
        assert roundtrip_entity.language == original_entity.language
        assert roundtrip_entity.content_type == original_entity.content_type
        assert roundtrip_entity.indexed_at == original_entity.indexed_at
