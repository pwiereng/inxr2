"""Tests for index_command utility functions and classes."""

import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from inxr2.adapters.cli.commands.index_command import (
    IndexingStats,
    _detect_language,
    _dict_to_reference,
    _dict_to_symbol,
    _filter_files_by_language,
    _shorten_path,
)
from inxr2.domain.value_objects import ReferenceType, SymbolKind


class TestShortenPath:
    """Tests for _shorten_path utility function."""

    def test_short_path_unchanged(self) -> None:
        """Short paths should be returned unchanged."""
        path = "src/main.py"
        assert _shorten_path(path, max_len=50) == path

    def test_path_at_max_length(self) -> None:
        """Path exactly at max length should be unchanged."""
        path = "a" * 50
        assert _shorten_path(path, max_len=50) == path

    def test_long_path_shortened(self) -> None:
        """Long paths should be shortened with ellipsis."""
        path = "very/long/path/to/some/deeply/nested/file.py"
        result = _shorten_path(path, max_len=20)
        assert result.startswith("...")
        assert result.endswith("nested/file.py")

    def test_two_part_path_unchanged(self) -> None:
        """Paths with only 2 parts should not be shortened."""
        path = "a" * 60 + "/" + "b" * 60  # Long but only 2 parts
        assert _shorten_path(path, max_len=50) == path

    def test_keeps_last_two_parts(self) -> None:
        """Shortened path should keep last two parts."""
        path = "one/two/three/four/five.py"
        result = _shorten_path(path, max_len=10)
        assert "four/five.py" in result


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


class TestFilterFilesByLanguage:
    """Tests for _filter_files_by_language utility function."""

    def test_include_all_text_files(self) -> None:
        """With include_all_text=True, should include all text files."""
        files = ["main.py", "README.md", "config.yaml", "image.png"]
        result = _filter_files_by_language(files, ["python"], include_all_text=True)
        # Should include text files, exclude binary
        assert "main.py" in result
        assert "README.md" in result
        assert "config.yaml" in result
        assert "image.png" not in result

    def test_filter_by_specific_languages(self) -> None:
        """With include_all_text=False, should only include specified languages."""
        files = ["main.py", "app.ts", "README.md", "style.css"]
        result = _filter_files_by_language(
            files, ["python", "typescript"], include_all_text=False
        )
        assert "main.py" in result
        assert "app.ts" in result
        assert "README.md" not in result
        assert "style.css" not in result

    def test_filter_python_only(self) -> None:
        """Should filter to Python files only."""
        files = ["main.py", "test.pyi", "app.ts", "index.js"]
        result = _filter_files_by_language(files, ["python"], include_all_text=False)
        assert result == ["main.py", "test.pyi"]

    def test_filter_javascript_only(self) -> None:
        """Should filter to JavaScript files only."""
        files = ["main.py", "app.js", "component.jsx", "index.mjs", "config.cjs"]
        result = _filter_files_by_language(
            files, ["javascript"], include_all_text=False
        )
        assert "app.js" in result
        assert "component.jsx" in result
        assert "index.mjs" in result
        assert "config.cjs" in result
        assert "main.py" not in result

    def test_empty_files_list(self) -> None:
        """Should handle empty file list."""
        result = _filter_files_by_language([], ["python"], include_all_text=True)
        assert result == []

    def test_unknown_language(self) -> None:
        """Should handle unknown language gracefully."""
        files = ["main.py", "app.rs"]
        result = _filter_files_by_language(files, ["rust"], include_all_text=False)
        # Rust not in predefined extensions, so nothing matches
        assert result == []


class TestIndexingStats:
    """Tests for IndexingStats dataclass."""

    def test_default_values(self) -> None:
        """Should have correct default values."""
        stats = IndexingStats()
        assert stats.files_total == 0
        assert stats.files_processed == 0
        assert stats.files_skipped == 0
        assert stats.files_failed == 0
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
        symbol = _dict_to_symbol(data, file_id=1, repository_id=2, commit_id=3)

        assert symbol.name == "my_function"
        assert symbol.kind == SymbolKind.FUNCTION
        assert symbol.file_id == 1
        assert symbol.repository_id == 2
        assert symbol.commit_id == 3
        assert symbol.start_line == 10
        assert symbol.end_line == 20

    def test_class_symbol(self) -> None:
        """Should convert class dict to Symbol."""
        data = {"name": "MyClass", "kind": "class", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1, commit_id=1)
        assert symbol.kind == SymbolKind.CLASS

    def test_method_symbol(self) -> None:
        """Should convert method dict to Symbol."""
        data = {"name": "my_method", "kind": "method", "start_line": 5}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1, commit_id=1)
        assert symbol.kind == SymbolKind.METHOD

    def test_interface_symbol(self) -> None:
        """Should convert interface dict to Symbol."""
        data = {"name": "IMyInterface", "kind": "interface", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1, commit_id=1)
        assert symbol.kind == SymbolKind.INTERFACE

    def test_constant_symbol(self) -> None:
        """Should convert constant dict to Symbol."""
        data = {"name": "MY_CONSTANT", "kind": "constant", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1, commit_id=1)
        assert symbol.kind == SymbolKind.CONSTANT

    def test_variable_symbol(self) -> None:
        """Should convert variable dict to Symbol."""
        data = {"name": "my_var", "kind": "variable", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1, commit_id=1)
        assert symbol.kind == SymbolKind.VARIABLE

    def test_type_alias_maps_to_namespace(self) -> None:
        """Type aliases should map to NAMESPACE."""
        data = {"name": "MyType", "kind": "type", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1, commit_id=1)
        assert symbol.kind == SymbolKind.NAMESPACE

    def test_unknown_kind_defaults_to_function(self) -> None:
        """Unknown kind should default to FUNCTION."""
        data = {"name": "something", "kind": "unknown_kind", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1, commit_id=1)
        assert symbol.kind == SymbolKind.FUNCTION

    def test_missing_kind_defaults_to_function(self) -> None:
        """Missing kind should default to FUNCTION."""
        data = {"name": "something", "start_line": 1}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1, commit_id=1)
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
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1, commit_id=1)
        assert symbol.qualified_name == "module.qualified_func"
        assert symbol.scope == "module"

    def test_default_line_values(self) -> None:
        """Should use defaults when line values missing."""
        data = {"name": "func"}
        symbol = _dict_to_symbol(data, file_id=1, repository_id=1, commit_id=1)
        assert symbol.start_line == 1
        assert symbol.start_column == 0
        assert symbol.end_line == 1
        assert symbol.end_column == 0


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
        ref = _dict_to_reference(data, source_file_id=1, repository_id=2, commit_id=3)

        assert ref.reference_type == ReferenceType.IMPORT
        assert ref.reference_text == "os"
        assert ref.source_line == 1
        assert ref.source_column == 7
        assert ref.source_file_id == 1
        assert ref.repository_id == 2
        assert ref.commit_id == 3

    def test_call_reference(self) -> None:
        """Should convert call reference dict."""
        data = {"type": "call", "text": "my_function", "source_line": 10}
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1, commit_id=1)
        assert ref.reference_type == ReferenceType.CALL

    def test_usage_reference(self) -> None:
        """Should convert usage reference dict."""
        data = {"type": "usage", "text": "my_var", "source_line": 5}
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1, commit_id=1)
        assert ref.reference_type == ReferenceType.USAGE

    def test_unknown_type_defaults_to_usage(self) -> None:
        """Unknown type should default to USAGE."""
        data = {"type": "unknown", "text": "something", "source_line": 1}
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1, commit_id=1)
        assert ref.reference_type == ReferenceType.USAGE

    def test_missing_type_defaults_to_usage(self) -> None:
        """Missing type should default to USAGE."""
        data = {"text": "something", "source_line": 1}
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1, commit_id=1)
        assert ref.reference_type == ReferenceType.USAGE

    def test_source_end_column_calculated(self) -> None:
        """source_end_column should be calculated from column + text length."""
        data = {"text": "hello", "source_line": 1, "source_column": 10}
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1, commit_id=1)
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
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1, commit_id=1)
        assert ref.metadata == {"from_module": "pathlib"}

    def test_no_from_module_metadata_is_none(self) -> None:
        """Without from_module, metadata should be None."""
        data = {"type": "import", "text": "os", "source_line": 1}
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1, commit_id=1)
        assert ref.metadata is None

    def test_default_values(self) -> None:
        """Should use defaults when values missing (except required text)."""
        data = {"text": "some_ref"}  # text is required by Reference entity
        ref = _dict_to_reference(data, source_file_id=1, repository_id=1, commit_id=1)
        assert ref.source_line == 1
        assert ref.source_column == 0
        assert ref.reference_text == "some_ref"
        assert ref.reference_type == ReferenceType.USAGE  # default type


class TestIndexCommandIntegration:
    """Integration tests for index commands using CLI runner."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def test_repo_path(self) -> Path:
        """Get path to a test repository (inxr in test-repos)."""
        # Use the inxr test repo since it's small
        test_repo = Path("/repos/test-repos/inxr")
        if test_repo.exists():
            return test_repo
        # Fallback for local development
        return Path(__file__).parent.parent.parent.parent

    def test_index_status_on_indexed_repo(
        self, runner: CliRunner, test_repo_path: Path
    ) -> None:
        """Test index status shows correct info for indexed repo."""
        from inxr2.cli import main

        result = runner.invoke(main, ["index", "status", "--path", str(test_repo_path)])
        # Should show repository info (may or may not be indexed)
        assert result.exit_code == 0
        assert "Repository" in result.output

    def test_index_full_requires_path_or_config(self, runner: CliRunner) -> None:
        """Test that index full requires either --path or --config."""
        from inxr2.cli import main

        result = runner.invoke(main, ["index", "full"])
        assert result.exit_code != 0
        assert "path" in result.output.lower() or "config" in result.output.lower()

    def test_index_full_validates_git_repo(self, runner: CliRunner) -> None:
        """Test that index full validates the path is a git repo."""
        from inxr2.cli import main

        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(main, ["index", "full", "--path", tmpdir])
            assert result.exit_code != 0
            assert ".git" in result.output or "git" in result.output.lower()

    def test_index_incremental_requires_path_or_config(self, runner: CliRunner) -> None:
        """Test that index incremental requires either --path or --config."""
        from inxr2.cli import main

        result = runner.invoke(main, ["index", "incremental"])
        assert result.exit_code != 0
        assert "path" in result.output.lower() or "config" in result.output.lower()


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
        from datetime import datetime, timezone

        from inxr2.adapters.cli.commands.index_command import _to_naive_utc

        # Create a datetime with UTC+5 timezone
        dt = datetime(2025, 1, 1, 17, 0, 0, tzinfo=timezone.utc)
        result = _to_naive_utc(dt)
        assert result is not None
        assert result.tzinfo is None
        assert result.hour == 17  # Should be same since input was UTC
