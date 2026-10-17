"""Contract tests for find_unreferenced_symbols (issue #548).

find_dead_code used to sample 200 symbols and probe each one over HTTP. The
repository now answers "which symbols have no reference" for the whole branch
head in one set-based query, with paging and coverage counts.

A symbol is unreferenced when no reference at the same scope (branch head, or
a specific commit) has its name as reference_text. Matching is by name, so it
needs no resolved target_symbol_id and stays correct under incremental
indexing: unchanged file versions are reused by the next commit, and their
references are compared afresh against that commit's symbols.
"""

from typing import Any

import pytest

from inxr2.domain.entities import Symbol
from inxr2.domain.value_objects import SymbolKind

from .conftest import (
    Repos,
    create_test_commit,
    create_test_file,
    create_test_reference,
    create_test_repo,
)

pytestmark = pytest.mark.contract


async def _symbol(
    repos: Repos,
    repo_id: int,
    file_id: int,
    name: str,
    kind: SymbolKind = SymbolKind.FUNCTION,
    line: int = 1,
    metadata: dict[str, Any] | None = None,
) -> int:
    saved = await repos.symbol.save(
        Symbol(
            file_id=file_id,
            repository_id=repo_id,
            name=name,
            kind=kind,
            start_line=line,
            start_column=0,
            end_line=line + 1,
            end_column=0,
            qualified_name=name,
            metadata=metadata,
        )
    )
    assert saved.id is not None
    return saved.id


class TestUnreferencedSymbolsAtHead:
    async def test_scans_every_symbol_and_returns_unreferenced(
        self, repos: Repos
    ) -> None:
        repo_id = await create_test_repo(repos)
        commit = await create_test_commit(repos, repo_id, "a" * 40)
        lib = await create_test_file(repos, repo_id, commit, "src/lib.py", "l" * 40)
        app = await create_test_file(repos, repo_id, commit, "src/app.py", "p" * 40)
        for i in range(250):
            await _symbol(repos, repo_id, lib, f"used_{i}", line=i + 1)
            await create_test_reference(repos, repo_id, commit, app, f"used_{i}")
        dead = await _symbol(repos, repo_id, lib, "dead_func", line=300)

        page = await repos.reference.find_unreferenced_symbols(repo_id)

        assert [s.id for s in page.symbols] == [dead]
        assert page.total == 1
        assert page.scanned == 250 + 1
        assert page.entry_points == 0

    async def test_entry_points_are_excluded_and_counted(self, repos: Repos) -> None:
        repo_id = await create_test_repo(repos)
        commit = await create_test_commit(repos, repo_id, "a" * 40)
        f = await create_test_file(repos, repo_id, commit, "App.swift", "s" * 40)
        await _symbol(
            repos,
            repo_id,
            f,
            "CarbingoApp",
            kind=SymbolKind.STRUCT,
            metadata={"attributes": ["main"], "entry_point": "@main"},
        )
        helper = await _symbol(
            repos, repo_id, f, "helper", line=5, metadata={"attributes": ["MainActor"]}
        )

        page = await repos.reference.find_unreferenced_symbols(repo_id)

        assert [s.id for s in page.symbols] == [helper]
        assert page.total == 1
        assert page.entry_points == 1
        assert page.scanned == 2

    async def test_entry_point_with_a_caller_is_not_counted(self, repos: Repos) -> None:
        repo_id = await create_test_repo(repos)
        commit = await create_test_commit(repos, repo_id, "a" * 40)
        f = await create_test_file(repos, repo_id, commit, "test_x.py", "t" * 40)
        await _symbol(repos, repo_id, f, "test_x", metadata={"entry_point": "pytest"})
        await _symbol(
            repos, repo_id, f, "db", line=5, metadata={"entry_point": "pytest fixture"}
        )
        await create_test_reference(repos, repo_id, commit, f, "db")

        page = await repos.reference.find_unreferenced_symbols(repo_id)

        assert page.symbols == []
        # db is referenced, so only the unreferenced test_x was excluded
        assert page.entry_points == 1
        assert page.scanned == 2

    async def test_empty_entry_point_label_still_marks_an_entry_point(
        self, repos: Repos
    ) -> None:
        repo_id = await create_test_repo(repos)
        commit = await create_test_commit(repos, repo_id, "a" * 40)
        f = await create_test_file(repos, repo_id, commit, "m.py", "m" * 40)
        await _symbol(repos, repo_id, f, "run", metadata={"entry_point": ""})

        page = await repos.reference.find_unreferenced_symbols(repo_id)

        assert page.symbols == []
        assert page.entry_points == 1

    async def test_one_entry_per_name(self, repos: Repos) -> None:
        """A header declaration and its implementation are reported once."""
        repo_id = await create_test_repo(repos)
        commit = await create_test_commit(repos, repo_id, "a" * 40)
        header = await create_test_file(repos, repo_id, commit, "src/a.h", "h" * 40)
        impl = await create_test_file(repos, repo_id, commit, "src/a.c", "c" * 40)
        # Saved first so the header has the lower id: path must decide, not id
        await _symbol(repos, repo_id, header, "dup")
        impl_sym = await _symbol(repos, repo_id, impl, "dup")
        # Within one file the earlier line wins, again against id order
        await _symbol(repos, repo_id, impl, "twice", line=50)
        early = await _symbol(repos, repo_id, impl, "twice", line=3)

        page = await repos.reference.find_unreferenced_symbols(repo_id)

        # The representative is the first location by path (a.c < a.h), then line
        assert [s.id for s in page.symbols] == [impl_sym, early]
        assert page.total == 2

    async def test_orders_by_path_and_line_and_pages(self, repos: Repos) -> None:
        repo_id = await create_test_repo(repos)
        commit = await create_test_commit(repos, repo_id, "a" * 40)
        b = await create_test_file(repos, repo_id, commit, "b.py", "b" * 40)
        a = await create_test_file(repos, repo_id, commit, "a.py", "a" * 40)
        # Names sort the opposite way to (path, line), so name order would fail
        b_late = await _symbol(repos, repo_id, b, "aaa_late", line=20)
        b_early = await _symbol(repos, repo_id, b, "mmm_early", line=2)
        a_only = await _symbol(repos, repo_id, a, "zzz_only", line=9)

        first = await repos.reference.find_unreferenced_symbols(repo_id, limit=2)
        rest = await repos.reference.find_unreferenced_symbols(
            repo_id, limit=2, offset=2
        )

        assert [s.id for s in first.symbols] == [a_only, b_early]
        assert [s.id for s in rest.symbols] == [b_late]
        assert first.total == rest.total == 3

    async def test_kind_filter_scopes_scan(self, repos: Repos) -> None:
        repo_id = await create_test_repo(repos)
        commit = await create_test_commit(repos, repo_id, "a" * 40)
        f = await create_test_file(repos, repo_id, commit, "m.swift", "m" * 40)
        await _symbol(repos, repo_id, f, "DeadClass", kind=SymbolKind.CLASS)
        func = await _symbol(repos, repo_id, f, "dead_func", line=4)
        proto = await _symbol(
            repos, repo_id, f, "DeadProto", kind=SymbolKind.PROTOCOL, line=8
        )

        funcs = await repos.reference.find_unreferenced_symbols(
            repo_id, kind="function"
        )
        interfaces = await repos.reference.find_unreferenced_symbols(
            repo_id, kind="interface"
        )

        assert [s.id for s in funcs.symbols] == [func]
        assert funcs.scanned == 1
        # "interface" also matches Swift protocols (KIND_ALIASES)
        assert [s.id for s in interfaces.symbols] == [proto]

    async def test_references_in_other_repositories_do_not_count(
        self, repos: Repos
    ) -> None:
        from inxr2.domain.entities import Repository

        repo_id = await create_test_repo(repos)
        other = await repos.repository.save(
            Repository(name="other-repo", url="https://example.com/other.git")
        )
        assert other.id is not None
        commit = await create_test_commit(repos, repo_id, "a" * 40)
        other_commit = await create_test_commit(repos, other.id, "b" * 40)
        f = await create_test_file(repos, repo_id, commit, "lib.py", "l" * 40)
        of = await create_test_file(repos, other.id, other_commit, "x.py", "x" * 40)
        sym = await _symbol(repos, repo_id, f, "lonely")
        await create_test_reference(repos, other.id, other_commit, of, "lonely")

        page = await repos.reference.find_unreferenced_symbols(repo_id)

        assert [s.id for s in page.symbols] == [sym]

    async def test_branch_scopes_symbols_and_references(self, repos: Repos) -> None:
        """main and feature heads differ: each branch sees only its own files."""
        repo_id = await create_test_repo(repos)
        main = await create_test_commit(repos, repo_id, "a" * 40, 0, branch="main")
        lib = await create_test_file(repos, repo_id, main, "lib.py", "l" * 40)
        app_main = await create_test_file(repos, repo_id, main, "app.py", "1" * 40)
        helper = await _symbol(repos, repo_id, lib, "helper")
        await create_test_reference(repos, repo_id, main, app_main, "helper")

        feature = await create_test_commit(
            repos, repo_id, "b" * 40, 1, branch="feature"
        )
        await repos.file.link_file_to_commit(lib, feature)
        app_feature = await create_test_file(
            repos, repo_id, feature, "app.py", "2" * 40
        )
        new_func = await _symbol(repos, repo_id, app_feature, "new_func")

        on_main = await repos.reference.find_unreferenced_symbols(
            repo_id, branch="main"
        )
        on_feature = await repos.reference.find_unreferenced_symbols(
            repo_id, branch="feature"
        )

        # helper is called on main only; new_func exists on feature only
        assert on_main.symbols == [] and on_main.scanned == 1
        assert [s.id for s in on_feature.symbols] == [new_func, helper]
        assert on_feature.scanned == 2

    async def test_empty_repository(self, repos: Repos) -> None:
        repo_id = await create_test_repo(repos)

        page = await repos.reference.find_unreferenced_symbols(repo_id)

        assert page.symbols == []
        assert page.total == page.scanned == page.entry_points == 0


class TestUnreferencedSymbolsIncremental:
    """Results follow the indexed head when later commits reuse file versions."""

    async def _two_commits(
        self, repos: Repos, caller_in_a: bool, caller_in_b: bool
    ) -> dict[str, int]:
        """lib.py (defines helper) is unchanged between A and B and reused.

        app.py changes between A and B; whether each version calls helper is
        set by caller_in_a / caller_in_b.
        """
        repo_id = await create_test_repo(repos)
        commit_a = await create_test_commit(repos, repo_id, "a" * 40, 0)
        lib = await create_test_file(repos, repo_id, commit_a, "lib.py", "l" * 40)
        app_a = await create_test_file(repos, repo_id, commit_a, "app.py", "1" * 40)
        helper = await _symbol(repos, repo_id, lib, "helper")
        if caller_in_a:
            await create_test_reference(repos, repo_id, commit_a, app_a, "helper")

        commit_b = await create_test_commit(repos, repo_id, "b" * 40, 1)
        await repos.file.link_file_to_commit(lib, commit_b)  # reused version
        app_b = await create_test_file(repos, repo_id, commit_b, "app.py", "2" * 40)
        if caller_in_b:
            await create_test_reference(repos, repo_id, commit_b, app_b, "helper")

        return {
            "repo_id": repo_id,
            "commit_a": commit_a,
            "commit_b": commit_b,
            "helper": helper,
        }

    @pytest.mark.parametrize("branch", ["main", None])
    async def test_symbol_becomes_dead_when_last_caller_is_removed(
        self, repos: Repos, branch: str | None
    ) -> None:
        data = await self._two_commits(repos, caller_in_a=True, caller_in_b=False)

        at_head = await repos.reference.find_unreferenced_symbols(
            data["repo_id"], branch=branch
        )
        at_a = await repos.reference.find_unreferenced_symbols(
            data["repo_id"], commit_id=data["commit_a"]
        )

        assert [s.id for s in at_head.symbols] == [data["helper"]]
        assert at_a.symbols == [] and at_a.scanned == 1

    async def test_symbol_becomes_live_when_a_caller_is_added(
        self, repos: Repos
    ) -> None:
        data = await self._two_commits(repos, caller_in_a=False, caller_in_b=True)

        at_head = await repos.reference.find_unreferenced_symbols(data["repo_id"])
        at_a = await repos.reference.find_unreferenced_symbols(
            data["repo_id"], commit_id=data["commit_a"]
        )

        assert at_head.symbols == [] and at_head.scanned == 1
        assert [s.id for s in at_a.symbols] == [data["helper"]]

    async def test_symbols_and_callers_in_deleted_files_are_ignored(
        self, repos: Repos
    ) -> None:
        """Deleted between commits: gone.py's symbols and references vanish (#547)."""
        repo_id = await create_test_repo(repos)
        commit_a = await create_test_commit(repos, repo_id, "a" * 40, 0)
        keep = await create_test_file(repos, repo_id, commit_a, "keep.py", "k" * 40)
        gone = await create_test_file(repos, repo_id, commit_a, "gone.py", "g" * 40)
        kept = await _symbol(repos, repo_id, keep, "kept_func")
        await _symbol(repos, repo_id, gone, "GoneThing")
        await create_test_reference(repos, repo_id, commit_a, gone, "kept_func")
        commit_b = await create_test_commit(repos, repo_id, "b" * 40, 1)
        await repos.file.link_file_to_commit(keep, commit_b)

        page = await repos.reference.find_unreferenced_symbols(repo_id)

        assert [s.id for s in page.symbols] == [kept]
        assert page.scanned == 1
