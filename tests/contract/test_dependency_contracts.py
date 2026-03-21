"""Contract tests for DependencyRepositoryPort — fake vs Postgres parity."""

import pytest

from inxr2.domain.entities import Dependency

from .conftest import Repos, create_test_commit, create_test_file, create_test_repo


@pytest.mark.asyncio
class TestDependencySaveContract:
    """Save and retrieve dependency entities."""

    async def test_save_and_find_by_id(self, repos: Repos) -> None:
        """Save a dependency and retrieve it by ID."""
        repo_id = await create_test_repo(repos)
        commit_id = await create_test_commit(repos, repo_id, "a" * 40)
        file_id = await create_test_file(
            repos, repo_id, commit_id, "pyproject.toml", "b" * 40
        )

        dep = await repos.dependency.save(
            Dependency(
                file_id=file_id,
                repository_id=repo_id,
                package_name="fastapi",
                language="python",
                version_spec="^0.109.0",
                resolved_version="0.109.1",
                dependency_type="runtime",
                is_direct=True,
            )
        )
        assert dep.id is not None

        found = await repos.dependency.find_by_id(dep.id)
        assert found is not None
        assert found.package_name == "fastapi"
        assert found.version_spec == "^0.109.0"
        assert found.resolved_version == "0.109.1"
        assert found.language == "python"
        assert found.dependency_type == "runtime"
        assert found.is_direct is True

    async def test_save_many(self, repos: Repos) -> None:
        """Bulk save multiple dependencies."""
        repo_id = await create_test_repo(repos)
        commit_id = await create_test_commit(repos, repo_id, "a" * 40)
        file_id = await create_test_file(
            repos, repo_id, commit_id, "pyproject.toml", "b" * 40
        )

        deps = await repos.dependency.save_many(
            [
                Dependency(
                    file_id=file_id,
                    repository_id=repo_id,
                    package_name="fastapi",
                    language="python",
                ),
                Dependency(
                    file_id=file_id,
                    repository_id=repo_id,
                    package_name="sqlalchemy",
                    language="python",
                ),
            ]
        )
        assert len(deps) == 2
        assert all(d.id is not None for d in deps)


@pytest.mark.asyncio
class TestDependencyFindByFileContract:
    """Find dependencies by manifest file version."""

    async def test_find_by_file(self, repos: Repos) -> None:
        """Find all dependencies for a file version."""
        repo_id = await create_test_repo(repos)
        commit_id = await create_test_commit(repos, repo_id, "a" * 40)
        file_id = await create_test_file(
            repos, repo_id, commit_id, "pyproject.toml", "b" * 40
        )

        await repos.dependency.save_many(
            [
                Dependency(
                    file_id=file_id,
                    repository_id=repo_id,
                    package_name="fastapi",
                    language="python",
                    dependency_type="runtime",
                ),
                Dependency(
                    file_id=file_id,
                    repository_id=repo_id,
                    package_name="pytest",
                    language="python",
                    dependency_type="dev",
                ),
            ]
        )

        all_deps = await repos.dependency.find_by_file(file_id)
        assert len(all_deps) == 2

        runtime_deps = await repos.dependency.find_by_file(
            file_id, dependency_type="runtime"
        )
        assert len(runtime_deps) == 1
        assert runtime_deps[0].package_name == "fastapi"

        dev_deps = await repos.dependency.find_by_file(file_id, dependency_type="dev")
        assert len(dev_deps) == 1
        assert dev_deps[0].package_name == "pytest"

    async def test_find_by_file_direct_filter(self, repos: Repos) -> None:
        """Filter by direct vs transitive dependencies."""
        repo_id = await create_test_repo(repos)
        commit_id = await create_test_commit(repos, repo_id, "a" * 40)
        file_id = await create_test_file(
            repos, repo_id, commit_id, "poetry.lock", "b" * 40
        )

        parent = await repos.dependency.save(
            Dependency(
                file_id=file_id,
                repository_id=repo_id,
                package_name="fastapi",
                language="python",
                is_direct=True,
            )
        )
        await repos.dependency.save(
            Dependency(
                file_id=file_id,
                repository_id=repo_id,
                package_name="starlette",
                language="python",
                is_direct=False,
                parent_dependency_id=parent.id,
            )
        )

        direct = await repos.dependency.find_by_file(file_id, is_direct=True)
        assert len(direct) == 1
        assert direct[0].package_name == "fastapi"

        transitive = await repos.dependency.find_by_file(file_id, is_direct=False)
        assert len(transitive) == 1
        assert transitive[0].package_name == "starlette"
        assert transitive[0].parent_dependency_id == parent.id


@pytest.mark.asyncio
class TestDependencyFindByCommitContract:
    """Find dependencies at a specific commit via commit_files junction."""

    async def test_find_by_commit(self, repos: Repos) -> None:
        """Dependencies for a commit are resolved via commit_files."""
        repo_id = await create_test_repo(repos)
        commit1_id = await create_test_commit(repos, repo_id, "a" * 40, 0)
        commit2_id = await create_test_commit(repos, repo_id, "c" * 40, 1)

        # Commit 1: pyproject.toml v1
        file1_id = await create_test_file(
            repos, repo_id, commit1_id, "pyproject.toml", "b" * 40
        )
        await repos.dependency.save(
            Dependency(
                file_id=file1_id,
                repository_id=repo_id,
                package_name="fastapi",
                language="python",
                version_spec="0.109.0",
            )
        )

        # Commit 2: pyproject.toml v2 (updated)
        file2_id = await create_test_file(
            repos, repo_id, commit2_id, "pyproject.toml", "d" * 40
        )
        await repos.dependency.save(
            Dependency(
                file_id=file2_id,
                repository_id=repo_id,
                package_name="fastapi",
                language="python",
                version_spec="0.110.0",
            )
        )

        # Query at commit 1 should get v1
        deps_at_c1 = await repos.dependency.find_by_commit(commit1_id, repo_id)
        assert len(deps_at_c1) == 1
        assert deps_at_c1[0].version_spec == "0.109.0"

        # Query at commit 2 should get v2
        deps_at_c2 = await repos.dependency.find_by_commit(commit2_id, repo_id)
        assert len(deps_at_c2) == 1
        assert deps_at_c2[0].version_spec == "0.110.0"

    async def test_find_by_commit_language_filter(self, repos: Repos) -> None:
        """Filter by language when querying by commit."""
        repo_id = await create_test_repo(repos)
        commit_id = await create_test_commit(repos, repo_id, "a" * 40)

        py_file = await create_test_file(
            repos, repo_id, commit_id, "pyproject.toml", "b" * 40
        )
        js_file = await create_test_file(
            repos, repo_id, commit_id, "package.json", "c" * 40
        )

        await repos.dependency.save(
            Dependency(
                file_id=py_file,
                repository_id=repo_id,
                package_name="fastapi",
                language="python",
            )
        )
        await repos.dependency.save(
            Dependency(
                file_id=js_file,
                repository_id=repo_id,
                package_name="react",
                language="javascript",
            )
        )

        py_deps = await repos.dependency.find_by_commit(
            commit_id, repo_id, language="python"
        )
        assert len(py_deps) == 1
        assert py_deps[0].package_name == "fastapi"

        js_deps = await repos.dependency.find_by_commit(
            commit_id, repo_id, language="javascript"
        )
        assert len(js_deps) == 1
        assert js_deps[0].package_name == "react"


@pytest.mark.asyncio
class TestDependencyReverseContract:
    """Reverse lookup: find repos using a package."""

    async def test_find_by_package_name(self, repos: Repos) -> None:
        """Find all dependencies matching a package name."""
        repo_id = await create_test_repo(repos)
        commit_id = await create_test_commit(repos, repo_id, "a" * 40)
        file_id = await create_test_file(
            repos, repo_id, commit_id, "pyproject.toml", "b" * 40
        )

        await repos.dependency.save(
            Dependency(
                file_id=file_id,
                repository_id=repo_id,
                package_name="fastapi",
                language="python",
            )
        )
        await repos.dependency.save(
            Dependency(
                file_id=file_id,
                repository_id=repo_id,
                package_name="sqlalchemy",
                language="python",
            )
        )

        results = await repos.dependency.find_by_package_name("fastapi")
        assert len(results) == 1
        assert results[0].package_name == "fastapi"

        results = await repos.dependency.find_by_package_name("nonexistent")
        assert len(results) == 0

    async def test_find_by_package_name_scoped_npm(self, repos: Repos) -> None:
        """@scope/package names are stored and retrieved exactly."""
        repo_id = await create_test_repo(repos)
        commit_id = await create_test_commit(repos, repo_id, "a" * 40)
        file_id = await create_test_file(
            repos, repo_id, commit_id, "package.json", "b" * 40
        )

        await repos.dependency.save(
            Dependency(
                file_id=file_id,
                repository_id=repo_id,
                package_name="@scope/pkg",
                language="javascript",
            )
        )

        results = await repos.dependency.find_by_package_name("@scope/pkg")
        assert len(results) == 1
        assert results[0].package_name == "@scope/pkg"

        # Exact match — unscoped name must not match
        results = await repos.dependency.find_by_package_name("pkg")
        assert len(results) == 0

    async def test_find_by_package_name_with_filter_language(
        self, repos: Repos
    ) -> None:
        """language filter narrows results for find_by_package_name."""
        repo_id = await create_test_repo(repos)
        commit_id = await create_test_commit(repos, repo_id, "a" * 40)
        py_file = await create_test_file(
            repos, repo_id, commit_id, "pyproject.toml", "b" * 40
        )
        js_file = await create_test_file(
            repos, repo_id, commit_id, "package.json", "c" * 40
        )

        await repos.dependency.save(
            Dependency(
                file_id=py_file,
                repository_id=repo_id,
                package_name="requests",
                language="python",
            )
        )
        await repos.dependency.save(
            Dependency(
                file_id=js_file,
                repository_id=repo_id,
                package_name="requests",
                language="javascript",
            )
        )

        py_results = await repos.dependency.find_by_package_name(
            "requests", language="python"
        )
        assert len(py_results) == 1
        assert py_results[0].language == "python"

        js_results = await repos.dependency.find_by_package_name(
            "requests", language="javascript"
        )
        assert len(js_results) == 1
        assert js_results[0].language == "javascript"

    async def test_find_by_package_name_with_filter_repository(
        self, repos: Repos
    ) -> None:
        """repository_id filter narrows results for find_by_package_name."""
        repo1_id = await create_test_repo(repos)
        # Use different hashes per repo to avoid unique constraint collisions
        commit1_id = await create_test_commit(repos, repo1_id, "a" * 40)
        file1_id = await create_test_file(
            repos, repo1_id, commit1_id, "pyproject.toml", "b" * 40
        )

        await repos.dependency.save(
            Dependency(
                file_id=file1_id,
                repository_id=repo1_id,
                package_name="fastapi",
                language="python",
            )
        )

        results = await repos.dependency.find_by_package_name(
            "fastapi", repository_id=repo1_id
        )
        assert len(results) == 1
        assert results[0].repository_id == repo1_id


@pytest.mark.asyncio
class TestDependencyDeleteContract:
    """Delete dependencies."""

    async def test_delete_by_file(self, repos: Repos) -> None:
        """Delete all dependencies for a file version."""
        repo_id = await create_test_repo(repos)
        commit_id = await create_test_commit(repos, repo_id, "a" * 40)
        file_id = await create_test_file(
            repos, repo_id, commit_id, "pyproject.toml", "b" * 40
        )

        await repos.dependency.save_many(
            [
                Dependency(
                    file_id=file_id,
                    repository_id=repo_id,
                    package_name="fastapi",
                    language="python",
                ),
                Dependency(
                    file_id=file_id,
                    repository_id=repo_id,
                    package_name="sqlalchemy",
                    language="python",
                ),
            ]
        )

        count = await repos.dependency.delete_by_file(file_id)
        assert count == 2

        remaining = await repos.dependency.find_by_file(file_id)
        assert len(remaining) == 0

    async def test_count_by_repository(self, repos: Repos) -> None:
        """Count dependencies in a repository."""
        repo_id = await create_test_repo(repos)
        commit_id = await create_test_commit(repos, repo_id, "a" * 40)
        file_id = await create_test_file(
            repos, repo_id, commit_id, "pyproject.toml", "b" * 40
        )

        await repos.dependency.save_many(
            [
                Dependency(
                    file_id=file_id,
                    repository_id=repo_id,
                    package_name="fastapi",
                    language="python",
                ),
                Dependency(
                    file_id=file_id,
                    repository_id=repo_id,
                    package_name="sqlalchemy",
                    language="python",
                ),
            ]
        )

        count = await repos.dependency.count_by_repository(repo_id)
        assert count == 2
