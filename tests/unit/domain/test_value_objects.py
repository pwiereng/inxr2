"""Tests for domain value objects."""

import pytest

from inxr2.domain.value_objects import SymbolLocation, CommitHash, SymbolKind


class TestSymbolLocation:
    """Tests for SymbolLocation value object."""

    def test_location_creation(self) -> None:
        """Test creating a symbol location."""
        loc = SymbolLocation(line=10, column=5)

        assert loc.line == 10
        assert loc.column == 5
        assert loc.end_line is None
        assert loc.end_column is None

    def test_location_with_range(self) -> None:
        """Test creating a symbol location with range."""
        loc = SymbolLocation(line=10, column=5, end_line=12, end_column=10)

        assert loc.line == 10
        assert loc.column == 5
        assert loc.end_line == 12
        assert loc.end_column == 10

    def test_location_is_immutable(self) -> None:
        """Test that location is frozen (immutable)."""
        loc = SymbolLocation(line=10, column=5)

        with pytest.raises(Exception):  # FrozenInstanceError
            loc.line = 20  # type: ignore


class TestCommitHash:
    """Tests for CommitHash value object."""

    def test_commit_hash_creation(self) -> None:
        """Test creating a commit hash."""
        hash_value = "abcdef1234567890abcdef1234567890abcdef12"
        commit_hash = CommitHash(hash_value)

        assert commit_hash.value == hash_value

    def test_short_hash(self) -> None:
        """Test short hash method."""
        hash_value = "abcdef1234567890abcdef1234567890abcdef12"
        commit_hash = CommitHash(hash_value)

        assert commit_hash.short() == "abcdef1"


class TestSymbolKind:
    """Tests for SymbolKind enum."""

    def test_symbol_kinds_exist(self) -> None:
        """Test that expected symbol kinds are defined."""
        assert SymbolKind.FUNCTION == "function"
        assert SymbolKind.CLASS == "class"
        assert SymbolKind.METHOD == "method"
        assert SymbolKind.VARIABLE == "variable"
        assert SymbolKind.MODULE == "module"

    def test_symbol_kind_is_string(self) -> None:
        """Test that symbol kind values are strings."""
        assert isinstance(SymbolKind.FUNCTION.value, str)
        assert SymbolKind.CLASS == "class"
