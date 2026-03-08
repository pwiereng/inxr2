"""Java dependency parser.

Handles: pom.xml, build.gradle, build.gradle.kts
No lock files — only direct dependencies (transitives require Maven/Gradle).
"""

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

from .base import BaseDependencyParser

logger = logging.getLogger(__name__)


class JavaDependencyParser(BaseDependencyParser):
    """Parser for Java/Kotlin build files."""

    @property
    def language(self) -> str:
        return "java"

    @property
    def supported_files(self) -> set[str]:
        return {"pom.xml", "build.gradle", "build.gradle.kts"}

    def parse(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Parse Java dependency file."""
        basename = file_path.rsplit("/", 1)[-1]

        if basename == "pom.xml":
            return self._parse_pom_xml(content)
        elif basename in ("build.gradle", "build.gradle.kts"):
            return self._parse_gradle(content)
        return []

    def _parse_pom_xml(self, content: str) -> list[dict[str, Any]]:
        """Parse Maven pom.xml."""
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            logger.warning("Failed to parse pom.xml")
            return []

        # Handle Maven namespace
        ns_match = re.match(r"\{(.+?)\}", root.tag)
        ns = ns_match.group(1) if ns_match else ""
        prefix = f"{{{ns}}}" if ns else ""

        deps: list[dict[str, Any]] = []

        # Collect properties for variable substitution
        properties: dict[str, str] = {}
        props_elem = root.find(f"{prefix}properties")
        if props_elem is not None:
            for prop in props_elem:
                tag = prop.tag.replace(prefix, "")
                if prop.text:
                    properties[tag] = prop.text

        # Parse <dependencies>
        deps_elem = root.find(f"{prefix}dependencies")
        if deps_elem is not None:
            for dep_elem in deps_elem.findall(f"{prefix}dependency"):
                dep = self._parse_maven_dep(dep_elem, prefix, properties)
                if dep:
                    deps.append(dep)

        # Parse <dependencyManagement><dependencies>
        mgmt = root.find(f"{prefix}dependencyManagement")
        if mgmt is not None:
            mgmt_deps = mgmt.find(f"{prefix}dependencies")
            if mgmt_deps is not None:
                for dep_elem in mgmt_deps.findall(f"{prefix}dependency"):
                    dep = self._parse_maven_dep(dep_elem, prefix, properties)
                    if dep:
                        dep["extras"] = {"managed": True}
                        deps.append(dep)

        return deps

    def _parse_maven_dep(
        self,
        elem: ET.Element,
        prefix: str,
        properties: dict[str, str],
    ) -> dict[str, Any] | None:
        """Parse a single Maven <dependency> element."""
        group_id = self._get_text(elem, f"{prefix}groupId")
        artifact_id = self._get_text(elem, f"{prefix}artifactId")
        version = self._get_text(elem, f"{prefix}version")
        scope = self._get_text(elem, f"{prefix}scope")

        if not group_id or not artifact_id:
            return None

        # Resolve property references like ${project.version}
        if version:
            version = self._resolve_properties(version, properties)

        # Map Maven scope to dependency type
        scope_map = {
            "compile": "runtime",
            "runtime": "runtime",
            "provided": "runtime",
            "test": "dev",
            "system": "runtime",
            "import": "build",
        }
        dep_type = scope_map.get(scope or "compile", "runtime")

        package_name = f"{group_id}:{artifact_id}"

        return self._make_dep(
            package_name=package_name,
            version_spec=version,
            dependency_type=dep_type,
            extras={"group_id": group_id, "artifact_id": artifact_id},
        )

    def _parse_gradle(self, content: str) -> list[dict[str, Any]]:
        """Parse build.gradle or build.gradle.kts using regex.

        Gradle files are Groovy/Kotlin scripts, so we use pattern matching
        rather than full parsing. Handles common dependency declaration patterns.
        """
        deps: list[dict[str, Any]] = []

        # Configuration to dependency type mapping
        config_map = {
            "implementation": "runtime",
            "api": "runtime",
            "compileOnly": "runtime",
            "runtimeOnly": "runtime",
            "testImplementation": "dev",
            "testRuntimeOnly": "dev",
            "testCompileOnly": "dev",
            "annotationProcessor": "build",
            "kapt": "build",
        }

        # Pattern: configuration("group:artifact:version")
        # Also handles: configuration 'group:artifact:version'
        # And: configuration("group:artifact") without version
        dep_pattern = re.compile(
            r"(?P<config>"
            + "|".join(re.escape(c) for c in config_map)
            + r")"
            + r"[\s(]+[\"']"
            + r"(?P<group>[^:\"']+):(?P<artifact>[^:\"']+)"
            + r"(?::(?P<version>[^\"']+))?"
            + r"[\"']"
        )

        for match in dep_pattern.finditer(content):
            config = match.group("config")
            group = match.group("group")
            artifact = match.group("artifact")
            version = match.group("version")

            dep_type = config_map.get(config, "runtime")
            package_name = f"{group}:{artifact}"

            deps.append(
                self._make_dep(
                    package_name=package_name,
                    version_spec=version,
                    dependency_type=dep_type,
                    extras={"group_id": group, "artifact_id": artifact},
                )
            )

        return deps

    @staticmethod
    def _get_text(elem: ET.Element, tag: str) -> str | None:
        """Get text content of a child element."""
        child = elem.find(tag)
        return child.text.strip() if child is not None and child.text else None

    @staticmethod
    def _resolve_properties(text: str, properties: dict[str, str]) -> str:
        """Resolve Maven property references like ${property.name}."""

        def replacer(m: re.Match[str]) -> str:
            prop_name = m.group(1)
            return properties.get(prop_name, m.group(0))

        return re.sub(r"\$\{([^}]+)\}", replacer, text)
