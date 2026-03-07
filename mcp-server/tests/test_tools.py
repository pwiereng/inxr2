"""Tests for MCP tool handlers using FakeInxr2Client."""

from typing import Any

from src.tools import (
    find_dead_code,
    find_references,
    go_to_definition,
    list_repositories,
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
        result = await find_references.handle(
            client, {"name": "Foo", "commit": "abc123"}
        )
        assert "Error" in result
        assert "'commit' requires 'repository'" in result

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
        result = await go_to_definition.handle(
            client, {"name": "Foo", "commit": "abc123"}
        )
        assert "Error" in result
        assert "'commit' requires 'repository'" in result

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
        result = await search_symbols.handle(
            client, {"query": "Foo", "commit": "abc123"}
        )
        assert "Error" in result
        assert "'commit' requires 'repository'" in result

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


# --- search_code ---


class TestSearchCode:
    async def test_search_returns_results(self) -> None:
        client = FakeInxr2Client()
        client.add_search_result(
            "src/main.py", 15, "def connect_database():", "my-repo"
        )

        result = await search_code.handle(client, {"query": "connect_database"})

        assert "1 shown" in result
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
        result = await search_code.handle(client, {"query": "test", "commit": "abc123"})
        assert "Error" in result
        assert "'commit' requires 'repository'" in result

    async def test_with_repository_filter(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "target-repo")
        client.add_repository(2, "other-repo")
        client.add_search_result("src/a.py", 1, "match in target", "target-repo")
        client.add_search_result("src/b.py", 5, "match in other", "other-repo")

        result = await search_code.handle(
            client, {"query": "match", "repository": "target-repo"}
        )

        assert "1 shown" in result
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

        async def patched_get(path: str, params: dict[str, Any] | None = None) -> Any:
            result = await original_get(path, params)
            if path == "/api/symbols" and isinstance(result, dict):
                result["total"] = 500
            return result

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


# --- server creation ---


class TestServerCreation:
    async def test_create_server_lists_tools(self) -> None:
        from src.server import create_server

        client = FakeInxr2Client()
        server = create_server(client)

        # Verify the server was created (basic smoke test)
        assert server is not None
        assert server.name == "inxr2"
