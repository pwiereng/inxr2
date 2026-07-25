"""Integration tests for /api/commits endpoints."""

import subprocess
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from inxr2.domain.entities import Commit, Repository
from inxr2.domain.value_objects import CommitHash


def _create_git_repo_with_commits(
    repo_path: Path,
    commits: list[tuple[str, str]],
    branch: str = "main",
) -> list[str]:
    """Create a real git repo with commits and return their hashes.

    Args:
        repo_path: Directory to initialize the git repo in.
        commits: List of (filename, message) tuples for each commit.
        branch: Branch name to create commits on.

    Returns:
        List of commit hashes (oldest first).
    """
    repo_path.mkdir(parents=True, exist_ok=True)
    env = {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@test.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@test.com",
    }

    def _run(*args: str) -> str:
        result = subprocess.run(
            args,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=True,
            env={**env, "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        return result.stdout.strip()

    _run("git", "init", "-b", branch)
    hashes = []
    for filename, message in commits:
        (repo_path / filename).write_text(f"content for {filename}\n")
        _run("git", "add", filename)
        _run("git", "commit", "-m", message)
        h = _run("git", "rev-parse", "HEAD")
        hashes.append(h)
    return hashes


def make_test_commit_hash(prefix: str) -> CommitHash:
    """Create a valid 40-character test commit hash with a readable prefix.

    Args:
        prefix: A short readable prefix (will be padded to 40 chars with zeros)

    Returns:
        A CommitHash with exactly 40 characters
    """
    # Ensure exactly 40 characters (standard git commit hash length)
    padded = (prefix + "0" * 40)[:40]
    return CommitHash(padded)


@pytest.mark.asyncio
class TestCommitsAPI:
    """Tests for /api/commits endpoints (time travel)."""

    async def test_list_commits_empty(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test listing commits for a repository with no commits."""
        # Arrange - create repository without commits
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="commits-empty-repo",
            url="https://github.com/test/empty.git",
        )
        await repo_adapter.save(repository)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/commits",
                params={"repo": "commits-empty-repo"},
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["commits"] == []
        assert data["total"] == 0

    async def test_list_commits_with_data(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Test listing commits for a repository with commits."""
        # Arrange — create a real git repo so list_commits can read from git
        repo_path = tmp_path / "commits-data-repo"
        git_hashes = _create_git_repo_with_commits(
            repo_path,
            [("file1.txt", "First commit"), ("file2.txt", "Second commit")],
        )

        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="commits-data-repo",
            url=str(repo_path),
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        # Index one commit in DB so we can verify is_indexed
        commit_adapter = PostgresCommitRepository(db_session)
        indexed_commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=CommitHash(git_hashes[0]),
            author_date=datetime(2025, 1, 1),
            commit_date=datetime(2025, 1, 1),
        )
        await commit_adapter.save(indexed_commit)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/commits",
                params={"repo": "commits-data-repo"},
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["commits"]) == 2

        # Verify commit structure (newest first)
        commit = data["commits"][0]
        assert "hash" in commit
        assert "short_hash" in commit
        assert "message" in commit
        assert "author_name" in commit
        assert "commit_date" in commit
        assert "is_indexed" in commit

        # Verify is_indexed: first git commit is indexed, second is not
        by_hash = {c["hash"]: c for c in data["commits"]}
        assert by_hash[git_hashes[0]]["is_indexed"] is True
        assert by_hash[git_hashes[1]]["is_indexed"] is False

    async def test_list_commits_with_branch_filter(
        self, test_app: FastAPI, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Test filtering commits by branch."""
        # Arrange — create a real git repo with commits on main branch
        repo_path = tmp_path / "commits-branch-repo"
        _create_git_repo_with_commits(
            repo_path,
            [("file1.txt", "Main commit 1"), ("file2.txt", "Main commit 2")],
            branch="main",
        )

        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="commits-branch-repo",
            url=str(repo_path),
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        # Act — filter by main branch
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/commits",
                params={"repo": "commits-branch-repo", "branch": "main"},
            )

        # Assert — should see both commits from main
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert "message" in data["commits"][0]
        assert "is_indexed" in data["commits"][0]

    async def test_list_commits_repo_not_found(self, test_app: FastAPI) -> None:
        """Test listing commits for non-existent repository."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/commits",
                params={"repo": "nonexistent-repo"},
            )

        assert response.status_code == 404

    async def test_get_commit_by_id(
        self, test_app: FastAPI, db_session: AsyncSession
    ) -> None:
        """Test getting a specific commit by ID."""
        # Arrange
        repo_adapter = PostgresRepositoryAdapter(db_session)
        repository = Repository(
            name="commit-detail-repo",
            url="https://github.com/test/detail.git",
        )
        saved_repo = await repo_adapter.save(repository)
        assert saved_repo.id is not None

        commit_adapter = PostgresCommitRepository(db_session)
        commit = Commit(
            repository_id=saved_repo.id,
            commit_hash=make_test_commit_hash("detail1"),
            author_date=datetime(2025, 1, 1, 10, 30),
            commit_date=datetime(2025, 1, 1, 12, 0),
        )
        saved_commit = await commit_adapter.save(commit)

        # Act
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/commits/{saved_commit.id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == saved_commit.id
        assert data["hash"] == commit.commit_hash.value
        assert data["short_hash"] == "detail1"
        # Author/message/parent_hashes are hydrated from git - empty in test since repo doesn't exist
        assert "message" in data
        assert "author_name" in data
        assert "committer_name" in data
        assert "parent_hashes" in data

    async def test_get_commit_not_found(self, test_app: FastAPI) -> None:
        """Test getting a non-existent commit."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/commits/99999")

        assert response.status_code == 404
