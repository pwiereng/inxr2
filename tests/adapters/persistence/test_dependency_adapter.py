"""Integration tests for PostgresDependencyRepository."""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from inxr2.adapters.persistence.repositories.commit_adapter import (
    PostgresCommitRepository,
)
from inxr2.adapters.persistence.repositories.dependency_adapter import (
    PostgresDependencyRepository,
)
from inxr2.adapters.persistence.repositories.file_adapter import (
    PostgresFileRepository,
)
from inxr2.adapters.persistence.repositories.repository_adapter import (
    PostgresRepositoryAdapter,
)
from inxr2.domain.entities import Dependency

from .factories import CommitFactory, FileFactory, RepositoryFactory


async def _setup(
    db_session: AsyncSession,
    repo_name: str = "test-repo",
    commit_hash: str = "a" * 40,
    file_path: str = "pyproject.toml",
    content_hash: str = "b" * 40,
) -> tuple[int, int, int]:
    """Create repo → commit → file linked together. Returns (repo_id, commit_id, file_id)."""
    repo = await PostgresRepositoryAdapter(db_session).save(
        RepositoryFactory.create(name=repo_name)
    )
    assert repo.id is not None

    commit_adapter = PostgresCommitRepository(db_session)
    commit = await commit_adapter.save(
        CommitFactory.create(repository_id=repo.id, commit_hash=commit_hash)
    )
    assert commit.id is not None
    await commit_adapter.link_commit_to_branch(repo.id, commit.id, "main")

    file = await PostgresFileRepository(db_session).save(
        FileFactory.create(
            repository_id=repo.id,
            path=file_path,
            content_hash=content_hash,
        )
    )
    assert file.id is not None
    await PostgresFileRepository(db_session).link_file_to_commit(file.id, commit.id)
    await db_session.commit()

    return repo.id, commit.id, file.id


def _dep(file_id: int, repo_id: int, **kwargs: Any) -> Dependency:
    """Shorthand for constructing a Dependency."""
    return Dependency(
        file_id=file_id,
        repository_id=repo_id,
        package_name=kwargs.pop("package_name", "fastapi"),
        language=kwargs.pop("language", "python"),
        **kwargs,
    )


@pytest.mark.asyncio
class TestFindByFile:
    """find_by_file() — filter combinations."""

    async def test_returns_all_deps_for_file(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save_many(
            [
                _dep(file_id, repo_id, package_name="fastapi"),
                _dep(file_id, repo_id, package_name="sqlalchemy"),
            ]
        )

        results = await adapter.find_by_file(file_id)
        assert len(results) == 2
        names = {d.package_name for d in results}
        assert names == {"fastapi", "sqlalchemy"}

    async def test_returns_empty_for_unknown_file(
        self, db_session: AsyncSession
    ) -> None:
        adapter = PostgresDependencyRepository(db_session)
        results = await adapter.find_by_file(999999)
        assert results == []

    async def test_filter_by_dependency_type_runtime(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save_many(
            [
                _dep(
                    file_id, repo_id, package_name="fastapi", dependency_type="runtime"
                ),
                _dep(file_id, repo_id, package_name="pytest", dependency_type="dev"),
            ]
        )

        results = await adapter.find_by_file(file_id, dependency_type="runtime")
        assert len(results) == 1
        assert results[0].package_name == "fastapi"

    async def test_filter_by_dependency_type_dev(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save_many(
            [
                _dep(
                    file_id, repo_id, package_name="fastapi", dependency_type="runtime"
                ),
                _dep(file_id, repo_id, package_name="pytest", dependency_type="dev"),
            ]
        )

        results = await adapter.find_by_file(file_id, dependency_type="dev")
        assert len(results) == 1
        assert results[0].package_name == "pytest"

    async def test_filter_by_is_direct_true(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        direct = await adapter.save(
            _dep(file_id, repo_id, package_name="fastapi", is_direct=True)
        )
        await adapter.save(
            _dep(
                file_id,
                repo_id,
                package_name="starlette",
                is_direct=False,
                parent_dependency_id=direct.id,
            )
        )

        results = await adapter.find_by_file(file_id, is_direct=True)
        assert len(results) == 1
        assert results[0].package_name == "fastapi"

    async def test_filter_by_is_direct_false(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        direct = await adapter.save(
            _dep(file_id, repo_id, package_name="fastapi", is_direct=True)
        )
        await adapter.save(
            _dep(
                file_id,
                repo_id,
                package_name="starlette",
                is_direct=False,
                parent_dependency_id=direct.id,
            )
        )

        results = await adapter.find_by_file(file_id, is_direct=False)
        assert len(results) == 1
        assert results[0].package_name == "starlette"
        assert results[0].parent_dependency_id == direct.id

    async def test_combined_filters(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save_many(
            [
                _dep(
                    file_id,
                    repo_id,
                    package_name="fastapi",
                    dependency_type="runtime",
                    is_direct=True,
                ),
                _dep(
                    file_id,
                    repo_id,
                    package_name="pytest",
                    dependency_type="dev",
                    is_direct=True,
                ),
                _dep(
                    file_id,
                    repo_id,
                    package_name="starlette",
                    dependency_type="runtime",
                    is_direct=False,
                ),
            ]
        )

        results = await adapter.find_by_file(
            file_id, dependency_type="runtime", is_direct=True
        )
        assert len(results) == 1
        assert results[0].package_name == "fastapi"

    async def test_results_ordered_by_package_name(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save_many(
            [
                _dep(file_id, repo_id, package_name="zlib"),
                _dep(file_id, repo_id, package_name="alembic"),
                _dep(file_id, repo_id, package_name="mypy"),
            ]
        )

        results = await adapter.find_by_file(file_id)
        assert [d.package_name for d in results] == ["alembic", "mypy", "zlib"]

    async def test_does_not_return_deps_from_other_file(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, commit_id, file1_id = await _setup(
            db_session, commit_hash="a" * 40, file_path="pyproject.toml"
        )
        file2 = await PostgresFileRepository(db_session).save(
            FileFactory.create(
                repository_id=repo_id,
                path="package.json",
                content_hash="c" * 40,
            )
        )
        assert file2.id is not None
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save(_dep(file1_id, repo_id, package_name="fastapi"))
        await adapter.save(
            _dep(file2.id, repo_id, package_name="react", language="javascript")
        )

        results = await adapter.find_by_file(file1_id)
        assert len(results) == 1
        assert results[0].package_name == "fastapi"


@pytest.mark.asyncio
class TestFindByCommit:
    """find_by_commit() — filter combinations and cross-commit isolation."""

    async def test_returns_deps_for_commit(self, db_session: AsyncSession) -> None:
        repo_id, commit_id, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save(_dep(file_id, repo_id, package_name="fastapi"))
        results = await adapter.find_by_commit(commit_id, repo_id)
        assert len(results) == 1
        assert results[0].package_name == "fastapi"

    async def test_empty_for_commit_with_no_deps(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, commit_id, _ = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        results = await adapter.find_by_commit(commit_id, repo_id)
        assert results == []

    async def test_isolates_by_commit(self, db_session: AsyncSession) -> None:
        """Two commits, two file versions — query at each returns correct snapshot."""
        repo_id, commit1_id, file1_id = await _setup(
            db_session,
            commit_hash="a" * 40,
            file_path="pyproject.toml",
            content_hash="b" * 40,
        )

        commit_adapter = PostgresCommitRepository(db_session)
        commit2 = await commit_adapter.save(
            CommitFactory.create(repository_id=repo_id, commit_hash="c" * 40)
        )
        assert commit2.id is not None

        file2 = await PostgresFileRepository(db_session).save(
            FileFactory.create(
                repository_id=repo_id, path="pyproject.toml", content_hash="d" * 40
            )
        )
        assert file2.id is not None
        await PostgresFileRepository(db_session).link_file_to_commit(
            file2.id, commit2.id
        )
        await db_session.commit()

        adapter = PostgresDependencyRepository(db_session)
        await adapter.save(
            _dep(file1_id, repo_id, package_name="fastapi", version_spec="0.109.0")
        )
        await adapter.save(
            _dep(file2.id, repo_id, package_name="fastapi", version_spec="0.110.0")
        )

        at_c1 = await adapter.find_by_commit(commit1_id, repo_id)
        assert len(at_c1) == 1
        assert at_c1[0].version_spec == "0.109.0"

        at_c2 = await adapter.find_by_commit(commit2.id, repo_id)
        assert len(at_c2) == 1
        assert at_c2[0].version_spec == "0.110.0"

    async def test_filter_by_language(self, db_session: AsyncSession) -> None:
        # Create repo+commit only; files are created with distinct paths/hashes below
        repo_id, commit_id, _ = await _setup(
            db_session, file_path="unused.txt", content_hash="z" * 40
        )
        file_adapter = PostgresFileRepository(db_session)

        py_file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo_id,
                path="pyproject.toml",
                content_hash="b" * 40,
                language="python",
            )
        )
        assert py_file.id is not None
        await file_adapter.link_file_to_commit(py_file.id, commit_id)

        js_file = await file_adapter.save(
            FileFactory.create(
                repository_id=repo_id,
                path="package.json",
                content_hash="c" * 40,
                language="javascript",
            )
        )
        assert js_file.id is not None
        await file_adapter.link_file_to_commit(js_file.id, commit_id)
        await db_session.commit()

        adapter = PostgresDependencyRepository(db_session)
        await adapter.save(
            _dep(py_file.id, repo_id, package_name="fastapi", language="python")
        )
        await adapter.save(
            _dep(js_file.id, repo_id, package_name="react", language="javascript")
        )

        py_results = await adapter.find_by_commit(commit_id, repo_id, language="python")
        assert len(py_results) == 1
        assert py_results[0].package_name == "fastapi"

        js_results = await adapter.find_by_commit(
            commit_id, repo_id, language="javascript"
        )
        assert len(js_results) == 1
        assert js_results[0].package_name == "react"

    async def test_filter_by_dependency_type(self, db_session: AsyncSession) -> None:
        repo_id, commit_id, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save(
            _dep(file_id, repo_id, package_name="fastapi", dependency_type="runtime")
        )
        await adapter.save(
            _dep(file_id, repo_id, package_name="pytest", dependency_type="dev")
        )

        results = await adapter.find_by_commit(
            commit_id, repo_id, dependency_type="runtime"
        )
        assert len(results) == 1
        assert results[0].package_name == "fastapi"

    async def test_filter_by_is_direct(self, db_session: AsyncSession) -> None:
        repo_id, commit_id, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        direct = await adapter.save(
            _dep(file_id, repo_id, package_name="fastapi", is_direct=True)
        )
        await adapter.save(
            _dep(
                file_id,
                repo_id,
                package_name="starlette",
                is_direct=False,
                parent_dependency_id=direct.id,
            )
        )

        results = await adapter.find_by_commit(commit_id, repo_id, is_direct=True)
        assert len(results) == 1
        assert results[0].package_name == "fastapi"

    async def test_does_not_return_deps_from_other_repo(
        self, db_session: AsyncSession
    ) -> None:
        repo1_id, commit1_id, file1_id = await _setup(
            db_session, repo_name="repo-1", commit_hash="a" * 40
        )
        repo2_id, _, file2_id = await _setup(
            db_session, repo_name="repo-2", commit_hash="e" * 40
        )

        adapter = PostgresDependencyRepository(db_session)
        await adapter.save(_dep(file1_id, repo1_id, package_name="fastapi"))
        await adapter.save(_dep(file2_id, repo2_id, package_name="fastapi"))

        results = await adapter.find_by_commit(commit1_id, repo1_id)
        assert len(results) == 1
        # All results belong to repo1
        for r in results:
            assert r.repository_id == repo1_id


@pytest.mark.asyncio
class TestFindByPackageName:
    """find_by_package_name() — reverse lookup including special characters."""

    async def test_finds_exact_match(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save(_dep(file_id, repo_id, package_name="fastapi"))
        await adapter.save(_dep(file_id, repo_id, package_name="sqlalchemy"))

        results = await adapter.find_by_package_name("fastapi")
        assert len(results) == 1
        assert results[0].package_name == "fastapi"

    async def test_returns_empty_for_nonexistent_package(
        self, db_session: AsyncSession
    ) -> None:
        adapter = PostgresDependencyRepository(db_session)
        results = await adapter.find_by_package_name("nonexistent-package")
        assert results == []

    async def test_scoped_npm_package_at_sign(self, db_session: AsyncSession) -> None:
        """Package names like @scope/package must be stored and found exactly."""
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save(
            _dep(file_id, repo_id, package_name="@scope/package", language="javascript")
        )

        results = await adapter.find_by_package_name("@scope/package")
        assert len(results) == 1
        assert results[0].package_name == "@scope/package"

    async def test_scoped_npm_package_no_partial_match(
        self, db_session: AsyncSession
    ) -> None:
        """find_by_package_name is exact — @scope/package must not match 'package'."""
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save(
            _dep(file_id, repo_id, package_name="@scope/package", language="javascript")
        )

        results = await adapter.find_by_package_name("package")
        assert results == []

    async def test_package_with_hyphen(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save(
            _dep(file_id, repo_id, package_name="my-pkg", language="javascript")
        )

        results = await adapter.find_by_package_name("my-pkg")
        assert len(results) == 1

    async def test_package_with_dots(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save(
            _dep(file_id, repo_id, package_name="com.google.guava", language="java")
        )

        results = await adapter.find_by_package_name("com.google.guava")
        assert len(results) == 1

    async def test_filter_by_repository_id(self, db_session: AsyncSession) -> None:
        repo1_id, _, file1_id = await _setup(
            db_session, repo_name="repo-a", commit_hash="a" * 40
        )
        repo2_id, _, file2_id = await _setup(
            db_session, repo_name="repo-b", commit_hash="e" * 40
        )
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save(_dep(file1_id, repo1_id, package_name="fastapi"))
        await adapter.save(_dep(file2_id, repo2_id, package_name="fastapi"))

        results = await adapter.find_by_package_name("fastapi", repository_id=repo1_id)
        assert len(results) == 1
        assert results[0].repository_id == repo1_id

    async def test_filter_by_language(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save(
            _dep(file_id, repo_id, package_name="requests", language="python")
        )
        await adapter.save(
            _dep(file_id, repo_id, package_name="requests", language="javascript")
        )

        results = await adapter.find_by_package_name("requests", language="python")
        assert len(results) == 1
        assert results[0].language == "python"

    async def test_returns_all_files_using_package_across_repos(
        self, db_session: AsyncSession
    ) -> None:
        repo1_id, _, file1_id = await _setup(
            db_session, repo_name="repo-x", commit_hash="a" * 40
        )
        repo2_id, _, file2_id = await _setup(
            db_session, repo_name="repo-y", commit_hash="e" * 40
        )
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save(_dep(file1_id, repo1_id, package_name="fastapi"))
        await adapter.save(_dep(file2_id, repo2_id, package_name="fastapi"))

        results = await adapter.find_by_package_name("fastapi")
        assert len(results) == 2
        repo_ids = {r.repository_id for r in results}
        assert repo_ids == {repo1_id, repo2_id}


@pytest.mark.asyncio
class TestDeleteByFile:
    """delete_by_file() — deletion and edge cases."""

    async def test_deletes_all_deps_for_file(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save_many(
            [
                _dep(file_id, repo_id, package_name="fastapi"),
                _dep(file_id, repo_id, package_name="sqlalchemy"),
                _dep(file_id, repo_id, package_name="pydantic"),
            ]
        )

        count = await adapter.delete_by_file(file_id)
        assert count == 3

        remaining = await adapter.find_by_file(file_id)
        assert remaining == []

    async def test_returns_count_of_deleted_rows(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save(_dep(file_id, repo_id, package_name="fastapi"))

        count = await adapter.delete_by_file(file_id)
        assert count == 1

    async def test_returns_zero_for_nonexistent_file(
        self, db_session: AsyncSession
    ) -> None:
        adapter = PostgresDependencyRepository(db_session)
        count = await adapter.delete_by_file(999999)
        assert count == 0

    async def test_does_not_delete_deps_from_other_file(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, commit_id, file1_id = await _setup(
            db_session, file_path="pyproject.toml", content_hash="b" * 40
        )
        file2 = await PostgresFileRepository(db_session).save(
            FileFactory.create(
                repository_id=repo_id, path="other.toml", content_hash="c" * 40
            )
        )
        assert file2.id is not None
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save(_dep(file1_id, repo_id, package_name="fastapi"))
        await adapter.save(_dep(file2.id, repo_id, package_name="sqlalchemy"))

        await adapter.delete_by_file(file1_id)

        remaining = await adapter.find_by_file(file2.id)
        assert len(remaining) == 1
        assert remaining[0].package_name == "sqlalchemy"

    async def test_delete_is_idempotent(self, db_session: AsyncSession) -> None:
        repo_id, _, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)

        await adapter.save(_dep(file_id, repo_id, package_name="fastapi"))
        await adapter.delete_by_file(file_id)

        # Second delete should return 0, not error
        count = await adapter.delete_by_file(file_id)
        assert count == 0


@pytest.mark.asyncio
class TestSearchByPackageName:
    """search_by_package_name() — filter and scope branch permutations."""

    async def test_all_filters_applied(self, db_session: AsyncSession) -> None:
        repo_id, _commit_id, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)
        await adapter.save_many(
            [
                _dep(
                    file_id,
                    repo_id,
                    package_name="fastapi",
                    language="python",
                    dependency_type="runtime",
                    is_direct=True,
                ),
                _dep(
                    file_id,
                    repo_id,
                    package_name="fastapi-cli",
                    language="javascript",
                    dependency_type="dev",
                    is_direct=False,
                ),
            ]
        )
        await db_session.commit()

        deps, total = await adapter.search_by_package_name(
            query="fastapi",
            repository_id=repo_id,
            language="python",
            dependency_type="runtime",
            is_direct=True,
            branch="main",
        )

        assert total == 1
        assert [d.package_name for d in deps] == ["fastapi"]

    async def test_no_filters_latest_scope(self, db_session: AsyncSession) -> None:
        repo_id, _commit_id, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)
        await adapter.save_many([_dep(file_id, repo_id, package_name="requests")])
        await db_session.commit()

        # No filters → falls through to the scope=="latest" HEAD subquery.
        deps, total = await adapter.search_by_package_name(query="requests")

        assert total == 1
        assert deps[0].package_name == "requests"

    async def test_no_filters_no_scope_returns_all_versions(
        self, db_session: AsyncSession
    ) -> None:
        repo_id, _commit_id, file_id = await _setup(db_session)
        adapter = PostgresDependencyRepository(db_session)
        await adapter.save_many([_dep(file_id, repo_id, package_name="numpy")])
        await db_session.commit()

        # scope=None and no repo/branch → no file-version scoping applied.
        deps, total = await adapter.search_by_package_name(query="numpy", scope=None)

        assert total == 1
        assert deps[0].package_name == "numpy"
