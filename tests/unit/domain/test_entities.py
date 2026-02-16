"""Tests for domain entities."""

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from inxr2.domain.entities import Commit, File, Reference, Repository, Symbol
from inxr2.domain.value_objects import (
    CommitHash,
    ReferenceType,
    SymbolKind,
)


class TestRepository:
    """Tests for Repository entity."""

    def test_repository_creation(self) -> None:
        """Test creating a repository entity."""
        repo = Repository(
            name="test-repo",
            url="https://github.com/test/repo.git",
            id=1,
            config={"branch": "main"},
        )

        assert repo.id == 1
        assert repo.name == "test-repo"
        assert repo.url == "https://github.com/test/repo.git"
        assert repo.config == {"branch": "main"}

    def test_repository_is_immutable(self) -> None:
        """Test that repository is frozen (immutable)."""
        repo = Repository(
            name="test-repo", url="https://github.com/test/repo.git", id=1
        )

        with pytest.raises(FrozenInstanceError):
            repo.name = "new-name"  # type: ignore


class TestCommit:
    """Tests for Commit entity."""

    def test_commit_creation(self) -> None:
        """Test creating a commit entity."""
        commit_hash = CommitHash("abcdef1234567890abcdef1234567890abcdef12")
        timestamp = datetime(2025, 1, 1, 12, 0, 0)

        commit = Commit(
            commit_hash=commit_hash,
            repository_id=1,
            author_date=timestamp,
            commit_date=timestamp,
        )

        assert commit.commit_hash == commit_hash
        assert commit.repository_id == 1
        assert commit.author_date == timestamp
        assert commit.short_hash == "abcdef1"


class TestFile:
    """Tests for File entity."""

    def test_file_creation(self) -> None:
        """Test creating a file entity."""
        file = File(
            repository_id=1,
            path="src/main.py",
            content_hash="sha256hash",
            size_bytes=1024,
            id=1,
            language="python",
        )

        assert file.id == 1
        assert file.repository_id == 1
        assert file.path == "src/main.py"
        assert file.language == "python"
        assert file.size_bytes == 1024


class TestSymbol:
    """Tests for Symbol entity."""

    def test_symbol_creation(self) -> None:
        """Test creating a symbol entity."""
        symbol = Symbol(
            file_id=1,
            repository_id=1,
            name="my_function",
            kind=SymbolKind.FUNCTION,
            start_line=10,
            start_column=4,
            end_line=20,
            end_column=10,
            id=1,
            scope="module",
            metadata={"params": ["x", "y"]},
        )

        assert symbol.id == 1
        assert symbol.name == "my_function"
        assert symbol.kind == SymbolKind.FUNCTION
        assert symbol.location.line == 10
        assert symbol.location.column == 4
        assert symbol.file_id == 1
        assert symbol.scope == "module"
        assert symbol.metadata == {"params": ["x", "y"]}


class TestReference:
    """Tests for Reference entity."""

    def test_reference_creation(self) -> None:
        """Test creating a reference entity."""
        ref = Reference(
            repository_id=1,
            source_file_id=2,
            source_line=20,
            source_column=8,
            source_end_column=15,
            reference_text="my_function",
            reference_type=ReferenceType.CALL,
            id=1,
            target_symbol_id=1,
        )

        assert ref.id == 1
        assert ref.source_line == 20
        assert ref.source_file_id == 2
        assert ref.target_symbol_id == 1
        assert ref.reference_type == ReferenceType.CALL
