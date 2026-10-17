"""Regression tests for issue #547: deleted files served at a branch head.

Each indexed commit is a full snapshot: commit_files links every file version
present in that commit's tree. A path deleted in a later commit is therefore
simply absent from the later commit's commit_files rows.

The bug was on the read side. "Latest file version" was computed per path over
every commit that ever contained the path, so a deleted path's last surviving
version (from the older commit) still ranked first in its own partition and
came back from symbol search, reference lookup, code search and resolution.

"Latest" now means "present at the head commit of the branch", where no
branch means the repository's default branch, and the head is the branch's
last indexed commit (issue #549).

Scenario:
  - commit A (day 0, main): src/keep.py and src/gone.py
  - commit B (day 1, main): src/keep.py only (gone.py deleted)
"""

import pytest

from inxr2.domain.entities import IndexStatus, Reference
from inxr2.domain.value_objects import ReferenceType

from .conftest import (
    Repos,
    create_test_commit,
    create_test_file,
    create_test_reference,
    create_test_repo,
    create_test_symbol,
)

pytestmark = pytest.mark.contract


async def _setup_deleted_file(repos: Repos) -> dict[str, int]:
    """Index commit A with keep.py + gone.py, then commit B without gone.py."""
    repo_id = await create_test_repo(repos)

    commit_a = await create_test_commit(
        repos, repo_id, "a" * 40, date_offset_days=0, branch="main"
    )
    keep_id = await create_test_file(repos, repo_id, commit_a, "src/keep.py", "k" * 40)
    gone_id = await create_test_file(repos, repo_id, commit_a, "src/gone.py", "g" * 40)

    # Commit B: keep.py unchanged (same file version re-linked), gone.py deleted
    commit_b = await create_test_commit(
        repos, repo_id, "b" * 40, date_offset_days=1, branch="main"
    )
    await repos.file.link_file_to_commit(keep_id, commit_b)

    kept_sym = await create_test_symbol(
        repos, keep_id, repo_id, commit_a, "kept_func", "keep.kept_func"
    )
    gone_sym = await create_test_symbol(
        repos, gone_id, repo_id, commit_a, "GoneThing", "gone.GoneThing"
    )
    # The only reference to kept_func lived in the deleted file
    await create_test_reference(repos, repo_id, commit_a, gone_id, "kept_func")

    return {
        "repo_id": repo_id,
        "commit_a": commit_a,
        "commit_b": commit_b,
        "keep_id": keep_id,
        "gone_id": gone_id,
        "kept_sym": kept_sym,
        "gone_sym": gone_sym,
    }


@pytest.mark.parametrize("branch", ["main", None])
class TestDeletedFileHiddenAtHead:
    """A path deleted between two indexed commits is absent at the newer head."""

    async def test_symbol_search_excludes_deleted_file(
        self, repos: Repos, branch: str | None
    ) -> None:
        data = await _setup_deleted_file(repos)

        gone, gone_total = await repos.symbol.search_by_name(
            "GoneThing", repository_id=data["repo_id"], branch=branch
        )
        kept, _ = await repos.symbol.search_by_name(
            "kept_func", repository_id=data["repo_id"], branch=branch
        )

        assert gone == [] and gone_total == 0
        assert [s.id for s in kept] == [data["kept_sym"]]

    async def test_regex_symbol_scan_excludes_deleted_file(
        self, repos: Repos, branch: str | None
    ) -> None:
        """find_dead_code scans symbols with regex '.'; deleted files must not appear."""
        data = await _setup_deleted_file(repos)

        results, total = await repos.symbol.search_by_name(
            ".", repository_id=data["repo_id"], branch=branch, mode="regex"
        )

        assert {s.id for s in results} == {data["kept_sym"]}
        assert total == 1

    async def test_references_by_text_exclude_deleted_file(
        self, repos: Repos, branch: str | None
    ) -> None:
        data = await _setup_deleted_file(repos)

        refs = await repos.reference.find_references_by_text(
            "kept_func", data["repo_id"], branch=branch
        )

        assert refs == []

    async def test_reference_text_search_excludes_deleted_file(
        self, repos: Repos, branch: str | None
    ) -> None:
        data = await _setup_deleted_file(repos)

        refs, total = await repos.reference.search_by_text(
            "kept_func", repository_id=data["repo_id"], branch=branch
        )

        assert refs == [] and total == 0


class TestDeletedFileUnscopedQueries:
    """Queries without a branch parameter also drop deleted paths."""

    async def test_find_by_qualified_name_excludes_deleted_file(
        self, repos: Repos
    ) -> None:
        data = await _setup_deleted_file(repos)

        assert (
            await repos.symbol.find_by_qualified_name(data["repo_id"], "gone.GoneThing")
            == []
        )
        kept = await repos.symbol.find_by_qualified_name(
            data["repo_id"], "keep.kept_func"
        )
        assert [s.id for s in kept] == [data["kept_sym"]]

    async def test_file_name_search_excludes_deleted_file(self, repos: Repos) -> None:
        data = await _setup_deleted_file(repos)

        files, total = await repos.file_search.search_by_name(
            "gone", repository_id=data["repo_id"]
        )

        assert files == [] and total == 0

    async def test_resolution_does_not_target_deleted_file_symbols(
        self, repos: Repos
    ) -> None:
        """A dangling reference must not be linked to a symbol in a deleted file."""
        data = await _setup_deleted_file(repos)
        ref = await repos.reference.save(
            Reference(
                repository_id=data["repo_id"],
                source_file_id=data["keep_id"],
                source_line=3,
                source_column=0,
                source_end_column=9,
                reference_text="GoneThing",
                reference_type=ReferenceType.CALL,
            )
        )
        assert ref.id is not None

        await repos.reference.resolve_unlinked_references(data["repo_id"])

        saved = await repos.reference.find_by_id(ref.id)
        assert saved is not None
        assert saved.target_symbol_id is None


class TestDeletedFileStillVisibleElsewhere:
    """The fix must not hide files that legitimately exist."""

    async def test_time_travel_to_older_commit_still_shows_file(
        self, repos: Repos
    ) -> None:
        data = await _setup_deleted_file(repos)

        results, _ = await repos.symbol.search_by_name(
            "GoneThing", repository_id=data["repo_id"], commit_id=data["commit_a"]
        )

        assert [s.id for s in results] == [data["gone_sym"]]

    async def test_feature_branch_head_still_has_file_deleted_on_main(
        self, repos: Repos
    ) -> None:
        """A branch whose head still has the file shows it when asked for."""
        data = await _setup_deleted_file(repos)
        # feature branches off A and keeps gone.py
        await repos.commit.link_commit_to_branch(
            data["repo_id"], data["commit_a"], "feature"
        )

        on_feature, _ = await repos.symbol.search_by_name(
            "GoneThing", repository_id=data["repo_id"], branch="feature"
        )
        on_main, _ = await repos.symbol.search_by_name(
            "GoneThing", repository_id=data["repo_id"], branch="main"
        )

        assert [s.id for s in on_feature] == [data["gone_sym"]]
        assert on_main == []

    async def test_modified_file_returns_only_head_version(self, repos: Repos) -> None:
        """A path changed (not deleted) at head resolves to the head version."""
        data = await _setup_deleted_file(repos)
        commit_c = await create_test_commit(
            repos, data["repo_id"], "c" * 40, date_offset_days=2, branch="main"
        )
        keep_v2 = await create_test_file(
            repos, data["repo_id"], commit_c, "src/keep.py", "m" * 40
        )
        v2_sym = await create_test_symbol(
            repos, keep_v2, data["repo_id"], commit_c, "kept_func", "keep.kept_func"
        )

        for branch in ("main", None):
            results, _ = await repos.symbol.search_by_name(
                "kept_func", repository_id=data["repo_id"], branch=branch
            )
            assert [s.id for s in results] == [v2_sym], branch


class TestUnscopedQueriesUseDefaultBranch:
    """With no branch, "latest" is the default branch head, not a union of heads.

    Stale, merged or abandoned branches keep their branch_commits rows, so a
    union of every branch head would resurrect paths deleted on the default
    branch, and file search would list paths browse can't open (PR #551).
    """

    async def _setup_stale_branch(self, repos: Repos) -> dict[str, int]:
        """Deleted-file scenario plus a stale `feature` branch whose head is A."""
        data = await _setup_deleted_file(repos)
        await repos.commit.link_commit_to_branch(
            data["repo_id"], data["commit_a"], "feature"
        )
        return data

    async def test_file_search_ignores_stale_branch(self, repos: Repos) -> None:
        data = await self._setup_stale_branch(repos)

        files, total = await repos.file_search.search_by_name(
            "gone", repository_id=data["repo_id"]
        )

        assert files == [] and total == 0

    async def test_references_by_text_ignore_stale_branch(self, repos: Repos) -> None:
        data = await self._setup_stale_branch(repos)

        unscoped = await repos.reference.find_references_by_text(
            "kept_func", data["repo_id"]
        )
        on_feature = await repos.reference.find_references_by_text(
            "kept_func", data["repo_id"], branch="feature"
        )

        assert unscoped == []
        assert len(on_feature) == 1

    async def test_qualified_name_ignores_stale_branch(self, repos: Repos) -> None:
        data = await self._setup_stale_branch(repos)

        assert (
            await repos.symbol.find_by_qualified_name(data["repo_id"], "gone.GoneThing")
            == []
        )

    async def test_symbol_search_ignores_stale_branch(self, repos: Repos) -> None:
        data = await self._setup_stale_branch(repos)

        results, total = await repos.symbol.search_by_name(
            "GoneThing", repository_id=data["repo_id"]
        )

        assert results == [] and total == 0


class TestBranchHeadsWithDifferentVersions:
    """Two branch heads hold different versions of the same path."""

    async def _setup(self, repos: Repos) -> dict[str, int]:
        """main head (day 0) has app.py v1; feature head (day 5, newer) has v2."""
        repo_id = await create_test_repo(repos)
        main_head = await create_test_commit(
            repos, repo_id, "a" * 40, date_offset_days=0, branch="main"
        )
        feature_head = await create_test_commit(
            repos, repo_id, "f" * 40, date_offset_days=5, branch="feature"
        )
        v1 = await create_test_file(repos, repo_id, main_head, "src/app.py", "1" * 40)
        v2 = await create_test_file(
            repos, repo_id, feature_head, "src/app.py", "2" * 40
        )
        # A file that exists only on feature
        only_feature = await create_test_file(
            repos, repo_id, feature_head, "src/feature_only.py", "3" * 40
        )
        sym_v1 = await create_test_symbol(
            repos, v1, repo_id, main_head, "run", "app.run"
        )
        sym_v2 = await create_test_symbol(
            repos, v2, repo_id, feature_head, "run", "app.run"
        )
        return {
            "repo_id": repo_id,
            "v1": v1,
            "v2": v2,
            "only_feature": only_feature,
            "sym_v1": sym_v1,
            "sym_v2": sym_v2,
        }

    async def test_unscoped_returns_default_branch_version(self, repos: Repos) -> None:
        """Even though feature's head is newer, no branch means main."""
        data = await self._setup(repos)

        unscoped, _ = await repos.symbol.search_by_name(
            "run", repository_id=data["repo_id"]
        )
        by_qname = await repos.symbol.find_by_qualified_name(data["repo_id"], "app.run")

        assert [s.id for s in unscoped] == [data["sym_v1"]]
        assert [s.id for s in by_qname] == [data["sym_v1"]]

    async def test_named_branch_returns_its_own_version(self, repos: Repos) -> None:
        data = await self._setup(repos)

        on_feature, _ = await repos.symbol.search_by_name(
            "run", repository_id=data["repo_id"], branch="feature"
        )
        on_main, _ = await repos.symbol.search_by_name(
            "run", repository_id=data["repo_id"], branch="main"
        )

        assert [s.id for s in on_feature] == [data["sym_v2"]]
        assert [s.id for s in on_main] == [data["sym_v1"]]

    async def test_file_search_matches_what_default_browse_can_open(
        self, repos: Repos
    ) -> None:
        """File search without a branch lists only default-branch files.

        Browse resolves a path without a branch against the default branch
        head, so listing feature-only files here would produce 404s.
        """
        data = await self._setup(repos)

        files, _ = await repos.file_search.search_by_name(
            "src/", repository_id=data["repo_id"]
        )

        assert {f.id for f in files} == {data["v1"]}


class TestResolutionFollowsIndexedBranch:
    """Reference resolution targets the head of the branch being indexed."""

    async def _setup(self, repos: Repos) -> dict[str, int]:
        """`helper` is defined only on feature; a feature file references it."""
        repo_id = await create_test_repo(repos)
        await create_test_commit(
            repos, repo_id, "a" * 40, date_offset_days=0, branch="main"
        )
        feature_head = await create_test_commit(
            repos, repo_id, "f" * 40, date_offset_days=1, branch="feature"
        )
        lib = await create_test_file(
            repos, repo_id, feature_head, "src/lib.py", "1" * 40
        )
        user = await create_test_file(
            repos, repo_id, feature_head, "src/user.py", "2" * 40
        )
        helper = await create_test_symbol(
            repos, lib, repo_id, feature_head, "helper", "lib.helper"
        )
        ref = await create_test_reference(repos, repo_id, feature_head, user, "helper")
        return {"repo_id": repo_id, "helper": helper, "ref": ref}

    async def test_batch_resolution_for_feature_branch(self, repos: Repos) -> None:
        data = await self._setup(repos)

        await repos.reference.prepare_resolution(data["repo_id"], branch="feature")
        await repos.reference.resolve_references_batch(data["repo_id"])

        ref = await repos.reference.find_by_id(data["ref"])
        assert ref is not None and ref.target_symbol_id == data["helper"]

    async def test_default_branch_resolution_skips_feature_only_symbols(
        self, repos: Repos
    ) -> None:
        data = await self._setup(repos)

        await repos.reference.resolve_unlinked_references(data["repo_id"])

        ref = await repos.reference.find_by_id(data["ref"])
        assert ref is not None and ref.target_symbol_id is None


class TestResolutionTargetsAnExactCommit:
    """Resolution's target pool when index_status is stale or ties exist.

    During an indexing run, resolution happens before index_status records
    the new HEAD, so the indexer passes the commit it just indexed as
    ``head_commit`` (PR #551 review).
    """

    async def _setup(self, repos: Repos) -> dict[str, int]:
        """A (old head, has old_helper) then B (new head, has new_helper).

        index_status still names A, as it does mid-run. app.py at B
        references both helpers.
        """
        repo_id = await create_test_repo(repos)
        commit_a = await create_test_commit(
            repos, repo_id, "a" * 40, date_offset_days=0, branch="main"
        )
        commit_b = await create_test_commit(
            repos, repo_id, "b" * 40, date_offset_days=1, branch="main"
        )
        lib_old = await create_test_file(
            repos, repo_id, commit_a, "lib_old.py", "1" * 40
        )
        lib_new = await create_test_file(
            repos, repo_id, commit_b, "lib_new.py", "2" * 40
        )
        app_b = await create_test_file(repos, repo_id, commit_b, "app.py", "3" * 40)
        old_sym = await create_test_symbol(
            repos, lib_old, repo_id, commit_a, "old_helper", "lib_old.old_helper"
        )
        new_sym = await create_test_symbol(
            repos, lib_new, repo_id, commit_b, "new_helper", "lib_new.new_helper"
        )
        ref_new = await create_test_reference(
            repos, repo_id, commit_b, app_b, "new_helper"
        )
        ref_old = await create_test_reference(
            repos, repo_id, commit_b, app_b, "old_helper"
        )
        await repos.index_status.save(
            IndexStatus(
                repository_id=repo_id,
                branch="main",
                indexing_status="in_progress",
                last_indexed_commit="a" * 40,  # previous run's HEAD
            )
        )
        return {
            "repo_id": repo_id,
            "old_sym": old_sym,
            "new_sym": new_sym,
            "ref_new": ref_new,
            "ref_old": ref_old,
        }

    async def _targets(self, repos: Repos, data: dict[str, int]) -> tuple:
        new = await repos.reference.find_by_id(data["ref_new"])
        old = await repos.reference.find_by_id(data["ref_old"])
        assert new is not None and old is not None
        return new.target_symbol_id, old.target_symbol_id

    async def test_batch_resolution_uses_explicit_head_commit(
        self, repos: Repos
    ) -> None:
        data = await self._setup(repos)

        await repos.reference.prepare_resolution(
            data["repo_id"], branch="main", head_commit="b" * 40
        )
        await repos.reference.resolve_references_batch(data["repo_id"])

        assert await self._targets(repos, data) == (data["new_sym"], None)

    async def test_unlinked_resolution_uses_explicit_head_commit(
        self, repos: Repos
    ) -> None:
        data = await self._setup(repos)

        await repos.reference.resolve_unlinked_references(
            data["repo_id"], branch="main", head_commit="b" * 40
        )

        assert await self._targets(repos, data) == (data["new_sym"], None)

    async def test_without_head_commit_uses_indexed_head(self, repos: Repos) -> None:
        """Covers the indexed-head ordering in LATEST_FILE_IDS_SQL.

        With no explicit commit, the pool is the branch's indexed head (A
        here, although B is newer by date).
        """
        data = await self._setup(repos)

        await repos.reference.prepare_resolution(data["repo_id"], branch="main")
        await repos.reference.resolve_references_batch(data["repo_id"])

        assert await self._targets(repos, data) == (None, data["old_sym"])


class TestHeadIsLastIndexedCommit:
    """Issue #549: the head is index_status.last_indexed_commit, not a date tie-break.

    Indexing runs newest-first, so within one run the newer commit gets the
    LOWER id. When commits share a timestamp, ``commit_date DESC, id DESC``
    picks the older one.
    """

    async def _setup_same_second(self, repos: Repos) -> dict[str, int]:
        """B (head, deletes gone.py) is saved before A; both share a timestamp."""
        repo_id = await create_test_repo(repos)
        commit_b = await create_test_commit(
            repos, repo_id, "b" * 40, date_offset_days=0, branch="main"
        )
        commit_a = await create_test_commit(
            repos, repo_id, "a" * 40, date_offset_days=0, branch="main"
        )
        assert commit_b < commit_a  # newest-first indexing order
        keep = await create_test_file(repos, repo_id, commit_a, "src/keep.py", "k" * 40)
        await repos.file.link_file_to_commit(keep, commit_b)
        gone = await create_test_file(repos, repo_id, commit_a, "src/gone.py", "g" * 40)
        gone_sym = await create_test_symbol(
            repos, gone, repo_id, commit_a, "GoneThing", "gone.GoneThing"
        )
        await repos.index_status.save(
            IndexStatus(
                repository_id=repo_id,
                branch="main",
                indexing_status="completed",
                last_indexed_commit="b" * 40,
            )
        )
        return {
            "repo_id": repo_id,
            "commit_a": commit_a,
            "commit_b": commit_b,
            "gone_sym": gone_sym,
        }

    @pytest.mark.parametrize("branch", ["main", None])
    async def test_latest_files_come_from_indexed_head(
        self, repos: Repos, branch: str | None
    ) -> None:
        data = await self._setup_same_second(repos)

        results, _ = await repos.symbol.search_by_name(
            "GoneThing", repository_id=data["repo_id"], branch=branch
        )

        assert results == []

    async def test_find_latest_by_branch_returns_indexed_head(
        self, repos: Repos
    ) -> None:
        """Browse and search agree on the head."""
        data = await self._setup_same_second(repos)

        head = await repos.commit.find_latest_by_branch(data["repo_id"], "main")

        assert head is not None and head.id == data["commit_b"]

    async def test_global_search_uses_indexed_head(self, repos: Repos) -> None:
        data = await self._setup_same_second(repos)

        results, _ = await repos.symbol.search_by_name("GoneThing", scope="latest")

        assert data["gone_sym"] not in {s.id for s in results}

    async def test_falls_back_to_newest_commit_without_index_status(
        self, repos: Repos
    ) -> None:
        """No index_status row: newest by commit date wins (distinct dates)."""
        data = await _setup_deleted_file(repos)

        head = await repos.commit.find_latest_by_branch(data["repo_id"], "main")

        assert head is not None and head.id == data["commit_b"]


class TestDistinctExtensionsAtHead:
    """The search extension filter lists only extensions present at the head."""

    async def _setup(self, repos: Repos, same_second: bool) -> int:
        """B is the head and deletes gone.rs, which only A contains.

        With ``same_second`` both commits share a timestamp and B is saved
        first (newest-first indexing), so only index_status identifies B.
        """
        repo_id = await create_test_repo(repos)
        commit_b = await create_test_commit(
            repos, repo_id, "b" * 40, date_offset_days=1, branch="main"
        )
        commit_a = await create_test_commit(
            repos,
            repo_id,
            "a" * 40,
            date_offset_days=1 if same_second else 0,
            branch="main",
        )
        keep = await create_test_file(
            repos, repo_id, commit_a, "src/keep.py", "k" * 40, extension=".py"
        )
        await repos.file.link_file_to_commit(keep, commit_b)
        await create_test_file(
            repos, repo_id, commit_a, "src/gone.rs", "g" * 40, extension=".rs"
        )
        await repos.index_status.save(
            IndexStatus(
                repository_id=repo_id,
                branch="main",
                indexing_status="completed",
                last_indexed_commit="b" * 40,
            )
        )
        return repo_id

    @pytest.mark.parametrize("branch", ["main", None])
    @pytest.mark.parametrize("same_second", [False, True])
    async def test_deleted_file_extension_not_listed(
        self, repos: Repos, branch: str | None, same_second: bool
    ) -> None:
        repo_id = await self._setup(repos, same_second)

        exts = await repos.file_search.get_distinct_extensions(
            repository_id=repo_id, branch=branch
        )

        assert exts == [".py"]
