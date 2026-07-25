"""Integration tests for git-service-backed /api/files endpoints.

Covers the raw-content, blame, and file-id content routes whose error and
encoding branches need a git service double plus a real on-disk repo path.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from inxr2.adapters.persistence.repositories.file_adapter import PostgresFileRepository
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from inxr2.application.ports.services import BlameLineInfo
from inxr2.domain.entities import Commit, File, Repository
from inxr2.domain.value_objects import CommitHash
from inxr2.infrastructure.dependencies import get_git_service
from tests.fixtures.test_doubles import FakeGitService


def _hash(prefix: str) -> CommitHash:
    return CommitHash((prefix + "0" * 40)[:40])


async def _make_repo_with_file(
    db_session: AsyncSession,
    *,
    name: str,
    url: str,
    path: str,
) -> tuple[Repository, Commit, File]:
    """Create repo/commit/file and link file→commit→main branch."""
    repo_adapter = PostgresRepositoryAdapter(db_session)
    repo = await repo_adapter.save(Repository(name=name, url=url))
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

    file_adapter = PostgresFileRepository(db_session)
    file = await file_adapter.save(
        File(
            repository_id=repo.id,
            path=path,
            content_hash="a" * 40,
            size_bytes=100,
            language="python",
        )
    )
    assert file.id is not None
    await file_adapter.link_file_to_commit(file.id, commit.id)
    await commit_adapter.link_commit_to_branch(
        repository_id=repo.id, commit_id=commit.id, branch="main"
    )
    return repo, commit, file


@pytest.mark.asyncio
class TestRawContentByPath:
    """GET /api/files/by-path/raw."""

    async def test_png_returns_base64(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_repo_with_file(
            db_session, name="raw-png", url=str(tmp_path), path="img/logo.png"
        )
        test_app.dependency_overrides[get_git_service] = lambda: FakeGitService()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path/raw",
                params={"repo": "raw-png", "path": "img/logo.png"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["content_type"] == "image/png"
        assert data["encoding"] == "base64"

    async def test_svg_returns_utf8(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_repo_with_file(
            db_session, name="raw-svg", url=str(tmp_path), path="img/icon.svg"
        )
        fake = FakeGitService()
        fake.set_file_content(
            str(tmp_path), _hash("raw-sv").value, "img/icon.svg", "<svg></svg>"
        )
        test_app.dependency_overrides[get_git_service] = lambda: fake

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path/raw",
                params={"repo": "raw-svg", "path": "img/icon.svg"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["encoding"] == "utf-8"
        assert data["content_type"] == "image/svg+xml"
        assert "<svg" in data["data"]

    async def test_svg_invalid_utf8_falls_back_to_base64(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_repo_with_file(
            db_session, name="raw-svgbad", url=str(tmp_path), path="img/bad.svg"
        )

        class BadSvgGit(FakeGitService):
            def get_file_raw_content(
                self, repo_path: Path, commit_hash: str, file_path: str
            ) -> bytes:
                return b"\xff\xfe\x00"

        test_app.dependency_overrides[get_git_service] = lambda: BadSvgGit()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path/raw",
                params={"repo": "raw-svgbad", "path": "img/bad.svg"},
            )

        assert response.status_code == 200
        assert response.json()["encoding"] == "base64"

    async def test_unsupported_extension_returns_400(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_repo_with_file(
            db_session, name="raw-py", url=str(tmp_path), path="src/main.py"
        )
        test_app.dependency_overrides[get_git_service] = lambda: FakeGitService()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path/raw",
                params={"repo": "raw-py", "path": "src/main.py"},
            )

        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    async def test_repo_path_missing_returns_404(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_repo_with_file(
            db_session,
            name="raw-nopath",
            url=str(tmp_path / "does-not-exist"),
            path="img/logo.png",
        )
        test_app.dependency_overrides[get_git_service] = lambda: FakeGitService()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path/raw",
                params={"repo": "raw-nopath", "path": "img/logo.png"},
            )

        assert response.status_code == 404
        assert "Repository path not found" in response.json()["detail"]

    async def test_file_not_found_at_commit_returns_404(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_repo_with_file(
            db_session, name="raw-gone", url=str(tmp_path), path="img/logo.png"
        )

        class MissingGit(FakeGitService):
            def get_file_raw_content(
                self, repo_path: Path, commit_hash: str, file_path: str
            ) -> bytes:
                raise FileNotFoundError(file_path)

        test_app.dependency_overrides[get_git_service] = lambda: MissingGit()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path/raw",
                params={"repo": "raw-gone", "path": "img/logo.png"},
            )

        assert response.status_code == 404
        assert "not found at this commit" in response.json()["detail"]


@pytest.mark.asyncio
class TestBlameByPath:
    """GET /api/files/by-path/blame."""

    async def test_blame_success(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        repo, commit, _ = await _make_repo_with_file(
            db_session, name="blame-ok", url=str(tmp_path), path="src/app.py"
        )

        class BlameGit(FakeGitService):
            def get_blame(
                self, repo_path: Path, commit_hash: str, file_path: str
            ) -> list[BlameLineInfo]:
                return [
                    BlameLineInfo(
                        line_number=1,
                        commit_hash=commit.commit_hash.value,
                        short_hash=commit.commit_hash.value[:7],
                        author_name="Author",
                        commit_date=datetime(2025, 1, 1, tzinfo=UTC),
                        message="msg",
                    ),
                    BlameLineInfo(
                        line_number=2,
                        commit_hash="f" * 40,
                        short_hash="fffffff",
                        author_name="Other",
                        commit_date=datetime(2025, 1, 2, tzinfo=UTC),
                        message="other",
                    ),
                ]

        test_app.dependency_overrides[get_git_service] = lambda: BlameGit()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path/blame",
                params={"repo": "blame-ok", "path": "src/app.py"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        indexed = {line["line_number"]: line["is_indexed"] for line in data["lines"]}
        # The indexed commit is recognized; the unknown hash is not.
        assert indexed[1] is True
        assert indexed[2] is False

    async def test_blame_repo_path_missing_returns_404(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_repo_with_file(
            db_session,
            name="blame-nopath",
            url=str(tmp_path / "nope"),
            path="src/app.py",
        )
        test_app.dependency_overrides[get_git_service] = lambda: FakeGitService()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path/blame",
                params={"repo": "blame-nopath", "path": "src/app.py"},
            )

        assert response.status_code == 404
        assert "Repository path not found" in response.json()["detail"]

    async def test_blame_file_not_found_returns_404(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_repo_with_file(
            db_session, name="blame-gone", url=str(tmp_path), path="src/app.py"
        )

        class MissingGit(FakeGitService):
            def get_blame(
                self, repo_path: Path, commit_hash: str, file_path: str
            ) -> list[BlameLineInfo]:
                raise FileNotFoundError(file_path)

        test_app.dependency_overrides[get_git_service] = lambda: MissingGit()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path/blame",
                params={"repo": "blame-gone", "path": "src/app.py"},
            )

        assert response.status_code == 404
        assert "not found at this commit" in response.json()["detail"]

    async def test_blame_value_error_returns_500(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_repo_with_file(
            db_session, name="blame-err", url=str(tmp_path), path="src/app.py"
        )

        class BrokenGit(FakeGitService):
            def get_blame(
                self, repo_path: Path, commit_hash: str, file_path: str
            ) -> list[BlameLineInfo]:
                raise ValueError("bad repo")

        test_app.dependency_overrides[get_git_service] = lambda: BrokenGit()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/files/by-path/blame",
                params={"repo": "blame-err", "path": "src/app.py"},
            )

        assert response.status_code == 500
        assert "Unable to access repository" in response.json()["detail"]


@pytest.mark.asyncio
class TestFileContentById:
    """GET /api/files/{file_id}/content."""

    async def test_success(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        _, _, file = await _make_repo_with_file(
            db_session, name="content-ok", url=str(tmp_path), path="src/app.py"
        )
        fake = FakeGitService()
        fake.set_file_content(
            str(tmp_path), _hash("conten").value, "src/app.py", "line1\nline2"
        )
        test_app.dependency_overrides[get_git_service] = lambda: fake

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/files/{file.id}/content")

        assert response.status_code == 200
        data = response.json()
        # No trailing newline → line_count counts the final partial line.
        assert data["line_count"] == 2
        assert data["content"] == "line1\nline2"

    async def test_file_not_found_returns_404(self, test_app: FastAPI) -> None:
        test_app.dependency_overrides[get_git_service] = lambda: FakeGitService()
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/files/999999/content")
        assert response.status_code == 404
        assert response.json()["detail"] == "File not found"

    async def test_no_commit_linked_returns_404(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repo = await repo_adapter.save(
            Repository(name="content-nolink", url="https://example.com/x.git")
        )
        assert repo.id is not None
        file_adapter = PostgresFileRepository(db_session)
        file = await file_adapter.save(
            File(
                repository_id=repo.id,
                path="src/orphan.py",
                content_hash="b" * 40,
                size_bytes=10,
                language="python",
            )
        )
        test_app.dependency_overrides[get_git_service] = lambda: FakeGitService()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/files/{file.id}/content")

        assert response.status_code == 404
        assert "No commit linked" in response.json()["detail"]

    async def test_repo_path_missing_returns_500(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        _, _, file = await _make_repo_with_file(
            db_session,
            name="content-nopath",
            url=str(tmp_path / "missing"),
            path="src/app.py",
        )
        test_app.dependency_overrides[get_git_service] = lambda: FakeGitService()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/files/{file.id}/content")

        assert response.status_code == 500
        assert "Repository path not found" in response.json()["detail"]

    async def test_git_file_not_found_returns_404(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        _, _, file = await _make_repo_with_file(
            db_session, name="content-gitgone", url=str(tmp_path), path="src/app.py"
        )

        class MissingGit(FakeGitService):
            def get_file_content(
                self, repo_path: Path, commit_hash: str, file_path: str
            ) -> str:
                raise FileNotFoundError("missing in git")

        test_app.dependency_overrides[get_git_service] = lambda: MissingGit()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/files/{file.id}/content")

        assert response.status_code == 404
        assert "missing in git" in response.json()["detail"]

    async def test_binary_file_returns_400(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        _, _, file = await _make_repo_with_file(
            db_session, name="content-bin", url=str(tmp_path), path="src/app.py"
        )

        class BinaryGit(FakeGitService):
            def get_file_content(
                self, repo_path: Path, commit_hash: str, file_path: str
            ) -> str:
                raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")

        test_app.dependency_overrides[get_git_service] = lambda: BinaryGit()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/files/{file.id}/content")

        assert response.status_code == 400
        assert "binary" in response.json()["detail"].lower()
