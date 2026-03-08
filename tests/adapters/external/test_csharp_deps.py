"""Tests for C# dependency parser."""

import pytest

from inxr2.adapters.external.dependency_parsers.csharp_deps import (
    CSharpDependencyParser,
)


@pytest.fixture
def parser() -> CSharpDependencyParser:
    return CSharpDependencyParser()


class TestSupportsFile:
    def test_supported(self, parser: CSharpDependencyParser) -> None:
        assert parser.supports_file("MyApp.csproj")
        assert parser.supports_file("src/MyApp.csproj")
        assert parser.supports_file("packages.lock.json")
        assert parser.supports_file("Directory.Packages.props")

    def test_unsupported(self, parser: CSharpDependencyParser) -> None:
        assert not parser.supports_file("package.json")
        assert not parser.supports_file("app.config")


class TestCsproj:
    def test_package_references(self, parser: CSharpDependencyParser) -> None:
        content = """\
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
    <PackageReference Include="Serilog" Version="3.1.1" />
  </ItemGroup>
</Project>
"""
        deps = parser.parse(content, "MyApp.csproj")
        assert len(deps) == 2

        newtonsoft = deps[0]
        assert newtonsoft["package_name"] == "Newtonsoft.Json"
        assert newtonsoft["version_spec"] == "13.0.3"
        assert newtonsoft["dependency_type"] == "runtime"
        assert newtonsoft["language"] == "csharp"

    def test_dev_dependencies(self, parser: CSharpDependencyParser) -> None:
        content = """\
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <PackageReference Include="xunit" Version="2.6.6" />
    <PackageReference Include="coverlet.collector" Version="6.0.0">
      <PrivateAssets>all</PrivateAssets>
    </PackageReference>
  </ItemGroup>
</Project>
"""
        deps = parser.parse(content, "Test.csproj")
        assert len(deps) == 2

        xunit = next(d for d in deps if d["package_name"] == "xunit")
        assert xunit["dependency_type"] == "runtime"

        coverlet = next(d for d in deps if d["package_name"] == "coverlet.collector")
        assert coverlet["dependency_type"] == "dev"

    def test_private_assets_attribute(self, parser: CSharpDependencyParser) -> None:
        content = """\
<Project>
  <ItemGroup>
    <PackageReference Include="Analyzer" Version="1.0" PrivateAssets="all" />
  </ItemGroup>
</Project>
"""
        deps = parser.parse(content, "App.csproj")
        assert deps[0]["dependency_type"] == "dev"

    def test_version_as_child_element(self, parser: CSharpDependencyParser) -> None:
        content = """\
<Project>
  <ItemGroup>
    <PackageReference Include="SomePackage">
      <Version>2.0.0</Version>
    </PackageReference>
  </ItemGroup>
</Project>
"""
        deps = parser.parse(content, "App.csproj")
        assert len(deps) == 1
        assert deps[0]["version_spec"] == "2.0.0"


class TestPackagesLockJson:
    def test_basic(self, parser: CSharpDependencyParser) -> None:
        content = """\
{
    "version": 1,
    "dependencies": {
        "net8.0": {
            "Newtonsoft.Json": {
                "type": "Direct",
                "requested": "[13.0.3, )",
                "resolved": "13.0.3"
            },
            "System.Text.Json": {
                "type": "Transitive",
                "resolved": "8.0.0"
            }
        }
    }
}
"""
        deps = parser.parse(content, "packages.lock.json")
        assert len(deps) == 2

        direct = next(d for d in deps if d["package_name"] == "Newtonsoft.Json")
        assert direct["is_direct"] is True
        assert direct["version_spec"] == "[13.0.3, )"
        assert direct["resolved_version"] == "13.0.3"

        transitive = next(d for d in deps if d["package_name"] == "System.Text.Json")
        assert transitive["is_direct"] is False
        assert transitive["resolved_version"] == "8.0.0"


class TestDirectoryPackagesProps:
    def test_basic(self, parser: CSharpDependencyParser) -> None:
        content = """\
<Project>
  <PropertyGroup>
    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>
  </PropertyGroup>
  <ItemGroup>
    <PackageVersion Include="Newtonsoft.Json" Version="13.0.3" />
    <PackageVersion Include="Serilog" Version="3.1.1" />
  </ItemGroup>
</Project>
"""
        deps = parser.parse(content, "Directory.Packages.props")
        assert len(deps) == 2
        assert deps[0]["package_name"] == "Newtonsoft.Json"
        assert deps[0]["extras"]["central_package_management"] is True


class TestEdgeCases:
    def test_invalid_xml(self, parser: CSharpDependencyParser) -> None:
        assert parser.parse("<invalid", "App.csproj") == []

    def test_invalid_json(self, parser: CSharpDependencyParser) -> None:
        assert parser.parse("{bad", "packages.lock.json") == []

    def test_empty_csproj(self, parser: CSharpDependencyParser) -> None:
        content = '<Project Sdk="Microsoft.NET.Sdk"></Project>'
        assert parser.parse(content, "App.csproj") == []
