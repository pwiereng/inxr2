"""Tests for index_command utility functions and classes."""

import csv
import tempfile
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path

import pytest
from click.testing import CliRunner
from git import Repo

from inxr2.adapters.cli.commands.index_command import (
    IndexingStats,
    _detect_language,
    _dict_to_reference,
    _dict_to_symbol,
    _write_csv_log,
)
from inxr2.domain.value_objects import ReferenceType, SymbolKind


class TestDetectLanguage:
    """Tests for _detect_language utility function."""

    def test_detect_python(self) -> None:
        """Should detect Python files."""
        assert _detect_language("main.py") == "python"
        assert _detect_language("src/utils.pyi") == "python"

    def test_detect_typescript(self) -> None:
        """Should detect TypeScript files."""
        assert _detect_language("app.ts") == "typescript"
        assert _detect_language("component.tsx") == "typescript"

    def test_detect_javascript(self) -> None:
        """Should detect JavaScript files."""
        assert _detect_language("index.js") == "javascript"
        assert _detect_language("app.jsx") == "javascript"

    def test_detect_markdown(self) -> None:
        """Should detect Markdown files."""
        assert _detect_language("README.md") == "markdown"

    def test_detect_unknown(self) -> None:
        """Should return None for unknown file types."""
        assert _detect_language("file.xyz") is None
        assert _detect_language("file.unknown123") is None


class TestIndexingStats:
    """Tests for IndexingStats dataclass."""

    def test_default_values(self) -> None:
        """Should have correct default values."""
        stats = IndexingStats()
        assert stats.files_total == 0
        assert stats.files_processed == 0
        assert stats.files_skipped == 0
        assert stats.files_failed == 0
        assert stats.files_at_head == 0
        assert stats.symbols_found == 0
        assert stats.references_found == 0
        assert stats.references_resolved == 0
        assert stats.errors == []

    def test_files_succeeded_property(self) -> None:
        """files_succeeded should be processed minus failed."""
        stats = IndexingStats(files_processed=100, files_failed=10)
        assert stats.files_succeeded == 90

    def test_files_succeeded_never_negative(self) -> None:
        """files_succeeded should never be negative."""
        stats = IndexingStats(files_processed=5, files_failed=10)
        assert stats.files_succeeded == 0

    def test_errors_list_mutable(self) -> None:
        """errors list should be mutable."""
        stats = IndexingStats()
        stats.errors.append("Error 1")
        stats.errors.append("Error 2")
        assert len(stats.errors) == 2

    def test_stats_can_be_updated(self) -> None:
        """Stats should be updateable."""
        stats = IndexingStats()
        stats.files_processed = 50
        stats.symbols_found = 100
        assert stats.files_processed == 50
        assert stats.symbols_found == 100


class TestDictToSymbol:
    """Tests for _dict_to_symbol converter function."""

    def test_basic_function_symbol(self) -> None:
        """Should convert basic function dict to Symbol."""
        data = {
            "name": "my_function",
            "kind": "function",
            "start_line": 10,
            "start_column": 0,
            "end_line": 20,
            "end_column": 0,
        }
        symbol = _dict_to_symbol(data, file_id=1, repository_id=2)

        assert symbol.name == "my_function"
        assert symbol.kind == SymbolKind.FUNCTION
        assert symbol.file_id == 1
        assert symbol.repository_id == 2
        assert symbol.start_line == 10
        assert symbol.end_line == 20

    def test_class_symbol(self) -> None:
        """Should convert class dict to Symbol."""
        data = {"name": "MyClass", "kind": "class", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.CLASS

    def test_method_symbol(self) -> None:
        """Should convert method dict to Symbol."""
        data = {"name": "my_method", "kind": "method", "start_line": 5}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.METHOD

    def test_interface_symbol(self) -> None:
        """Should convert interface dict to Symbol."""
        data = {"name": "IMyInterface", "kind": "interface", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.INTERFACE

    def test_constant_symbol(self) -> None:
        """Should convert constant dict to Symbol."""
        data = {"name": "MY_CONSTANT", "kind": "constant", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.CONSTANT

    def test_variable_symbol(self) -> None:
        """Should convert variable dict to Symbol."""
        data = {"name": "my_var", "kind": "variable", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.VARIABLE

    def test_type_alias_maps_to_namespace(self) -> None:
        """Type aliases should map to NAMESPACE."""
        data = {"name": "MyType", "kind": "type", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.NAMESPACE

    def test_unknown_kind_defaults_to_function(self) -> None:
        """Unknown kind should default to FUNCTION."""
        data = {"name": "something", "kind": "unknown_kind", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.FUNCTION

    def test_missing_kind_defaults_to_function(self) -> None:
        """Missing kind should default to FUNCTION."""
        data = {"name": "something", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.FUNCTION

    def test_optional_fields(self) -> None:
        """Should handle optional fields."""
        data = {
            "name": "qualified_func",
            "kind": "function",
            "start_line": 1,
            "qualified_name": "module.qualified_func",
            "scope": "module",
        }
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.qualified_name == "module.qualified_func"
        assert symbol.scope == "module"

    def test_default_line_values(self) -> None:
        """Should use defaults when line values missing."""
        data = {"name": "func"}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.start_line == 1
        assert symbol.start_column == 0
        assert symbol.end_line == 1
        assert symbol.end_column == 0

    # C-specific symbol kinds
    def test_struct_symbol(self) -> None:
        """Should convert struct dict to Symbol."""
        data = {"name": "MyStruct", "kind": "struct", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.STRUCT

    def test_union_symbol(self) -> None:
        """Should convert union dict to Symbol."""
        data = {"name": "MyUnion", "kind": "union", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.UNION

    def test_typedef_symbol(self) -> None:
        """Should convert typedef dict to Symbol."""
        data = {"name": "MyType", "kind": "typedef", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.TYPEDEF

    def test_macro_symbol(self) -> None:
        """Should convert macro dict to Symbol."""
        data = {"name": "MY_MACRO", "kind": "macro", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.MACRO

    def test_enum_symbol(self) -> None:
        """Should convert enum dict to Symbol."""
        data = {"name": "MyEnum", "kind": "enum", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.ENUM

    def test_enum_value_symbol(self) -> None:
        """Should convert enum_value dict to Symbol."""
        data = {"name": "ENUM_VALUE", "kind": "enum_value", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.ENUM_VALUE

    def test_struct_field_symbol(self) -> None:
        """Should convert struct_field dict to Symbol."""
        data = {"name": "field_name", "kind": "struct_field", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.STRUCT_FIELD

    def test_union_field_symbol(self) -> None:
        """Should convert union_field dict to Symbol."""
        data = {"name": "field_name", "kind": "union_field", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1)
        assert symbol.kind == SymbolKind.UNION_FIELD


class TestDictToReference:
    """Tests for _dict_to_reference converter function."""

    def test_basic_import_reference(self) -> None:
        """Should convert import reference dict."""
        data = {
            "type": "import",
            "text": "os",
            "source_line": 1,
            "source_column": 7,
        }
        ref = _dict_to_reference(data, source_file_id=1, repository_id=2)

        assert ref.reference_type == ReferenceType.IMPORT
        assert ref.reference_text == "os"
        assert ref.source_line == 1
        assert ref.source_column == 7
        assert ref.source_file_id == 1
        assert ref.repository_id == 2

    def test_call_reference(self) -> None:
        """Should convert call reference dict."""
        data = {"type": "call", "text": "my_function", "source_line": 10}
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1)
        assert ref.reference_type == ReferenceType.CALL

    def test_usage_reference(self) -> None:
        """Should convert usage reference dict."""
        data = {"type": "usage", "text": "my_var", "source_line": 5}
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1)
        assert ref.reference_type == ReferenceType.USAGE

    def test_unknown_type_defaults_to_usage(self) -> None:
        """Unknown type should default to USAGE."""
        data = {"type": "unknown", "text": "something", "source_line": 1}
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1)
        assert ref.reference_type == ReferenceType.USAGE

    def test_missing_type_defaults_to_usage(self) -> None:
        """Missing type should default to USAGE."""
        data = {"text": "something", "source_line": 1}
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1)
        assert ref.reference_type == ReferenceType.USAGE

    def test_source_end_column_calculated(self) -> None:
        """source_end_column should be calculated from column + text length."""
        data = {"text": "hello", "source_line": 1, "source_column": 10}
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1)
        assert ref.source_column == 10
        assert ref.source_end_column == 15  # 10 + len("hello")

    def test_from_module_metadata(self) -> None:
        """Should include from_module in metadata."""
        data = {
            "type": "import",
            "text": "Path",
            "source_line": 1,
            "from_module": "pathlib",
        }
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1)
        assert ref.metadata == {"from_module": "pathlib"}

    def test_no_from_module_metadata_is_none(self) -> None:
        """Without from_module, metadata should be None."""
        data = {"type": "import", "text": "os", "source_line": 1}
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1)
        assert ref.metadata is None

    def test_default_values(self) -> None:
        """Should use defaults when values missing (except required text)."""
        data = {"text": "some_ref"}  # text is required by Reference entity
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1)
        assert ref.source_line == 1
        assert ref.source_column == 0
        assert ref.reference_text == "some_ref"
        assert ref.reference_type == ReferenceType.USAGE  # default type

    # C-specific reference types
    def test_include_reference(self) -> None:
        """Should convert include reference dict (C/C++ #include)."""
        data = {"type": "include", "text": "stdio.h", "source_line": 1}
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1)
        assert ref.reference_type == ReferenceType.INCLUDE

    def test_type_annotation_reference(self) -> None:
        """Should convert type_annotation reference dict."""
        data = {"type": "type_annotation", "text": "MyStruct", "source_line": 10}
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1)
        assert ref.reference_type == ReferenceType.TYPE_ANNOTATION


class TestIndexCommandIntegration:
    """Integration tests for index commands using CLI runner.

    These tests use an isolated PostgreSQL test database. The
    isolated_cli_runner fixture from conftest.py provides database
    isolation via DATABASE_URL env var.
    """

    @pytest.fixture
    def runner(self, isolated_cli_runner: CliRunner) -> CliRunner:
        """Use the isolated CLI runner with test database."""
        return isolated_cli_runner

    @pytest.fixture
    def temp_git_repo(self, tmp_path: Path) -> Path:
        """Create a temporary git repository for testing.

        This fixture creates an isolated git repo with a single commit,
        making tests independent of external test repositories.
        Uses unique repo name to avoid database collisions.
        """
        repo_path = tmp_path / "idx-cmd-test-repo"
        repo_path.mkdir()

        # Initialize repo
        repo = Repo.init(repo_path, initial_branch="main")

        # Configure git user for commits
        repo.config_writer().set_value("user", "name", "Test User").release()
        repo.config_writer().set_value("user", "email", "test@example.com").release()

        # Create initial commit
        readme = repo_path / "README.md"
        readme.write_text("# Test Repository\n")

        repo.index.add(["README.md"])
        repo.index.commit("Initial commit")

        return repo_path

    def test_index_status_on_git_repo(
        self, runner: CliRunner, temp_git_repo: Path
    ) -> None:
        """Test index status shows correct info for a git repository."""
        from inxr2.cli import main

        result = runner.invoke(main, ["index", "status", "--path", str(temp_git_repo)])
        # Should show repository info (will show "not indexed" for new repo)
        assert result.exit_code == 0
        assert "Repository" in result.output

    def test_index_requires_path_or_config(self, runner: CliRunner) -> None:
        """Test that index requires either --path or --config."""
        from inxr2.cli import main

        result = runner.invoke(main, ["index"])
        assert result.exit_code != 0
        assert "path" in result.output.lower() or "config" in result.output.lower()

    def test_index_validates_git_repo(self, runner: CliRunner) -> None:
        """Test that index validates the path is a git repo."""
        from inxr2.cli import main

        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(main, ["index", "--path", tmpdir])
            assert result.exit_code != 0
            assert ".git" in result.output or "git" in result.output.lower()


class TestTimeUtilities:
    """Tests for time-related utility functions."""

    def test_utc_now_returns_naive_datetime(self) -> None:
        """_utc_now should return naive UTC datetime."""
        from inxr2.adapters.cli.commands.index_command import _utc_now

        now = _utc_now()
        assert now.tzinfo is None

    def test_to_naive_utc_with_none(self) -> None:
        """_to_naive_utc should return None for None input."""
        from inxr2.adapters.cli.commands.index_command import _to_naive_utc

        assert _to_naive_utc(None) is None

    def test_to_naive_utc_with_naive_datetime(self) -> None:
        """_to_naive_utc should return naive datetime unchanged."""
        from datetime import datetime

        from inxr2.adapters.cli.commands.index_command import _to_naive_utc

        dt = datetime(2025, 1, 1, 12, 0, 0)
        result = _to_naive_utc(dt)
        assert result == dt
        assert result.tzinfo is None

    def test_to_naive_utc_with_aware_datetime(self) -> None:
        """_to_naive_utc should convert aware datetime to naive UTC."""
        from datetime import datetime

        from inxr2.adapters.cli.commands.index_command import _to_naive_utc

        # Create a datetime with UTC timezone
        dt = datetime(2025, 1, 1, 17, 0, 0, tzinfo=UTC)
        result = _to_naive_utc(dt)
        assert result is not None
        assert result.tzinfo is None
        assert result.hour == 17  # Should be same since input was UTC


@dataclass
class _FakeResponse:
    """Minimal stub matching IndexRepositoryResponse fields used by _write_csv_log."""

    repository_name: str = "test-repo"
    branch: str = "main"
    commits_indexed: int = 5
    files_at_head: int = 100
    files_processed: int = 80
    files_failed: int = 2
    file_versions_new: int = 10
    file_versions_cached: int = 8
    symbols_found: int = 400
    references_found: int = 300
    references_resolved: int = 250
    elapsed_seconds: float = 12.34
    indexing_seconds: float = 10.12
    resolving_seconds: float = 2.22
    lines_indexed: int = 5000


class TestWriteCsvLog:
    """Tests for _write_csv_log helper."""

    def test_creates_file_with_header_and_data(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """First call should create file with header row + one data row."""
        monkeypatch.chdir(tmp_path)
        _write_csv_log(_FakeResponse())

        log = tmp_path / "index.log"
        assert log.exists()

        rows = list(csv.reader(log.open()))
        assert len(rows) == 2
        assert rows[0][0] == "timestamp"
        assert rows[0][-1] == "db_size_added_mb"
        assert rows[1][1] == "test-repo"
        assert rows[1][2] == "main"

    def test_appends_without_duplicate_headers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Second call should append data row without repeating headers."""
        monkeypatch.chdir(tmp_path)
        _write_csv_log(_FakeResponse())
        _write_csv_log(_FakeResponse(branch="dev", commits_indexed=10))

        rows = list(csv.reader((tmp_path / "index.log").open()))
        assert len(rows) == 3
        # Only one header row
        assert rows[0][0] == "timestamp"
        assert rows[1][0] != "timestamp"
        assert rows[2][0] != "timestamp"
        # Second row has different branch
        assert rows[2][2] == "dev"

    def test_numeric_fields_correct(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Numeric fields should match response values."""
        monkeypatch.chdir(tmp_path)
        resp = _FakeResponse(
            commits_indexed=7,
            files_at_head=200,
            files_processed=150,
            files_failed=3,
            file_versions_new=30,
            file_versions_cached=17,
            symbols_found=900,
            references_found=800,
            references_resolved=700,
            elapsed_seconds=45.678,
            indexing_seconds=30.123,
            resolving_seconds=15.555,
            lines_indexed=12000,
        )
        _write_csv_log(resp)

        rows = list(csv.reader((tmp_path / "index.log").open()))
        data = rows[1]
        # columns: ts, repo, branch, commits, files_at_head, processed, failed,
        #          file_versions_new, file_versions_cached, symbols, refs, resolved,
        #          elapsed, indexing, resolving, lines
        assert data[3] == "7"
        assert data[4] == "200"
        assert data[5] == "150"
        assert data[6] == "3"
        assert data[7] == "30"
        assert data[8] == "17"
        assert data[9] == "900"
        assert data[10] == "800"
        assert data[11] == "700"
        assert data[12] == "45.7"  # rounded to 1 decimal
        assert data[13] == "30.1"
        assert data[14] == "15.6"
        assert data[15] == "12000"

    def test_does_not_crash_on_write_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Write failures should be silently swallowed."""
        # Point to a non-existent directory so open() fails
        monkeypatch.chdir(tmp_path)
        bad_dir = tmp_path / "no_such_dir"
        monkeypatch.setattr(
            "inxr2.adapters.cli.commands.index_command.Path",
            lambda _: bad_dir / "index.log",
        )
        # Should not raise
        _write_csv_log(_FakeResponse())

    def test_has_18_columns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CSV should have exactly 18 columns (including db_size_mb, db_size_added_mb)."""
        monkeypatch.chdir(tmp_path)
        _write_csv_log(_FakeResponse())

        rows = list(csv.reader((tmp_path / "index.log").open()))
        assert len(rows[0]) == 18
        assert len(rows[1]) == 18
