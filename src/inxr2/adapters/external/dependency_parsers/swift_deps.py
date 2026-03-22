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
    r'\s*,\s*\.upToNextMajor\s*\(from\s*:\s*"(?P<major_ver>[^"]+)"\)'
    r"|"
    r'\s*,\s*\.upToNextMinor\s*\(from\s*:\s*"(?P<minor_ver>[^"]+)"\)'
    r"|"
    r'\s*,\s*branch\s*:\s*"(?P<branch>[^"]+)"'
    r"|"
    r'\s*,\s*revision\s*:\s*"(?P<revision>[^"]+)"'
    r"|"
    # Half-open range: "1.0.0" ..< "2.0.0"  →  >= 1.0.0, < 2.0.0
    r'\s*,\s*"(?P<excl_low>[^"]+)"\s*\.\.<\s*"(?P<excl_high>[^"]+)"'
    r"|"
    # Closed range:     "1.0.0" ... "2.0.0"  →  >= 1.0.0, <= 2.0.0
    r'\s*,\s*"(?P<incl_low>[^"]+)"\s*\.\.\.\s*"(?P<incl_high>[^"]+)"'
    r")?",
)


# Strip Swift block comments (non-nested) and line comments.
# Applied before regex matching to avoid treating commented-out
# .package(url:) calls as real dependencies.
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
# Negative lookbehind for ':' so that '://' inside URLs is not treated as a
# line-comment marker (e.g. 'https://github.com/...' must not be stripped).
_LINE_COMMENT_RE = re.compile(r"(?<!:)//[^\n]*")


def _strip_swift_comments(content: str) -> str:
    """Remove // and /* */ comments from Swift source.

    Preserves newlines inside block comments so that line numbers in the
    original text remain valid for source_line lookups.
    Note: does not handle nested block comments (rare in Package.swift).
    """

    # Replace block comments, preserving newlines inside them
    def _blank_block(m: re.Match[str]) -> str:
        return "\n" * m.group(0).count("\n")

    stripped = _BLOCK_COMMENT_RE.sub(_blank_block, content)
    # Replace line comments, preserving the trailing newline
    stripped = _LINE_COMMENT_RE.sub("", stripped)
    return stripped


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
        # Keep original lines for source_line lookups (line numbers must
        # refer to the unmodified file).
        lines = self._split_lines(content)
        # Strip comments so commented-out .package(url:) calls are ignored.
        stripped = _strip_swift_comments(content)

        for m in _PACKAGE_URL_RE.finditer(stripped):
            url = m.group("url") or ""
            if not url:
                continue

            name = _package_name_from_url(url)

            from_ver = m.group("from_ver")
            exact_ver = m.group("exact_ver")
            major_ver = m.group("major_ver")
            minor_ver = m.group("minor_ver")
            excl_low = m.group("excl_low")
            excl_high = m.group("excl_high")
            incl_low = m.group("incl_low")
            incl_high = m.group("incl_high")
            branch = m.group("branch")
            revision = m.group("revision")

            # Build a version spec string preserving SwiftPM constraint semantics.
            spec: str | None = None
            if from_ver:
                spec = f">= {from_ver}"
            elif exact_ver:
                spec = f"== {exact_ver}"
            elif major_ver:
                try:
                    major = int(major_ver.split(".")[0])
                    upper = f"{major + 1}.0.0"
                    spec = f">= {major_ver}, < {upper}"
                except (ValueError, IndexError):
                    spec = f">= {major_ver}"
            elif minor_ver:
                try:
                    parts = minor_ver.split(".")
                    minor = int(parts[1]) if len(parts) > 1 else 0
                    upper = f"{parts[0]}.{minor + 1}.0"
                    spec = f">= {minor_ver}, < {upper}"
                except (ValueError, IndexError):
                    spec = f">= {minor_ver}"
            elif excl_low:
                # Half-open range: "1.0.0" ..< "2.0.0"
                spec = f">= {excl_low}, < {excl_high}"
            elif incl_low:
                # Closed range: "1.0.0" ... "2.0.0"
                spec = f">= {incl_low}, <= {incl_high}"
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
