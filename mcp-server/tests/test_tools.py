"""Tests for MCP tool handlers using FakeInxr2Client."""

from src.tools import (
    find_references,
    go_to_definition,
    list_repositories,
    search_code,
    search_symbols,
)
from tests.fake_client import FakeInxr2Client

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

    async def test_multiple_definitions(self) -> None:
        client = FakeInxr2Client()
        client.add_symbol(1, "Handler", file_path="src/a.py", start_line=10)
        client.add_symbol(2, "Handler", file_path="src/b.py", start_line=20)

        result = await go_to_definition.handle(client, {"name": "Handler"})

        assert "2 found" in result
        assert "src/a.py" in result
        assert "src/b.py" in result


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

    async def test_no_results(self) -> None:
        client = FakeInxr2Client()
        result = await search_symbols.handle(client, {"query": "nothing"})
        assert "No symbols found" in result


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

    async def test_with_repository_filter(self) -> None:
        client = FakeInxr2Client()
        client.add_repository(1, "target-repo")
        client.add_search_result("src/a.py", 1, "match", "target-repo")

        result = await search_code.handle(
            client, {"query": "match", "repository": "target-repo"}
        )

        assert "1 shown" in result


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


# --- server creation ---


class TestServerCreation:
    async def test_create_server_lists_tools(self) -> None:
        from src.server import create_server

        client = FakeInxr2Client()
        server = create_server(client)

        # Verify the server was created (basic smoke test)
        assert server is not None
        assert server.name == "inxr2"
