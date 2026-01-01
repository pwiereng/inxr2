"""Tests for domain exceptions."""

from inxr2.domain.exceptions import (
    DomainException,
    RepositoryNotFound,
    SymbolNotFound,
)


class TestDomainException:
    """Tests for DomainException."""

    def test_exception_creation(self) -> None:
        """Test creating a domain exception."""
        exc = DomainException("Test error", details={"key": "value"})

        assert str(exc) == "Test error"
        assert exc.message == "Test error"
        assert exc.details == {"key": "value"}

    def test_exception_without_details(self) -> None:
        """Test creating exception without details."""
        exc = DomainException("Test error")

        assert exc.message == "Test error"
        assert exc.details == {}


class TestRepositoryNotFound:
    """Tests for RepositoryNotFound exception."""

    def test_repository_not_found(self) -> None:
        """Test repository not found exception."""
        exc = RepositoryNotFound("repo-123")

        assert "repo-123" in str(exc)
        assert exc.details == {"repository_id": "repo-123"}


class TestSymbolNotFound:
    """Tests for SymbolNotFound exception."""

    def test_symbol_not_found(self) -> None:
        """Test symbol not found exception."""
        exc = SymbolNotFound("sym-456")

        assert "sym-456" in str(exc)
        assert exc.details == {"symbol_id": "sym-456"}
