"""Tests for TextContentModel ORM model."""

from datetime import datetime

from inxr2.adapters.persistence.models.text_content import TextContentModel


class TestTextContentModel:
    """Test TextContentModel ORM model."""

    def test_text_content_model_creation(self) -> None:
        """Test creating a TextContentModel instance."""
        now = datetime.now()
        model = TextContentModel(
            id=1,
            repository_id=10,
            commit_id=100,
            source_type="comment",
            source_file_id=50,
            source_line=42,
            source_end_line=42,
            content="TODO: refactor this function",
            language="python",
            content_type="single_line_comment",
            indexed_at=now,
        )

        assert model.id == 1
        assert model.repository_id == 10
        assert model.commit_id == 100
        assert model.source_type == "comment"
        assert model.source_file_id == 50
        assert model.source_line == 42
        assert model.source_end_line == 42
        assert model.content == "TODO: refactor this function"
        assert model.language == "python"
        assert model.content_type == "single_line_comment"
        assert model.indexed_at == now

    def test_text_content_model_commit_message(self) -> None:
        """Test creating TextContentModel for commit message."""
        model = TextContentModel(
            repository_id=10,
            commit_id=100,
            source_type="commit_message",
            source_file_id=None,
            source_line=None,
            content="fix: resolve null pointer in parser",
        )

        assert model.source_type == "commit_message"
        assert model.source_file_id is None
        assert model.source_line is None
        assert model.content == "fix: resolve null pointer in parser"

    def test_text_content_model_repr(self) -> None:
        """Test TextContentModel string representation."""
        model = TextContentModel(
            id=1,
            repository_id=10,
            commit_id=100,
            source_type="comment",
            source_file_id=50,
            source_line=42,
            content="TODO: refactor this",
        )

        repr_str = repr(model)
        assert "TextContentModel" in repr_str
        assert "id=1" in repr_str
