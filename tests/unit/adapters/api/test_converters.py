"""Tests for API response converter functions."""

from datetime import datetime

from inxr2.adapters.api.converters import (
    reference_to_response,
    repository_to_response,
    symbol_to_response,
)
from inxr2.domain.entities.reference import Reference
from inxr2.domain.entities.repository import Repository
from inxr2.domain.entities.symbol import Symbol
from inxr2.domain.value_objects.reference_type import ReferenceType
from inxr2.domain.value_objects.symbol_kind import SymbolKind


class TestRepositoryToResponse:
    def test_converts_all_fields(self) -> None:
        created = datetime(2026, 1, 15, 10, 30, 0)
        updated = datetime(2026, 2, 20, 14, 0, 0)
        repo = Repository(
            name="my-repo",
            url="/repos/my-repo",
            id=42,
            description="A test repo",
            default_branch="main",
            created_at=created,
            updated_at=updated,
        )

        result = repository_to_response(repo)

        assert result.id == 42
        assert result.name == "my-repo"
        assert result.url == "/repos/my-repo"
        assert result.description == "A test repo"
        assert result.default_branch == "main"
        assert result.created_at == "2026-01-15T10:30:00"
        assert result.updated_at == "2026-02-20T14:00:00"

    def test_none_id_defaults_to_zero(self) -> None:
        repo = Repository(name="new-repo", url="/repos/new-repo", id=None)

        result = repository_to_response(repo)

        assert result.id == 0

    def test_none_datetimes_become_none(self) -> None:
        repo = Repository(
            name="repo",
            url="/repos/repo",
            created_at=None,
            updated_at=None,
        )

        result = repository_to_response(repo)

        assert result.created_at is None
        assert result.updated_at is None


class TestSymbolToResponse:
    def test_converts_all_fields(self) -> None:
        symbol = Symbol(
            file_id=10,
            repository_id=1,
            name="my_function",
            kind=SymbolKind.FUNCTION,
            start_line=5,
            start_column=0,
            end_line=15,
            end_column=20,
            id=99,
            qualified_name="module.my_function",
            signature="def my_function(x: int) -> str",
        )

        result = symbol_to_response(symbol)

        assert result.id == 99
        assert result.name == "my_function"
        assert result.qualified_name == "module.my_function"
        assert result.kind == "function"
        assert result.start_line == 5
        assert result.start_column == 0
        assert result.end_line == 15
        assert result.end_column == 20
        assert result.signature == "def my_function(x: int) -> str"

    def test_none_id_defaults_to_zero(self) -> None:
        symbol = Symbol(
            file_id=10,
            repository_id=1,
            name="func",
            kind=SymbolKind.FUNCTION,
            start_line=1,
            start_column=0,
            end_line=1,
            end_column=10,
            id=None,
        )

        result = symbol_to_response(symbol)

        assert result.id == 0

    def test_none_optional_fields(self) -> None:
        symbol = Symbol(
            file_id=10,
            repository_id=1,
            name="func",
            kind=SymbolKind.METHOD,
            start_line=1,
            start_column=0,
            end_line=1,
            end_column=10,
            id=5,
            qualified_name=None,
            signature=None,
        )

        result = symbol_to_response(symbol)

        assert result.qualified_name is None
        assert result.signature is None


class TestReferenceToResponse:
    def test_converts_all_fields(self) -> None:
        ref = Reference(
            repository_id=1,
            source_file_id=10,
            source_line=42,
            source_column=8,
            source_end_column=20,
            reference_text="my_function",
            reference_type=ReferenceType.CALL,
            id=77,
            target_symbol_id=99,
        )

        result = reference_to_response(ref)

        assert result.id == 77
        assert result.reference_text == "my_function"
        assert result.reference_type == "call"
        assert result.source_line == 42
        assert result.source_column == 8
        assert result.target_symbol_id == 99

    def test_none_id_defaults_to_zero(self) -> None:
        ref = Reference(
            repository_id=1,
            source_file_id=10,
            source_line=1,
            source_column=0,
            source_end_column=5,
            reference_text="x",
            reference_type=ReferenceType.USAGE,
            id=None,
        )

        result = reference_to_response(ref)

        assert result.id == 0

    def test_none_target_symbol_id(self) -> None:
        ref = Reference(
            repository_id=1,
            source_file_id=10,
            source_line=1,
            source_column=0,
            source_end_column=5,
            reference_text="unknown",
            reference_type=ReferenceType.IMPORT,
            id=3,
            target_symbol_id=None,
        )

        result = reference_to_response(ref)

        assert result.target_symbol_id is None
