"""Integration tests for /api/renames by-commit and file-history endpoints."""

from collections.abc import AsyncGenerator
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from inxr2.adapters.persistence.repositories.file_rename_adapter import (
    PostgresFileRenameRepository,
)
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from inxr2.domain.entities import Commit, FileRename, Repository
from inxr2.domain.value_objects import CommitHash
from inxr2.infrastructure.database import get_db_session
from inxr2.infrastructure.fastapi.app import create_app


def _hash(prefix: str) -> CommitHash:
    return CommitHash((prefix + "0" * 40)[:40])


@pytest_asyncio.fixture
async def test_app(db_session: AsyncSession) -> FastAPI:
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db
    return app


async def _repo_and_commit(
    db_session: AsyncSession, name: str
) -> tuple[Repository, Commit]:
    repo_adapter = PostgresRepositoryAdapter(db_session)
    repo = await repo_adapter.save(
        Repository(name=name, url=f"https://example.com/{name}.git")
    )
    assert repo.id is not None
    commit_adapter = PostgresCommitRepository(db_session)
    commit = await commit_adapter.save(
        Commit(
            repository_id=repo.id,
            commit_hash=_hash(name[:6]),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
    )
    assert commit.id is not None
    return repo, commit


@pytest.mark.asyncio
class TestRenamesByCommit:
    """GET /api/renames/by-commit."""

    async def test_success(self, test_app: FastAPI, db_session: AsyncSession) -> None:
        repo, commit = await _repo_and_commit(db_session, "bc-ok")
        assert repo.id is not None and commit.id is not None
        rename_adapter = PostgresFileRenameRepository(db_session)
        await rename_adapter.save_renames(
            [
                FileRename(
                    repository_id=repo.id,
                    commit_id=commit.id,
                    old_path="src/old.py",
                    new_path="src/new.py",
                    similarity=98,
                )
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/renames/by-commit",
                params={"repo": "bc-ok", "commit": commit.commit_hash.value},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        rename = data["renames"][0]
        assert rename["old_path"] == "src/old.py"
        assert rename["new_path"] == "src/new.py"
        assert rename["similarity"] == 98
        assert rename["commit_hash"] == commit.commit_hash.value

    async def test_repo_not_found_returns_404(self, test_app: FastAPI) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/renames/by-commit",
                params={"repo": "ghost-repo", "commit": "a" * 40},
            )
        assert response.status_code == 404
        assert "Repository not found" in response.json()["detail"]

    async def test_commit_not_found_returns_404(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        await _repo_and_commit(db_session, "bc-nocommit")
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/renames/by-commit",
                params={"repo": "bc-nocommit", "commit": "f" * 40},
            )
        assert response.status_code == 404
        assert "Commit not found" in response.json()["detail"]


@pytest.mark.asyncio
class TestRenamesFileHistory:
    """GET /api/renames/file-history."""

    async def test_success(self, test_app: FastAPI, db_session: AsyncSession) -> None:
        repo, commit = await _repo_and_commit(db_session, "fh-ok")
        assert repo.id is not None and commit.id is not None
        rename_adapter = PostgresFileRenameRepository(db_session)
        await rename_adapter.save_renames(
            [
                FileRename(
                    repository_id=repo.id,
                    commit_id=commit.id,
                    old_path="src/old.py",
                    new_path="src/new.py",
                    similarity=90,
                )
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/renames/file-history",
                params={"repo": "fh-ok", "path": "src/new.py"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["renames"][0]["new_path"] == "src/new.py"
        assert data["renames"][0]["commit_hash"] == commit.commit_hash.value

    async def test_empty_history_returns_empty(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        await _repo_and_commit(db_session, "fh-empty")
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/renames/file-history",
                params={"repo": "fh-empty", "path": "src/never-renamed.py"},
            )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_repo_not_found_returns_404(self, test_app: FastAPI) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/renames/file-history",
                params={"repo": "ghost-repo", "path": "src/x.py"},
            )
        assert response.status_code == 404
        assert "Repository not found" in response.json()["detail"]
