"""Tests for MCP tool handlers using FakeInxr2Client."""

from typing import Any

from src.tools import (
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


# --- server creation ---


class TestServerCreation:
    async def test_create_server_lists_tools(self) -> None:
        from src.server import create_server

        client = FakeInxr2Client()
        server = create_server(client)

        # Verify the server was created (basic smoke test)
        assert server is not None
        assert server.name == "inxr2"
