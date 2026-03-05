"""Tests for domain entities."""

from datetime import datetime

import pytest

from inxr2.domain.entities import Commit, Repository, Symbol
from inxr2.domain.value_objects import (
    CommitHash,
    SymbolKind,
)


class TestRepository:
    """Tests for Repository entity name validation."""

    def _make_repo(self, name: str) -> Repository:
        return Repository(name=name, url="https://example.com/repo.git")

    def test_valid_simple_name(self) -> None:
        repo = self._make_repo("my-repo")
        assert repo.name == "my-repo"

    def test_valid_name_with_dot(self) -> None:
        repo = self._make_repo("nexd.io")
        assert repo.name == "nexd.io"

    def test_valid_name_with_multiple_dots(self) -> None:
        repo = self._make_repo("vue.js.org")
        assert repo.name == "vue.js.org"

    def test_invalid_name_starts_with_dot(self) -> None:
        with pytest.raises(ValueError, match="cannot start or end with a dot"):
            self._make_repo(".hidden")

    def test_invalid_name_ends_with_dot(self) -> None:
        with pytest.raises(ValueError, match="cannot start or end with a dot"):
            self._make_repo("repo.")

    def test_invalid_name_single_dot(self) -> None:
        with pytest.raises(ValueError, match="cannot start or end with a dot"):
            self._make_repo(".")

    def test_invalid_name_double_dot(self) -> None:
        with pytest.raises(ValueError, match="cannot start or end with a dot"):
            self._make_repo("..")

    def test_invalid_name_with_spaces(self) -> None:
        with pytest.raises(ValueError, match="must contain only"):
            self._make_repo("my repo")

    def test_invalid_name_with_slash(self) -> None:
        with pytest.raises(ValueError, match="must contain only"):
            self._make_repo("my/repo")

    def test_empty_name(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            self._make_repo("")


class TestCommit:
    """Tests for Commit entity."""

    def test_short_hash(self) -> None:
        """Test short_hash returns first 7 characters of the commit hash."""
        commit_hash = CommitHash("abcdef1234567890abcdef1234567890abcdef12")
        timestamp = datetime(2025, 1, 1, 12, 0, 0)

        commit = Commit(
            commit_hash=commit_hash,
            repository_id=1,
            author_date=timestamp,
            commit_date=timestamp,
        )

        assert commit.short_hash == "abcdef1"


class TestSymbol:
    """Tests for Symbol entity."""

    def test_location_property(self) -> None:
        """Test location returns a SymbolLocation from line/column fields."""
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
        )

        assert symbol.location.line == 10
        assert symbol.location.column == 4
