"""Tests for JavaScript/TypeScript dependency parser."""

import pytest

from inxr2.adapters.external.dependency_parsers.javascript_deps import (
    JavaScriptDependencyParser,
)


@pytest.fixture
def parser() -> JavaScriptDependencyParser:
    return JavaScriptDependencyParser()


class TestSupportsFile:
    def test_supported(self, parser: JavaScriptDependencyParser) -> None:
        assert parser.supports_file("package.json")
        assert parser.supports_file("frontend/package.json")
        assert parser.supports_file("package-lock.json")
        assert parser.supports_file("yarn.lock")
        assert parser.supports_file("pnpm-lock.yaml")

    def test_unsupported(self, parser: JavaScriptDependencyParser) -> None:
        assert not parser.supports_file("pyproject.toml")
        assert not parser.supports_file("tsconfig.json")


class TestPackageJson:
    def test_all_sections(self, parser: JavaScriptDependencyParser) -> None:
        content = """\
{
    "name": "myapp",
    "dependencies": {
        "react": "^18.2.0",
        "react-dom": "^18.2.0"
    },
    "devDependencies": {
        "typescript": "^5.0.0",
        "vitest": "^1.0.0"
    },
    "peerDependencies": {
        "react": ">=16.8.0"
    },
    "optionalDependencies": {
        "fsevents": "^2.3.0"
    }
}
"""
        deps = parser.parse(content, "package.json")
        # react appears in both dependencies and peerDependencies = 6 total
        assert len(deps) == 6

        runtime = [d for d in deps if d["dependency_type"] == "runtime"]
        dev = [d for d in deps if d["dependency_type"] == "dev"]
        peer = [d for d in deps if d["dependency_type"] == "peer"]
        optional = [d for d in deps if d["dependency_type"] == "optional"]

        assert len(runtime) == 2
        assert len(dev) == 2
        assert len(peer) == 1
        assert len(optional) == 1

        react = next(d for d in runtime if d["package_name"] == "react")
        assert react["version_spec"] == "^18.2.0"
        assert react["language"] == "javascript"

    def test_scoped_packages(self, parser: JavaScriptDependencyParser) -> None:
        content = """\
{
    "dependencies": {
        "@mui/material": "^5.0.0",
        "@types/react": "^18.0.0"
    }
}
"""
        deps = parser.parse(content, "package.json")
        assert len(deps) == 2
        assert deps[0]["package_name"] == "@mui/material"
        assert deps[1]["package_name"] == "@types/react"

    def test_no_dependencies(self, parser: JavaScriptDependencyParser) -> None:
        content = '{"name": "mylib", "version": "1.0.0"}'
        deps = parser.parse(content, "package.json")
        assert len(deps) == 0


class TestPackageLockJson:
    def test_v3_format(self, parser: JavaScriptDependencyParser) -> None:
        content = """\
{
    "name": "myapp",
    "lockfileVersion": 3,
    "packages": {
        "": {"name": "myapp"},
        "node_modules/react": {
            "version": "18.2.0"
        },
        "node_modules/typescript": {
            "version": "5.3.3",
            "dev": true
        },
        "node_modules/react/node_modules/loose-envify": {
            "version": "1.4.0"
        }
    }
}
"""
        deps = parser.parse(content, "package-lock.json")
        assert len(deps) == 3

        react = next(d for d in deps if d["package_name"] == "react")
        assert react["resolved_version"] == "18.2.0"
        assert react["dependency_type"] == "runtime"
        assert react["is_direct"] is True

        ts = next(d for d in deps if d["package_name"] == "typescript")
        assert ts["dependency_type"] == "dev"

        envify = next(d for d in deps if d["package_name"] == "loose-envify")
        assert envify["is_direct"] is False

    def test_scoped_package_in_lock(self, parser: JavaScriptDependencyParser) -> None:
        content = """\
{
    "lockfileVersion": 3,
    "packages": {
        "": {},
        "node_modules/@scope/pkg": {
            "version": "1.0.0"
        }
    }
}
"""
        deps = parser.parse(content, "package-lock.json")
        assert len(deps) == 1
        assert deps[0]["package_name"] == "@scope/pkg"


class TestYarnLock:
    def test_basic(self, parser: JavaScriptDependencyParser) -> None:
        content = """\
# yarn lockfile v1

react@^18.2.0:
  version "18.2.0"
  resolved "https://registry.yarnpkg.com/react/-/react-18.2.0.tgz"

typescript@^5.0.0:
  version "5.3.3"
  resolved "https://registry.yarnpkg.com/typescript/-/typescript-5.3.3.tgz"
"""
        deps = parser.parse(content, "yarn.lock")
        assert len(deps) == 2

        react = next(d for d in deps if d["package_name"] == "react")
        assert react["resolved_version"] == "18.2.0"
        assert react["is_direct"] is False
        assert react["language"] == "javascript"

    def test_scoped_packages(self, parser: JavaScriptDependencyParser) -> None:
        content = """\
"@mui/material@^5.0.0":
  version "5.15.0"
"""
        deps = parser.parse(content, "yarn.lock")
        assert len(deps) == 1
        assert deps[0]["package_name"] == "@mui/material"
        assert deps[0]["resolved_version"] == "5.15.0"


class TestEdgeCases:
    def test_empty(self, parser: JavaScriptDependencyParser) -> None:
        assert parser.parse("", "package.json") == []
        assert parser.parse("", "yarn.lock") == []

    def test_invalid_json(self, parser: JavaScriptDependencyParser) -> None:
        assert parser.parse("{invalid", "package.json") == []
        assert parser.parse("{invalid", "package-lock.json") == []
