"""Tests for Python dependency parser."""

import pytest

from inxr2.adapters.external.dependency_parsers.python_deps import (
    PythonDependencyParser,
)


@pytest.fixture
def parser() -> PythonDependencyParser:
    return PythonDependencyParser()


class TestSupportsFile:
    def test_pyproject_toml(self, parser: PythonDependencyParser) -> None:
        assert parser.supports_file("pyproject.toml")
        assert parser.supports_file("backend/pyproject.toml")

    def test_requirements_txt(self, parser: PythonDependencyParser) -> None:
        assert parser.supports_file("requirements.txt")
        assert parser.supports_file("requirements-dev.txt")
        assert parser.supports_file("requirements_dev.txt")
        assert parser.supports_file("dev-requirements.txt")
        assert parser.supports_file("test-requirements.txt")

    def test_lock_files(self, parser: PythonDependencyParser) -> None:
        assert parser.supports_file("poetry.lock")
        assert parser.supports_file("Pipfile.lock")

    def test_unsupported(self, parser: PythonDependencyParser) -> None:
        assert not parser.supports_file("setup.py")
        assert not parser.supports_file("package.json")


class TestPyprojectTomlPEP621:
    def test_project_dependencies(self, parser: PythonDependencyParser) -> None:
        content = """\
[project]
name = "myapp"
dependencies = [
    "fastapi>=0.109.0",
    "sqlalchemy~=2.0",
    "pydantic",
]
"""
        deps = parser.parse(content, "pyproject.toml")
        assert len(deps) == 3

        assert deps[0]["package_name"] == "fastapi"
        assert deps[0]["version_spec"] == ">=0.109.0"
        assert deps[0]["dependency_type"] == "runtime"
        assert deps[0]["language"] == "python"

        assert deps[1]["package_name"] == "sqlalchemy"
        assert deps[1]["version_spec"] == "~=2.0"

        assert deps[2]["package_name"] == "pydantic"
        assert deps[2]["version_spec"] is None

    def test_optional_dependencies(self, parser: PythonDependencyParser) -> None:
        content = """\
[project]
dependencies = ["fastapi>=0.100"]

[project.optional-dependencies]
dev = ["pytest>=8.0", "black"]
docs = ["sphinx"]
"""
        deps = parser.parse(content, "pyproject.toml")
        assert len(deps) == 4

        runtime = [d for d in deps if d["dependency_type"] == "runtime"]
        dev = [d for d in deps if d["dependency_type"] == "dev"]
        optional = [d for d in deps if d["dependency_type"] == "optional"]

        assert len(runtime) == 1
        assert len(dev) == 2
        assert len(optional) == 1
        assert optional[0]["package_name"] == "sphinx"

    def test_build_system_requires(self, parser: PythonDependencyParser) -> None:
        content = """\
[build-system]
requires = ["setuptools>=68.0", "wheel"]
"""
        deps = parser.parse(content, "pyproject.toml")
        assert len(deps) == 2
        assert all(d["dependency_type"] == "build" for d in deps)

    def test_extras_and_markers(self, parser: PythonDependencyParser) -> None:
        content = """\
[project]
dependencies = [
    "uvicorn[standard]>=0.20; python_version >= '3.8'",
]
"""
        deps = parser.parse(content, "pyproject.toml")
        assert len(deps) == 1
        assert deps[0]["package_name"] == "uvicorn"
        assert deps[0]["version_spec"] == ">=0.20"
        assert deps[0]["extras"]["extras"] == ["standard"]
        assert "python_version" in deps[0]["extras"]["markers"]


class TestPyprojectTomlPoetry:
    def test_poetry_dependencies(self, parser: PythonDependencyParser) -> None:
        content = """\
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.109.0"
sqlalchemy = {version = "^2.0", optional = true}

[tool.poetry.dev-dependencies]
pytest = "^8.0"
"""
        deps = parser.parse(content, "pyproject.toml")
        # python is excluded
        assert len(deps) == 3

        fastapi = next(d for d in deps if d["package_name"] == "fastapi")
        assert fastapi["version_spec"] == "^0.109.0"
        assert fastapi["dependency_type"] == "runtime"

        sqlalchemy = next(d for d in deps if d["package_name"] == "sqlalchemy")
        assert sqlalchemy["dependency_type"] == "optional"

        pytest_dep = next(d for d in deps if d["package_name"] == "pytest")
        assert pytest_dep["dependency_type"] == "dev"

    def test_poetry_groups(self, parser: PythonDependencyParser) -> None:
        content = """\
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.109.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"

[tool.poetry.group.docs.dependencies]
sphinx = "^7.0"
"""
        deps = parser.parse(content, "pyproject.toml")
        assert len(deps) == 3

        dev = [d for d in deps if d["dependency_type"] == "dev"]
        assert len(dev) == 1
        assert dev[0]["package_name"] == "pytest"


class TestRequirementsTxt:
    def test_basic(self, parser: PythonDependencyParser) -> None:
        content = """\
fastapi>=0.109.0
sqlalchemy~=2.0
pydantic
"""
        deps = parser.parse(content, "requirements.txt")
        assert len(deps) == 3
        assert deps[0]["package_name"] == "fastapi"
        assert deps[0]["dependency_type"] == "runtime"

    def test_comments_and_options(self, parser: PythonDependencyParser) -> None:
        content = """\
# Production deps
--index-url https://pypi.org/simple
fastapi>=0.109.0
-e ./local-package
# Dev
pytest>=8.0
"""
        deps = parser.parse(content, "requirements.txt")
        assert len(deps) == 2
        assert deps[0]["package_name"] == "fastapi"
        assert deps[1]["package_name"] == "pytest"

    def test_dev_requirements(self, parser: PythonDependencyParser) -> None:
        content = "pytest>=8.0\nblack\n"
        deps = parser.parse(content, "requirements-dev.txt")
        assert all(d["dependency_type"] == "dev" for d in deps)

    def test_underscore_dev_requirements(self, parser: PythonDependencyParser) -> None:
        content = "pytest>=8.0\nblack\n"
        deps = parser.parse(content, "requirements_dev.txt")
        assert len(deps) == 2
        assert all(d["dependency_type"] == "dev" for d in deps)


class TestPoetryLock:
    def test_basic(self, parser: PythonDependencyParser) -> None:
        content = """\
[[package]]
name = "fastapi"
version = "0.109.1"
category = "main"

[[package]]
name = "pytest"
version = "8.0.2"
category = "dev"

[[package]]
name = "starlette"
version = "0.35.1"
category = "main"
"""
        deps = parser.parse(content, "poetry.lock")
        assert len(deps) == 3
        assert all(d["is_direct"] is False for d in deps)

        fastapi = next(d for d in deps if d["package_name"] == "fastapi")
        assert fastapi["resolved_version"] == "0.109.1"
        assert fastapi["dependency_type"] == "runtime"

        pytest_dep = next(d for d in deps if d["package_name"] == "pytest")
        assert pytest_dep["dependency_type"] == "dev"


class TestPipfileLock:
    def test_basic(self, parser: PythonDependencyParser) -> None:
        content = """\
{
    "_meta": {"hash": {"sha256": "abc123"}},
    "default": {
        "fastapi": {"version": "==0.109.1"},
        "sqlalchemy": {"version": "==2.0.25"}
    },
    "develop": {
        "pytest": {"version": "==8.0.2"}
    }
}
"""
        deps = parser.parse(content, "Pipfile.lock")
        assert len(deps) == 3

        fastapi = next(d for d in deps if d["package_name"] == "fastapi")
        assert fastapi["resolved_version"] == "0.109.1"
        assert fastapi["dependency_type"] == "runtime"

        pytest_dep = next(d for d in deps if d["package_name"] == "pytest")
        assert pytest_dep["dependency_type"] == "dev"


class TestEdgeCases:
    def test_empty_content(self, parser: PythonDependencyParser) -> None:
        assert parser.parse("", "pyproject.toml") == []
        assert parser.parse("", "requirements.txt") == []

    def test_invalid_toml(self, parser: PythonDependencyParser) -> None:
        assert parser.parse("not valid toml {{{", "pyproject.toml") == []

    def test_invalid_json(self, parser: PythonDependencyParser) -> None:
        assert parser.parse("not json", "Pipfile.lock") == []
