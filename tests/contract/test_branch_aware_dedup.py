"""Regression tests for branch-aware file deduplication (issues #45 and #47).

Issue #45: search_by_name with branch filter drops valid symbols when the
globally-latest file version for a path lives on a different branch.

Issue #47: find_references_to_symbol and find_references_by_text ignore the
branch parameter and use global "latest file per path" dedup, which can return
references with wrong line numbers from a different branch's file version.

Scenario:
  - Repository with 2 branches: "main" and "feature"
  - File src/app.py exists on both, but with different content
  - "feature" branch has a newer commit (day 2) than "main" (day 1)
  - Global dedup picks "feature"'s file version as the latest
  - Queries filtered to "main" should still return results from main's version

These tests serve as regression/contract tests to ensure these bugs do not recur.
"""

import pytest

from inxr2.domain.entities import Reference
from inxr2.domain.value_objects import ReferenceType

from .conftest import (
    Repos,
    create_test_commit,
    create_test_file,
    create_test_repo,
    create_test_symbol,
)

pytestmark = pytest.mark.contract


async def _setup_two_branches(repos: Repos) -> dict[str, int]:
    """Create a repo with 2 branches, each with a different version of the same file.

    Timeline:
      - commit1 (day 0) on "main": src/app.py with content hash "aaa..."
      - commit2 (day 2) on "feature": src/app.py with content hash "bbb..."

    The globally-latest file for src/app.py is file2 (from "feature", newer date).
    But when browsing "main", we should see file1's symbols and references.

    Returns dict with keys: repo_id, commit1_id, commit2_id,
    file1_id, file2_id, symbol1_id, symbol2_id
    """
    repo_id = await create_test_repo(repos)

    # Create commits on different branches
    commit1_id = await create_test_commit(
        repos, repo_id, "a" * 40, date_offset_days=0, branch="main"
    )
    commit2_id = await create_test_commit(
        repos, repo_id, "b" * 40, date_offset_days=2, branch="feature"
    )

    # Same path, different content (file changed between branches)
    file1_id = await create_test_file(
        repos, repo_id, commit1_id, "src/app.py", "c" * 40
    )
    file2_id = await create_test_file(
        repos, repo_id, commit2_id, "src/app.py", "d" * 40
    )

    # Symbol "setup_logging" exists at both file versions, different lines
    symbol1_id = await create_test_symbol(
        repos, file1_id, repo_id, commit1_id, "setup_logging", "module.setup_logging"
    )
    symbol2_id = await create_test_symbol(
        repos, file2_id, repo_id, commit2_id, "setup_logging", "module.setup_logging"
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


# ---- Issue #45: Symbol search drops results on branch filter ----


class TestSearchByNameBranchDedup:
    """search_by_name with branch should scope dedup to that branch."""

    async def test_search_on_main_returns_main_symbol(self, repos: Repos) -> None:
        """Searching on 'main' should return the symbol from main's file version.

        Bug: Global dedup picks feature's file (newer), then branch filter
        intersects with main's files → empty result → symbol silently dropped.
        """
        data = await _setup_two_branches(repos)

        results = await repos.symbol.search_by_name(
            "setup_logging",
            repository_id=data["repo_id"],
            branch="main",
        )

        # Should find exactly one symbol from main's file version
        assert len(results) == 1, (
            f"Expected 1 symbol on 'main', got {len(results)}. "
            "Bug #45: global dedup drops symbols when latest file is on another branch."
        )
        assert results[0].file_id == data["file1_id"]

    async def test_search_on_feature_returns_feature_symbol(self, repos: Repos) -> None:
        """Searching on 'feature' should return the symbol from feature's file.

        This one passes even with the bug because feature has the globally-latest file.
        """
        data = await _setup_two_branches(repos)

        results = await repos.symbol.search_by_name(
            "setup_logging",
            repository_id=data["repo_id"],
            branch="feature",
        )

        assert len(results) == 1
        assert results[0].file_id == data["file2_id"]

    async def test_search_without_branch_returns_default_branch(
        self, repos: Repos
    ) -> None:
        """Without branch filter, search falls back to default branch (main)."""
        data = await _setup_two_branches(repos)

        results = await repos.symbol.search_by_name(
            "setup_logging",
            repository_id=data["repo_id"],
        )

        assert len(results) == 1
        assert results[0].file_id == data["file1_id"]


# ---- Issue #47: References return wrong line numbers on branch filter ----


class TestFindReferencesToSymbolBranchDedup:
    """find_references_to_symbol with branch should scope dedup to that branch."""

    async def test_references_on_main_use_main_line_numbers(self, repos: Repos) -> None:
        """References on 'main' should come from main's file version with correct lines.

        Bug: branch param is ignored in PostgresReferenceRepository, global dedup
        picks feature's file version, returning wrong line numbers for main.
        """
        data = await _setup_two_branches(repos)

        # Reference to setup_logging at line 362 on main's file version
        await repos.reference.save(
            Reference(
                repository_id=data["repo_id"],
                source_file_id=data["file1_id"],
                source_line=362,
                source_column=4,
                source_end_column=17,
                reference_text="setup_logging",
                reference_type=ReferenceType.CALL,
                target_symbol_id=data["symbol1_id"],
            )
        )

        # Reference to setup_logging at line 541 on feature's file version
        await repos.reference.save(
            Reference(
                repository_id=data["repo_id"],
                source_file_id=data["file2_id"],
                source_line=541,
                source_column=4,
                source_end_column=17,
                reference_text="setup_logging",
                reference_type=ReferenceType.CALL,
                target_symbol_id=data["symbol2_id"],
            )
        )

        # When browsing main, should see reference at line 362, not 541
        results = await repos.reference.find_references_to_symbol(
            data["symbol1_id"],
            branch="main",
        )

        assert len(results) == 1, (
            f"Expected 1 reference on 'main', got {len(results)}. "
            "Bug #47: branch param ignored, global dedup returns wrong file version."
        )
        assert results[0].source_file_id == data["file1_id"]
        assert results[0].source_line == 362, (
            f"Expected line 362 (main's version), got {results[0].source_line}. "
            "Bug #47: wrong line number from different branch's file version."
        )

    async def test_references_on_feature_use_feature_line_numbers(
        self, repos: Repos
    ) -> None:
        """References on 'feature' should come from feature's file version."""
        data = await _setup_two_branches(repos)

        await repos.reference.save(
            Reference(
                repository_id=data["repo_id"],
                source_file_id=data["file1_id"],
                source_line=362,
                source_column=4,
                source_end_column=17,
                reference_text="setup_logging",
                reference_type=ReferenceType.CALL,
                target_symbol_id=data["symbol1_id"],
            )
        )
        await repos.reference.save(
            Reference(
                repository_id=data["repo_id"],
                source_file_id=data["file2_id"],
                source_line=541,
                source_column=4,
                source_end_column=17,
                reference_text="setup_logging",
                reference_type=ReferenceType.CALL,
                target_symbol_id=data["symbol2_id"],
            )
        )

        results = await repos.reference.find_references_to_symbol(
            data["symbol2_id"],
            branch="feature",
        )

        assert len(results) == 1
        assert results[0].source_file_id == data["file2_id"]
        assert results[0].source_line == 541


class TestFindReferencesToSymbolWithRepositoryId:
    """find_references_to_symbol with repository_id scopes dedup correctly.

    Regression test for issue #148: Without repository_id, the
    latest_file_ids_subquery scans ALL repositories, causing cross-repo
    pollution when multiple repos share the same branch name.

    Uses TWO repositories that both have a "main" branch to verify that
    passing repository_id restricts the latest-file dedup to the correct repo.
    """

    async def test_repository_id_scopes_dedup_across_repos(self, repos: Repos) -> None:
        """With two repos sharing branch 'main', repository_id prevents cross-repo pollution.

        Bug #148: find_references_to_symbol didn't pass repository_id to
        latest_file_ids_subquery, so the branch filter matched commits
        across all repos with that branch name.
        """
        from inxr2.domain.entities import Repository

        # --- Repo A ---
        repo_a = await repos.repository.save(
            Repository(name="repo-a", url="https://example.com/a.git")
        )
        assert repo_a.id is not None
        commit_a = await create_test_commit(
            repos, repo_a.id, "a" * 40, date_offset_days=0
        )
        await repos.commit.link_commit_to_branch(repo_a.id, commit_a, "main")
        file_a = await create_test_file(
            repos, repo_a.id, commit_a, "src/app.py", "ca" * 20
        )
        symbol_a = await create_test_symbol(
            repos, file_a, repo_a.id, commit_a, "handler", "mod.handler"
        )
        await repos.reference.save(
            Reference(
                repository_id=repo_a.id,
                source_file_id=file_a,
                source_line=10,
                source_column=0,
                source_end_column=7,
                reference_text="handler",
                reference_type=ReferenceType.CALL,
                target_symbol_id=symbol_a,
            )
        )

        # --- Repo B (same branch name "main", same file path) ---
        repo_b = await repos.repository.save(
            Repository(name="repo-b", url="https://example.com/b.git")
        )
        assert repo_b.id is not None
        commit_b = await create_test_commit(
            repos, repo_b.id, "b" * 40, date_offset_days=1
        )
        await repos.commit.link_commit_to_branch(repo_b.id, commit_b, "main")
        file_b = await create_test_file(
            repos, repo_b.id, commit_b, "src/app.py", "cb" * 20
        )

        # Reference in repo B that intentionally targets symbol_a, simulating
        # a data integrity issue where a reference points at a symbol in
        # a different repository.
        await repos.reference.save(
            Reference(
                repository_id=repo_b.id,
                source_file_id=file_b,
                source_line=99,
                source_column=0,
                source_end_column=7,
                reference_text="handler",
                reference_type=ReferenceType.CALL,
                target_symbol_id=symbol_a,
            )
        )

        # Query scoped to repo A — should only return repo A's reference
        results = await repos.reference.find_references_to_symbol(
            symbol_a,
            branch="main",
            repository_id=repo_a.id,
        )

        assert len(results) == 1, (
            f"Expected 1 reference from repo A, got {len(results)}. "
            "Bug #148: repository_id not passed to latest_file_ids_subquery, "
            "so files from repo B leaked into the result set."
        )
        assert results[0].source_file_id == file_a
        assert results[0].source_line == 10


class TestFindReferencesByTextBranchDedup:
    """find_references_by_text with branch should scope dedup to that branch."""

    async def test_text_search_on_main_returns_main_references(
        self, repos: Repos
    ) -> None:
        """find_references_by_text on 'main' should return from main's file version.

        Bug: branch param is ignored, global dedup picks feature's file version.
        """
        data = await _setup_two_branches(repos)

        await repos.reference.save(
            Reference(
                repository_id=data["repo_id"],
                source_file_id=data["file1_id"],
                source_line=100,
                source_column=0,
                source_end_column=13,
                reference_text="setup_logging",
                reference_type=ReferenceType.CALL,
            )
        )
        await repos.reference.save(
            Reference(
                repository_id=data["repo_id"],
                source_file_id=data["file2_id"],
                source_line=200,
                source_column=0,
                source_end_column=13,
                reference_text="setup_logging",
                reference_type=ReferenceType.CALL,
            )
        )

        results = await repos.reference.find_references_by_text(
            "setup_logging",
            data["repo_id"],
            branch="main",
        )

        assert len(results) == 1, (
            f"Expected 1 reference on 'main', got {len(results)}. "
            "Bug #47: branch param ignored in find_references_by_text."
        )
        assert results[0].source_file_id == data["file1_id"]
        assert results[0].source_line == 100

    async def test_text_search_on_feature_returns_feature_references(
        self, repos: Repos
    ) -> None:
        """find_references_by_text on 'feature' should return from feature's file."""
        data = await _setup_two_branches(repos)

        await repos.reference.save(
            Reference(
                repository_id=data["repo_id"],
                source_file_id=data["file1_id"],
                source_line=100,
                source_column=0,
                source_end_column=13,
                reference_text="setup_logging",
                reference_type=ReferenceType.CALL,
            )
        )
        await repos.reference.save(
            Reference(
                repository_id=data["repo_id"],
                source_file_id=data["file2_id"],
                source_line=200,
                source_column=0,
                source_end_column=13,
                reference_text="setup_logging",
                reference_type=ReferenceType.CALL,
            )
        )

        results = await repos.reference.find_references_by_text(
            "setup_logging",
            data["repo_id"],
            branch="feature",
        )

        assert len(results) == 1
        assert results[0].source_file_id == data["file2_id"]
        assert results[0].source_line == 200
