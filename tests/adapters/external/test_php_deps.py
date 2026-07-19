"""Tests for the PHP / Composer dependency parser."""

import pytest

from inxr2.adapters.external.dependency_parsers.php_deps import PhpDependencyParser


@pytest.fixture
def parser() -> PhpDependencyParser:
    return PhpDependencyParser()


class TestMetadata:
    def test_language(self, parser: PhpDependencyParser) -> None:
        assert parser.language == "php"

    def test_supported_files(self, parser: PhpDependencyParser) -> None:
        assert parser.supports_file("composer.json")
        assert parser.supports_file("/app/composer.lock")

    def test_unsupported_files(self, parser: PhpDependencyParser) -> None:
        assert not parser.supports_file("package.json")
        assert not parser.supports_file("Gemfile")


COMPOSER_JSON = """{
  "name": "laravel/laravel",
  "require": {
    "php": "^8.1",
    "ext-json": "*",
    "laravel/framework": "^10.0",
    "guzzlehttp/guzzle": "^7.2"
  },
  "require-dev": {
    "phpunit/phpunit": "^10.0",
    "mockery/mockery": "^1.5"
  }
}"""


class TestComposerJson:
    def test_parses_require(self, parser: PhpDependencyParser) -> None:
        deps = parser.parse(COMPOSER_JSON, "composer.json")
        by_name = {d["package_name"]: d for d in deps}
        assert "laravel/framework" in by_name
        assert by_name["laravel/framework"]["version_spec"] == "^10.0"
        assert by_name["laravel/framework"]["dependency_type"] == "runtime"
        assert by_name["laravel/framework"]["is_direct"] is True

    def test_parses_require_dev(self, parser: PhpDependencyParser) -> None:
        deps = parser.parse(COMPOSER_JSON, "composer.json")
        by_name = {d["package_name"]: d for d in deps}
        assert by_name["phpunit/phpunit"]["dependency_type"] == "dev"
        assert by_name["mockery/mockery"]["dependency_type"] == "dev"

    def test_skips_platform_requirements(self, parser: PhpDependencyParser) -> None:
        deps = parser.parse(COMPOSER_JSON, "composer.json")
        names = {d["package_name"] for d in deps}
        assert "php" not in names
        assert "ext-json" not in names

    def test_source_line_populated(self, parser: PhpDependencyParser) -> None:
        deps = parser.parse(COMPOSER_JSON, "composer.json")
        framework = next(d for d in deps if d["package_name"] == "laravel/framework")
        assert framework["source_line"] is not None

    def test_invalid_json_returns_empty(self, parser: PhpDependencyParser) -> None:
        assert parser.parse("{ not valid", "composer.json") == []


COMPOSER_LOCK = """{
  "packages": [
    {
      "name": "laravel/framework",
      "version": "v10.10.0"
    },
    {
      "name": "psr/log",
      "version": "3.0.0"
    }
  ],
  "packages-dev": [
    {
      "name": "phpunit/phpunit",
      "version": "10.1.0"
    }
  ]
}"""


class TestComposerLock:
    def test_parses_packages(self, parser: PhpDependencyParser) -> None:
        deps = parser.parse(COMPOSER_LOCK, "composer.lock")
        by_name = {d["package_name"]: d for d in deps}
        assert by_name["laravel/framework"]["resolved_version"] == "v10.10.0"
        assert by_name["laravel/framework"]["dependency_type"] == "runtime"
        # Lockfile entries are marked transitive (can't distinguish direct).
        assert by_name["laravel/framework"]["is_direct"] is False

    def test_parses_dev_packages(self, parser: PhpDependencyParser) -> None:
        deps = parser.parse(COMPOSER_LOCK, "composer.lock")
        by_name = {d["package_name"]: d for d in deps}
        assert by_name["phpunit/phpunit"]["dependency_type"] == "dev"

    def test_invalid_json_returns_empty(self, parser: PhpDependencyParser) -> None:
        assert parser.parse("nope", "composer.lock") == []
