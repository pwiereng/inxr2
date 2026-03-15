"""Tests for FileRename domain entity."""

import pytest

from inxr2.domain.entities import FileRename


class TestFileRenameEntity:
    """Tests for FileRename entity creation and validation."""

    def test_create_valid_file_rename(self) -> None:
        rename = FileRename(
            repository_id=1,
            commit_id=10,
            old_path="src/old_name.py",
            new_path="src/new_name.py",
            similarity=95,
        )
        assert rename.repository_id == 1
        assert rename.commit_id == 10
        assert rename.old_path == "src/old_name.py"
        assert rename.new_path == "src/new_name.py"
        assert rename.similarity == 95
        assert rename.id is None
        assert rename.indexed_at is None

    def test_create_with_all_fields(self) -> None:
        from datetime import datetime

        rename = FileRename(
            repository_id=1,
            commit_id=10,
            old_path="a.py",
            new_path="b.py",
            similarity=50,
            id=42,
            indexed_at=datetime(2024, 1, 1),
        )
        assert rename.id == 42
        assert rename.indexed_at == datetime(2024, 1, 1)

    def test_frozen_immutable(self) -> None:
        rename = FileRename(
            repository_id=1,
            commit_id=10,
            old_path="a.py",
            new_path="b.py",
            similarity=80,
        )
        with pytest.raises(AttributeError):
            rename.old_path = "changed.py"  # type: ignore[misc]

    def test_empty_old_path_raises(self) -> None:
        with pytest.raises(ValueError, match="old_path cannot be empty"):
            FileRename(
                repository_id=1,
                commit_id=10,
                old_path="",
                new_path="b.py",
                similarity=80,
            )

    def test_empty_new_path_raises(self) -> None:
        with pytest.raises(ValueError, match="new_path cannot be empty"):
            FileRename(
                repository_id=1,
                commit_id=10,
                old_path="a.py",
                new_path="",
                similarity=80,
            )

    def test_same_paths_raises(self) -> None:
        with pytest.raises(ValueError, match="old_path and new_path must be different"):
            FileRename(
                repository_id=1,
                commit_id=10,
                old_path="same.py",
                new_path="same.py",
                similarity=100,
            )

    def test_similarity_below_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="similarity must be between 0 and 100"):
            FileRename(
                repository_id=1,
                commit_id=10,
                old_path="a.py",
                new_path="b.py",
                similarity=-1,
            )

    def test_similarity_above_100_raises(self) -> None:
        with pytest.raises(ValueError, match="similarity must be between 0 and 100"):
            FileRename(
                repository_id=1,
                commit_id=10,
                old_path="a.py",
                new_path="b.py",
                similarity=101,
            )

    def test_similarity_boundary_values(self) -> None:
        r0 = FileRename(
            repository_id=1,
            commit_id=10,
            old_path="a.py",
            new_path="b.py",
            similarity=0,
        )
        r100 = FileRename(
            repository_id=1,
            commit_id=10,
            old_path="a.py",
            new_path="b.py",
            similarity=100,
        )
        assert r0.similarity == 0
        assert r100.similarity == 100
