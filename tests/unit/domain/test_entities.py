"""Tests for domain entities."""

from datetime import datetime
from pathlib import Path

import pytest

from inxr2.domain.entities import Repository, Commit, File, Symbol, Reference
from inxr2.domain.value_objects import SymbolLocation, CommitHash, SymbolKind


class TestRepository:
    """Tests for Repository entity."""

    def test_repository_creation(self) -> None:
        """Test creating a repository entity."""
        repo = Repository(
            id="repo-1",
            name="test-repo",
            url="https://github.com/test/repo.git",
            config={"branch": "main"},
        )

        assert repo.id == "repo-1"
        assert repo.name == "test-repo"
        assert repo.url == "https://github.com/test/repo.git"
        assert repo.config == {"branch": "main"}

    def test_repository_is_immutable(self) -> None:
        """Test that repository is frozen (immutable)."""
        repo = Repository(
            id="repo-1", name="test-repo", url="https://github.com/test/repo.git"
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            repo.name = "new-name"  # type: ignore


class TestCommit:
    """Tests for Commit entity."""

    def test_commit_creation(self) -> None:
        """Test creating a commit entity."""
        commit_hash = CommitHash("abcdef1234567890abcdef1234567890abcdef12")
        timestamp = datetime(2025, 1, 1, 12, 0, 0)

        commit = Commit(
            hash=commit_hash,
            repository_id="repo-1",
            branch="main",
            timestamp=timestamp,
            author="Test Author",
            message="Initial commit",
        )

        assert commit.hash == commit_hash
        assert commit.repository_id == "repo-1"
        assert commit.branch == "main"
        assert commit.timestamp == timestamp
        assert commit.author == "Test Author"
        assert commit.message == "Initial commit"


class TestFile:
    """Tests for File entity."""

    def test_file_creation(self) -> None:
        """Test creating a file entity."""
        file = File(
            id="file-1",
            repository_id="repo-1",
            commit_hash="abcdef12",
            path=Path("src/main.py"),
            content_hash="sha256hash",
            language="python",
            content="print('hello')",
        )

        assert file.id == "file-1"
        assert file.repository_id == "repo-1"
        assert file.path == Path("src/main.py")
        assert file.language == "python"
        assert file.content == "print('hello')"


class TestSymbol:
    """Tests for Symbol entity."""

    def test_symbol_creation(self) -> None:
        """Test creating a symbol entity."""
        location = SymbolLocation(line=10, column=4)
        symbol = Symbol(
            id="sym-1",
            name="my_function",
            kind=SymbolKind.FUNCTION,
            location=location,
            file_id="file-1",
            scope="module",
            metadata={"params": ["x", "y"]},
        )

        assert symbol.id == "sym-1"
        assert symbol.name == "my_function"
        assert symbol.kind == SymbolKind.FUNCTION
        assert symbol.location.line == 10
        assert symbol.location.column == 4
        assert symbol.file_id == "file-1"
        assert symbol.scope == "module"
        assert symbol.metadata == {"params": ["x", "y"]}


class TestReference:
    """Tests for Reference entity."""

    def test_reference_creation(self) -> None:
        """Test creating a reference entity."""
        location = SymbolLocation(line=20, column=8)
        ref = Reference(
            id="ref-1",
            source_location=location,
            source_file_id="file-2",
            target_symbol_id="sym-1",
            reference_type="call",
        )

        assert ref.id == "ref-1"
        assert ref.source_location.line == 20
        assert ref.source_file_id == "file-2"
        assert ref.target_symbol_id == "sym-1"
        assert ref.reference_type == "call"
