"""Ruby dependency parser.

Handles: Gemfile, Gemfile.lock
"""

import logging
import re
from typing import Any

from .base import BaseDependencyParser

logger = logging.getLogger(__name__)

# Gemfile: gem 'name', '~> 1.0' (captures first version constraint only)
_GEMFILE_RE = re.compile(
    r"^\s*gem\s+['\"](?P<name>[^'\"]+)['\"]"
    r"(?:\s*,\s*['\"](?P<version>[^'\"]+)['\"])?"
)

# Gemfile.lock: top-level gem with version (4-space indent under specs:)
_LOCKFILE_GEM_RE = re.compile(
    r"^    (?P<name>[a-zA-Z0-9][-a-zA-Z0-9_.]*)\s+\((?P<version>[^)]+)\)$"
)

# Gemfile.lock: transitive dep (6-space indent)
_LOCKFILE_TRANSITIVE_RE = re.compile(
    r"^      (?P<name>[a-zA-Z0-9][-a-zA-Z0-9_.]*)" r"(?:\s+\((?P<version>[^)]+)\))?$"
)


class RubyDependencyParser(BaseDependencyParser):
    """Parser for Ruby dependency files."""

    @property
    def language(self) -> str:
        return "ruby"

    @property
    def supported_files(self) -> set[str]:
        return {"Gemfile", "Gemfile.lock"}

    def parse(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Parse Ruby dependency file."""
        basename = file_path.rsplit("/", 1)[-1]

        if basename == "Gemfile":
            return self._parse_gemfile(content)
        elif basename == "Gemfile.lock":
            return self._parse_gemfile_lock(content)
        return []

    def _parse_gemfile(self, content: str) -> list[dict[str, Any]]:
        """Parse Gemfile gem declarations."""
        deps: list[dict[str, Any]] = []
        group_stack: list[list[str]] = []

        for line in content.splitlines():
            stripped = line.strip()

            # Track group blocks as a proper stack for nesting
            if stripped.startswith("group "):
                # Extract group names: group :development, :test do
                groups = re.findall(r":(\w+)", stripped)
                group_stack.append(groups)
                continue
            if stripped == "end" and group_stack:
                group_stack.pop()
                continue

            match = _GEMFILE_RE.match(line)
            if not match:
                continue

            name = match.group("name")
            version = match.group("version")

            dep_type = "runtime"
            all_groups = [g for groups in group_stack for g in groups]
            if all_groups:
                if any(g in ("development", "test") for g in all_groups):
                    dep_type = "dev"

            deps.append(
                self._make_dep(
                    package_name=name,
                    version_spec=version,
                    dependency_type=dep_type,
                    is_direct=True,
                )
            )

        return deps

    def _parse_gemfile_lock(self, content: str) -> list[dict[str, Any]]:
        """Parse Gemfile.lock resolved dependencies."""
        deps: list[dict[str, Any]] = []
        in_gem_specs = False
        current_parent: str | None = None

        for line in content.splitlines():
            # Detect the GEM > specs: section
            if line == "  specs:":
                in_gem_specs = True
                continue

            # Leave GEM specs section on any non-indented or differently-indented line
            if in_gem_specs and line and not line.startswith("    "):
                in_gem_specs = False
                current_parent = None
                continue

            if not in_gem_specs:
                continue

            # Top-level gem (4-space indent)
            gem_match = _LOCKFILE_GEM_RE.match(line)
            if gem_match:
                name = gem_match.group("name")
                version = gem_match.group("version")
                current_parent = name
                deps.append(
                    self._make_dep(
                        package_name=name,
                        resolved_version=version,
                        dependency_type="runtime",
                        is_direct=False,
                    )
                )
                continue

            # Transitive dep (6-space indent)
            trans_match = _LOCKFILE_TRANSITIVE_RE.match(line)
            if trans_match:
                name = trans_match.group("name")
                version = trans_match.group("version")
                deps.append(
                    self._make_dep(
                        package_name=name,
                        version_spec=version,
                        dependency_type="runtime",
                        is_direct=False,
                        extras={"parent": current_parent} if current_parent else None,
                    )
                )

        return deps
