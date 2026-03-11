"""Tests for SearchDependenciesUseCase."""

import pytest

from inxr2.application.use_cases.dependencies import (
    SearchDependenciesRequest,
    SearchDependenciesUseCase,
)
from inxr2.domain.entities import Dependency, File, Repository
from tests.fixtures.test_doubles import (
    InMemoryDependencyRepository,
    InMemoryFileRepository,
    InMemoryRepositoryRepository,
)


class TestSearchDependenciesUseCase:
    """Tests for searching dependencies by package name."""

    @pytest.fixture
    def repository_repo(self) -> InMemoryRepositoryRepository:
        repo = InMemoryRepositoryRepository()
        repo.add(Repository(id=1, name="repo-a", url="/a", default_branch="main"))
        repo.add(Repository(id=2, name="repo-b", url="/b", default_branch="main"))
        return repo

    @pytest.fixture
    def file_repo(self) -> InMemoryFileRepository:
        repo = InMemoryFileRepository()
        repo.add(
            File(
                id=1,
                repository_id=1,
                path="package.json",
                language="javascript",
                size_bytes=300,
                content_hash="a" * 40,
            )
        )
        repo.add(
            File(
                id=2,
                repository_id=2,
                path="pyproject.toml",
                language="python",
                size_bytes=500,
                content_hash="b" * 40,
            )
        )
        return repo

    @pytest.fixture
    async def dependency_repo(self) -> InMemoryDependencyRepository:
        repo = InMemoryDependencyRepository()
        await repo.save(
            Dependency(
                file_id=1,
                repository_id=1,
                package_name="@emotion/react",
                language="javascript",
                version_spec="^11.0.0",
                resolved_version="11.11.1",
                dependency_type="runtime",
                is_direct=True,
            )
        )
        await repo.save(
            Dependency(
                file_id=1,
                repository_id=1,
                package_name="@emotion/styled",
                language="javascript",
                version_spec="^11.0.0",
                resolved_version="11.11.0",
                dependency_type="runtime",
                is_direct=True,
            )
        )
        await repo.save(
            Dependency(
                file_id=1,
                repository_id=1,
                package_name="react",
                language="javascript",
                version_spec="^18.0.0",
                dependency_type="runtime",
                is_direct=True,
            )
        )
        await repo.save(
            Dependency(
                file_id=2,
                repository_id=2,
                package_name="fastapi",
                language="python",
                version_spec=">=0.100.0",
                dependency_type="runtime",
                is_direct=True,
            )
        )
        await repo.save(
            Dependency(
                file_id=2,
                repository_id=2,
                package_name="react-scripts",
                language="python",
                version_spec=">=1.0",
                dependency_type="dev",
                is_direct=True,
            )
        )
        return repo

    @pytest.fixture
    def use_case(
        self,
        dependency_repo: InMemoryDependencyRepository,
        file_repo: InMemoryFileRepository,
        repository_repo: InMemoryRepositoryRepository,
    ) -> SearchDependenciesUseCase:
        return SearchDependenciesUseCase(
            dependency_repo=dependency_repo,
            file_repo=file_repo,
            repository_repo=repository_repo,
        )

    async def test_search_partial_match(
        self, use_case: SearchDependenciesUseCase
    ) -> None:
        """Searching 'emotion' finds both @emotion/react and @emotion/styled."""
        response = await use_case.execute(SearchDependenciesRequest(query="emotion"))
        assert response.total == 2
        names = [r.package_name for r in response.results]
        assert "@emotion/react" in names
        assert "@emotion/styled" in names

    async def test_search_case_insensitive(
        self, use_case: SearchDependenciesUseCase
    ) -> None:
        """Search is case-insensitive."""
        response = await use_case.execute(SearchDependenciesRequest(query="FASTAPI"))
        assert response.total == 1
        assert response.results[0].package_name == "fastapi"

    async def test_search_cross_repo(self, use_case: SearchDependenciesUseCase) -> None:
        """Searching 'react' finds matches across repos."""
        response = await use_case.execute(SearchDependenciesRequest(query="react"))
        assert response.total == 3  # @emotion/react, react, react-scripts
        repo_names = {r.repository_name for r in response.results}
        assert "repo-a" in repo_names
        assert "repo-b" in repo_names

    async def test_search_filter_by_repository(
        self, use_case: SearchDependenciesUseCase
    ) -> None:
        """Filter by repository_id limits results."""
        response = await use_case.execute(
            SearchDependenciesRequest(query="react", repository_id=1)
        )
        assert response.total == 2  # @emotion/react, react
        assert all(r.repository_id == 1 for r in response.results)

    async def test_search_filter_by_language(
        self, use_case: SearchDependenciesUseCase
    ) -> None:
        """Filter by language limits results."""
        response = await use_case.execute(
            SearchDependenciesRequest(query="react", language="python")
        )
        assert response.total == 1
        assert response.results[0].package_name == "react-scripts"

    async def test_search_no_results(self, use_case: SearchDependenciesUseCase) -> None:
        """Searching for non-existent package returns empty."""
        response = await use_case.execute(
            SearchDependenciesRequest(query="nonexistent-package")
        )
        assert response.total == 0
        assert response.results == []

    async def test_search_hydrates_file_path(
        self, use_case: SearchDependenciesUseCase
    ) -> None:
        """Results include file_path from file repository."""
        response = await use_case.execute(SearchDependenciesRequest(query="fastapi"))
        assert response.results[0].file_path == "pyproject.toml"

    async def test_search_hydrates_repository_name(
        self, use_case: SearchDependenciesUseCase
    ) -> None:
        """Results include repository_name from repository repository."""
        response = await use_case.execute(SearchDependenciesRequest(query="fastapi"))
        assert response.results[0].repository_name == "repo-b"

    async def test_search_pagination(self, use_case: SearchDependenciesUseCase) -> None:
        """Pagination via limit/offset works correctly."""
        # Get first page
        response1 = await use_case.execute(
            SearchDependenciesRequest(query="react", limit=2, offset=0)
        )
        assert len(response1.results) == 2
        assert response1.total == 3

        # Get second page
        response2 = await use_case.execute(
            SearchDependenciesRequest(query="react", limit=2, offset=2)
        )
        assert len(response2.results) == 1
        assert response2.total == 3

    async def test_search_response_metadata(
        self, use_case: SearchDependenciesUseCase
    ) -> None:
        """Response includes query metadata."""
        response = await use_case.execute(
            SearchDependenciesRequest(query="emotion", limit=10, offset=5)
        )
        assert response.query == "emotion"
        assert response.limit == 10
        assert response.offset == 5

    async def test_search_filter_by_dependency_type(
        self, use_case: SearchDependenciesUseCase
    ) -> None:
        """Filter by dependency_type works."""
        response = await use_case.execute(
            SearchDependenciesRequest(query="react", dependency_type="dev")
        )
        assert response.total == 1
        assert response.results[0].package_name == "react-scripts"

    async def test_search_filter_by_is_direct_true(
        self, use_case: SearchDependenciesUseCase
    ) -> None:
        """Filter by is_direct=True returns only direct dependencies."""
        response = await use_case.execute(
            SearchDependenciesRequest(query="react", is_direct=True)
        )
        assert response.total == 3
        assert all(r.is_direct is True for r in response.results)

    async def test_search_filter_by_is_direct_false(
        self, use_case: SearchDependenciesUseCase
    ) -> None:
        """Filter by is_direct=False returns only transitive dependencies."""
        response = await use_case.execute(
            SearchDependenciesRequest(query="react", is_direct=False)
        )
        assert response.total == 0
        assert response.results == []
