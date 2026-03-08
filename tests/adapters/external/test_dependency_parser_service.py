"""Tests for the DependencyParserService dispatcher."""

import pytest

from inxr2.adapters.external.dependency_parsers.service import (
    DependencyParserService,
)


@pytest.fixture
def service() -> DependencyParserService:
    return DependencyParserService()


class TestSupportsFile:
    def test_python_files(self, service: DependencyParserService) -> None:
        assert service.supports_file("pyproject.toml")
        assert service.supports_file("requirements.txt")
        assert service.supports_file("poetry.lock")
        assert service.supports_file("Pipfile.lock")

    def test_javascript_files(self, service: DependencyParserService) -> None:
        assert service.supports_file("package.json")
        assert service.supports_file("package-lock.json")
        assert service.supports_file("yarn.lock")
        assert service.supports_file("pnpm-lock.yaml")

    def test_java_files(self, service: DependencyParserService) -> None:
        assert service.supports_file("pom.xml")
        assert service.supports_file("build.gradle")
        assert service.supports_file("build.gradle.kts")

    def test_csharp_files(self, service: DependencyParserService) -> None:
        assert service.supports_file("App.csproj")
        assert service.supports_file("packages.lock.json")
        assert service.supports_file("Directory.Packages.props")

    def test_nested_paths(self, service: DependencyParserService) -> None:
        assert service.supports_file("backend/pyproject.toml")
        assert service.supports_file("frontend/package.json")
        assert service.supports_file("services/api/pom.xml")

    def test_unsupported(self, service: DependencyParserService) -> None:
        assert not service.supports_file("README.md")
        assert not service.supports_file("main.py")
        assert not service.supports_file("Dockerfile")


class TestParse:
    def test_dispatches_to_python(self, service: DependencyParserService) -> None:
        content = """\
[project]
dependencies = ["fastapi>=0.100"]
"""
        deps = service.parse(content, "pyproject.toml")
        assert len(deps) == 1
        assert deps[0]["language"] == "python"

    def test_dispatches_to_javascript(self, service: DependencyParserService) -> None:
        content = '{"dependencies": {"react": "^18.0.0"}}'
        deps = service.parse(content, "package.json")
        assert len(deps) == 1
        assert deps[0]["language"] == "javascript"

    def test_dispatches_to_java(self, service: DependencyParserService) -> None:
        content = """\
<project>
    <dependencies>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13</version>
        </dependency>
    </dependencies>
</project>
"""
        deps = service.parse(content, "pom.xml")
        assert len(deps) == 1
        assert deps[0]["language"] == "java"

    def test_dispatches_to_csharp(self, service: DependencyParserService) -> None:
        content = """\
<Project>
  <ItemGroup>
    <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
  </ItemGroup>
</Project>
"""
        deps = service.parse(content, "App.csproj")
        assert len(deps) == 1
        assert deps[0]["language"] == "csharp"

    def test_unsupported_file(self, service: DependencyParserService) -> None:
        deps = service.parse("anything", "unknown.txt")
        assert deps == []

    def test_invalid_content_returns_empty(
        self, service: DependencyParserService
    ) -> None:
        deps = service.parse("{{{invalid", "pyproject.toml")
        assert deps == []
