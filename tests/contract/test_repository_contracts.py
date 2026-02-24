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
