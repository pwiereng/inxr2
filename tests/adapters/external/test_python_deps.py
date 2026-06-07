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


class TestSourceLine:
    """Tests for source line number tracking."""

    def test_requirements_txt_source_lines(
        self, parser: PythonDependencyParser
    ) -> None:
        content = """\
# Requirements
fastapi>=0.100.0
uvicorn[standard]>=0.20.0
# Dev
pytest>=7.0
"""
        deps = parser.parse(content, "requirements.txt")
        fastapi = next(d for d in deps if d["package_name"] == "fastapi")
        uvicorn = next(d for d in deps if d["package_name"] == "uvicorn")
        pytest_dep = next(d for d in deps if d["package_name"] == "pytest")

        assert fastapi["source_line"] == 2
        assert uvicorn["source_line"] == 3
        assert pytest_dep["source_line"] == 5

    def test_pyproject_toml_source_lines(self, parser: PythonDependencyParser) -> None:
        content = """\
[project]
name = "myproject"
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn>=0.20.0",
]
"""
        deps = parser.parse(content, "pyproject.toml")
        fastapi = next(d for d in deps if d["package_name"] == "fastapi")
        uvicorn = next(d for d in deps if d["package_name"] == "uvicorn")

        assert fastapi["source_line"] == 4
        assert uvicorn["source_line"] == 5


class TestEdgeCases:
    def test_empty_content(self, parser: PythonDependencyParser) -> None:
        assert parser.parse("", "pyproject.toml") == []
        assert parser.parse("", "requirements.txt") == []

    def test_invalid_toml(self, parser: PythonDependencyParser) -> None:
        assert parser.parse("not valid toml {{{", "pyproject.toml") == []

    def test_invalid_json(self, parser: PythonDependencyParser) -> None:
        assert parser.parse("not json", "Pipfile.lock") == []


class TestBranchCoverageEdgeCases:
    """Edge-case branch coverage for the Python dependency parser."""

    def test_pyproject_poetry_dict_specs(self, parser: PythonDependencyParser) -> None:
        content = """\
[tool.poetry.dependencies]
python = "^3.11"
requests = "^2.0"
django = {version = "^4.0", optional = true, extras = ["bcrypt"], markers = "sys_platform == 'linux'", python = "^3.11"}

[tool.poetry.dev-dependencies]
pytest = "^7.0"

[tool.poetry.group.test.dependencies]
coverage = "^6.0"

[tool.poetry.group.lint.dependencies]
ruff = "^0.1"
"""
        deps = parser.parse(content, "pyproject.toml")
        by_name = {d["package_name"]: d for d in deps}
        # python is skipped
        assert "python" not in by_name
        assert by_name["requests"]["dependency_type"] == "runtime"
        # dict spec with optional → optional type, extras/markers/python captured
        assert by_name["django"]["dependency_type"] == "optional"
        assert by_name["django"]["extras"]["extras"] == ["bcrypt"]
        assert "markers" in by_name["django"]["extras"]
        assert "python" in by_name["django"]["extras"]
        assert by_name["pytest"]["dependency_type"] == "dev"
        # group "test" → dev, group "lint" → optional
        assert by_name["coverage"]["dependency_type"] == "dev"
        assert by_name["ruff"]["dependency_type"] == "optional"

    def test_pyproject_invalid_deps_skipped(
        self, parser: PythonDependencyParser
    ) -> None:
        content = """\
[project]
name = "x"
dependencies = ["requests>=2.0", "", "  "]

[project.optional-dependencies]
extra = ["", "click"]

[build-system]
requires = ["setuptools", ""]
"""
        deps = parser.parse(content, "pyproject.toml")
        names = {d["package_name"] for d in deps}
        assert "requests" in names
        assert "click" in names
        assert "setuptools" in names

    def test_poetry_lock_optional_and_dev(self, parser: PythonDependencyParser) -> None:
        content = """\
[[package]]
name = "runtimelib"
version = "1.0.0"
category = "main"

[[package]]
name = "devlib"
version = "2.0.0"
category = "dev"

[[package]]
name = "optlib"
version = "3.0.0"
category = "main"
optional = true
"""
        deps = parser.parse(content, "poetry.lock")
        by_name = {d["package_name"]: d for d in deps}
        assert by_name["runtimelib"]["dependency_type"] == "runtime"
        assert by_name["devlib"]["dependency_type"] == "dev"
        assert by_name["optlib"]["dependency_type"] == "optional"

    def test_pipfile_lock(self, parser: PythonDependencyParser) -> None:
        content = """\
{
  "default": {
    "requests": {"version": "==2.28.0"},
    "click": {"version": ">=8.0"}
  },
  "develop": {
    "pytest": {"version": "==7.0.0"}
  }
}
"""
        deps = parser.parse(content, "Pipfile.lock")
        by_name = {d["package_name"]: d for d in deps}
        assert by_name["requests"]["dependency_type"] == "runtime"
        assert by_name["requests"]["resolved_version"] == "2.28.0"
        # Non-"==" version stays a spec, not resolved.
        assert by_name["click"]["dependency_type"] == "runtime"
        assert by_name["pytest"]["dependency_type"] == "dev"

    def test_pep508_empty_and_unparseable(self, parser: PythonDependencyParser) -> None:
        assert parser._parse_pep508("", "runtime") is None
        assert parser._parse_pep508("   ", "runtime") is None
        # Leading symbol fails the PEP 508 name pattern.
        assert parser._parse_pep508("@@@nope", "runtime") is None

    def test_poetry_dep_non_str_non_dict(self, parser: PythonDependencyParser) -> None:
        # A spec that's neither str nor dict (e.g. a list) → fallback dep.
        dep = parser._poetry_dep("weird", ["a", "b"], "runtime")
        assert dep["package_name"] == "weird"
        assert dep["dependency_type"] == "runtime"
