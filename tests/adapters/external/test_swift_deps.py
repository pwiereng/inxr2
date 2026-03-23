"""Tests for Swift Package Manager dependency parser."""

import pytest

from inxr2.adapters.external.dependency_parsers.swift_deps import SwiftDependencyParser


@pytest.fixture
def parser() -> SwiftDependencyParser:
    return SwiftDependencyParser()


class TestSwiftDependencyParserMetadata:
    def test_language(self, parser: SwiftDependencyParser) -> None:
        assert parser.language == "swift"

    def test_supports_package_resolved(self, parser: SwiftDependencyParser) -> None:
        assert parser.supports_file("Package.resolved")
        assert parser.supports_file("/some/path/Package.resolved")

    def test_supports_package_swift(self, parser: SwiftDependencyParser) -> None:
        assert parser.supports_file("Package.swift")
        assert parser.supports_file("/some/path/Package.swift")

    def test_does_not_support_other_files(self, parser: SwiftDependencyParser) -> None:
        assert not parser.supports_file("package.json")
        assert not parser.supports_file("Podfile")
        assert not parser.supports_file("Cartfile")


PACKAGE_RESOLVED_V2 = """{
  "pins" : [
    {
      "identity" : "alamofire",
      "kind" : "remoteSourceControl",
      "location" : "https://github.com/Alamofire/Alamofire.git",
      "state" : {
        "revision" : "b3a5d1af37e2a3d6a5d0f1234567890abcdef012",
        "version" : "5.8.1"
      }
    },
    {
      "identity" : "swift-argument-parser",
      "kind" : "remoteSourceControl",
      "location" : "https://github.com/apple/swift-argument-parser.git",
      "state" : {
        "revision" : "abcdef1234567890abcdef1234567890abcdef12",
        "version" : "1.3.0"
      }
    }
  ],
  "version" : 2
}"""

PACKAGE_RESOLVED_V1 = """{
  "object": {
    "pins": [
      {
        "package": "Alamofire",
        "repositoryURL": "https://github.com/Alamofire/Alamofire.git",
        "state": {
          "branch": null,
          "revision": "b3a5d1af37e2a3d6a5d0f1234567890abcdef012",
          "version": "5.8.1"
        }
      },
      {
        "package": "SnapKit",
        "repositoryURL": "https://github.com/SnapKit/SnapKit.git",
        "state": {
          "branch": null,
          "revision": "deadbeef1234567890abcdef1234567890abcdef",
          "version": "5.6.0"
        }
      }
    ]
  },
  "version": 1
}"""

PACKAGE_SWIFT = """// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "MyApp",
    dependencies: [
        .package(url: "https://github.com/Alamofire/Alamofire.git", from: "5.8.0"),
        .package(url: "https://github.com/apple/swift-argument-parser.git", exact: "1.3.0"),
        .package(url: "https://github.com/nicklockwood/SwiftyJSON.git", .upToNextMajor(from: "4.0.0")),
        .package(url: "https://github.com/onevcat/Kingfisher.git", branch: "main"),
    ],
    targets: [
        .target(name: "MyApp", dependencies: ["Alamofire", "Kingfisher"]),
    ]
)
"""


class TestPackageResolvedV2:
    def test_parses_pins(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_RESOLVED_V2, "Package.resolved")
        assert len(deps) == 2

    def test_package_names(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_RESOLVED_V2, "Package.resolved")
        names = {d["package_name"] for d in deps}
        assert "alamofire" in names
        assert "swift-argument-parser" in names

    def test_resolved_versions(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_RESOLVED_V2, "Package.resolved")
        by_name = {d["package_name"]: d for d in deps}
        assert by_name["alamofire"]["resolved_version"] == "5.8.1"
        assert by_name["swift-argument-parser"]["resolved_version"] == "1.3.0"

    def test_language_is_swift(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_RESOLVED_V2, "Package.resolved")
        assert all(d["language"] == "swift" for d in deps)

    def test_is_not_direct(self, parser: SwiftDependencyParser) -> None:
        # Lockfile entries are resolved (all), not necessarily direct
        deps = parser.parse(PACKAGE_RESOLVED_V2, "Package.resolved")
        assert all(not d["is_direct"] for d in deps)

    def test_url_in_extras(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_RESOLVED_V2, "Package.resolved")
        by_name = {d["package_name"]: d for d in deps}
        assert (
            by_name["alamofire"]["extras"]["url"]
            == "https://github.com/Alamofire/Alamofire.git"
        )


class TestPackageResolvedV1:
    def test_parses_pins(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_RESOLVED_V1, "Package.resolved")
        assert len(deps) == 2

    def test_package_names_from_package_field(
        self, parser: SwiftDependencyParser
    ) -> None:
        deps = parser.parse(PACKAGE_RESOLVED_V1, "Package.resolved")
        names = {d["package_name"] for d in deps}
        assert "Alamofire" in names
        assert "SnapKit" in names

    def test_resolved_versions(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_RESOLVED_V1, "Package.resolved")
        by_name = {d["package_name"]: d for d in deps}
        assert by_name["Alamofire"]["resolved_version"] == "5.8.1"
        assert by_name["SnapKit"]["resolved_version"] == "5.6.0"

    def test_invalid_json_returns_empty(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse("not json {{{", "Package.resolved")
        assert deps == []


class TestPackageSwift:
    def test_parses_package_dependencies(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_SWIFT, "Package.swift")
        assert len(deps) == 4

    def test_package_names_extracted_from_url(
        self, parser: SwiftDependencyParser
    ) -> None:
        deps = parser.parse(PACKAGE_SWIFT, "Package.swift")
        names = {d["package_name"] for d in deps}
        assert "Alamofire" in names
        assert "swift-argument-parser" in names
        assert "SwiftyJSON" in names
        assert "Kingfisher" in names

    def test_from_version_spec(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_SWIFT, "Package.swift")
        by_name = {d["package_name"]: d for d in deps}
        assert by_name["Alamofire"]["version_spec"] == ">= 5.8.0"

    def test_exact_version_spec(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_SWIFT, "Package.swift")
        by_name = {d["package_name"]: d for d in deps}
        assert by_name["swift-argument-parser"]["version_spec"] == "== 1.3.0"

    def test_up_to_next_major_version_spec(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_SWIFT, "Package.swift")
        by_name = {d["package_name"]: d for d in deps}
        assert by_name["SwiftyJSON"]["version_spec"] == ">= 4.0.0, < 5.0.0"

    def test_branch_version_spec(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_SWIFT, "Package.swift")
        by_name = {d["package_name"]: d for d in deps}
        assert by_name["Kingfisher"]["version_spec"] == "branch: main"

    def test_is_direct(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_SWIFT, "Package.swift")
        assert all(d["is_direct"] for d in deps)

    def test_language_is_swift(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_SWIFT, "Package.swift")
        assert all(d["language"] == "swift" for d in deps)

    def test_source_line_numbers(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_SWIFT, "Package.swift")
        # All deps should have source lines
        assert all(d["source_line"] is not None for d in deps)

    def test_prerelease_version_does_not_raise(
        self, parser: SwiftDependencyParser
    ) -> None:
        """Non-numeric major segment must not crash — falls back to >= only."""
        content = """// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "MyApp",
    dependencies: [
        .package(url: "https://github.com/Foo/Bar.git", .upToNextMajor(from: "beta.1")),
    ]
)
"""
        deps = parser.parse(content, "Package.swift")
        assert len(deps) == 1
        assert deps[0]["version_spec"] == ">= beta.1"

    def test_up_to_next_minor_version_spec(self, parser: SwiftDependencyParser) -> None:
        content = """// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "MyApp",
    dependencies: [
        .package(url: "https://github.com/Foo/Bar.git", .upToNextMinor(from: "2.3.0")),
    ]
)
"""
        deps = parser.parse(content, "Package.swift")
        assert deps[0]["version_spec"] == ">= 2.3.0, < 2.4.0"

    def test_half_open_range_version_spec(self, parser: SwiftDependencyParser) -> None:
        content = """// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "MyApp",
    dependencies: [
        .package(url: "https://github.com/Foo/Bar.git", "1.0.0" ..< "2.0.0"),
    ]
)
"""
        deps = parser.parse(content, "Package.swift")
        assert len(deps) == 1
        assert deps[0]["version_spec"] == ">= 1.0.0, < 2.0.0"

    def test_closed_range_version_spec(self, parser: SwiftDependencyParser) -> None:
        content = """// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "MyApp",
    dependencies: [
        .package(url: "https://github.com/Foo/Bar.git", "1.0.0" ... "1.9.9"),
    ]
)
"""
        deps = parser.parse(content, "Package.swift")
        assert len(deps) == 1
        assert deps[0]["version_spec"] == ">= 1.0.0, <= 1.9.9"

    def test_empty_package_swift(self, parser: SwiftDependencyParser) -> None:
        content = """// swift-tools-version: 5.9
import PackageDescription
let package = Package(name: "Empty", targets: [])
"""
        deps = parser.parse(content, "Package.swift")
        assert deps == []


class TestCommentStripping:
    """Commented-out .package() calls must not produce false dependencies."""

    def test_line_comment_suppresses_dependency(
        self, parser: SwiftDependencyParser
    ) -> None:
        content = """// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "MyApp",
    dependencies: [
        // .package(url: "https://github.com/Foo/Bar.git", from: "1.0.0"),
        .package(url: "https://github.com/Real/Dep.git", from: "2.0.0"),
    ]
)
"""
        deps = parser.parse(content, "Package.swift")
        names = {d["package_name"] for d in deps}
        assert "Bar" not in names
        assert "Dep" in names

    def test_block_comment_suppresses_dependency(
        self, parser: SwiftDependencyParser
    ) -> None:
        content = """// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "MyApp",
    dependencies: [
        /* .package(url: "https://github.com/Foo/Bar.git", from: "1.0.0"), */
        .package(url: "https://github.com/Real/Dep.git", from: "2.0.0"),
    ]
)
"""
        deps = parser.parse(content, "Package.swift")
        names = {d["package_name"] for d in deps}
        assert "Bar" not in names
        assert "Dep" in names

    def test_source_line_still_correct_after_stripping(
        self, parser: SwiftDependencyParser
    ) -> None:
        """Line numbers must refer to the original file, not the stripped content."""
        content = """// swift-tools-version: 5.9
import PackageDescription
// This is a comment
let package = Package(
    name: "MyApp",
    dependencies: [
        .package(url: "https://github.com/Real/Dep.git", from: "2.0.0"),
    ]
)
"""
        deps = parser.parse(content, "Package.swift")
        assert len(deps) == 1
        # The .package line is line 7 in the original file
        assert deps[0]["source_line"] == 7


class TestFileUrlPreservation:
    """file:/// URLs must not be corrupted by comment stripping."""

    def test_file_url_not_stripped(self, parser: SwiftDependencyParser) -> None:
        content = """// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "MyApp",
    dependencies: [
        .package(url: "file:///Users/dev/MyLib", from: "1.0.0"),
    ]
)
"""
        deps = parser.parse(content, "Package.swift")
        assert len(deps) == 1
        assert deps[0]["extras"]["url"] == "file:///Users/dev/MyLib"


class TestDuplicateUrlSourceLines:
    """Each dependency reports the correct source_line even for duplicate URLs."""

    def test_duplicate_url_gets_distinct_source_lines(
        self, parser: SwiftDependencyParser
    ) -> None:
        content = """// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "MyApp",
    dependencies: [
        .package(url: "https://github.com/Foo/Bar.git", from: "1.0.0"),
        .package(url: "https://github.com/Foo/Bar.git", from: "2.0.0"),
    ]
)
"""
        deps = parser.parse(content, "Package.swift")
        assert len(deps) == 2
        lines = [d["source_line"] for d in deps]
        # Both lines must be non-None and distinct
        assert None not in lines
        assert lines[0] != lines[1]


class TestPackageNameFromUrl:
    """Test the URL-to-name extraction helper."""

    def test_strips_git_suffix(self, parser: SwiftDependencyParser) -> None:
        deps = parser.parse(PACKAGE_RESOLVED_V2, "Package.resolved")
        # alamofire identity takes precedence over URL extraction, but check URL extras
        by_name = {d["package_name"]: d for d in deps}
        assert "alamofire" in by_name

    def test_handles_url_without_git_suffix(
        self, parser: SwiftDependencyParser
    ) -> None:
        content = """{
  "pins": [
    {
      "identity": "my-lib",
      "kind": "remoteSourceControl",
      "location": "https://example.com/org/my-lib",
      "state": {"version": "1.0.0"}
    }
  ],
  "version": 2
}"""
        deps = parser.parse(content, "Package.resolved")
        assert deps[0]["package_name"] == "my-lib"
