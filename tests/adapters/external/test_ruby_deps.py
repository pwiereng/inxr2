"""Tests for Ruby dependency parser."""

import pytest

from inxr2.adapters.external.dependency_parsers.ruby_deps import RubyDependencyParser


@pytest.fixture
def parser() -> RubyDependencyParser:
    return RubyDependencyParser()


class TestSupportsFile:
    def test_supported(self, parser: RubyDependencyParser) -> None:
        assert parser.supports_file("Gemfile")
        assert parser.supports_file("Gemfile.lock")
        assert parser.supports_file("some/path/Gemfile")

    def test_unsupported(self, parser: RubyDependencyParser) -> None:
        assert not parser.supports_file("gemfile")
        assert not parser.supports_file("package.json")


class TestGemfile:
    def test_basic_gems(self, parser: RubyDependencyParser) -> None:
        content = """\
source 'https://rubygems.org'

gem 'rails', '~> 7.1.0'
gem 'pg', '>= 1.5'
gem 'puma'
"""
        deps = parser.parse(content, "Gemfile")
        assert len(deps) == 3

        rails = deps[0]
        assert rails["package_name"] == "rails"
        assert rails["version_spec"] == "~> 7.1.0"
        assert rails["language"] == "ruby"
        assert rails["is_direct"] is True
        assert rails["dependency_type"] == "runtime"

        puma = deps[2]
        assert puma["package_name"] == "puma"
        assert puma["version_spec"] is None

    def test_group_block(self, parser: RubyDependencyParser) -> None:
        content = """\
gem 'rails', '~> 7.1.0'

group :development, :test do
  gem 'rspec-rails', '~> 6.0'
  gem 'pry'
end

gem 'sidekiq', '~> 7.0'
"""
        deps = parser.parse(content, "Gemfile")
        assert len(deps) == 4

        assert deps[0]["dependency_type"] == "runtime"
        assert deps[1]["dependency_type"] == "dev"
        assert deps[2]["dependency_type"] == "dev"
        assert deps[3]["dependency_type"] == "runtime"

    def test_nested_groups(self, parser: RubyDependencyParser) -> None:
        content = """\
gem 'rails'

group :development do
  gem 'pry'
  group :test do
    gem 'rspec'
  end
  gem 'rubocop'
end

gem 'sidekiq'
"""
        deps = parser.parse(content, "Gemfile")
        assert len(deps) == 5

        assert deps[0]["package_name"] == "rails"
        assert deps[0]["dependency_type"] == "runtime"
        assert deps[1]["package_name"] == "pry"
        assert deps[1]["dependency_type"] == "dev"
        assert deps[2]["package_name"] == "rspec"
        assert deps[2]["dependency_type"] == "dev"
        # rubocop is still inside the outer :development group
        assert deps[3]["package_name"] == "rubocop"
        assert deps[3]["dependency_type"] == "dev"
        assert deps[4]["package_name"] == "sidekiq"
        assert deps[4]["dependency_type"] == "runtime"

    def test_double_quotes(self, parser: RubyDependencyParser) -> None:
        content = 'gem "nokogiri", "~> 1.15"\n'
        deps = parser.parse(content, "Gemfile")
        assert len(deps) == 1
        assert deps[0]["package_name"] == "nokogiri"
        assert deps[0]["version_spec"] == "~> 1.15"


class TestGemfileLock:
    def test_basic_lockfile(self, parser: RubyDependencyParser) -> None:
        content = """\
GEM
  remote: https://rubygems.org/
  specs:
    rails (7.1.0)
      actioncable (= 7.1.0)
      actionmailer (= 7.1.0)
    actioncable (7.1.0)
      actionpack (= 7.1.0)
    pg (1.5.4)

PLATFORMS
  ruby

DEPENDENCIES
  rails (~> 7.1.0)
  pg (>= 1.5)
"""
        deps = parser.parse(content, "Gemfile.lock")

        # Top-level gems: rails, actioncable, pg
        top_level = [d for d in deps if "extras" not in d]
        assert len(top_level) == 3

        rails = top_level[0]
        assert rails["package_name"] == "rails"
        assert rails["resolved_version"] == "7.1.0"
        assert rails["is_direct"] is False  # Lock file — directness from Gemfile

        # Transitive deps under rails
        transitives = [d for d in deps if d.get("extras", {}).get("parent") == "rails"]
        assert len(transitives) == 2
        assert transitives[0]["package_name"] == "actioncable"
        assert transitives[0]["version_spec"] == "= 7.1.0"

    def test_no_gem_section(self, parser: RubyDependencyParser) -> None:
        content = """\
PLATFORMS
  ruby

DEPENDENCIES
  rails (~> 7.1.0)
"""
        deps = parser.parse(content, "Gemfile.lock")
        assert deps == []


class TestEdgeCases:
    def test_empty(self, parser: RubyDependencyParser) -> None:
        assert parser.parse("", "Gemfile") == []
        assert parser.parse("", "Gemfile.lock") == []

    def test_comments_in_gemfile(self, parser: RubyDependencyParser) -> None:
        content = """\
# Database
gem 'pg'
# gem 'mysql2'  # commented out
"""
        deps = parser.parse(content, "Gemfile")
        assert len(deps) == 1
        assert deps[0]["package_name"] == "pg"
