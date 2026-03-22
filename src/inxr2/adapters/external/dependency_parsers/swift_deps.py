"""Swift Package Manager dependency parser.

Handles:
- Package.resolved  (JSON lockfile — v1 and v2 formats)
- Package.swift     (manifest — regex-based extraction of .package(url:) calls)
"""

import json
import logging
import re
from typing import Any

from .base import BaseDependencyParser

logger = logging.getLogger(__name__)

# Matches: .package(url: "https://github.com/Foo/Bar.git", from: "1.0.0")
# Captures: url, version spec (from/exact/.upToNextMajor/etc.), or branch
_PACKAGE_URL_RE = re.compile(
    r'\.package\s*\(\s*url\s*:\s*"(?P<url>[^"]+)"'
    r"(?:"
    r'\s*,\s*from\s*:\s*"(?P<from_ver>[^"]+)"'
    r"|"
    r'\s*,\s*exact\s*:\s*"(?P<exact_ver>[^"]+)"'
    r"|"
    r'\s*,\s*(?:\.upToNextMajor|\.upToNextMinor)\s*\(from\s*:\s*"(?P<range_ver>[^"]+)"\)'
    r"|"
    r'\s*,\s*branch\s*:\s*"(?P<branch>[^"]+)"'
    r"|"
    r'\s*,\s*revision\s*:\s*"(?P<revision>[^"]+)"'
    r"|"
    r'\s*,\s*"(?P<bare_ver>[^"]+)"\s*\.\.\.'
    r")?",
)


def _package_name_from_url(url: str) -> str:
    """Extract a human-readable package name from a git URL.

    E.g. https://github.com/Alamofire/Alamofire.git -> Alamofire
    """
    # Strip trailing .git and take the last path segment
    path = url.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return path.rsplit("/", 1)[-1]


class SwiftDependencyParser(BaseDependencyParser):
    """Parser for Swift Package Manager manifest and lockfiles."""

    @property
    def language(self) -> str:
        return "swift"

    @property
    def supported_files(self) -> set[str]:
        return {"Package.resolved", "Package.swift"}

    def parse(self, content: str, file_path: str) -> list[dict[str, Any]]:
        basename = file_path.rsplit("/", 1)[-1]
        if basename == "Package.resolved":
            return self._parse_package_resolved(content)
        if basename == "Package.swift":
            return self._parse_package_swift(content)
        return []

    # ------------------------------------------------------------------
    # Package.resolved  (JSON lockfile)
    # ------------------------------------------------------------------

    def _parse_package_resolved(self, content: str) -> list[dict[str, Any]]:
        """Parse Package.resolved JSON (supports v1 and v2 schema)."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse Package.resolved: %s", e)
            return []

        version = data.get("version", 1)

        if version == 2:
            return self._parse_resolved_v2(data)
        # v1 (and fallback)
        return self._parse_resolved_v1(data)

    def _parse_resolved_v1(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse Package.resolved format version 1."""
        deps: list[dict[str, Any]] = []
        pins = data.get("object", {}).get("pins", [])
        for pin in pins:
            url = pin.get("repositoryURL", "")
            name = pin.get("package") or _package_name_from_url(url)
            state = pin.get("state", {})
            resolved_version = (
                state.get("version") or state.get("branch") or state.get("revision")
            )
            deps.append(
                self._make_dep(
                    package_name=name,
                    resolved_version=resolved_version,
                    is_direct=False,  # lockfile = all (direct + transitive)
                    extras={"url": url} if url else None,
                )
            )
        return deps

    def _parse_resolved_v2(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse Package.resolved format version 2."""
        deps: list[dict[str, Any]] = []
        pins = data.get("pins", [])
        for pin in pins:
            url = pin.get("location", "")
            name = pin.get("identity") or _package_name_from_url(url)
            state = pin.get("state", {})
            resolved_version = (
                state.get("version") or state.get("branch") or state.get("revision")
            )
            deps.append(
                self._make_dep(
                    package_name=name,
                    resolved_version=resolved_version,
                    is_direct=False,
                    extras={"url": url} if url else None,
                )
            )
        return deps

    # ------------------------------------------------------------------
    # Package.swift  (manifest — regex extraction)
    # ------------------------------------------------------------------

    def _parse_package_swift(self, content: str) -> list[dict[str, Any]]:
        """Extract dependencies from Package.swift using regex."""
        deps: list[dict[str, Any]] = []
        lines = self._split_lines(content)

        for m in _PACKAGE_URL_RE.finditer(content):
            url = m.group("url") or ""
            if not url:
                continue

            name = _package_name_from_url(url)

            version_spec = (
                m.group("from_ver")
                or m.group("exact_ver")
                or m.group("range_ver")
                or m.group("bare_ver")
            )
            branch = m.group("branch")
            revision = m.group("revision")

            # Build a version spec string
            spec: str | None = None
            if version_spec:
                spec = f">= {version_spec}"
            elif branch:
                spec = f"branch: {branch}"
            elif revision:
                spec = f"revision: {revision}"

            source_line = self._find_line(lines, url)

            deps.append(
                self._make_dep(
                    package_name=name,
                    version_spec=spec,
                    is_direct=True,
                    source_line=source_line,
                    extras={"url": url},
                )
            )

        return deps
