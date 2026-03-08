"""C# dependency parser.

Handles: *.csproj, packages.lock.json, Directory.Packages.props
"""

import json
import logging
import xml.etree.ElementTree as ET
from typing import Any

from .base import BaseDependencyParser

logger = logging.getLogger(__name__)


class CSharpDependencyParser(BaseDependencyParser):
    """Parser for C#/.NET dependency files."""

    @property
    def language(self) -> str:
        return "csharp"

    @property
    def supported_files(self) -> set[str]:
        return {"packages.lock.json", "Directory.Packages.props"}

    def supports_file(self, file_path: str) -> bool:
        """Check if file is a C# dependency file (includes *.csproj pattern)."""
        basename = file_path.rsplit("/", 1)[-1]
        if basename in self.supported_files:
            return True
        return basename.endswith(".csproj")

    def parse(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Parse C# dependency file."""
        basename = file_path.rsplit("/", 1)[-1]

        if basename.endswith(".csproj"):
            return self._parse_csproj(content)
        elif basename == "packages.lock.json":
            return self._parse_packages_lock_json(content)
        elif basename == "Directory.Packages.props":
            return self._parse_directory_packages_props(content)
        return []

    def _parse_csproj(self, content: str) -> list[dict[str, Any]]:
        """Parse .csproj file for PackageReference items."""
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            logger.warning("Failed to parse .csproj")
            return []

        deps: list[dict[str, Any]] = []

        # Find all PackageReference elements (no namespace in SDK-style projects)
        for ref in root.iter("PackageReference"):
            name = ref.get("Include") or ref.get("Update")
            version = ref.get("Version")

            if not name:
                continue

            # Check for version as child element
            if not version:
                version_elem = ref.find("Version")
                if version_elem is not None and version_elem.text:
                    version = version_elem.text.strip()

            # Check PrivateAssets to determine if it's a dev dependency
            private_assets = ref.get("PrivateAssets", "")
            private_elem = ref.find("PrivateAssets")
            if private_elem is not None and private_elem.text:
                private_assets = private_elem.text.strip()

            dep_type = "dev" if private_assets.lower() == "all" else "runtime"

            deps.append(
                self._make_dep(
                    package_name=name,
                    version_spec=version,
                    dependency_type=dep_type,
                )
            )

        return deps

    def _parse_packages_lock_json(self, content: str) -> list[dict[str, Any]]:
        """Parse packages.lock.json (NuGet lock file)."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse packages.lock.json")
            return []

        deps: list[dict[str, Any]] = []

        # Structure: { "version": 1, "dependencies": { "net8.0": { "PackageName": { ... } } } }
        dependencies = data.get("dependencies", {})
        for _framework, framework_deps in dependencies.items():
            if not isinstance(framework_deps, dict):
                continue

            for name, info in framework_deps.items():
                if not isinstance(info, dict):
                    continue

                resolved = info.get("resolved")
                requested = info.get("requested")
                dep_type_raw = info.get("type", "Direct")

                is_direct = dep_type_raw == "Direct"
                dep_type = "runtime"  # NuGet doesn't distinguish dev in lock files

                deps.append(
                    self._make_dep(
                        package_name=name,
                        version_spec=requested,
                        resolved_version=resolved,
                        dependency_type=dep_type,
                        is_direct=is_direct,
                    )
                )

        return deps

    def _parse_directory_packages_props(self, content: str) -> list[dict[str, Any]]:
        """Parse Directory.Packages.props (central package management)."""
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            logger.warning("Failed to parse Directory.Packages.props")
            return []

        deps: list[dict[str, Any]] = []

        for ref in root.iter("PackageVersion"):
            name = ref.get("Include")
            version = ref.get("Version")

            if not name:
                continue

            deps.append(
                self._make_dep(
                    package_name=name,
                    version_spec=version,
                    extras={"central_package_management": True},
                )
            )

        return deps
