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

    def test_null_packages(self, parser: JavaScriptDependencyParser) -> None:
        content = '{"lockfileVersion": 3, "packages": null}'
        deps = parser.parse(content, "package-lock.json")
        assert deps == []


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


class TestPnpmLock:
    def test_basic(self, parser: JavaScriptDependencyParser) -> None:
        content = """\
lockfileVersion: '6.0'
packages:
  /react@18.2.0:
    dev: false
  /typescript@5.3.3:
    dev: true
  /@scope/pkg@1.0.0:
    optional: true
"""
        deps = parser.parse(content, "pnpm-lock.yaml")
        assert len(deps) == 3

        react = next(d for d in deps if d["package_name"] == "react")
        assert react["resolved_version"] == "18.2.0"
        assert react["dependency_type"] == "runtime"
        assert react["is_direct"] is False
        assert react["language"] == "javascript"

        ts = next(d for d in deps if d["package_name"] == "typescript")
        assert ts["dependency_type"] == "dev"

        scoped = next(d for d in deps if d["package_name"] == "@scope/pkg")
        assert scoped["dependency_type"] == "optional"
        assert scoped["resolved_version"] == "1.0.0"

    def test_empty_packages(self, parser: JavaScriptDependencyParser) -> None:
        content = "lockfileVersion: '6.0'\npackages: {}\n"
        deps = parser.parse(content, "pnpm-lock.yaml")
        assert len(deps) == 0

    def test_null_packages(self, parser: JavaScriptDependencyParser) -> None:
        content = "lockfileVersion: '6.0'\npackages:\n"
        deps = parser.parse(content, "pnpm-lock.yaml")
        assert deps == []

    def test_invalid_yaml(self, parser: JavaScriptDependencyParser) -> None:
        deps = parser.parse("{{invalid", "pnpm-lock.yaml")
        assert deps == []


class TestSourceLine:
    """Tests for source line number tracking."""

    def test_package_json_source_lines(
        self, parser: JavaScriptDependencyParser
    ) -> None:
        content = """\
{
    "dependencies": {
        "react": "^18.0.0",
        "lodash": "^4.17.0"
    },
    "devDependencies": {
        "typescript": "^5.0.0"
    }
}
"""
        deps = parser.parse(content, "package.json")
        react = next(d for d in deps if d["package_name"] == "react")
        lodash = next(d for d in deps if d["package_name"] == "lodash")
        ts = next(d for d in deps if d["package_name"] == "typescript")

        assert react["source_line"] == 3
        assert lodash["source_line"] == 4
        assert ts["source_line"] == 7

    def test_yarn_lock_source_lines(self, parser: JavaScriptDependencyParser) -> None:
        content = """\
# yarn lockfile v1

lodash@^4.17.0:
  version "4.17.21"

react@^18.0.0:
  version "18.2.0"
"""
        deps = parser.parse(content, "yarn.lock")
        lodash = next(d for d in deps if d["package_name"] == "lodash")
        react = next(d for d in deps if d["package_name"] == "react")

        assert lodash["source_line"] == 3
        assert react["source_line"] == 6


class TestEdgeCases:
    def test_empty(self, parser: JavaScriptDependencyParser) -> None:
        assert parser.parse("", "package.json") == []
        assert parser.parse("", "yarn.lock") == []

    def test_invalid_json(self, parser: JavaScriptDependencyParser) -> None:
        assert parser.parse("{invalid", "package.json") == []
        assert parser.parse("{invalid", "package-lock.json") == []


class TestBranchCoverageEdgeCases:
    """Edge-case branch coverage for the JS dependency parser."""

    def test_parse_unknown_basename_returns_empty(
        self, parser: JavaScriptDependencyParser
    ) -> None:
        assert parser.parse("{}", "some/unknown.txt") == []

    def test_package_lock_v2_dep_types(
        self, parser: JavaScriptDependencyParser
    ) -> None:
        content = """\
{
  "packages": {
    "": {"name": "root"},
    "node_modules/react": {"version": "18.0.0"},
    "node_modules/@scope/dev": {"version": "1.0.0", "dev": true},
    "node_modules/peerlib": {"version": "2.0.0", "peer": true},
    "node_modules/optlib": {"version": "3.0.0", "optional": true},
    "node_modules/a/node_modules/nested": {"version": "4.0.0"}
  }
}
"""
        deps = parser.parse(content, "package-lock.json")
        by_name = {d["package_name"]: d for d in deps}
        assert by_name["react"]["dependency_type"] == "runtime"
        assert by_name["@scope/dev"]["dependency_type"] == "dev"
        assert by_name["peerlib"]["dependency_type"] == "peer"
        assert by_name["optlib"]["dependency_type"] == "optional"
        # Top-level node_modules entry is direct; nested is transitive.
        assert by_name["react"]["is_direct"] is True
        assert by_name["nested"]["is_direct"] is False

    def test_package_lock_v1_nested(self, parser: JavaScriptDependencyParser) -> None:
        content = """\
{
  "dependencies": {
    "top": {
      "version": "1.0.0",
      "dev": true,
      "dependencies": {
        "child": {"version": "2.0.0"}
      }
    }
  }
}
"""
        deps = parser.parse(content, "package-lock.json")
        by_name = {d["package_name"]: d for d in deps}
        assert by_name["top"]["dependency_type"] == "dev"
        assert by_name["top"]["is_direct"] is True
        assert by_name["child"]["is_direct"] is False

    def test_yarn_lock_quoted_and_colon_versions(
        self, parser: JavaScriptDependencyParser
    ) -> None:
        content = """\
# yarn lockfile v1

left-pad@^1.0.0:
  version "1.3.0"
  resolved "https://example.com/left-pad"

"@scope/berry@npm:^2.0.0":
  version: 2.1.0
"""
        deps = parser.parse(content, "yarn.lock")
        by_name = {d["package_name"]: d for d in deps}
        assert by_name["left-pad"]["resolved_version"] == "1.3.0"
        assert by_name["@scope/berry"]["resolved_version"] == "2.1.0"

    def test_yarn_lock_entry_without_version_skipped(
        self, parser: JavaScriptDependencyParser
    ) -> None:
        content = """\
no-version@^1.0.0:
  resolved "https://example.com/x"

has-version@^1.0.0:
  version "1.0.0"
"""
        deps = parser.parse(content, "yarn.lock")
        names = {d["package_name"] for d in deps}
        # Entry with no version line is not emitted.
        assert "no-version" not in names
        assert "has-version" in names

    def test_pnpm_non_dict_and_unmatched_key(
        self, parser: JavaScriptDependencyParser
    ) -> None:
        content = """\
lockfileVersion: '6.0'
packages:
  /react@18.2.0:
    dev: false
  /devpkg@1.0.0:
    dev: true
  not-a-valid-key:
    resolution: {}
  /scalar-info: just-a-string
"""
        deps = parser.parse(content, "pnpm-lock.yaml")
        by_name = {d["package_name"]: d for d in deps}
        assert by_name["react"]["dependency_type"] == "runtime"
        assert by_name["devpkg"]["dependency_type"] == "dev"
        # "not-a-valid-key" doesn't match the name@version regex → skipped.
        assert "not-a-valid-key" not in by_name

    def test_pnpm_non_dict_root_returns_empty(
        self, parser: JavaScriptDependencyParser
    ) -> None:
        # Top-level YAML that isn't a mapping → empty result.
        assert parser.parse("- just\n- a\n- list\n", "pnpm-lock.yaml") == []
