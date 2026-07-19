"""PHP / Composer dependency parser.

Handles:
- composer.json  (manifest — direct require / require-dev)
- composer.lock  (lockfile — resolved packages + packages-dev)
"""

import json
import logging
from typing import Any

from .base import BaseDependencyParser

logger = logging.getLogger(__name__)


def _is_platform_requirement(name: str) -> bool:
    """Return True for Composer platform requirements (not real packages).

    Composer treats ``php``, ``hhvm``, PHP extensions (``ext-*``), system
    libraries (``lib-*``) and runtime markers (``composer-*``) as platform
    constraints rather than installable packages.
    """
    lowered = name.lower()
    if lowered in ("php", "php-64bit", "php-ipv6", "hhvm"):
        return True
    return lowered.startswith(("ext-", "lib-", "composer-"))


class PhpDependencyParser(BaseDependencyParser):
    """Parser for Composer manifest and lockfiles."""

    @property
    def language(self) -> str:
        return "php"

    @property
    def supported_files(self) -> set[str]:
        return {"composer.json", "composer.lock"}

    def parse(self, content: str, file_path: str) -> list[dict[str, Any]]:
        basename = file_path.rsplit("/", 1)[-1]
        if basename == "composer.json":
            return self._parse_composer_json(content)
        if basename == "composer.lock":
            return self._parse_composer_lock(content)
        return []

    # ------------------------------------------------------------------
    # composer.json  (manifest)
    # ------------------------------------------------------------------

    def _parse_composer_json(self, content: str) -> list[dict[str, Any]]:
        """Parse composer.json — direct require / require-dev."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse composer.json")
            return []

        if not isinstance(data, dict):
            return []

        deps: list[dict[str, Any]] = []
        lines = self._split_lines(content)

        section_map = {
            "require": "runtime",
            "require-dev": "dev",
        }
        for section, dep_type in section_map.items():
            section_data = data.get(section)
            if not isinstance(section_data, dict):
                continue
            # Reset per section — sections may appear in any order in the file.
            last_line = 0
            for name, version in section_data.items():
                if _is_platform_requirement(name):
                    continue
                line = self._find_line(lines, f'"{name}"', last_line)
                if line is not None:
                    last_line = line
                deps.append(
                    self._make_dep(
                        package_name=name,
                        version_spec=version if isinstance(version, str) else None,
                        dependency_type=dep_type,
                        is_direct=True,
                        source_line=line,
                    )
                )

        return deps

    # ------------------------------------------------------------------
    # composer.lock  (lockfile)
    # ------------------------------------------------------------------

    def _parse_composer_lock(self, content: str) -> list[dict[str, Any]]:
        """Parse composer.lock — resolved packages (all transitive)."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse composer.lock")
            return []

        if not isinstance(data, dict):
            return []

        deps: list[dict[str, Any]] = []

        section_map = {
            "packages": "runtime",
            "packages-dev": "dev",
        }
        for section, dep_type in section_map.items():
            packages = data.get(section)
            if not isinstance(packages, list):
                continue
            for pkg in packages:
                if not isinstance(pkg, dict):
                    continue
                name = pkg.get("name")
                if not name or _is_platform_requirement(name):
                    continue
                version = pkg.get("version")
                deps.append(
                    self._make_dep(
                        package_name=name,
                        resolved_version=version if isinstance(version, str) else None,
                        dependency_type=dep_type,
                        # Lockfile lists direct + transitive; can't distinguish.
                        is_direct=False,
                    )
                )

        return deps
