"""Contract tests verifying fake and Postgres implementations behave identically.

Each test sets up the same scenario in both implementations via the parametrized
`repos` fixture, then asserts identical results.

Scenario: A repository with 2 commits indexing the same file path.
The "latest" file version is the one with the newest commit_date.
Methods should return only symbols/references from the latest file version
when not in time-travel mode.

The "head_first" variants simulate the real indexer which inserts HEAD files
first (lower auto-increment IDs) and older commits later (higher IDs).
This catches bugs where max(id) is incorrectly used to mean "latest".
"""

import pytest

from .conftest import (
    Repos,
    create_test_commit,
    create_test_file,
    create_test_reference,
    create_test_repo,
    create_test_symbol,
)

pytestmark = pytest.mark.contract


async def _setup_two_commits(repos: Repos) -> dict[str, int]:
    """Create a repo with 2 commits, same file path at each.

    Returns dict with keys: repo_id, commit1_id, commit2_id,
    file1_id, file2_id, symbol1_id, symbol2_id.
    """
    repo_id = await create_test_repo(repos)
    commit1_id = await create_test_commit(repos, repo_id, "a" * 40, date_offset_days=0)
    commit2_id = await create_test_commit(repos, repo_id, "b" * 40, date_offset_days=1)

    # Same path, different content hashes (file changed between commits)
    file1_id = await create_test_file(
        repos, repo_id, commit1_id, "src/main.py", "c" * 40
    )
    file2_id = await create_test_file(
        repos, repo_id, commit2_id, "src/main.py", "d" * 40
    )

    # Symbol "foo" exists at both file versions
    symbol1_id = await create_test_symbol(
        repos, file1_id, repo_id, commit1_id, "foo", "module.foo"
    )
    symbol2_id = await create_test_symbol(
        repos, file2_id, repo_id, commit2_id, "foo", "module.foo"
    )

    return {
        "repo_id": repo_id,
        "commit1_id": commit1_id,
        "commit2_id": commit2_id,
        "file1_id": file1_id,
        "file2_id": file2_id,
        "symbol1_id": symbol1_id,
        "symbol2_id": symbol2_id,
    }


# ---- Symbol Repository contracts ----


class TestSearchByNameContract:
    async def test_filters_to_latest_file_version(self, repos: Repos) -> None:
        """search_by_name should return only symbols from latest file version."""
        data = await _setup_two_commits(repos)

        results = await repos.symbol.search_by_name(
            "foo", repository_id=data["repo_id"]
        )

        assert len(results) == 1
        assert results[0].file_id == data["file2_id"]

    async def test_no_filter_without_repository_id(self, repos: Repos) -> None:
        """search_by_name without repository_id returns all matches."""
        await _setup_two_commits(repos)

        results = await repos.symbol.search_by_name("foo")

        # Without repository_id, no latest-file filtering is applied
        assert len(results) == 2


class TestFindByExactNameContract:
    async def test_filters_to_latest_file_version(self, repos: Repos) -> None:
        """find_by_exact_name without commit_id filters to latest file."""
        data = await _setup_two_commits(repos)

        results = await repos.symbol.find_by_exact_name(
            "foo", repository_id=data["repo_id"]
        )

        assert len(results) == 1
        assert results[0].file_id == data["file2_id"]

    async def test_time_travel_returns_specific_commit(self, repos: Repos) -> None:
        """find_by_exact_name with commit_id returns from that commit."""
        data = await _setup_two_commits(repos)

        results = await repos.symbol.find_by_exact_name(
            "foo",
            repository_id=data["repo_id"],
            commit_id=data["commit1_id"],
        )

        assert len(results) == 1
        assert results[0].file_id == data["file1_id"]


class TestFindByQualifiedNameContract:
    async def test_filters_to_latest_file_version(self, repos: Repos) -> None:
        """find_by_qualified_name returns only from latest file version."""
        data = await _setup_two_commits(repos)

        results = await repos.symbol.find_by_qualified_name(
            data["repo_id"], "module.foo"
        )

        assert len(results) == 1
        assert results[0].file_id == data["file2_id"]


# ---- Reference Repository contracts ----


class TestFindReferencesToSymbolContract:
    async def test_filters_to_latest_file_version(self, repos: Repos) -> None:
        """find_references_to_symbol filters to latest file when no commit_id."""
        data = await _setup_two_commits(repos)

        # Create refs in both file versions pointing to symbol2
        await create_test_reference(
            repos,
            data["repo_id"],
            data["commit1_id"],
            data["file1_id"],
            "foo",
            target_symbol_id=data["symbol2_id"],
        )
        await create_test_reference(
            repos,
            data["repo_id"],
            data["commit2_id"],
            data["file2_id"],
            "foo",
            target_symbol_id=data["symbol2_id"],
        )

        results = await repos.reference.find_references_to_symbol(data["symbol2_id"])

        assert len(results) == 1
        assert results[0].source_file_id == data["file2_id"]

    async def test_time_travel_returns_specific_commit(self, repos: Repos) -> None:
        """find_references_to_symbol with commit_id returns from that commit."""
        data = await _setup_two_commits(repos)

        await create_test_reference(
            repos,
            data["repo_id"],
            data["commit1_id"],
            data["file1_id"],
            "foo",
            target_symbol_id=data["symbol2_id"],
        )
        await create_test_reference(
            repos,
            data["repo_id"],
            data["commit2_id"],
            data["file2_id"],
            "foo",
            target_symbol_id=data["symbol2_id"],
        )

        results = await repos.reference.find_references_to_symbol(
            data["symbol2_id"], commit_id=data["commit1_id"]
        )

        assert len(results) == 1
        assert results[0].source_file_id == data["file1_id"]


class TestFindReferencesByTextContract:
    async def test_filters_to_latest_file_version(self, repos: Repos) -> None:
        """find_references_by_text filters to latest file when no commit_id."""
        data = await _setup_two_commits(repos)

        await create_test_reference(
            repos,
            data["repo_id"],
            data["commit1_id"],
            data["file1_id"],
            "bar",
        )
        await create_test_reference(
            repos,
            data["repo_id"],
            data["commit2_id"],
            data["file2_id"],
            "bar",
        )

        results = await repos.reference.find_references_by_text("bar", data["repo_id"])

        assert len(results) == 1
        assert results[0].source_file_id == data["file2_id"]


# ---- File Repository contracts (list_changed_at_commit) ----


class TestListChangedAtCommitContract:
    async def test_new_file_is_reported_as_changed(self, repos: Repos) -> None:
        """A file that only appears at the target commit is reported as new/changed."""
        repo_id = await create_test_repo(repos)
        commit_id = await create_test_commit(
            repos, repo_id, "a" * 40, date_offset_days=0
        )
        await create_test_file(repos, repo_id, commit_id, "src/new.py", "c" * 40)

        changed = await repos.file_version.list_changed_at_commit(repo_id, commit_id)

        assert len(changed) == 1
        assert changed[0].path == "src/new.py"

    async def test_unchanged_file_is_not_reported(self, repos: Repos) -> None:
        """A file with same content_hash as prior version is excluded."""
        repo_id = await create_test_repo(repos)
        commit1_id = await create_test_commit(
            repos, repo_id, "a" * 40, date_offset_days=0
        )
        commit2_id = await create_test_commit(
            repos, repo_id, "b" * 40, date_offset_days=1
        )

        # Same hash at both commits
        same_hash = "c" * 40
        await create_test_file(repos, repo_id, commit1_id, "src/same.py", same_hash)
        await create_test_file(repos, repo_id, commit2_id, "src/same.py", same_hash)

        changed = await repos.file_version.list_changed_at_commit(repo_id, commit2_id)

        assert len(changed) == 0

    async def test_modified_file_is_reported_as_changed(self, repos: Repos) -> None:
        """A file with different content_hash from prior version is included."""
        repo_id = await create_test_repo(repos)
        commit1_id = await create_test_commit(
            repos, repo_id, "a" * 40, date_offset_days=0
        )
        commit2_id = await create_test_commit(
            repos, repo_id, "b" * 40, date_offset_days=1
        )

        await create_test_file(repos, repo_id, commit1_id, "src/mod.py", "c" * 40)
        await create_test_file(repos, repo_id, commit2_id, "src/mod.py", "d" * 40)

        changed = await repos.file_version.list_changed_at_commit(repo_id, commit2_id)

        assert len(changed) == 1
        assert changed[0].path == "src/mod.py"

    async def test_multiple_prior_commits_uses_most_recent(self, repos: Repos) -> None:
        """With 3 commits, comparison should be against the immediate prior."""
        repo_id = await create_test_repo(repos)
        commit1_id = await create_test_commit(
            repos, repo_id, "a" * 40, date_offset_days=0
        )
        commit2_id = await create_test_commit(
            repos, repo_id, "b" * 40, date_offset_days=1
        )
        commit3_id = await create_test_commit(
            repos, repo_id, "c" * 40, date_offset_days=2
        )

        # File changes: hash1 -> hash2 -> hash2 (unchanged between commit2 and 3)
        hash1 = "1" * 40
        hash2 = "2" * 40
        await create_test_file(repos, repo_id, commit1_id, "src/f.py", hash1)
        await create_test_file(repos, repo_id, commit2_id, "src/f.py", hash2)
        await create_test_file(repos, repo_id, commit3_id, "src/f.py", hash2)

        # Commit3's file has same hash as commit2 (most recent prior) -> not changed
        changed = await repos.file_version.list_changed_at_commit(repo_id, commit3_id)
        assert len(changed) == 0

        # Commit2's file differs from commit1 (most recent prior) -> changed
        changed = await repos.file_version.list_changed_at_commit(repo_id, commit2_id)
        assert len(changed) == 1
        assert changed[0].path == "src/f.py"


# ---- HEAD-first indexing contracts (newer commit has LOWER file IDs) ----
#
# The real indexer processes HEAD first, so HEAD files get lower auto-increment
# IDs than older commits. These tests verify that latest-file filtering uses
# commit_date, not max(id).


async def _setup_two_commits_head_first(repos: Repos) -> dict[str, int]:
    """Create a repo simulating HEAD-first indexing.

    Newer commit (commit2, date_offset=1) is inserted FIRST → lower file ID.
    Older commit (commit1, date_offset=0) is inserted SECOND → higher file ID.

    The "latest" should be commit2's file (newer date, but LOWER ID).
    """
    repo_id = await create_test_repo(repos)
    # Create both commits first (dates determine "latest", not insertion order)
    commit1_id = await create_test_commit(repos, repo_id, "a" * 40, date_offset_days=0)
    commit2_id = await create_test_commit(repos, repo_id, "b" * 40, date_offset_days=1)

    # Insert HEAD file first (newer commit) → gets lower auto-increment ID
    file2_id = await create_test_file(
        repos, repo_id, commit2_id, "src/main.py", "d" * 40
    )
    # Insert older file second → gets higher auto-increment ID
    file1_id = await create_test_file(
        repos, repo_id, commit1_id, "src/main.py", "c" * 40
    )

    # file1_id > file2_id (older commit's file has higher ID)
    # Symbol at HEAD (commit2)
    symbol2_id = await create_test_symbol(
        repos, file2_id, repo_id, commit2_id, "foo", "module.foo"
    )
    # Symbol at older commit
    symbol1_id = await create_test_symbol(
        repos, file1_id, repo_id, commit1_id, "foo", "module.foo"
    )

    return {
        "repo_id": repo_id,
        "commit1_id": commit1_id,
        "commit2_id": commit2_id,
        "file1_id": file1_id,
        "file2_id": file2_id,
        "symbol1_id": symbol1_id,
        "symbol2_id": symbol2_id,
    }


class TestSearchByNameTopLevelOnly:
    """Contract tests for top_level_only filtering in search_by_name."""

    async def _setup_nested_symbols(self, repos: Repos) -> dict[str, int]:
        """Create a repo with top-level and nested symbols.

        Creates:
        - top_level_func: a function with no parent (top-level)
        - nested_method: a function inside MyClass (has parent)
        - ns_func: a function inside a namespace (effectively top-level)
        """
        from inxr2.domain.entities import Symbol
        from inxr2.domain.value_objects import SymbolKind

        repo_id = await create_test_repo(repos)
        commit_id = await create_test_commit(
            repos, repo_id, "a" * 40, date_offset_days=0
        )
        file_id = await create_test_file(
            repos, repo_id, commit_id, "src/main.py", "c" * 40
        )

        # Top-level function (no parent)
        top_func = await repos.symbol.save(
            Symbol(
                file_id=file_id,
                repository_id=repo_id,
                name="top_level_func",
                kind=SymbolKind.FUNCTION,
                start_line=1,
                start_column=0,
                end_line=5,
                end_column=0,
            )
        )
        assert top_func.id is not None

        # A class (top-level, no parent)
        my_class = await repos.symbol.save(
            Symbol(
                file_id=file_id,
                repository_id=repo_id,
                name="MyClass",
                kind=SymbolKind.CLASS,
                start_line=10,
                start_column=0,
                end_line=30,
                end_column=0,
            )
        )
        assert my_class.id is not None

        # A method nested inside MyClass
        nested_method = await repos.symbol.save(
            Symbol(
                file_id=file_id,
                repository_id=repo_id,
                name="nested_method",
                kind=SymbolKind.METHOD,
                start_line=12,
                start_column=4,
                end_line=15,
                end_column=0,
                parent_symbol_id=my_class.id,
            )
        )
        assert nested_method.id is not None

        # A namespace (top-level container)
        namespace = await repos.symbol.save(
            Symbol(
                file_id=file_id,
                repository_id=repo_id,
                name="myns",
                kind=SymbolKind.NAMESPACE,
                start_line=40,
                start_column=0,
                end_line=60,
                end_column=0,
            )
        )
        assert namespace.id is not None

        # A function inside the namespace (effectively top-level)
        ns_func = await repos.symbol.save(
            Symbol(
                file_id=file_id,
                repository_id=repo_id,
                name="ns_func",
                kind=SymbolKind.FUNCTION,
                start_line=42,
                start_column=4,
                end_line=50,
                end_column=0,
                parent_symbol_id=namespace.id,
            )
        )
        assert ns_func.id is not None

        return {
            "repo_id": repo_id,
            "top_func_id": top_func.id,
            "my_class_id": my_class.id,
            "nested_method_id": nested_method.id,
            "namespace_id": namespace.id,
            "ns_func_id": ns_func.id,
        }

    async def test_excludes_nested_symbols(self, repos: Repos) -> None:
        """top_level_only=True should exclude symbols nested inside non-namespace parents."""
        data = await self._setup_nested_symbols(repos)

        results = await repos.symbol.search_by_name(
            "", repository_id=data["repo_id"], top_level_only=True
        )

        result_ids = {s.id for s in results}
        # nested_method is inside MyClass, should be excluded
        assert data["nested_method_id"] not in result_ids
        # top_level_func, MyClass, namespace, ns_func should be included
        assert data["top_func_id"] in result_ids
        assert data["my_class_id"] in result_ids

    async def test_includes_namespace_children(self, repos: Repos) -> None:
        """top_level_only=True should include symbols whose parent is a namespace."""
        data = await self._setup_nested_symbols(repos)

        results = await repos.symbol.search_by_name(
            "", repository_id=data["repo_id"], top_level_only=True
        )

        result_ids = {s.id for s in results}
        assert data["ns_func_id"] in result_ids

    async def test_default_returns_all(self, repos: Repos) -> None:
        """top_level_only=False (default) should return all symbols including nested."""
        data = await self._setup_nested_symbols(repos)

        results = await repos.symbol.search_by_name(
            "", repository_id=data["repo_id"], top_level_only=False
        )

        result_ids = {s.id for s in results}
        assert data["top_func_id"] in result_ids
        assert data["my_class_id"] in result_ids
        assert data["nested_method_id"] in result_ids
        assert data["ns_func_id"] in result_ids


class TestSearchByNameHeadFirst:
    async def test_returns_symbol_from_newer_commit(self, repos: Repos) -> None:
        """search_by_name should return symbol from newer commit even if it has lower ID."""
        data = await _setup_two_commits_head_first(repos)

        results = await repos.symbol.search_by_name(
            "foo", repository_id=data["repo_id"]
        )

        assert len(results) == 1
        assert results[0].file_id == data["file2_id"]


class TestFindByExactNameHeadFirst:
    async def test_returns_symbol_from_newer_commit(self, repos: Repos) -> None:
        """find_by_exact_name should return symbol from newer commit."""
        data = await _setup_two_commits_head_first(repos)

        results = await repos.symbol.find_by_exact_name(
            "foo", repository_id=data["repo_id"]
        )

        assert len(results) == 1
        assert results[0].file_id == data["file2_id"]


class TestFindByQualifiedNameHeadFirst:
    async def test_returns_symbol_from_newer_commit(self, repos: Repos) -> None:
        """find_by_qualified_name should return symbol from newer commit."""
        data = await _setup_two_commits_head_first(repos)

        results = await repos.symbol.find_by_qualified_name(
            data["repo_id"], "module.foo"
        )

        assert len(results) == 1
        assert results[0].file_id == data["file2_id"]


class TestFindReferencesToSymbolHeadFirst:
    async def test_returns_ref_from_newer_commit(self, repos: Repos) -> None:
        """find_references_to_symbol should return refs from newer commit's file."""
        data = await _setup_two_commits_head_first(repos)

        # Refs in both file versions pointing to symbol2
        await create_test_reference(
            repos,
            data["repo_id"],
            data["commit2_id"],
            data["file2_id"],
            "foo",
            target_symbol_id=data["symbol2_id"],
        )
        await create_test_reference(
            repos,
            data["repo_id"],
            data["commit1_id"],
            data["file1_id"],
            "foo",
            target_symbol_id=data["symbol2_id"],
        )

        results = await repos.reference.find_references_to_symbol(data["symbol2_id"])

        assert len(results) == 1
        assert results[0].source_file_id == data["file2_id"]


class TestFindReferencesByTextHeadFirst:
    async def test_returns_ref_from_newer_commit(self, repos: Repos) -> None:
        """find_references_by_text should return refs from newer commit's file."""
        data = await _setup_two_commits_head_first(repos)

        await create_test_reference(
            repos,
            data["repo_id"],
            data["commit2_id"],
            data["file2_id"],
            "bar",
        )
        await create_test_reference(
            repos,
            data["repo_id"],
            data["commit1_id"],
            data["file1_id"],
            "bar",
        )

        results = await repos.reference.find_references_by_text("bar", data["repo_id"])

        assert len(results) == 1
        assert results[0].source_file_id == data["file2_id"]
