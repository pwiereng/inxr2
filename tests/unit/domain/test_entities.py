"""Tests for domain entities."""

from datetime import datetime

from inxr2.domain.entities import Commit, Symbol
from inxr2.domain.value_objects import (
    CommitHash,
    SymbolKind,
)


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
