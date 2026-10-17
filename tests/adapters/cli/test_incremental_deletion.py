"""End-to-end regression test for issue #547.

A file deleted between two indexed commits must be absent at the newer
commit after incremental indexing: from file lookup (get_file_structure),
symbol search, the dead-code symbol scan and code search.

Indexes a throwaway git repository in tmp_path with the real CLI (real git,
tree-sitter and PostgreSQL test database), then queries through the same
adapters and use cases the API uses.
"""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

import pytest
from click.testing import CliRunner
from git import Repo
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from inxr2.adapters.persistence.repositories import (
    PostgresCommitRepository,
    PostgresFileRepository,
    PostgresFileVersionRepository,
    PostgresReferenceRepository,
    PostgresRepositoryAdapter,
    PostgresSymbolRepository,
    PostgresTextSearchRepository,
)
from inxr2.application.ports.services import TextSearchQuery
from inxr2.application.use_cases.files import ResolveFileRequest, ResolveFileUseCase
from inxr2.domain.exceptions import FileNotFound
from tests.db_helpers import normalize_asyncpg_url

T = TypeVar("T")

REPO_NAME = "deletion-e2e-repo"

KEEP_PY = """\
# keepmarker
def kept_func():
    return 1
"""

GONE_PY = """\
# zebramarker
class GoneThing:
    def gone_method(self):
        return 2
"""


def _commit(repo: Repo, message: str, date: str) -> str:
    """Commit the staged index with fixed author/committer dates."""
    commit = repo.index.commit(message, author_date=date, commit_date=date)
    return commit.hexsha


@pytest.fixture
def git_repo(tmp_path: Path) -> tuple[Path, str]:
    """Repo whose commit A has keep.py + gone.py. Returns (repo_path, hash_a).

    The test creates commit B (deleting gone.py) after indexing A.
    """
    repo_path = tmp_path / REPO_NAME
    repo_path.mkdir()
    repo = Repo.init(repo_path, initial_branch="main")
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    (repo_path / "keep.py").write_text(KEEP_PY)
    (repo_path / "gone.py").write_text(GONE_PY)
    repo.index.add(["keep.py", "gone.py"])
    hash_a = _commit(repo, "A: add keep.py and gone.py", "2024-01-01T10:00:00")
    return repo_path, hash_a


def _run(
    db_url: str,
    fn: Callable[[AsyncSession], Coroutine[Any, Any, T]],
) -> T:
    """Run an async query against the CLI test database in a fresh session."""

    async def runner() -> T:
        engine = create_async_engine(normalize_asyncpg_url(db_url), echo=False)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(runner())


class TestIncrementalIndexingDropsDeletedFiles:
    """Issue #547: deleted files are not served at the newer branch head."""

    def test_deleted_file_absent_after_incremental_index(
        self,
        isolated_cli_runner: CliRunner,
        cli_test_db: str,
        git_repo: tuple[Path, str],
    ) -> None:
        from inxr2.cli import main

        repo_path, hash_a = git_repo

        # Index commit A (fresh)
        result = isolated_cli_runner.invoke(
            main, ["index", "--path", str(repo_path), "--branch", "main"]
        )
        assert result.exit_code == 0, result.output

        # Commit B deletes gone.py; index incrementally
        repo = Repo(repo_path)
        repo.index.remove(["gone.py"], working_tree=True)
        hash_b = _commit(repo, "B: delete gone.py", "2024-01-02T10:00:00")
        result = isolated_cli_runner.invoke(
            main, ["index", "--path", str(repo_path), "--branch", "main"]
        )
        assert result.exit_code == 0, result.output

        async def query(session: AsyncSession) -> dict[str, Any]:
            repo_entity = await PostgresRepositoryAdapter(session).find_by_name(
                REPO_NAME
            )
            assert repo_entity is not None and repo_entity.id is not None
            repo_id = repo_entity.id
            commit_repo = PostgresCommitRepository(session)
            commit_a = await commit_repo.find_by_hash(repo_id, hash_a)
            commit_b = await commit_repo.find_by_hash(repo_id, hash_b)
            assert commit_a is not None and commit_b is not None

            file_repo = PostgresFileRepository(session)
            resolve = ResolveFileUseCase(
                repository_repo=PostgresRepositoryAdapter(session),
                file_repo=file_repo,
                file_version_repo=PostgresFileVersionRepository(session),
                commit_repo=commit_repo,
            )
            lookups: dict[str, str] = {}
            for label, branch in (("default", None), ("main", "main")):
                try:
                    await resolve.execute(
                        ResolveFileRequest(
                            repository_name=REPO_NAME,
                            file_path="gone.py",
                            branch=branch,
                        )
                    )
                    lookups[label] = "found"
                except FileNotFound:
                    lookups[label] = "not found"
            at_a = await resolve.execute(
                ResolveFileRequest(
                    repository_name=REPO_NAME,
                    file_path="gone.py",
                    commit_hash=hash_a,
                )
            )

            symbol_repo = PostgresSymbolRepository(session)
            gone_symbols, _ = await symbol_repo.search_by_name(
                "GoneThing", repository_id=repo_id, branch="main"
            )
            # find_dead_code's whole-head scan (#548)
            dead = await PostgresReferenceRepository(session).find_unreferenced_symbols(
                repo_id, branch="main"
            )
            scan_files = {
                f.path
                for f in (
                    await file_repo.find_by_ids(list({s.file_id for s in dead.symbols}))
                ).values()
            }

            text_search = PostgresTextSearchRepository(session)
            gone_text, gone_text_total = await text_search.search(
                TextSearchQuery(query="zebramarker", repository_id=repo_id)
            )
            keep_text, _ = await text_search.search(
                TextSearchQuery(query="keepmarker", repository_id=repo_id)
            )

            return {
                "lookups": lookups,
                "at_a_path": at_a.file.path,
                "gone_symbols": gone_symbols,
                "scan_files": scan_files,
                "gone_text_total": gone_text_total,
                "gone_text": gone_text,
                "keep_text_count": len(keep_text),
            }

        out = _run(cli_test_db, query)

        # File lookup (get_file_structure): gone at head, present at commit A
        assert out["lookups"] == {"default": "not found", "main": "not found"}
        assert out["at_a_path"] == "gone.py"
        # Symbol search
        assert out["gone_symbols"] == []
        # Dead-code scan covers only files that exist at head
        assert out["scan_files"] == {"keep.py"}
        # Code search
        assert out["gone_text"] == [] and out["gone_text_total"] == 0
        assert out["keep_text_count"] >= 1

    def test_same_second_commits_indexed_in_one_run(
        self,
        isolated_cli_runner: CliRunner,
        cli_test_db: str,
        git_repo: tuple[Path, str],
    ) -> None:
        """Issue #549: the head is git's HEAD even when commits tie on date.

        Commits A and B share a timestamp and are indexed newest-first in one
        run, so B (the HEAD, which deletes gone.py) gets the lower id. A date
        and id tie-break would pick A and serve the deleted file again.
        """
        from inxr2.cli import main

        repo_path, _ = git_repo
        repo = Repo(repo_path)
        # Re-date A to the last hour so --days picks it up; B gets the same date
        now = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        repo.git.commit(
            "--amend", "--no-edit", f"--date={now}", env={"GIT_COMMITTER_DATE": now}
        )
        repo.index.remove(["gone.py"], working_tree=True)
        hash_b = _commit(repo, "B: delete gone.py", now)
        hash_a = repo.head.commit.parents[0].hexsha
        assert repo.head.commit.committed_date == repo.commit(hash_a).committed_date

        result = isolated_cli_runner.invoke(
            main,
            ["index", "--path", str(repo_path), "--branch", "main", "--days", "1"],
        )
        assert result.exit_code == 0, result.output

        async def query(session: AsyncSession) -> dict[str, Any]:
            repo_entity = await PostgresRepositoryAdapter(session).find_by_name(
                REPO_NAME
            )
            assert repo_entity is not None and repo_entity.id is not None
            commit_repo = PostgresCommitRepository(session)
            commit_a = await commit_repo.find_by_hash(repo_entity.id, hash_a)
            commit_b = await commit_repo.find_by_hash(repo_entity.id, hash_b)
            assert commit_a is not None and commit_a.id is not None
            assert commit_b is not None and commit_b.id is not None
            head = await commit_repo.find_latest_by_branch(repo_entity.id, "main")
            gone, _ = await PostgresSymbolRepository(session).search_by_name(
                "GoneThing", repository_id=repo_entity.id, branch="main"
            )
            return {
                "b_has_lower_id": commit_b.id < commit_a.id,
                "head": head.commit_hash.value if head else None,
                "gone": gone,
            }

        out = _run(cli_test_db, query)

        assert out["b_has_lower_id"]  # the ordering that defeats an id tie-break
        assert out["head"] == hash_b
        assert out["gone"] == []


async def _app_reference_targets(
    session: AsyncSession, head_hash: str, source_path: str
) -> dict[str, str | None]:
    """Map reference text -> target symbol's file path, for one file at a commit."""
    repo_entity = await PostgresRepositoryAdapter(session).find_by_name(REPO_NAME)
    assert repo_entity is not None and repo_entity.id is not None
    commit = await PostgresCommitRepository(session).find_by_hash(
        repo_entity.id, head_hash
    )
    assert commit is not None and commit.id is not None
    file_repo = PostgresFileRepository(session)
    source = await file_repo.find_by_path(repo_entity.id, commit.id, source_path)
    assert source is not None and source.id is not None
    symbol_repo = PostgresSymbolRepository(session)
    targets: dict[str, str | None] = {}
    for ref in await PostgresReferenceRepository(session).list_by_file(source.id):
        target_path: str | None = None
        if ref.target_symbol_id is not None:
            symbol = await symbol_repo.find_by_id(ref.target_symbol_id)
            assert symbol is not None
            target_file = await file_repo.find_by_id(symbol.file_id)
            target_path = target_file.path if target_file else None
        targets[ref.reference_text] = target_path
    return targets


class TestIncrementalResolutionTargetsNewHead:
    """References resolve against the commit just indexed, not the previous head.

    Resolution runs before index_status records the new HEAD, so a head
    lookup by index_status during the run would still see the previous
    run's HEAD (PR #551 review).
    """

    def test_new_symbols_are_targets_and_deleted_ones_are_not(
        self,
        isolated_cli_runner: CliRunner,
        cli_test_db: str,
        tmp_path: Path,
    ) -> None:
        from inxr2.cli import main

        repo_path = tmp_path / REPO_NAME
        repo_path.mkdir()
        repo = Repo.init(repo_path, initial_branch="main")
        repo.config_writer().set_value("user", "name", "Test User").release()
        repo.config_writer().set_value("user", "email", "test@example.com").release()

        # Commit A: lib_old.py and app.py calling old_helper
        (repo_path / "lib_old.py").write_text("def old_helper():\n    return 1\n")
        (repo_path / "app.py").write_text(
            "from lib_old import old_helper\n\n\ndef main():\n    return old_helper()\n"
        )
        repo.index.add(["lib_old.py", "app.py"])
        _commit(repo, "A", "2024-01-01T10:00:00")
        result = isolated_cli_runner.invoke(
            main, ["index", "--path", str(repo_path), "--branch", "main"]
        )
        assert result.exit_code == 0, result.output

        # Commit B: add lib_new.py, call new_helper (and still old_helper),
        # delete lib_old.py; index incrementally
        (repo_path / "lib_new.py").write_text("def new_helper():\n    return 2\n")
        (repo_path / "app.py").write_text(
            "from lib_new import new_helper\n\n\n"
            "def main():\n    return new_helper() + old_helper()\n"
        )
        repo.index.add(["lib_new.py", "app.py"])
        repo.index.remove(["lib_old.py"], working_tree=True)
        hash_b = _commit(repo, "B", "2024-01-02T10:00:00")
        result = isolated_cli_runner.invoke(
            main, ["index", "--path", str(repo_path), "--branch", "main"]
        )
        assert result.exit_code == 0, result.output

        targets = _run(
            cli_test_db, lambda s: _app_reference_targets(s, hash_b, "app.py")
        )

        # Added in this run: resolved to the new file
        assert targets.get("new_helper") == "lib_new.py"
        # Deleted in this run: the reference is recorded but has no target
        assert "old_helper" in targets
        assert targets["old_helper"] is None

    def test_first_run_with_same_second_commits_resolves_at_head(
        self,
        isolated_cli_runner: CliRunner,
        cli_test_db: str,
        tmp_path: Path,
    ) -> None:
        """No index_status exists yet on a first run; the date tie-break
        would pick the older of two same-second commits (#549)."""
        from inxr2.cli import main

        repo_path = tmp_path / REPO_NAME
        repo_path.mkdir()
        repo = Repo.init(repo_path, initial_branch="main")
        repo.config_writer().set_value("user", "name", "Test User").release()
        repo.config_writer().set_value("user", "email", "test@example.com").release()
        now = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")

        (repo_path / "app.py").write_text("def main():\n    return 0\n")
        repo.index.add(["app.py"])
        _commit(repo, "A", now)
        # B (same second): add fresh.py and call fresh_func from app.py
        (repo_path / "fresh.py").write_text("def fresh_func():\n    return 3\n")
        (repo_path / "app.py").write_text(
            "from fresh import fresh_func\n\n\ndef main():\n    return fresh_func()\n"
        )
        repo.index.add(["fresh.py", "app.py"])
        hash_b = _commit(repo, "B", now)

        result = isolated_cli_runner.invoke(
            main,
            ["index", "--path", str(repo_path), "--branch", "main", "--days", "1"],
        )
        assert result.exit_code == 0, result.output

        targets = _run(
            cli_test_db, lambda s: _app_reference_targets(s, hash_b, "app.py")
        )

        assert targets.get("fresh_func") == "fresh.py"
