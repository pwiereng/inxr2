"""Tests for MCP tool handlers using FakeInxr2Client."""

from typing import Any

import pytest

from src.errors import McpToolError
from src.tools import (
    explain_symbol,
    find_dead_code,
    find_references,
    get_change_impact,
    get_file_structure,
    go_to_definition,
    list_repositories,
    review_helper,
    search_code,
    search_symbols,
)
from tests.fake_client import FakeInxr2Client

FRONTEND_URL = "http://localhost:5173"

# --- find_references ---


class TestFindReferences:
    async def test_finds_references_by_name(self) -> None:
        client = FakeInxr2Client()
        client.add_symbol(1, "MyClass", kind="class", file_path="src/models.py")
        client.add_reference(
            1, "src/app.py", 10, "import", "from models import MyClass"
        )
        client.add_reference(1, "src/views.py", 25, "usage", "obj = MyClass()")

        result = await find_references.handle(client, {"name": "MyClass"})

        assert "2 found" in result
        assert "src/app.py:10" in result
        assert "src/views.py:25" in result

    async def test_filters_by_ref_type(self) -> None:
        client = FakeInxr2Client()
        client.add_symbol(1, "MyClass", kind="class")
        client.add_reference(1, "src/app.py", 10, "import", "import MyClass")
        client.add_reference(1, "src/views.py", 25, "call", "MyClass()")

        result = await find_references.handle(
            client, {"name": "MyClass", "ref_type": "import"}
        )

        assert "1 found" in result
        assert "src/app.py:10" in result
        assert "src/views.py" not in result

    async def test_filters_by_repository(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "repo-a")
        client.add_repository(2, "repo-b")
        client.add_symbol(1, "helper", repository_id=1)
        client.add_symbol(2, "helper", repository_id=2)
        client.add_reference(1, "src/a.py", 5, "usage", "helper()")
        client.add_reference(2, "src/b.py", 10, "usage", "helper()")

        result = await find_references.handle(
            client, {"name": "helper", "repository": "repo-a"}
        )

        assert "src/a.py:5" in result
        # repo-b symbols filtered out by repository_id
        assert "src/b.py" not in result

    async def test_no_matches(self) -> None:
        client = FakeInxr2Client()
        result = await find_references.handle(client, {"name": "NonExistent"})
        assert "No symbols found" in result

    async def test_commit_requires_repository(self) -> None:
        client = FakeInxr2Client()
        with pytest.raises(McpToolError, match="'commit' requires 'repository'"):
            await find_references.handle(client, {"name": "Foo", "commit": "abc123"})

    async def test_includes_browse_urls_with_repository(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(1, "MyClass", kind="class", repository_id=1)
        client.add_reference(1, "src/app.py", 10, "import", "import MyClass")

        result = await find_references.handle(
            client,
            {"name": "MyClass", "repository": "my-repo"},
            frontend_url=FRONTEND_URL,
        )

        assert "http://localhost:5173/browse/my-repo/src/app.py?line=10" in result

    async def test_no_browse_urls_without_repository(self) -> None:
        client = FakeInxr2Client()
        client.add_symbol(1, "MyClass", kind="class")
        client.add_reference(1, "src/app.py", 10, "import", "import MyClass")

        result = await find_references.handle(
            client, {"name": "MyClass"}, frontend_url=FRONTEND_URL
        )

        assert "http://localhost:5173" not in result

    async def test_no_browse_urls_without_frontend_url(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(1, "MyClass", kind="class", repository_id=1)
        client.add_reference(1, "src/app.py", 10, "import", "import MyClass")

        result = await find_references.handle(
            client, {"name": "MyClass", "repository": "my-repo"}
        )

        assert "http://" not in result


# --- go_to_definition ---


class TestGoToDefinition:
    async def test_finds_definition(self) -> None:
        client = FakeInxr2Client()
        client.add_symbol(
            1,
            "process_data",
            kind="function",
            file_path="src/pipeline.py",
            start_line=42,
            signature="def process_data(input: list) -> dict",
            docstring="Process input data and return results.",
        )

        result = await go_to_definition.handle(client, {"name": "process_data"})

        assert "src/pipeline.py" in result
        assert "42" in result
        assert "function" in result
        assert "def process_data" in result
        assert "Process input data" in result

    async def test_filters_by_file_path(self) -> None:
        client = FakeInxr2Client()
        client.add_symbol(1, "Config", file_path="src/config.py", start_line=10)
        client.add_symbol(2, "Config", file_path="tests/config.py", start_line=5)

        result = await go_to_definition.handle(
            client, {"name": "Config", "file_path": "src/config.py"}
        )

        assert "src/config.py" in result
        assert "tests/config.py" not in result

    async def test_no_definition_found(self) -> None:
        client = FakeInxr2Client()
        result = await go_to_definition.handle(client, {"name": "Ghost"})
        assert "No definition found" in result

    async def test_commit_requires_repository(self) -> None:
        client = FakeInxr2Client()
        with pytest.raises(McpToolError, match="'commit' requires 'repository'"):
            await go_to_definition.handle(client, {"name": "Foo", "commit": "abc123"})

    async def test_multiple_definitions(self) -> None:
        client = FakeInxr2Client()
        client.add_symbol(1, "Handler", file_path="src/a.py", start_line=10)
        client.add_symbol(2, "Handler", file_path="src/b.py", start_line=20)

        result = await go_to_definition.handle(client, {"name": "Handler"})

        assert "2 found" in result
        assert "src/a.py" in result
        assert "src/b.py" in result

    async def test_includes_browse_urls_with_repository(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1,
            "MyFunc",
            kind="function",
            file_path="src/lib.py",
            start_line=42,
            repository_id=1,
        )

        result = await go_to_definition.handle(
            client,
            {"name": "MyFunc", "repository": "my-repo"},
            frontend_url=FRONTEND_URL,
        )

        assert "http://localhost:5173/browse/my-repo/src/lib.py?line=42" in result

    async def test_includes_browse_urls_without_repository(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "auto-repo")
        client.add_symbol(
            1, "MyFunc", kind="function", file_path="src/lib.py", repository_id=1
        )

        result = await go_to_definition.handle(
            client, {"name": "MyFunc"}, frontend_url=FRONTEND_URL
        )

        assert "http://localhost:5173/browse/auto-repo/src/lib.py?line=1" in result


# --- search_symbols ---


class TestSearchSymbols:
    async def test_search_by_query(self) -> None:
        client = FakeInxr2Client()
        client.add_symbol(1, "SearchService", kind="class", file_path="src/search.py")
        client.add_symbol(2, "search_index", kind="function", file_path="src/index.py")
        client.add_symbol(3, "unrelated", kind="function", file_path="src/other.py")

        result = await search_symbols.handle(client, {"query": "search"})

        assert "2 shown" in result
        assert "SearchService" in result
        assert "search_index" in result
        assert "unrelated" not in result

    async def test_filter_by_kind(self) -> None:
        client = FakeInxr2Client()
        client.add_symbol(1, "SearchService", kind="class")
        client.add_symbol(2, "search_index", kind="function")

        result = await search_symbols.handle(
            client, {"query": "search", "kind": "class"}
        )

        assert "SearchService" in result
        assert "search_index" not in result

    async def test_respects_limit(self) -> None:
        client = FakeInxr2Client()
        for i in range(10):
            client.add_symbol(i, f"item_{i}", kind="function")

        result = await search_symbols.handle(client, {"query": "item", "limit": 3})

        assert "3 shown" in result
        assert "of 10 total" in result

    async def test_no_results(self) -> None:
        client = FakeInxr2Client()
        result = await search_symbols.handle(client, {"query": "nothing"})
        assert "No symbols found" in result

    async def test_commit_requires_repository(self) -> None:
        client = FakeInxr2Client()
        with pytest.raises(McpToolError, match="'commit' requires 'repository'"):
            await search_symbols.handle(client, {"query": "Foo", "commit": "abc123"})

    async def test_includes_browse_urls_with_repository(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1,
            "MyClass",
            kind="class",
            file_path="src/models.py",
            start_line=10,
            repository_id=1,
        )

        result = await search_symbols.handle(
            client,
            {"query": "MyClass", "repository": "my-repo"},
            frontend_url=FRONTEND_URL,
        )

        assert "http://localhost:5173/browse/my-repo/src/models.py?line=10" in result

    async def test_includes_browse_urls_without_repository(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "auto-repo")
        client.add_symbol(
            1,
            "MyClass",
            kind="class",
            file_path="src/models.py",
            start_line=5,
            repository_id=1,
        )

        result = await search_symbols.handle(
            client, {"query": "MyClass"}, frontend_url=FRONTEND_URL
        )

        assert "http://localhost:5173/browse/auto-repo/src/models.py?line=5" in result

    async def test_browse_urls_include_branch(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1, "MyClass", kind="class", file_path="src/models.py", repository_id=1
        )

        result = await search_symbols.handle(
            client,
            {"query": "MyClass", "repository": "my-repo", "branch": "develop"},
            frontend_url=FRONTEND_URL,
        )

        assert "branch=develop" in result


# Bug #385 — MCP-level regression: kind:interface finds Swift protocol symbols


class TestSearchSymbolsKindInterface:
    """MCP-level regression tests for kind='interface' matching Swift protocols (#385).

    FakeInxr2Client now applies KIND_ALIASES so this exercises the full
    search_symbols handler path, not just the backend layer.
    """

    async def test_kind_interface_returns_protocol_symbol(self) -> None:
        """search_symbols with kind=interface must return Swift protocol symbols."""
        client = FakeInxr2Client()
        client.add_symbol(
            1, "Codable", kind="protocol", file_path="Sources/Proto.swift"
        )
        client.add_symbol(2, "Drawable", kind="interface", file_path="src/iface.kt")
        client.add_symbol(3, "helper", kind="function", file_path="src/helper.py")

        result = await search_symbols.handle(client, {"query": "", "kind": "interface"})

        assert "Codable" in result
        assert "Drawable" in result
        assert "helper" not in result

    async def test_kind_interface_excludes_other_kinds(self) -> None:
        """kind=interface must not return functions or classes."""
        client = FakeInxr2Client()
        client.add_symbol(1, "MyProtocol", kind="protocol", file_path="src/proto.swift")
        client.add_symbol(2, "MyClass", kind="class", file_path="src/cls.py")

        result = await search_symbols.handle(client, {"query": "", "kind": "interface"})

        assert "MyProtocol" in result
        assert "MyClass" not in result


# --- search_code ---


class TestSearchCode:
    async def test_search_returns_results(self) -> None:
        client = FakeInxr2Client()
        client.add_search_result(
            "src/main.py", 15, "def connect_database():", "my-repo"
        )

        result = await search_code.handle(client, {"query": "connect_database"})

        assert "1 results" in result
        assert "my-repo:src/main.py:15" in result
        assert "connect_database" in result

    async def test_uses_headline_over_content(self) -> None:
        client = FakeInxr2Client()
        client.add_search_result(
            "src/main.py",
            10,
            "some raw content",
            headline="<b>highlighted</b> result",
        )

        result = await search_code.handle(client, {"query": "test"})

        assert "<b>highlighted</b> result" in result

    async def test_no_results(self) -> None:
        client = FakeInxr2Client()
        result = await search_code.handle(client, {"query": "nonexistent"})
        assert "No results" in result

    async def test_commit_requires_repository(self) -> None:
        client = FakeInxr2Client()
        with pytest.raises(McpToolError, match="'commit' requires 'repository'"):
            await search_code.handle(client, {"query": "test", "commit": "abc123"})

    async def test_with_repository_filter(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "target-repo")
        client.add_repository(2, "other-repo")
        client.add_search_result("src/a.py", 1, "match in target", "target-repo")
        client.add_search_result("src/b.py", 5, "match in other", "other-repo")

        result = await search_code.handle(
            client, {"query": "match", "repository": "target-repo"}
        )

        assert "1 results" in result
        assert "src/a.py" in result
        assert "src/b.py" not in result

    async def test_includes_browse_urls(self) -> None:
        client = FakeInxr2Client()
        client.add_search_result("src/main.py", 15, "def connect():", "my-repo")

        result = await search_code.handle(
            client, {"query": "connect"}, frontend_url=FRONTEND_URL
        )

        assert "http://localhost:5173/browse/my-repo/src/main.py?line=15" in result

    async def test_no_browse_urls_without_frontend_url(self) -> None:
        client = FakeInxr2Client()
        client.add_search_result("src/main.py", 15, "def connect():", "my-repo")

        result = await search_code.handle(client, {"query": "connect"})

        assert "http://" not in result


# --- list_repositories ---


class TestListRepositories:
    async def test_lists_all_repos(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(
            1,
            "my-app",
            default_branch="main",
            indexed_branches=[
                {
                    "name": "main",
                    "commit_count": 50,
                    "last_indexed_commit": "abc123def456",
                },
            ],
        )
        client.add_repository(
            2,
            "my-lib",
            default_branch="master",
            indexed_branches=[
                {
                    "name": "master",
                    "commit_count": 20,
                    "last_indexed_commit": "def789abc012",
                },
            ],
        )

        result = await list_repositories.handle(client, {})

        assert "2 available" in result
        assert "my-app" in result
        assert "my-lib" in result
        assert "main" in result
        assert "master" in result

    async def test_single_repo_detail(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(
            1,
            "my-app",
            default_branch="main",
            indexed_branches=[
                {
                    "name": "main",
                    "commit_count": 50,
                    "last_indexed_commit": "abc123def456",
                },
                {
                    "name": "develop",
                    "commit_count": 10,
                    "last_indexed_commit": "xyz789000111",
                },
            ],
        )

        result = await list_repositories.handle(client, {"repository": "my-app"})

        assert "my-app" in result
        assert "Indexed branches: 2" in result
        assert "main (50 commits" in result
        assert "develop (10 commits" in result

    async def test_filters_unindexed_branches(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(
            1,
            "my-app",
            indexed_branches=[
                {"name": "main", "commit_count": 50, "last_indexed_commit": "abc123"},
                {
                    "name": "stale-branch",
                    "commit_count": 0,
                    "last_indexed_commit": None,
                },
            ],
        )

        result = await list_repositories.handle(client, {"repository": "my-app"})

        assert "main" in result
        assert "stale-branch" not in result
        assert "Indexed branches: 1" in result


# --- find_dead_code ---


class TestFindDeadCode:
    async def test_finds_symbols_with_no_references(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(1, "used_func", kind="function", repository_id=1)
        client.add_symbol(2, "dead_func", kind="function", repository_id=1)
        client.add_reference(1, "src/app.py", 10, "call", "used_func()")

        result = await find_dead_code.handle(client, {"repository": "my-repo"})

        assert "dead_func" in result
        assert "used_func" not in result
        assert "1 symbols with no references" in result

    async def test_filters_by_kind(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(1, "DeadClass", kind="class", repository_id=1)
        client.add_symbol(2, "dead_func", kind="function", repository_id=1)

        result = await find_dead_code.handle(
            client, {"repository": "my-repo", "kind": "function"}
        )

        assert "dead_func" in result
        assert "DeadClass" not in result
        assert "functions with no references" in result

    async def test_returns_message_when_all_have_references(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(1, "used_func", kind="function", repository_id=1)
        client.add_reference(1, "src/app.py", 10, "call", "used_func()")

        result = await find_dead_code.handle(client, {"repository": "my-repo"})

        assert "No dead code found" in result
        assert "all" in result

    async def test_returns_message_when_no_symbols(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")

        result = await find_dead_code.handle(client, {"repository": "my-repo"})

        assert "No symbols found" in result

    async def test_includes_browse_urls(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1,
            "dead_func",
            kind="function",
            file_path="src/utils.py",
            start_line=42,
            repository_id=1,
        )

        result = await find_dead_code.handle(
            client,
            {"repository": "my-repo"},
            frontend_url=FRONTEND_URL,
        )

        assert "http://localhost:5173/browse/my-repo/src/utils.py?line=42" in result

    async def test_no_browse_urls_without_frontend_url(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(1, "dead_func", kind="function", repository_id=1)

        result = await find_dead_code.handle(client, {"repository": "my-repo"})

        assert "http://" not in result

    async def test_deduplicates_by_name(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        # Same function name in header and implementation
        client.add_symbol(
            1,
            "my_func",
            kind="function",
            file_path="src/lib.h",
            repository_id=1,
        )
        client.add_symbol(
            2,
            "my_func",
            kind="function",
            file_path="src/lib.c",
            repository_id=1,
        )

        result = await find_dead_code.handle(client, {"repository": "my-repo"})

        # Should show only one entry for my_func
        assert result.count("[function] my_func") == 1

    async def test_respects_limit(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        for i in range(10):
            client.add_symbol(i, f"dead_{i}", kind="function", repository_id=1)

        result = await find_dead_code.handle(
            client, {"repository": "my-repo", "limit": 3}
        )

        assert "showing 3" in result
        assert "10 symbols with no references" in result

    async def test_pluralizes_property_correctly(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(1, "my_prop", kind="property", repository_id=1)

        result = await find_dead_code.handle(
            client, {"repository": "my-repo", "kind": "property"}
        )

        assert "properties with no references" in result
        assert "propertys" not in result

    async def test_warns_when_scan_incomplete(self) -> None:
        """When total symbols exceeds fetched count, warn the user."""
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        # Add 3 symbols but fake the total as higher
        for i in range(3):
            client.add_symbol(i, f"dead_{i}", kind="function", repository_id=1)

        # Monkey-patch to return inflated total
        original_get = client.get

        async def patched_get(
            path: str, params: dict[str, Any] | None = None
        ) -> dict[str, Any]:
            result = await original_get(path, params)
            if path == "/api/symbols" and isinstance(result, dict):
                result["total"] = 500
            return dict(result)

        client.get = patched_get  # type: ignore[method-assign]

        result = await find_dead_code.handle(client, {"repository": "my-repo"})

        assert "scanned 3 of 500 symbols" in result
        assert "results may be incomplete" in result


# --- staleness warning ---


class TestStalenessWarning:
    async def test_no_warning_when_not_stale(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(1, is_stale=False)
        client.add_symbol(1, "MyClass", kind="class", repository_id=1)

        result = await search_symbols.handle(
            client, {"query": "MyClass", "repository": "my-repo"}
        )

        assert "Warning" not in result
        assert "stale" not in result
        assert "MyClass" in result

    async def test_warning_prepended_when_stale(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(
            1,
            is_stale=True,
            last_indexed_commit="abc1234def5678",
            last_indexed_at="2026-03-07T10:00:00",
        )
        client.add_symbol(1, "MyClass", kind="class", repository_id=1)

        result = await search_symbols.handle(
            client, {"query": "MyClass", "repository": "my-repo"}
        )

        assert result.startswith("Warning:")
        assert "stale" in result
        assert "abc1234" in result
        assert "2026-03-07T10:00:00" in result
        assert "MyClass" in result

    async def test_no_warning_without_repository(self) -> None:
        client = FakeInxr2Client()
        client.add_symbol(1, "MyClass", kind="class")

        result = await search_symbols.handle(client, {"query": "MyClass"})

        assert "Warning" not in result
        assert "MyClass" in result

    async def test_warning_on_find_references(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(1, is_stale=True, last_indexed_commit="abc1234def5678")
        client.add_symbol(1, "MyFunc", kind="function", repository_id=1)
        client.add_reference(1, "src/app.py", 10, "call", "MyFunc()")

        result = await find_references.handle(
            client, {"name": "MyFunc", "repository": "my-repo"}
        )

        assert result.startswith("Warning:")
        assert "stale" in result
        assert "1 found" in result

    async def test_warning_on_go_to_definition(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(1, is_stale=True, last_indexed_commit="abc1234def5678")
        client.add_symbol(1, "MyFunc", kind="function", repository_id=1)

        result = await go_to_definition.handle(
            client, {"name": "MyFunc", "repository": "my-repo"}
        )

        assert result.startswith("Warning:")
        assert "stale" in result
        assert "MyFunc" in result

    async def test_warning_on_search_code(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(1, is_stale=True, last_indexed_commit="abc1234def5678")
        client.add_search_result("src/main.py", 15, "def connect():", "my-repo")

        result = await search_code.handle(
            client, {"query": "connect", "repository": "my-repo"}
        )

        assert result.startswith("Warning:")
        assert "stale" in result
        assert "connect" in result

    async def test_warning_on_find_dead_code(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(1, is_stale=True, last_indexed_commit="abc1234def5678")
        client.add_symbol(1, "dead_func", kind="function", repository_id=1)

        result = await find_dead_code.handle(client, {"repository": "my-repo"})

        assert result.startswith("Warning:")
        assert "stale" in result
        assert "dead_func" in result

    async def test_warning_when_stale_and_no_symbol_results(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(1, is_stale=True, last_indexed_commit="abc1234def5678")

        result = await search_symbols.handle(
            client, {"query": "NonExistent", "repository": "my-repo"}
        )

        assert result.startswith("Warning:")
        assert "stale" in result
        assert "No symbols found" in result

    async def test_warning_when_stale_and_no_search_code_results(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(1, is_stale=True, last_indexed_commit="abc1234def5678")

        result = await search_code.handle(
            client, {"query": "NonExistent", "repository": "my-repo"}
        )

        assert result.startswith("Warning:")
        assert "stale" in result
        assert "No results" in result

    async def test_warning_when_stale_and_no_references(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(1, is_stale=True, last_indexed_commit="abc1234def5678")

        result = await find_references.handle(
            client, {"name": "NonExistent", "repository": "my-repo"}
        )

        assert result.startswith("Warning:")
        assert "stale" in result
        assert "No symbols found" in result

    async def test_warning_when_stale_and_no_definition(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(1, is_stale=True, last_indexed_commit="abc1234def5678")

        result = await go_to_definition.handle(
            client, {"name": "NonExistent", "repository": "my-repo"}
        )

        assert result.startswith("Warning:")
        assert "stale" in result
        assert "No definition found" in result

    async def test_warning_when_stale_and_no_symbols_for_dead_code(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(1, is_stale=True, last_indexed_commit="abc1234def5678")

        result = await find_dead_code.handle(client, {"repository": "my-repo"})

        assert result.startswith("Warning:")
        assert "stale" in result
        assert "No symbols found" in result

    async def test_warning_when_stale_and_all_have_references_for_dead_code(
        self,
    ) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(1, is_stale=True, last_indexed_commit="abc1234def5678")
        client.add_symbol(1, "used_func", kind="function", repository_id=1)
        client.add_reference(1, "src/app.py", 10, "call", "used_func()")

        result = await find_dead_code.handle(client, {"repository": "my-repo"})

        assert result.startswith("Warning:")
        assert "stale" in result
        assert "No dead code found" in result
        assert "all" in result

    async def test_warning_on_review_helper(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(1, is_stale=True, last_indexed_commit="abc1234def5678")
        commit_hash = "abc1234567890abcdef1234567890abcdef123456"
        client.add_commit("my-repo", commit_hash, message="test commit")
        client.add_changed_file(commit_hash, "src/app.py", file_id=10)
        client.add_symbol(
            1, "my_func", kind="function", file_path="src/app.py", repository_id=1
        )

        result = await review_helper.handle(
            client, {"repository": "my-repo", "commit": "abc1234"}
        )

        assert result.startswith("Warning:")
        assert "stale" in result
        assert "Blast radius" in result


# --- review_helper ---


COMMIT_HASH = "abc1234567890abcdef1234567890abcdef123456"


class TestReviewHelper:
    def _setup_client(self) -> FakeInxr2Client:
        """Create a client with a repo, commit, changed files, and symbols."""
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_commit(
            "my-repo", COMMIT_HASH, message="fix: update validation logic"
        )
        client.add_changed_file(COMMIT_HASH, "src/validate.py", file_id=10)
        client.add_changed_file(COMMIT_HASH, "src/models.py", file_id=11)
        client.add_symbol(
            1,
            "validate_input",
            kind="function",
            file_path="src/validate.py",
            start_line=15,
            repository_id=1,
        )
        client.add_symbol(
            2,
            "UserModel",
            kind="class",
            file_path="src/models.py",
            start_line=5,
            repository_id=1,
        )
        return client

    async def test_shows_changed_files_and_symbols(self) -> None:
        client = self._setup_client()

        result = await review_helper.handle(
            client, {"repository": "my-repo", "commit": "abc1234"}
        )

        assert "Blast radius for commit abc1234" in result
        assert "fix: update validation logic" in result
        assert "Changed files: 2" in result
        assert "src/validate.py" in result
        assert "src/models.py" in result
        assert "Symbols in changed files: 2" in result
        assert "[function] validate_input" in result
        assert "[class] UserModel" in result

    async def test_shows_downstream_references(self) -> None:
        client = self._setup_client()
        client.add_reference(1, "src/app.py", 42, "call", "validate_input(data)")
        client.add_reference(2, "src/views.py", 10, "usage", "user = UserModel()")

        result = await review_helper.handle(
            client, {"repository": "my-repo", "commit": "abc1234"}
        )

        assert "Downstream references: 2" in result
        assert "validate_input" in result
        assert "referenced from 1 location" in result
        assert "src/app.py:42" in result
        assert "src/views.py:10" in result

    async def test_includes_browse_urls(self) -> None:
        client = self._setup_client()
        client.add_reference(1, "src/app.py", 42, "call", "validate_input()")

        result = await review_helper.handle(
            client,
            {"repository": "my-repo", "commit": "abc1234"},
            frontend_url=FRONTEND_URL,
        )

        # Browse URL for changed file
        assert (
            f"http://localhost:5173/browse/my-repo/src/validate.py?commit={COMMIT_HASH}"
            in result
        )
        # Browse URL for reference
        assert (
            f"http://localhost:5173/browse/my-repo/src/app.py?line=42&commit={COMMIT_HASH}"
            in result
        )

    async def test_no_browse_urls_without_frontend_url(self) -> None:
        client = self._setup_client()

        result = await review_helper.handle(
            client, {"repository": "my-repo", "commit": "abc1234"}
        )

        assert "http://" not in result

    async def test_commit_not_found(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")

        result = await review_helper.handle(
            client, {"repository": "my-repo", "commit": "deadbeef"}
        )

        assert "Commit 'deadbeef' not found" in result

    async def test_no_changed_files(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_commit("my-repo", COMMIT_HASH, message="empty commit")

        result = await review_helper.handle(
            client, {"repository": "my-repo", "commit": "abc1234"}
        )

        assert "Changed files: 0" in result
        assert "No changed files found" in result

    async def test_no_downstream_references(self) -> None:
        client = self._setup_client()

        result = await review_helper.handle(
            client, {"repository": "my-repo", "commit": "abc1234"}
        )

        assert "Downstream references: 0" in result
        assert "No downstream references found" in result

    async def test_respects_limit(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_commit("my-repo", COMMIT_HASH, message="many symbols")
        client.add_changed_file(COMMIT_HASH, "src/big.py", file_id=10)
        for i in range(10):
            client.add_symbol(
                i,
                f"func_{i}",
                kind="function",
                file_path="src/big.py",
                repository_id=1,
            )

        result = await review_helper.handle(
            client, {"repository": "my-repo", "commit": "abc1234", "limit": 3}
        )

        assert "Symbols in changed files: 10" in result
        assert "showing first 3" in result

    async def test_matches_full_hash(self) -> None:
        client = self._setup_client()

        result = await review_helper.handle(
            client, {"repository": "my-repo", "commit": COMMIT_HASH}
        )

        assert "Blast radius for commit abc1234" in result

    async def test_ambiguous_commit_prefix(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_commit("my-repo", "abc1234" + "a" * 33, message="commit A")
        client.add_commit("my-repo", "abc1234" + "b" * 33, message="commit B")

        result = await review_helper.handle(
            client, {"repository": "my-repo", "commit": "abc1234"}
        )

        assert "ambiguous" in result
        assert "abc1234" in result

    async def test_warns_when_scan_incomplete(self) -> None:
        client = self._setup_client()

        # Monkey-patch to return inflated total
        original_get = client.get

        async def patched_get(
            path: str, params: dict[str, Any] | None = None
        ) -> dict[str, Any]:
            result = await original_get(path, params)
            if path == "/api/symbols" and isinstance(result, dict):
                result["total"] = 500
            return dict(result)

        client.get = patched_get  # type: ignore[method-assign]

        result = await review_helper.handle(
            client, {"repository": "my-repo", "commit": "abc1234"}
        )

        assert "scanned 2 of 500 symbols" in result
        assert "results may be incomplete" in result


# --- get_change_impact ---


class TestGetChangeImpact:
    async def test_shows_symbol_definition_and_direct_references(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1,
            "MyClass",
            kind="class",
            file_path="src/models.py",
            start_line=10,
            repository_id=1,
        )
        client.add_reference(1, "src/app.py", 20, "usage", "obj = MyClass()")
        client.add_reference(
            1, "src/views.py", 5, "import", "from models import MyClass"
        )

        result = await get_change_impact.handle(
            client, {"name": "MyClass", "repository": "my-repo"}
        )

        assert "Change impact for 'MyClass' in 'my-repo'" in result
        assert "src/models.py:10 [class]" in result
        assert "Direct references: 2" in result
        assert "src/app.py" in result
        assert "src/views.py" in result

    async def test_classifies_test_files(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1, "my_func", kind="function", file_path="src/lib.py", repository_id=1
        )
        client.add_reference(1, "src/app.py", 5, "call", "my_func()")
        client.add_reference(1, "tests/test_app.py", 10, "call", "my_func()")

        result = await get_change_impact.handle(
            client, {"name": "my_func", "repository": "my-repo"}
        )

        assert "Source files (1):" in result
        assert "Test files (1):" in result
        assert "tests/test_app.py" in result
        assert "Tests  (1):" in result

    async def test_classifies_top_level_tests_directory(self) -> None:
        """tests/conftest.py must classify as test, not source (leading-slash bug)."""
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1, "my_func", kind="function", file_path="src/lib.py", repository_id=1
        )
        client.add_reference(1, "tests/conftest.py", 5, "usage", "my_func")
        client.add_reference(1, "tests/helpers.py", 10, "usage", "my_func")

        result = await get_change_impact.handle(
            client, {"name": "my_func", "repository": "my-repo"}
        )

        assert "Test files (2):" in result
        assert "Source files" not in result

    async def test_classifies_config_files(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1, "DB_HOST", kind="variable", file_path="src/config.py", repository_id=1
        )
        client.add_reference(1, "src/app.py", 5, "usage", "DB_HOST")
        client.add_reference(1, "config.yaml", 1, "usage", "db_host")

        result = await get_change_impact.handle(
            client, {"name": "DB_HOST", "repository": "my-repo"}
        )

        assert "Source files (1):" in result
        assert "Config files (1):" in result
        assert "config.yaml" in result
        assert "Config (1):" in result

    async def test_no_references_reports_unused(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(1, "orphan_func", kind="function", repository_id=1)

        result = await get_change_impact.handle(
            client, {"name": "orphan_func", "repository": "my-repo"}
        )

        assert "Direct references: 0" in result
        assert "may be unused" in result

    async def test_no_symbol_found(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")

        result = await get_change_impact.handle(
            client, {"name": "NonExistent", "repository": "my-repo"}
        )

        assert "No symbols found" in result
        assert "NonExistent" in result

    async def test_includes_browse_urls(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1,
            "MyClass",
            kind="class",
            file_path="src/models.py",
            start_line=10,
            repository_id=1,
        )
        client.add_reference(1, "src/app.py", 20, "usage", "MyClass()")

        result = await get_change_impact.handle(
            client,
            {"name": "MyClass", "repository": "my-repo"},
            frontend_url=FRONTEND_URL,
        )

        assert "http://localhost:5173/browse/my-repo/src/models.py?line=10" in result
        assert "http://localhost:5173/browse/my-repo/src/app.py?line=20" in result

    async def test_no_browse_urls_without_frontend_url(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(1, "MyClass", kind="class", repository_id=1)
        client.add_reference(1, "src/app.py", 20, "usage", "MyClass()")

        result = await get_change_impact.handle(
            client, {"name": "MyClass", "repository": "my-repo"}
        )

        assert "http://" not in result

    async def test_staleness_warning_prepended(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(1, is_stale=True, last_indexed_commit="abc1234def5678")
        client.add_symbol(1, "MyClass", kind="class", repository_id=1)
        client.add_reference(1, "src/app.py", 5, "usage", "MyClass()")

        result = await get_change_impact.handle(
            client, {"name": "MyClass", "repository": "my-repo"}
        )

        assert result.startswith("Warning:")
        assert "stale" in result
        assert "Change impact" in result

    async def test_multiple_definitions(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1,
            "Config",
            kind="class",
            file_path="src/config.py",
            start_line=1,
            repository_id=1,
        )
        client.add_symbol(
            2,
            "Config",
            kind="class",
            file_path="tests/config.py",
            start_line=5,
            repository_id=1,
        )

        result = await get_change_impact.handle(
            client, {"name": "Config", "repository": "my-repo"}
        )

        assert "src/config.py:1 [class]" in result
        assert "tests/config.py:5 [class]" in result

    async def test_depth_2_finds_transitive_files(self) -> None:
        """depth=2 follows: target ← l1_symbol ← l2_file."""
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        # Target symbol in lib.py
        client.add_symbol(
            1, "my_func", kind="function", file_path="src/lib.py", repository_id=1
        )
        # Symbol in level-1 file (app.py) that calls my_func
        client.add_symbol(
            2, "helper", kind="function", file_path="src/app.py", repository_id=1
        )
        # level-2 file: main.py calls helper
        client.add_reference(1, "src/app.py", 5, "call", "my_func()")
        client.add_reference(2, "src/main.py", 10, "call", "helper()")

        result = await get_change_impact.handle(
            client, {"name": "my_func", "repository": "my-repo", "depth": 2}
        )

        assert "Transitive impact (depth=2)" in result
        assert "src/main.py" in result
        assert "via: helper" in result

    async def test_depth_2_no_additional_files(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1, "my_func", kind="function", file_path="src/lib.py", repository_id=1
        )
        client.add_symbol(
            2, "helper", kind="function", file_path="src/app.py", repository_id=1
        )
        # helper has no further callers
        client.add_reference(1, "src/app.py", 5, "call", "my_func()")

        result = await get_change_impact.handle(
            client, {"name": "my_func", "repository": "my-repo", "depth": 2}
        )

        assert "Transitive impact (depth=2)" in result
        assert "No additional files at depth 2" in result

    async def test_depth_1_no_transitive_section(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(1, "my_func", kind="function", repository_id=1)
        client.add_reference(1, "src/app.py", 5, "call", "my_func()")

        result = await get_change_impact.handle(
            client, {"name": "my_func", "repository": "my-repo", "depth": 1}
        )

        assert "Transitive impact" not in result

    async def test_depth_capped_at_2(self) -> None:
        """depth=10 should be treated as depth=2."""
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1, "my_func", kind="function", file_path="src/lib.py", repository_id=1
        )
        client.add_reference(1, "src/app.py", 5, "call", "my_func()")

        result = await get_change_impact.handle(
            client, {"name": "my_func", "repository": "my-repo", "depth": 10}
        )

        # Should show transitive section (depth=2), not crash
        assert "Transitive impact (depth=2)" in result

    async def test_affected_files_summary(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1, "handler", kind="function", file_path="src/api.py", repository_id=1
        )
        client.add_reference(1, "src/router.py", 5, "call", "handler()")
        client.add_reference(1, "tests/test_api.py", 10, "call", "handler()")

        result = await get_change_impact.handle(
            client, {"name": "handler", "repository": "my-repo"}
        )

        assert "Affected files summary:" in result
        assert "Source (1): src/router.py" in result
        assert "Tests  (1): tests/test_api.py" in result


# --- get_file_structure ---


class TestGetFileStructure:
    async def test_shows_file_header(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_file_structure(
            "my-repo",
            "src/models.py",
            language="python",
            line_count=80,
            symbols=[],
        )

        result = await get_file_structure.handle(
            client, {"file_path": "src/models.py", "repository": "my-repo"}
        )

        assert "File: src/models.py" in result
        assert "Language: python" in result
        assert "Lines: 80" in result

    async def test_shows_top_level_symbols(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_file_structure(
            "my-repo",
            "src/models.py",
            symbols=[
                {
                    "id": 1,
                    "name": "MyClass",
                    "kind": "class",
                    "start_line": 10,
                    "end_line": 50,
                    "signature": None,
                    "docstring": None,
                    "parent_symbol_id": None,
                },
                {
                    "id": 2,
                    "name": "helper",
                    "kind": "function",
                    "start_line": 55,
                    "end_line": 60,
                    "signature": "(x: int) -> str",
                    "docstring": None,
                    "parent_symbol_id": None,
                },
            ],
        )

        result = await get_file_structure.handle(
            client, {"file_path": "src/models.py", "repository": "my-repo"}
        )

        assert "class MyClass" in result
        assert "[L10-50]" in result
        assert "def helper" in result
        assert "[L55-60]" in result

    async def test_includes_signatures_by_default(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_file_structure(
            "my-repo",
            "src/app.py",
            symbols=[
                {
                    "id": 1,
                    "name": "run",
                    "kind": "function",
                    "start_line": 1,
                    "end_line": 5,
                    "signature": "(host: str, port: int) -> None",
                    "docstring": None,
                    "parent_symbol_id": None,
                }
            ],
        )

        result = await get_file_structure.handle(
            client, {"file_path": "src/app.py", "repository": "my-repo"}
        )

        assert "(host: str, port: int) -> None" in result

    async def test_omits_signatures_when_disabled(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_file_structure(
            "my-repo",
            "src/app.py",
            symbols=[
                {
                    "id": 1,
                    "name": "run",
                    "kind": "function",
                    "start_line": 1,
                    "end_line": 5,
                    "signature": "(host: str, port: int) -> None",
                    "docstring": None,
                    "parent_symbol_id": None,
                }
            ],
        )

        result = await get_file_structure.handle(
            client,
            {
                "file_path": "src/app.py",
                "repository": "my-repo",
                "include_signatures": False,
            },
        )

        assert "(host: str, port: int) -> None" not in result
        assert "def run" in result

    async def test_shows_child_symbols_indented(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_file_structure(
            "my-repo",
            "src/models.py",
            symbols=[
                {
                    "id": 1,
                    "name": "MyClass",
                    "kind": "class",
                    "start_line": 1,
                    "end_line": 20,
                    "signature": None,
                    "docstring": None,
                    "parent_symbol_id": None,
                },
                {
                    "id": 2,
                    "name": "__init__",
                    "kind": "method",
                    "start_line": 3,
                    "end_line": 5,
                    "signature": "(self, x: int)",
                    "docstring": None,
                    "parent_symbol_id": 1,
                },
            ],
        )

        result = await get_file_structure.handle(
            client, {"file_path": "src/models.py", "repository": "my-repo"}
        )

        result_lines = result.splitlines()
        class_line = next(ln for ln in result_lines if "class MyClass" in ln)
        method_line = next(ln for ln in result_lines if "__init__" in ln)

        # Method should be indented more than class
        assert method_line.startswith("    ")
        assert class_line.startswith("  ") and not class_line.startswith("    ")

    async def test_includes_docstrings_when_enabled(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_file_structure(
            "my-repo",
            "src/app.py",
            symbols=[
                {
                    "id": 1,
                    "name": "run",
                    "kind": "function",
                    "start_line": 1,
                    "end_line": 5,
                    "signature": None,
                    "docstring": "Start the application server.",
                    "parent_symbol_id": None,
                }
            ],
        )

        result = await get_file_structure.handle(
            client,
            {
                "file_path": "src/app.py",
                "repository": "my-repo",
                "include_docstrings": True,
            },
        )

        assert "Start the application server." in result

    async def test_filters_non_structural_kinds(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_file_structure(
            "my-repo",
            "src/service.py",
            symbols=[
                {
                    "id": 1,
                    "name": "MyService",
                    "kind": "class",
                    "start_line": 1,
                    "end_line": 20,
                    "signature": None,
                    "docstring": None,
                    "parent_symbol_id": None,
                },
                {
                    "id": 2,
                    "name": "_repo",
                    "kind": "instance_variable",
                    "start_line": 5,
                    "end_line": 5,
                    "signature": None,
                    "docstring": None,
                    "parent_symbol_id": 1,
                },
                {
                    "id": 3,
                    "name": "MAX_SIZE",
                    "kind": "class_variable",
                    "start_line": 6,
                    "end_line": 6,
                    "signature": None,
                    "docstring": None,
                    "parent_symbol_id": 1,
                },
                {
                    "id": 4,
                    "name": "execute",
                    "kind": "method",
                    "start_line": 8,
                    "end_line": 15,
                    "signature": "(self)",
                    "docstring": None,
                    "parent_symbol_id": 1,
                },
            ],
        )

        result = await get_file_structure.handle(
            client, {"file_path": "src/service.py", "repository": "my-repo"}
        )

        assert "_repo" not in result
        assert "MAX_SIZE" not in result
        assert "instance_variable" not in result
        assert "class_variable" not in result
        assert "def execute" in result
        assert "class MyService" in result

    async def test_denylist_covers_all_variable_like_kinds(self) -> None:
        """Denylist approach: variable-like kinds are excluded, structural kinds pass through."""
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_file_structure(
            "my-repo",
            "src/models.py",
            symbols=[
                {
                    "id": 1,
                    "name": "MyClass",
                    "kind": "class",
                    "start_line": 1,
                    "end_line": 30,
                    "signature": None,
                    "docstring": None,
                    "parent_symbol_id": None,
                },
                # These should all be excluded
                *[
                    {
                        "id": i,
                        "name": f"noise_{kind}",
                        "kind": kind,
                        "start_line": i,
                        "end_line": i,
                        "signature": None,
                        "docstring": None,
                        "parent_symbol_id": 1,
                    }
                    for i, kind in enumerate(
                        [
                            "variable",
                            "constant",
                            "field",
                            "enum_value",
                            "enum_member",
                            "struct_field",
                            "union_field",
                            "instance_variable",
                            "class_variable",
                            "class_constant",
                            "static_field",
                            "readonly_field",
                            "interface_property",
                            "macro",
                        ],
                        start=2,
                    )
                ],
                # Unknown future kind — should pass through (not silently dropped)
                {
                    "id": 99,
                    "name": "future_kind_symbol",
                    "kind": "some_future_kind",
                    "start_line": 25,
                    "end_line": 25,
                    "signature": None,
                    "docstring": None,
                    "parent_symbol_id": None,
                },
            ],
        )

        result = await get_file_structure.handle(
            client, {"file_path": "src/models.py", "repository": "my-repo"}
        )

        assert "class MyClass" in result
        assert "future_kind_symbol" in result  # unknown kinds pass through
        assert "noise_" not in result  # all variable-like kinds excluded

    async def test_no_symbols(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_file_structure("my-repo", "src/empty.py", symbols=[])

        result = await get_file_structure.handle(
            client, {"file_path": "src/empty.py", "repository": "my-repo"}
        )

        assert "no symbols found" in result

    async def test_includes_browse_url(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_file_structure("my-repo", "src/models.py", symbols=[])

        result = await get_file_structure.handle(
            client,
            {"file_path": "src/models.py", "repository": "my-repo"},
            frontend_url=FRONTEND_URL,
        )

        assert "http://localhost:5173/browse/my-repo/src/models.py" in result

    async def test_prepends_staleness_warning(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(1, is_stale=True, last_indexed_commit="abc1234")
        client.add_file_structure("my-repo", "src/models.py", symbols=[])

        result = await get_file_structure.handle(
            client, {"file_path": "src/models.py", "repository": "my-repo"}
        )

        assert "Warning" in result
        assert "stale" in result


# --- explain_symbol ---


class TestExplainSymbol:
    async def test_symbol_found_with_references(self) -> None:
        client = FakeInxr2Client()
        client.add_symbol(
            1,
            "SearchSymbolsUseCase",
            kind="class",
            file_path="src/inxr2/application/use_cases/search_symbols.py",
            start_line=12,
            signature="class SearchSymbolsUseCase",
            docstring="Use case for searching symbols across a repository.",
        )
        client.add_reference(
            1,
            "tests/test_search_symbols.py",
            5,
            "import",
            "from ... import SearchSymbolsUseCase",
        )
        client.add_reference(
            1,
            "src/inxr2/adapters/api/symbols.py",
            8,
            "import",
            "import SearchSymbolsUseCase",
        )
        client.add_reference(
            1, "src/inxr2/di_container.py", 87, "call", "SearchSymbolsUseCase()"
        )

        result = await explain_symbol.handle(client, {"name": "SearchSymbolsUseCase"})

        assert "SearchSymbolsUseCase" in result
        assert "class" in result
        assert "src/inxr2/application/use_cases/search_symbols.py:12" in result
        assert "Use case for searching symbols" in result
        assert "class SearchSymbolsUseCase" in result
        assert "3 total" in result
        assert "import" in result
        assert "call" in result

    async def test_symbol_not_found(self) -> None:
        client = FakeInxr2Client()
        result = await explain_symbol.handle(client, {"name": "NonExistent"})
        assert "not found" in result
        assert "NonExistent" in result

    async def test_symbol_found_but_no_references(self) -> None:
        client = FakeInxr2Client()
        client.add_symbol(
            1,
            "OrphanClass",
            kind="class",
            file_path="src/orphan.py",
            start_line=5,
        )

        result = await explain_symbol.handle(client, {"name": "OrphanClass"})

        assert "OrphanClass" in result
        assert "src/orphan.py:5" in result
        assert "none found" in result

    async def test_references_grouped_by_type(self) -> None:
        client = FakeInxr2Client()
        client.add_symbol(1, "MyFunc", kind="function", file_path="src/lib.py")
        client.add_reference(1, "src/a.py", 1, "import", "")
        client.add_reference(1, "src/b.py", 2, "import", "")
        client.add_reference(1, "src/c.py", 3, "call", "")
        client.add_reference(1, "src/d.py", 4, "type_annotation", "")

        result = await explain_symbol.handle(client, {"name": "MyFunc"})

        assert "import (2)" in result
        assert "call (1)" in result
        assert "type_annotation (1)" in result

    async def test_truncates_long_reference_lists(self) -> None:
        client = FakeInxr2Client()
        client.add_symbol(1, "PopularFunc", kind="function")
        for i in range(8):
            client.add_reference(1, f"src/file_{i}.py", i + 1, "call", "")

        result = await explain_symbol.handle(client, {"name": "PopularFunc"})

        assert "and 3 more" in result

    async def test_filters_by_repository(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1, "MyClass", kind="class", file_path="src/m.py", repository_id=1
        )

        result = await explain_symbol.handle(
            client, {"name": "MyClass", "repository": "my-repo"}
        )

        assert "my-repo" in result
        assert "MyClass" in result

    async def test_commit_requires_repository(self) -> None:
        client = FakeInxr2Client()
        with pytest.raises(McpToolError, match="'commit' requires 'repository'"):
            await explain_symbol.handle(client, {"name": "Foo", "commit": "abc123"})

    async def test_includes_browse_url_with_repository(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1,
            "MyClass",
            kind="class",
            file_path="src/models.py",
            start_line=10,
            repository_id=1,
        )

        result = await explain_symbol.handle(
            client,
            {"name": "MyClass", "repository": "my-repo"},
            frontend_url=FRONTEND_URL,
        )

        assert "http://localhost:5173/browse/my-repo/src/models.py?line=10" in result

    async def test_shows_resolved_repo_name_without_repository_arg(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1, "MyFunc", kind="function", file_path="src/lib.py", repository_id=1
        )

        result = await explain_symbol.handle(client, {"name": "MyFunc"})

        # Repo name should appear in the header even though 'repository' was not passed
        assert "my-repo" in result

    async def test_disambiguation_note_on_multiple_matches(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "repo-a")
        client.add_repository(2, "repo-b")
        client.add_symbol(
            1,
            "helper",
            kind="function",
            file_path="src/a.py",
            start_line=1,
            repository_id=1,
        )
        client.add_symbol(
            2,
            "helper",
            kind="function",
            file_path="src/b.py",
            start_line=5,
            repository_id=2,
        )

        result = await explain_symbol.handle(client, {"name": "helper"})

        assert "2 definitions found" in result
        assert "src/b.py:5" in result
        assert "Specify 'repository' to disambiguate" in result

    async def test_disambiguation_hint_differs_when_repo_provided(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.add_symbol(
            1,
            "helper",
            kind="function",
            file_path="src/a.py",
            start_line=1,
            repository_id=1,
        )
        client.add_symbol(
            2,
            "helper",
            kind="function",
            file_path="src/b.py",
            start_line=5,
            repository_id=1,
        )

        result = await explain_symbol.handle(
            client, {"name": "helper", "repository": "my-repo"}
        )

        assert "2 definitions found" in result
        assert "Specify 'repository'" not in result
        assert "Specify 'commit'" in result

    async def test_references_truncation_note_when_api_total_exceeds_fetched(
        self,
    ) -> None:
        client = FakeInxr2Client()
        client.add_symbol(1, "BigFunc", kind="function")
        for i in range(10):
            client.add_reference(1, f"src/file_{i}.py", i + 1, "call", "")

        original_get = client.get

        async def patched_get(
            path: str, params: dict[str, Any] | None = None
        ) -> dict[str, Any]:
            result = await original_get(path, params)
            if "/references" in path and isinstance(result, dict):
                result = dict(result)
                result["total"] = 600
            return result

        client.get = patched_get  # type: ignore[method-assign]

        result = await explain_symbol.handle(client, {"name": "BigFunc"})

        assert "600 total" in result
        assert "showing first 10" in result

    async def test_truncation_when_fetch_limit_hit(self) -> None:
        """Backend returns total==len(items) when limit is hit; tool should still detect truncation."""
        client = FakeInxr2Client()
        client.add_symbol(1, "HotFunc", kind="function")
        # Simulate exactly 500 refs returned (the fetch limit) with total also == 500
        for i in range(500):
            client.add_reference(1, f"src/file_{i}.py", i + 1, "call", "")

        result = await explain_symbol.handle(client, {"name": "HotFunc"})

        assert "at least 500 total" in result
        assert "showing first 500" in result
        assert "per-type counts" in result

    async def test_staleness_warning_prepended(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "my-repo")
        client.set_stats(1, is_stale=True, last_indexed_commit="abc1234def5678")
        client.add_symbol(1, "MyClass", kind="class", repository_id=1)

        result = await explain_symbol.handle(
            client, {"name": "MyClass", "repository": "my-repo"}
        )

        assert result.startswith("Warning:")
        assert "stale" in result
        assert "MyClass" in result


# --- server creation ---


class TestServerCreation:
    async def test_create_server_lists_tools(self) -> None:
        from src.server import create_server

        client = FakeInxr2Client()
        server = create_server(client)

        # Verify the server was created (basic smoke test)
        assert server is not None
        assert server.name == "inxr2"

    async def test_unknown_tool_sets_is_error(self) -> None:
        """Regression: unknown tool name must set isError=True, not return in content."""
        from mcp.types import CallToolRequest, CallToolRequestParams

        from src.server import create_server

        client = FakeInxr2Client()
        server = create_server(client)

        req = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(name="nonexistent_tool", arguments={}),
        )
        # NOTE: server.request_handlers is an internal attribute of the MCP SDK's
        # Server class. There is no public test-client API; this is the least-bad
        # option for exercising the full dispatch path. If the SDK reorganises its
        # handler registry this will raise AttributeError unrelated to the behaviour
        # under test — update the accessor if that happens.
        handler = server.request_handlers[type(req)]
        result = await handler(req)

        assert result.root.isError is True
        assert result.root.content, "expected non-empty content in error result"
        assert "Unknown tool" in result.root.content[0].text

    async def test_invalid_repository_sets_is_error(self) -> None:
        """Regression: invalid repository name must set isError=True, not return in content."""
        from mcp.types import CallToolRequest, CallToolRequestParams

        from src.server import create_server

        client = FakeInxr2Client()  # no repositories registered
        server = create_server(client)

        req = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(
                name="search_symbols",
                arguments={"query": "foo", "repository": "nonexistent"},
            ),
        )
        # NOTE: see test_unknown_tool_sets_is_error for why we use request_handlers.
        handler = server.request_handlers[type(req)]
        result = await handler(req)

        assert result.root.isError is True

    async def test_validation_error_sets_is_error(self) -> None:
        """Regression: commit-without-repository validation error must set isError=True."""
        from mcp.types import CallToolRequest, CallToolRequestParams

        from src.server import create_server

        client = FakeInxr2Client()
        server = create_server(client)

        req = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(
                name="search_symbols",
                arguments={"query": "foo", "commit": "abc1234"},
            ),
        )
        # NOTE: see test_unknown_tool_sets_is_error for why we use request_handlers.
        handler = server.request_handlers[type(req)]
        result = await handler(req)

        assert result.root.isError is True
        assert result.root.content, "expected non-empty content in error result"
        assert "'commit' requires 'repository'" in result.root.content[0].text


# ============================================================
# Bug #386 — search_code extensions param causes 422
# ============================================================


class _ParamCapturingClient(FakeInxr2Client):
    """FakeInxr2Client that records the last params sent to GET /api/search/text."""

    def __init__(self) -> None:
        super().__init__()
        self.captured_search_params: dict[str, Any] | None = None

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if path == "/api/search/text":
            self.captured_search_params = dict(params or {})
        return await super().get(path, params)


class TestSearchCodeExtensions:
    """Tests for search_code extensions parameter formatting (bug #386).

    The MCP tool passes extensions as a plain string (e.g. "swift"), but the
    backend expects a list of dot-prefixed values (e.g. [".swift"]).  The tool
    must pre-process the string before calling the API.
    """

    async def test_extensions_sent_as_dot_prefixed_list(self) -> None:
        """extensions='swift' must be sent to the API as ['.swift'], not as a bare string."""
        client = _ParamCapturingClient()
        client.add_repository(1, "test-repo")
        client.set_stats(1)

        await search_code.handle(
            client,
            {"query": "foo", "repository": "test-repo", "extensions": "swift"},
        )

        assert client.captured_search_params is not None
        # Bug: currently sends extensions="swift" (str), which the backend rejects with 422
        # After fix: should send extensions=[".swift"] or extensions=".swift" (with dot)
        ext = client.captured_search_params.get("extensions")
        assert isinstance(
            ext, list
        ), f"expected list, got {type(ext).__name__}: {ext!r}"
        assert ".swift" in ext

    async def test_extensions_multiple_values_sent_as_list(self) -> None:
        """extensions='py,ts' must be split into ['.py', '.ts']."""
        client = _ParamCapturingClient()
        client.add_repository(1, "test-repo")
        client.set_stats(1)

        await search_code.handle(
            client,
            {"query": "foo", "repository": "test-repo", "extensions": "py,ts"},
        )

        assert client.captured_search_params is not None
        ext = client.captured_search_params.get("extensions")
        assert isinstance(
            ext, list
        ), f"expected list, got {type(ext).__name__}: {ext!r}"
        assert ".py" in ext
        assert ".ts" in ext

    async def test_extensions_already_dot_prefixed_accepted(self) -> None:
        """extensions='.swift' (already has dot) should be handled without doubling the dot."""
        client = _ParamCapturingClient()
        client.add_repository(1, "test-repo")
        client.set_stats(1)

        await search_code.handle(
            client,
            {"query": "foo", "repository": "test-repo", "extensions": ".swift"},
        )

        assert client.captured_search_params is not None
        ext = client.captured_search_params.get("extensions")
        assert isinstance(ext, list)
        assert ".swift" in ext
        assert "..swift" not in ext  # must not double the dot

    async def test_no_extensions_param_omitted(self) -> None:
        """When no extensions argument is given the param must not appear in the request."""
        client = _ParamCapturingClient()
        client.add_repository(1, "test-repo")
        client.set_stats(1)

        await search_code.handle(
            client,
            {"query": "foo", "repository": "test-repo"},
        )

        assert client.captured_search_params is not None
        assert "extensions" not in client.captured_search_params


# ============================================================
# Bug #395 — extensions array and source_only string rejected by schema
# ============================================================


class TestSearchCodeInputCoercion:
    """Regression tests for GH #395: AI models may pass extensions as an array
    or source_only as the string "true"; both must be accepted."""

    async def test_extensions_as_array_sent_as_dot_prefixed_list(self) -> None:
        """extensions=['swift'] (array) must be coerced to ['.swift'] for the API."""
        client = _ParamCapturingClient()
        client.add_repository(1, "test-repo")
        client.set_stats(1)

        await search_code.handle(
            client,
            {"query": "foo", "repository": "test-repo", "extensions": ["swift"]},
        )

        assert client.captured_search_params is not None
        ext = client.captured_search_params.get("extensions")
        assert isinstance(
            ext, list
        ), f"expected list, got {type(ext).__name__}: {ext!r}"
        assert ".swift" in ext

    async def test_extensions_array_already_dot_prefixed(self) -> None:
        """extensions=['.py', '.ts'] (already dot-prefixed array) must not double the dot."""
        client = _ParamCapturingClient()
        client.add_repository(1, "test-repo")
        client.set_stats(1)

        await search_code.handle(
            client,
            {"query": "foo", "repository": "test-repo", "extensions": [".py", ".ts"]},
        )

        assert client.captured_search_params is not None
        ext = client.captured_search_params.get("extensions")
        assert isinstance(ext, list)
        assert ".py" in ext
        assert ".ts" in ext
        assert "..py" not in ext

    async def test_source_only_string_true_filters_non_source(self) -> None:
        """source_only='true' (string) must filter out non-source files."""
        client = FakeInxr2Client()
        client.add_search_result("README.md", 1, "foo bar")
        client.add_search_result("src/main.py", 5, "def foo(): pass")

        result = await search_code.handle(
            client, {"query": "foo", "source_only": "true"}
        )

        assert "src/main.py" in result
        assert "README.md" not in result

    async def test_source_only_string_false_does_not_filter(self) -> None:
        """source_only='false' (string) must not filter anything."""
        client = FakeInxr2Client()
        client.add_search_result("README.md", 1, "foo bar")

        result = await search_code.handle(
            client, {"query": "foo", "source_only": "false"}
        )

        assert "README.md" in result


# ============================================================
# Bug #387 — search_code returns commit message matches (file: None)
# ============================================================


class TestSearchCodeCommitMessages:
    """Tests for search_code filtering commit message results (bug #387).

    Text search can return results whose file_path is None (commit messages).
    These must not appear in search_code output; only file-backed results
    should be shown.
    """

    async def test_commit_message_result_not_shown(self) -> None:
        """Results with file_path=None (commit messages) must be excluded from output."""
        client = FakeInxr2Client()
        # Inject a commit-message result (file_path is None) via the helper
        client.add_raw_result(
            {
                "id": 1,
                "repository_id": 1,
                "repository_name": "test-repo",
                "file_path": None,
                "source_line": None,
                "source_end_line": None,
                "source_type": "commit_message",
                "content": "fix: the important bug",
                "content_type": None,
                "language": None,
                "commit_hash": "abc123",
                "branch": None,
                "rank": 0.5,
                "headline": None,
            }
        )
        # Also add a real file result so the handler has something to show
        client.add_search_result("src/main.py", 10, "// fix the bug", "test-repo")

        result = await search_code.handle(client, {"query": "bug"})

        # Bug: currently the commit message result appears as "test-repo:None"
        assert ":None" not in result
        assert "commit_message" not in result

    async def test_file_result_still_shown(self) -> None:
        """File-backed results must still appear after commit message filtering."""
        client = FakeInxr2Client()
        client.add_raw_result(
            {
                "id": 1,
                "repository_id": 1,
                "repository_name": "test-repo",
                "file_path": None,
                "source_line": None,
                "source_end_line": None,
                "source_type": "commit_message",
                "content": "fix: the important bug",
                "content_type": None,
                "language": None,
                "commit_hash": "abc123",
                "branch": None,
                "rank": 0.5,
                "headline": None,
            }
        )
        client.add_search_result("src/main.py", 10, "// fix the bug", "test-repo")

        result = await search_code.handle(client, {"query": "bug"})

        assert "src/main.py" in result

    async def test_all_commit_message_results_no_output(self) -> None:
        """When all results are commit messages, report no results found."""
        client = FakeInxr2Client()
        client.add_raw_result(
            {
                "id": 1,
                "repository_id": 1,
                "repository_name": "test-repo",
                "file_path": None,
                "source_line": None,
                "source_end_line": None,
                "source_type": "commit_message",
                "content": "fix: something",
                "content_type": None,
                "language": None,
                "commit_hash": "abc123",
                "branch": None,
                "rank": 0.5,
                "headline": None,
            }
        )

        result = await search_code.handle(client, {"query": "something"})

        assert "No results" in result


# ============================================================
# Bug #388 — list_repositories shows "indexed branches: none"
# ============================================================


class TestListRepositoriesIndexedBranches:
    """Tests for list_repositories correctly identifying indexed branches (bug #388).

    A branch is considered indexed if indexing has completed — even if
    total_commits_indexed is 0.  The tool currently uses commit_count > 0
    to decide, which incorrectly hides branches that were indexed.
    """

    async def test_branch_with_zero_commits_but_indexed_is_shown(self) -> None:
        """A branch with commit_count=0 but a last_indexed_commit must appear as indexed."""
        client = FakeInxr2Client()
        client.add_repository(
            1,
            "my-repo",
            indexed_branches=[
                {
                    "name": "main",
                    "commit_count": 0,  # Bug trigger: currently filters this out
                    "last_indexed_commit": "abc123def456abc123def456abc123def456abc1",
                    "oldest_indexed_commit": None,
                    "last_indexed_at": "2026-01-01T00:00:00",
                }
            ],
        )

        result = await list_repositories.handle(client, {})

        # Bug: currently shows "indexed branches: none"
        assert "indexed branches: none" not in result
        assert "main" in result

    async def test_branch_with_no_indexing_data_not_shown(self) -> None:
        """A branch with commit_count=0 AND no last_indexed_commit is truly unindexed."""
        client = FakeInxr2Client()
        client.add_repository(
            1,
            "my-repo",
            indexed_branches=[
                {
                    "name": "feature",
                    "commit_count": 0,
                    "last_indexed_commit": None,
                    "oldest_indexed_commit": None,
                    "last_indexed_at": None,
                }
            ],
        )

        result = await list_repositories.handle(client, {})

        assert "indexed branches: none" in result

    async def test_single_repo_detail_shows_indexed_branch(self) -> None:
        """Single-repo detail view must also show branches indexed with commit_count=0."""
        client = FakeInxr2Client()
        client.add_repository(
            1,
            "my-repo",
            indexed_branches=[
                {
                    "name": "main",
                    "commit_count": 0,
                    "last_indexed_commit": "abc123def456abc123def456abc123def456abc1",
                    "oldest_indexed_commit": None,
                    "last_indexed_at": "2026-01-01T00:00:00",
                }
            ],
        )

        result = await list_repositories.handle(client, {"repository": "my-repo"})

        # Bug: currently shows "Indexed branches: 0"
        assert "Indexed branches: 0" not in result
        assert "main" in result

    async def test_branch_with_positive_commit_count_shown(self) -> None:
        """Branches with commit_count > 0 must still appear as indexed (regression guard)."""
        client = FakeInxr2Client()
        client.add_repository(
            1,
            "my-repo",
            indexed_branches=[
                {
                    "name": "main",
                    "commit_count": 42,
                    "last_indexed_commit": "abc123def456abc123def456abc123def456abc1",
                    "oldest_indexed_commit": None,
                    "last_indexed_at": "2026-01-01T00:00:00",
                }
            ],
        )

        result = await list_repositories.handle(client, {})

        assert "indexed branches: none" not in result
        assert "main" in result


# ============================================================
# Bug #393 — search_code without extension filter returns non-source files
# ============================================================


class TestSearchCodeSourceOnly:
    """Tests for search_code source_only parameter (bug #393).

    Without an extension filter, search results can include markdown docs,
    YAML configs, etc.  The source_only=True flag excludes known non-source
    file types.
    """

    async def test_source_only_excludes_markdown(self) -> None:
        """source_only=True must exclude .md results."""
        client = FakeInxr2Client()
        client.add_search_result("src/main.py", 1, "def foo():", "my-repo")
        client.add_search_result("README.md", 5, "## Usage", "my-repo")
        client.add_search_result("docs/guide.md", 10, "## Guide", "my-repo")

        result = await search_code.handle(client, {"query": "foo", "source_only": True})

        assert "src/main.py" in result
        assert "README.md" not in result
        assert "docs/guide.md" not in result

    async def test_source_only_excludes_yaml_and_toml(self) -> None:
        """source_only=True must exclude config file types."""
        client = FakeInxr2Client()
        client.add_search_result("src/app.py", 1, "app = App()", "my-repo")
        client.add_search_result("config.yaml", 3, "app: true", "my-repo")
        client.add_search_result("pyproject.toml", 8, "[tool.app]", "my-repo")

        result = await search_code.handle(client, {"query": "app", "source_only": True})

        assert "src/app.py" in result
        assert "config.yaml" not in result
        assert "pyproject.toml" not in result

    async def test_source_only_false_includes_all(self) -> None:
        """source_only=False (default) must include all file types."""
        client = FakeInxr2Client()
        client.add_search_result("src/main.py", 1, "def foo():", "my-repo")
        client.add_search_result("README.md", 5, "## foo usage", "my-repo")

        result = await search_code.handle(
            client, {"query": "foo", "source_only": False}
        )

        assert "src/main.py" in result
        assert "README.md" in result

    async def test_source_only_default_is_false(self) -> None:
        """Without source_only arg, non-source files are included (backward compat)."""
        client = FakeInxr2Client()
        client.add_search_result("src/main.py", 1, "def foo():", "my-repo")
        client.add_search_result("README.md", 5, "## foo usage", "my-repo")

        result = await search_code.handle(client, {"query": "foo"})

        assert "src/main.py" in result
        assert "README.md" in result
