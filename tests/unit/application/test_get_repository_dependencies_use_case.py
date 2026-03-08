"""Tests for GetRepositoryDependenciesUseCase."""

from datetime import datetime

import pytest

from inxr2.application.use_cases.dependencies import (
    GetRepositoryDependenciesRequest,
    GetRepositoryDependenciesUseCase,
)
from inxr2.domain.entities import Commit, Dependency, File, Repository
from inxr2.domain.value_objects import CommitHash
from tests.fixtures.test_doubles import (
    InMemoryCommitRepository,
    InMemoryDependencyRepository,
    InMemoryFileRepository,
    InMemoryRepositoryRepository,
)


class TestGetRepositoryDependenciesUseCase:
    """Tests for retrieving dependencies at a specific commit/branch."""

    @pytest.fixture
    def repository_repo(self) -> InMemoryRepositoryRepository:
        repo = InMemoryRepositoryRepository()
        repo.add(
            Repository(
                id=1,
                name="test-repo",
                url="/path/to/repo",
                default_branch="main",
            )
        )
        return repo

    @pytest.fixture
    def file_repo(self) -> InMemoryFileRepository:
        repo = InMemoryFileRepository()
        # pyproject.toml
        repo.add(
            File(
                id=1,
                repository_id=1,
                path="pyproject.toml",
                language="python",
                size_bytes=500,
                content_hash="a" * 40,
            )
        )
        # package.json
        repo.add(
            File(
                id=2,
                repository_id=1,
                path="package.json",
                language="javascript",
                size_bytes=300,
                content_hash="b" * 40,
            )
        )
        return repo

    @pytest.fixture
    async def commit_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemoryCommitRepository:
        repo = InMemoryCommitRepository()
        # commit on main
        repo.add(
            Commit(
                id=1,
                repository_id=1,
                commit_hash=CommitHash("a" * 40),
                author_date=datetime(2026, 1, 1, 10, 0, 0),
                commit_date=datetime(2026, 1, 1, 10, 0, 0),
            )
        )
        await repo.link_commit_to_branch(1, 1, "main")
        # commit on feature branch
        repo.add(
            Commit(
                id=2,
                repository_id=1,
                commit_hash=CommitHash("b" * 40),
                author_date=datetime(2026, 1, 2, 10, 0, 0),
                commit_date=datetime(2026, 1, 2, 10, 0, 0),
            )
        )
        await repo.link_commit_to_branch(1, 2, "feature")
        # Link files to commits
        file_repo._commit_files.add((1, 1))  # commit 1 has pyproject.toml
        file_repo._commit_files.add((1, 2))  # commit 1 has package.json
        file_repo._commit_files.add((2, 1))  # commit 2 has pyproject.toml only
        return repo

    @pytest.fixture
    def dependency_repo(
        self, file_repo: InMemoryFileRepository
    ) -> InMemoryDependencyRepository:
        repo = InMemoryDependencyRepository(file_repo=file_repo)
        # Python deps from pyproject.toml (file_id=1)
        repo._dependencies[1] = Dependency(
            id=1,
            file_id=1,
            repository_id=1,
            package_name="fastapi",
            language="python",
            version_spec=">=0.100",
            dependency_type="runtime",
            is_direct=True,
        )
        repo._dependencies[2] = Dependency(
            id=2,
            file_id=1,
            repository_id=1,
            package_name="pytest",
            language="python",
            version_spec=">=7.0",
            dependency_type="dev",
            is_direct=True,
        )
        # JS deps from package.json (file_id=2)
        repo._dependencies[3] = Dependency(
            id=3,
            file_id=2,
            repository_id=1,
            package_name="react",
            language="javascript",
            version_spec="^18.0.0",
            dependency_type="runtime",
            is_direct=True,
        )
        repo._dependencies[4] = Dependency(
            id=4,
            file_id=2,
            repository_id=1,
            package_name="vitest",
            language="javascript",
            version_spec="^1.0.0",
            dependency_type="dev",
            is_direct=True,
        )
        repo._next_id = 5
        return repo

    @pytest.fixture
    def use_case(
        self,
        repository_repo: InMemoryRepositoryRepository,
        dependency_repo: InMemoryDependencyRepository,
        commit_repo: InMemoryCommitRepository,
        file_repo: InMemoryFileRepository,
    ) -> GetRepositoryDependenciesUseCase:
        return GetRepositoryDependenciesUseCase(
            repository_repo=repository_repo,
            dependency_repo=dependency_repo,
            commit_repo=commit_repo,
            file_repo=file_repo,
        )

    async def test_get_dependencies_by_name_default_branch(
        self, use_case: GetRepositoryDependenciesUseCase
    ) -> None:
        """Should return all deps at latest commit on default branch."""
        response = await use_case.execute(
            GetRepositoryDependenciesRequest(repository_name="test-repo")
        )
        assert response.repository_id == 1
        assert response.repository_name == "test-repo"
        assert response.total == 4
        assert response.commit_hash == "a" * 40
        names = {item.package_name for item in response.items}
        assert names == {"fastapi", "pytest", "react", "vitest"}

    async def test_get_dependencies_by_id(
        self, use_case: GetRepositoryDependenciesUseCase
    ) -> None:
        """Should resolve repository by ID."""
        response = await use_case.execute(
            GetRepositoryDependenciesRequest(repository_id=1)
        )
        assert response.repository_id == 1
        assert response.total == 4

    async def test_get_dependencies_by_branch(
        self, use_case: GetRepositoryDependenciesUseCase
    ) -> None:
        """Should resolve to latest commit on specified branch."""
        response = await use_case.execute(
            GetRepositoryDependenciesRequest(
                repository_name="test-repo", branch="feature"
            )
        )
        # feature branch (commit 2) only has pyproject.toml (file_id=1)
        assert response.commit_hash == "b" * 40
        assert response.total == 2
        names = {item.package_name for item in response.items}
        assert names == {"fastapi", "pytest"}

    async def test_get_dependencies_by_commit_hash(
        self, use_case: GetRepositoryDependenciesUseCase
    ) -> None:
        """Should query deps at explicit commit hash."""
        response = await use_case.execute(
            GetRepositoryDependenciesRequest(
                repository_name="test-repo",
                commit_hash="b" * 40,
            )
        )
        assert response.commit_hash == "b" * 40
        assert response.total == 2

    async def test_filter_by_language(
        self, use_case: GetRepositoryDependenciesUseCase
    ) -> None:
        """Should filter by language."""
        response = await use_case.execute(
            GetRepositoryDependenciesRequest(
                repository_name="test-repo", language="python"
            )
        )
        assert response.total == 2
        assert all(item.language == "python" for item in response.items)

    async def test_filter_by_dependency_type(
        self, use_case: GetRepositoryDependenciesUseCase
    ) -> None:
        """Should filter by dependency type."""
        response = await use_case.execute(
            GetRepositoryDependenciesRequest(
                repository_name="test-repo", dependency_type="dev"
            )
        )
        assert response.total == 2
        names = {item.package_name for item in response.items}
        assert names == {"pytest", "vitest"}

    async def test_filter_by_is_direct(
        self, use_case: GetRepositoryDependenciesUseCase
    ) -> None:
        """Should filter by direct/transitive."""
        response = await use_case.execute(
            GetRepositoryDependenciesRequest(
                repository_name="test-repo", is_direct=True
            )
        )
        assert response.total == 4
        assert all(item.is_direct for item in response.items)

    async def test_combined_filters(
        self, use_case: GetRepositoryDependenciesUseCase
    ) -> None:
        """Should combine multiple filters."""
        response = await use_case.execute(
            GetRepositoryDependenciesRequest(
                repository_name="test-repo",
                language="javascript",
                dependency_type="runtime",
            )
        )
        assert response.total == 1
        assert response.items[0].package_name == "react"

    async def test_file_paths_enriched(
        self, use_case: GetRepositoryDependenciesUseCase
    ) -> None:
        """Should enrich items with file paths."""
        response = await use_case.execute(
            GetRepositoryDependenciesRequest(repository_name="test-repo")
        )
        paths = {item.file_path for item in response.items}
        assert "pyproject.toml" in paths
        assert "package.json" in paths

    async def test_repository_not_found(
        self, use_case: GetRepositoryDependenciesUseCase
    ) -> None:
        """Should raise ValueError for unknown repository."""
        with pytest.raises(ValueError, match="Repository not found"):
            await use_case.execute(
                GetRepositoryDependenciesRequest(repository_name="nonexistent")
            )

    async def test_branch_not_found(
        self, use_case: GetRepositoryDependenciesUseCase
    ) -> None:
        """Should raise ValueError for branch with no indexed commits."""
        with pytest.raises(ValueError, match="No indexed commits found for branch"):
            await use_case.execute(
                GetRepositoryDependenciesRequest(
                    repository_name="test-repo", branch="nonexistent"
                )
            )

    async def test_commit_not_found(
        self, use_case: GetRepositoryDependenciesUseCase
    ) -> None:
        """Should raise ValueError for unknown commit hash."""
        with pytest.raises(ValueError, match="Commit not found"):
            await use_case.execute(
                GetRepositoryDependenciesRequest(
                    repository_name="test-repo",
                    commit_hash="c" * 40,
                )
            )

    async def test_request_requires_id_or_name(self) -> None:
        """Should raise ValueError when neither id nor name provided."""
        with pytest.raises(ValueError, match="Either repository_id or repository_name"):
            GetRepositoryDependenciesRequest()
