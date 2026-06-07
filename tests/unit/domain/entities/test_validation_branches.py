"""Validation (__post_init__) branch coverage for domain entities."""

import pytest

from inxr2.domain.entities import File, IndexStatus, Reference, Symbol
from inxr2.domain.value_objects import ReferenceType, SymbolKind


def _symbol(
    *,
    name: str = "fn",
    start_line: int = 1,
    start_column: int = 0,
    end_line: int = 2,
    end_column: int = 0,
) -> Symbol:
    return Symbol(
        file_id=1,
        repository_id=1,
        name=name,
        kind=SymbolKind.FUNCTION,
        start_line=start_line,
        start_column=start_column,
        end_line=end_line,
        end_column=end_column,
    )


def _reference(
    *,
    reference_text: str = "ref",
    source_line: int = 1,
    source_column: int = 0,
    source_end_column: int = 5,
    resolution_confidence: float = 1.0,
) -> Reference:
    return Reference(
        repository_id=1,
        source_file_id=1,
        source_line=source_line,
        source_column=source_column,
        source_end_column=source_end_column,
        reference_text=reference_text,
        reference_type=ReferenceType.CALL,
        resolution_confidence=resolution_confidence,
    )


def _file(
    *,
    path: str = "src/main.py",
    size_bytes: int = 10,
    line_count: int | None = None,
) -> File:
    return File(
        repository_id=1,
        path=path,
        content_hash="a" * 40,
        size_bytes=size_bytes,
        line_count=line_count,
    )


def _index_status(
    *,
    branch: str = "main",
    indexing_status: str = "pending",
    total_commits_indexed: int = 0,
    total_files_indexed: int = 0,
    total_symbols_indexed: int = 0,
    total_references_indexed: int = 0,
    error_count: int = 0,
) -> IndexStatus:
    return IndexStatus(
        repository_id=1,
        branch=branch,
        indexing_status=indexing_status,
        total_commits_indexed=total_commits_indexed,
        total_files_indexed=total_files_indexed,
        total_symbols_indexed=total_symbols_indexed,
        total_references_indexed=total_references_indexed,
        error_count=error_count,
    )


class TestSymbolValidation:
    def test_empty_name(self) -> None:
        with pytest.raises(ValueError, match="name cannot be empty"):
            _symbol(name="")

    def test_start_line_below_one(self) -> None:
        with pytest.raises(ValueError, match="Start line must be"):
            _symbol(start_line=0, end_line=0)

    def test_start_column_negative(self) -> None:
        with pytest.raises(ValueError, match="Start column must be"):
            _symbol(start_column=-1)

    def test_end_line_before_start(self) -> None:
        with pytest.raises(ValueError, match="cannot be before"):
            _symbol(start_line=5, end_line=3)

    def test_end_column_before_start_same_line(self) -> None:
        with pytest.raises(ValueError, match="End column"):
            _symbol(start_line=1, end_line=1, start_column=5, end_column=2)

    def test_valid(self) -> None:
        assert _symbol().name == "fn"


class TestReferenceValidation:
    def test_empty_text(self) -> None:
        with pytest.raises(ValueError, match="Reference text cannot be empty"):
            _reference(reference_text="")

    def test_source_line_below_one(self) -> None:
        with pytest.raises(ValueError, match="Source line must be"):
            _reference(source_line=0)

    def test_source_column_negative(self) -> None:
        with pytest.raises(ValueError, match="Source column must be"):
            _reference(source_column=-1)

    def test_end_column_before_start(self) -> None:
        with pytest.raises(ValueError, match="cannot be before"):
            _reference(source_column=10, source_end_column=2)

    def test_confidence_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            _reference(resolution_confidence=1.5)

    def test_valid(self) -> None:
        assert _reference().reference_text == "ref"


class TestFileValidation:
    def test_empty_path(self) -> None:
        with pytest.raises(ValueError, match="File path cannot be empty"):
            _file(path="")

    def test_negative_size(self) -> None:
        with pytest.raises(ValueError, match="File size cannot be negative"):
            _file(size_bytes=-1)

    def test_negative_line_count(self) -> None:
        with pytest.raises(ValueError, match="Line count cannot be negative"):
            _file(line_count=-1)

    def test_valid(self) -> None:
        assert _file().path == "src/main.py"


class TestIndexStatusValidation:
    def test_empty_branch(self) -> None:
        with pytest.raises(ValueError, match="Branch cannot be empty"):
            _index_status(branch="")

    def test_invalid_status(self) -> None:
        with pytest.raises(ValueError, match="Invalid indexing status"):
            _index_status(indexing_status="bogus")

    def test_negative_commits(self) -> None:
        with pytest.raises(ValueError, match="Total commits cannot be negative"):
            _index_status(total_commits_indexed=-1)

    def test_negative_files(self) -> None:
        with pytest.raises(ValueError, match="Total files cannot be negative"):
            _index_status(total_files_indexed=-1)

    def test_negative_symbols(self) -> None:
        with pytest.raises(ValueError, match="Total symbols cannot be negative"):
            _index_status(total_symbols_indexed=-1)

    def test_negative_references(self) -> None:
        with pytest.raises(ValueError, match="Total references cannot be negative"):
            _index_status(total_references_indexed=-1)

    def test_negative_error_count(self) -> None:
        with pytest.raises(ValueError, match="Error count cannot be negative"):
            _index_status(error_count=-1)

    def test_valid(self) -> None:
        assert _index_status().branch == "main"
