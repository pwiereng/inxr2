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
            # find_dead_code scans every symbol with regex "."
            scan, _ = await symbol_repo.search_by_name(
                ".", repository_id=repo_id, branch="main", mode="regex", limit=500
            )
            scan_files = {
                f.path
                for f in (
                    await file_repo.find_by_ids(list({s.file_id for s in scan}))
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
