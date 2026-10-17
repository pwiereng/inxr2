"""End-to-end test: dead code stays accurate across incremental indexing (#548).

Indexes commit A, then commit B in which only app.py changes, with the real
CLI (git, tree-sitter, PostgreSQL test database). B reuses lib.py's file
version from A without re-parsing it, so the dead-code scan must combine the
reused version's symbols with B's new references.
"""

from pathlib import Path
from typing import Any

from click.testing import CliRunner
from git import Repo
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories import (
    PostgresCommitRepository,
    PostgresReferenceRepository,
    PostgresRepositoryAdapter,
)
from tests.adapters.cli.test_incremental_deletion import _commit, _run

REPO_NAME = "dead-code-e2e-repo"

LIB_PY = """\
def helper():
    return 1


def orphan():
    return 2


class Widget:
    pass
"""

APP_A = """\
def main(x):
    helper()
    return isinstance(x, Widget)
"""

APP_B = """\
def main(x):
    return isinstance(x, Widget)
"""

TEST_APP_PY = """\
import pytest


@pytest.fixture
def db():
    return None


def test_main(db):
    assert db is None
"""


class TestIncrementalDeadCode:
    def test_dead_code_follows_the_head_with_reused_file_versions(
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

        (repo_path / "lib.py").write_text(LIB_PY)
        (repo_path / "app.py").write_text(APP_A)
        (repo_path / "test_app.py").write_text(TEST_APP_PY)
        repo.index.add(["lib.py", "app.py", "test_app.py"])
        hash_a = _commit(repo, "A", "2024-01-01T10:00:00")
        result = isolated_cli_runner.invoke(
            main, ["index", "--path", str(repo_path), "--branch", "main"]
        )
        assert result.exit_code == 0, result.output

        # B drops the only call to helper; lib.py and test_app.py are unchanged
        (repo_path / "app.py").write_text(APP_B)
        repo.index.add(["app.py"])
        _commit(repo, "B", "2024-01-02T10:00:00")
        result = isolated_cli_runner.invoke(
            main, ["index", "--path", str(repo_path), "--branch", "main"]
        )
        assert result.exit_code == 0, result.output

        async def query(session: AsyncSession) -> dict[str, Any]:
            repo_entity = await PostgresRepositoryAdapter(session).find_by_name(
                REPO_NAME
            )
            assert repo_entity is not None and repo_entity.id is not None
            commit_a = await PostgresCommitRepository(session).find_by_hash(
                repo_entity.id, hash_a
            )
            assert commit_a is not None
            refs = PostgresReferenceRepository(session)
            at_head = await refs.find_unreferenced_symbols(repo_entity.id)
            at_a = await refs.find_unreferenced_symbols(
                repo_entity.id, commit_id=commit_a.id
            )
            return {
                "head": {s.name for s in at_head.symbols},
                "head_entry_points": at_head.entry_points,
                "head_scanned": at_head.scanned,
                "a": {s.name for s in at_a.symbols},
            }

        out = _run(cli_test_db, query)

        # helper lost its only caller in B; Widget is still used by isinstance
        assert out["head"] == {"main", "orphan", "helper"}
        assert out["a"] == {"main", "orphan"}
        # test_main and the db fixture are run by pytest, not called
        assert out["head_entry_points"] == 2
        # helper, orphan, Widget, main, db, test_main
        assert out["head_scanned"] == 6
