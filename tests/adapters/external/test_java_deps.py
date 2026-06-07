"""Tests for Java dependency parser."""

import pytest

from inxr2.adapters.external.dependency_parsers.java_deps import JavaDependencyParser


@pytest.fixture
def parser() -> JavaDependencyParser:
    return JavaDependencyParser()


class TestSupportsFile:
    def test_supported(self, parser: JavaDependencyParser) -> None:
        assert parser.supports_file("pom.xml")
        assert parser.supports_file("build.gradle")
        assert parser.supports_file("build.gradle.kts")

    def test_unsupported(self, parser: JavaDependencyParser) -> None:
        assert not parser.supports_file("settings.gradle")
        assert not parser.supports_file("package.json")


class TestPomXml:
    def test_basic_dependencies(self, parser: JavaDependencyParser) -> None:
        content = """\
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter</artifactId>
            <version>3.2.0</version>
        </dependency>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
"""
        deps = parser.parse(content, "pom.xml")
        assert len(deps) == 2

        spring = deps[0]
        assert spring["package_name"] == "org.springframework.boot:spring-boot-starter"
        assert spring["version_spec"] == "3.2.0"
        assert spring["dependency_type"] == "runtime"
        assert spring["language"] == "java"

        junit = deps[1]
        assert junit["package_name"] == "junit:junit"
        assert junit["dependency_type"] == "dev"

    def test_property_resolution(self, parser: JavaDependencyParser) -> None:
        content = """\
<project>
    <properties>
        <spring.version>3.2.0</spring.version>
    </properties>
    <dependencies>
        <dependency>
            <groupId>org.springframework</groupId>
            <artifactId>spring-core</artifactId>
            <version>${spring.version}</version>
        </dependency>
    </dependencies>
</project>
"""
        deps = parser.parse(content, "pom.xml")
        assert len(deps) == 1
        assert deps[0]["version_spec"] == "3.2.0"

    def test_dependency_management(self, parser: JavaDependencyParser) -> None:
        content = """\
<project>
    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>com.google.guava</groupId>
                <artifactId>guava</artifactId>
                <version>32.1.3-jre</version>
            </dependency>
        </dependencies>
    </dependencyManagement>
</project>
"""
        deps = parser.parse(content, "pom.xml")
        assert len(deps) == 1
        assert deps[0]["extras"]["managed"] is True

    def test_no_namespace(self, parser: JavaDependencyParser) -> None:
        content = """\
<project>
    <dependencies>
        <dependency>
            <groupId>com.example</groupId>
            <artifactId>mylib</artifactId>
            <version>1.0</version>
        </dependency>
    </dependencies>
</project>
"""
        deps = parser.parse(content, "pom.xml")
        assert len(deps) == 1
        assert deps[0]["package_name"] == "com.example:mylib"


class TestGradle:
    def test_implementation(self, parser: JavaDependencyParser) -> None:
        content = """\
dependencies {
    implementation("org.springframework.boot:spring-boot-starter:3.2.0")
    testImplementation("junit:junit:4.13.2")
    api("com.google.guava:guava:32.1.3-jre")
}
"""
        deps = parser.parse(content, "build.gradle")
        assert len(deps) == 3

        spring = next(
            d
            for d in deps
            if d["package_name"] == "org.springframework.boot:spring-boot-starter"
        )
        assert spring["version_spec"] == "3.2.0"
        assert spring["dependency_type"] == "runtime"

        junit = next(d for d in deps if d["package_name"] == "junit:junit")
        assert junit["dependency_type"] == "dev"

    def test_groovy_single_quotes(self, parser: JavaDependencyParser) -> None:
        content = """\
dependencies {
    implementation 'com.google.guava:guava:32.1.3-jre'
}
"""
        deps = parser.parse(content, "build.gradle")
        assert len(deps) == 1
        assert deps[0]["package_name"] == "com.google.guava:guava"

    def test_no_version(self, parser: JavaDependencyParser) -> None:
        content = """\
dependencies {
    implementation("org.springframework.boot:spring-boot-starter")
}
"""
        deps = parser.parse(content, "build.gradle")
        assert len(deps) == 1
        assert deps[0]["version_spec"] is None

    def test_kotlin_dsl(self, parser: JavaDependencyParser) -> None:
        content = """\
dependencies {
    implementation("io.ktor:ktor-server-core:2.3.7")
    testImplementation("io.ktor:ktor-server-tests:2.3.7")
}
"""
        deps = parser.parse(content, "build.gradle.kts")
        assert len(deps) == 2


class TestEdgeCases:
    def test_invalid_xml(self, parser: JavaDependencyParser) -> None:
        assert parser.parse("<invalid xml", "pom.xml") == []

    def test_empty(self, parser: JavaDependencyParser) -> None:
        assert parser.parse("", "build.gradle") == []


class TestBranchCoverageEdgeCases:
    """Edge-case branch coverage for the Java dependency parser."""

    def test_parse_unknown_basename(self, parser: JavaDependencyParser) -> None:
        assert parser.parse("x", "weird.txt") == []

    def test_pom_properties_management_and_incomplete_deps(
        self, parser: JavaDependencyParser
    ) -> None:
        content = """\
<project>
  <properties>
    <spring.version>5.3.0</spring.version>
    <empty.prop></empty.prop>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-core</artifactId>
      <version>${spring.version}</version>
    </dependency>
    <dependency>
      <artifactId>missing-group</artifactId>
    </dependency>
  </dependencies>
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>com.example</groupId>
        <artifactId>bom</artifactId>
        <version>1.0.0</version>
        <scope>import</scope>
      </dependency>
      <dependency>
        <artifactId>also-incomplete</artifactId>
      </dependency>
    </dependencies>
  </dependencyManagement>
</project>
"""
        deps = parser.parse(content, "pom.xml")
        by_name = {d["package_name"]: d for d in deps}
        # property ${spring.version} resolved
        assert by_name["org.springframework:spring-core"]["version_spec"] == "5.3.0"
        # dependency missing groupId is skipped
        assert "missing-group" not in str(by_name)
        # managed dependency with import scope marked managed
        assert by_name["com.example:bom"]["extras"]["managed"] is True
