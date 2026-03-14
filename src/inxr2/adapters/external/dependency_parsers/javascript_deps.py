"""JavaScript/TypeScript dependency parser.

Handles: package.json, package-lock.json, yarn.lock, pnpm-lock.yaml
"""

import json
import logging
import re
from typing import Any

from .base import BaseDependencyParser

logger = logging.getLogger(__name__)


class JavaScriptDependencyParser(BaseDependencyParser):
    """Parser for JavaScript/TypeScript dependency files."""

    @property
    def language(self) -> str:
        return "javascript"

    @property
    def supported_files(self) -> set[str]:
        return {
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
        }

    def parse(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Parse JS/TS dependency file."""
        basename = file_path.rsplit("/", 1)[-1]

        if basename == "package.json":
            return self._parse_package_json(content)
        elif basename == "package-lock.json":
            return self._parse_package_lock_json(content)
        elif basename == "yarn.lock":
            return self._parse_yarn_lock(content)
        elif basename == "pnpm-lock.yaml":
            return self._parse_pnpm_lock(content)
        return []

    def _parse_package_json(self, content: str) -> list[dict[str, Any]]:
        """Parse package.json — direct dependencies only."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse package.json")
            return []

        deps: list[dict[str, Any]] = []

        section_map = {
            "dependencies": "runtime",
            "devDependencies": "dev",
            "peerDependencies": "peer",
            "optionalDependencies": "optional",
        }

        last_line = 0
        for section, dep_type in section_map.items():
            for name, version in (data.get(section) or {}).items():
                line = self._find_line(content, f'"{name}"', last_line)
                if line is not None:
                    last_line = line
                deps.append(
                    self._make_dep(
                        package_name=name,
                        version_spec=version,
                        dependency_type=dep_type,
                        source_line=line,
                    )
                )

        return deps

    def _parse_package_lock_json(self, content: str) -> list[dict[str, Any]]:
        """Parse package-lock.json (v2/v3 format with packages)."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse package-lock.json")
            return []

        deps: list[dict[str, Any]] = []
        packages = data.get("packages") or {}

        for pkg_path, info in packages.items():
            # Skip root package (empty key)
            if not pkg_path:
                continue

            # Extract package name from path: "node_modules/react" -> "react"
            # Also handles scoped: "node_modules/@scope/pkg" -> "@scope/pkg"
            name = pkg_path
            if "node_modules/" in name:
                name = name.rsplit("node_modules/", 1)[-1]

            version = info.get("version", "")
            is_dev = info.get("dev", False)
            is_optional = info.get("optional", False)
            is_peer = info.get("peer", False)

            if is_dev:
                dep_type = "dev"
            elif is_peer:
                dep_type = "peer"
            elif is_optional:
                dep_type = "optional"
            else:
                dep_type = "runtime"

            # In lock files, dependencies are generally transitive
            # unless they appear at the top level node_modules
            is_direct = pkg_path.count("node_modules/") == 1

            deps.append(
                self._make_dep(
                    package_name=name,
                    resolved_version=version,
                    dependency_type=dep_type,
                    is_direct=is_direct,
                    source_line=self._find_line(content, f'"{pkg_path}"'),
                )
            )

        # Fallback: v1 format with "dependencies" key
        if not packages and "dependencies" in data:
            deps.extend(
                self._parse_lock_v1_deps(
                    data["dependencies"], is_direct=True, content=content
                )
            )

        return deps

    def _parse_lock_v1_deps(
        self,
        dependencies: dict[str, Any],
        is_direct: bool,
        content: str = "",
    ) -> list[dict[str, Any]]:
        """Recursively parse v1 package-lock.json dependencies."""
        deps: list[dict[str, Any]] = []

        for name, info in dependencies.items():
            version = info.get("version", "")
            is_dev = info.get("dev", False)
            dep_type = "dev" if is_dev else "runtime"

            deps.append(
                self._make_dep(
                    package_name=name,
                    resolved_version=version,
                    dependency_type=dep_type,
                    is_direct=is_direct,
                    source_line=(
                        self._find_line(content, f'"{name}"') if content else None
                    ),
                )
            )

            # Nested dependencies (transitive)
            nested = info.get("dependencies", {})
            if nested:
                deps.extend(
                    self._parse_lock_v1_deps(nested, is_direct=False, content=content)
                )

        return deps

    def _parse_yarn_lock(self, content: str) -> list[dict[str, Any]]:
        """Parse yarn.lock (custom format).

        Yarn.lock entries look like:
          package-name@^1.0.0:
            version "1.0.5"
            resolved "..."
            dependencies:
              other-package "^2.0.0"

        Or in yarn berry (v2+):
          "package-name@npm:^1.0.0":
            version: 1.0.5
        """
        deps: list[dict[str, Any]] = []
        current_name: str | None = None
        current_version: str | None = None
        current_line: int | None = None

        for line_num, line in enumerate(content.splitlines(), 1):
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # New entry: "name@version:" or name@version:
            if not line.startswith(" ") and not line.startswith("\t"):
                # Save previous entry
                if current_name and current_version:
                    deps.append(
                        self._make_dep(
                            package_name=current_name,
                            resolved_version=current_version,
                            is_direct=False,
                            source_line=current_line,
                        )
                    )

                current_name = None
                current_version = None
                current_line = None

                # Parse entry header
                header = line.rstrip(":")
                # Remove quotes
                header = header.strip('"')
                # Extract name: "name@^1.0.0, name@~1.0.0" -> name
                # Handle scoped packages: "@scope/name@^1.0.0"
                match = re.match(r"^(@?[^@]+)@", header)
                if match:
                    current_name = match.group(1)
                    current_line = line_num
                    # Remove "npm:" prefix from berry format
                    if current_name.endswith(", "):
                        current_name = current_name.rstrip(", ")
                continue

            stripped = line.strip()

            # Version line
            if stripped.startswith("version"):
                # version "1.0.5" or version: 1.0.5
                version_match = re.search(r'"([^"]+)"', stripped)
                if version_match:
                    current_version = version_match.group(1)
                elif ":" in stripped:
                    current_version = stripped.split(":", 1)[1].strip()

        # Don't forget the last entry
        if current_name and current_version:
            deps.append(
                self._make_dep(
                    package_name=current_name,
                    resolved_version=current_version,
                    is_direct=False,
                    source_line=current_line,
                )
            )

        return deps

    def _parse_pnpm_lock(self, content: str) -> list[dict[str, Any]]:
        """Parse pnpm-lock.yaml."""
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML not available, cannot parse pnpm-lock.yaml")
            return []

        try:
            data = yaml.safe_load(content)
        except Exception:
            logger.warning("Failed to parse pnpm-lock.yaml")
            return []

        if not isinstance(data, dict):
            return []

        deps: list[dict[str, Any]] = []

        # pnpm v6+ format: packages key
        packages = data.get("packages") or {}
        for pkg_key, info in packages.items():
            if not isinstance(info, dict):
                continue

            # Parse key: "/react@18.2.0" or "/@scope/pkg@1.0.0"
            match = re.match(r"^/?(@?[^@]+)@(.+)$", pkg_key)
            if not match:
                continue

            name = match.group(1)
            version = match.group(2)
            is_dev = info.get("dev", False)
            is_optional = info.get("optional", False)

            dep_type = "dev" if is_dev else "optional" if is_optional else "runtime"

            deps.append(
                self._make_dep(
                    package_name=name,
                    resolved_version=version,
                    dependency_type=dep_type,
                    is_direct=False,
                    source_line=self._find_line(content, pkg_key),
                )
            )

        return deps
