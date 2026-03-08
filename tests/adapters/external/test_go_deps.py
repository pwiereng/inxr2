"""Tests for Go dependency parser."""

import pytest

from inxr2.adapters.external.dependency_parsers.go_deps import GoDependencyParser


@pytest.fixture
def parser() -> GoDependencyParser:
    return GoDependencyParser()


class TestSupportsFile:
    def test_supported(self, parser: GoDependencyParser) -> None:
        assert parser.supports_file("go.mod")
        assert parser.supports_file("some/path/go.mod")

    def test_unsupported(self, parser: GoDependencyParser) -> None:
        assert not parser.supports_file("go.sum")
        assert not parser.supports_file("package.json")


class TestGoMod:
    def test_require_block(self, parser: GoDependencyParser) -> None:
        content = """\
module github.com/example/myproject

go 1.21

require (
\tgithub.com/gin-gonic/gin v1.9.1
\tgithub.com/stretchr/testify v1.8.4
\tgolang.org/x/text v0.14.0 // indirect
)
"""
        deps = parser.parse(content, "go.mod")
        assert len(deps) == 3

        gin = deps[0]
        assert gin["package_name"] == "github.com/gin-gonic/gin"
        assert gin["version_spec"] == "v1.9.1"
        assert gin["resolved_version"] is None
        assert gin["language"] == "go"
        assert gin["is_direct"] is True

        text = deps[2]
        assert text["package_name"] == "golang.org/x/text"
        assert text["is_direct"] is False

    def test_single_require(self, parser: GoDependencyParser) -> None:
        content = """\
module example.com/foo

go 1.20

require github.com/pkg/errors v0.9.1
"""
        deps = parser.parse(content, "go.mod")
        assert len(deps) == 1
        assert deps[0]["package_name"] == "github.com/pkg/errors"
        assert deps[0]["version_spec"] == "v0.9.1"
        assert deps[0]["is_direct"] is True

    def test_multiple_require_blocks(self, parser: GoDependencyParser) -> None:
        content = """\
module example.com/foo

require (
\tgithub.com/foo/bar v1.0.0
)

require (
\tgithub.com/baz/qux v2.0.0 // indirect
)
"""
        deps = parser.parse(content, "go.mod")
        assert len(deps) == 2
        assert deps[0]["is_direct"] is True
        assert deps[1]["is_direct"] is False

    def test_prerelease_version(self, parser: GoDependencyParser) -> None:
        content = """\
module example.com/foo

require github.com/foo/bar v0.0.0-20231201000000-abcdef123456
"""
        deps = parser.parse(content, "go.mod")
        assert len(deps) == 1
        assert deps[0]["version_spec"] == "v0.0.0-20231201000000-abcdef123456"
        assert deps[0]["resolved_version"] is None


class TestEdgeCases:
    def test_empty(self, parser: GoDependencyParser) -> None:
        assert parser.parse("", "go.mod") == []

    def test_no_require(self, parser: GoDependencyParser) -> None:
        content = """\
module example.com/foo

go 1.21
"""
        assert parser.parse(content, "go.mod") == []

    def test_comments_and_blank_lines(self, parser: GoDependencyParser) -> None:
        content = """\
module example.com/foo

require (
\t// This is a comment
\tgithub.com/foo/bar v1.0.0

\tgithub.com/baz/qux v2.0.0
)
"""
        deps = parser.parse(content, "go.mod")
        assert len(deps) == 2
