"""Go dependency parser.

Handles: go.mod
"""

import logging
import re
from typing import Any

from .base import BaseDependencyParser

logger = logging.getLogger(__name__)

# Matches a require line: module/path v1.2.3 [// indirect]
_REQUIRE_RE = re.compile(
    r"^\s*(?P<module>\S+)\s+(?P<version>v\S+)" r"(?:\s*//\s*(?P<comment>.*))?$"
)


class GoDependencyParser(BaseDependencyParser):
    """Parser for Go dependency files."""

    @property
    def language(self) -> str:
        return "go"

    @property
    def supported_files(self) -> set[str]:
        return {"go.mod"}

    def parse(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Parse go.mod file."""
        return self._parse_go_mod(content)

    def _parse_go_mod(self, content: str) -> list[dict[str, Any]]:
        """Parse go.mod require directives."""
        deps: list[dict[str, Any]] = []
        in_require_block = False

        for line_num, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()

            # Handle require block boundaries
            if stripped.startswith("require ("):
                in_require_block = True
                continue
            if in_require_block and stripped == ")":
                in_require_block = False
                continue

            # Single-line require: require github.com/foo/bar v1.0.0
            if stripped.startswith("require "):
                dep_line = stripped[len("require ") :]
                dep = self._parse_require_line(dep_line, line_num)
                if dep:
                    deps.append(dep)
                continue

            # Lines inside a require block
            if in_require_block:
                dep = self._parse_require_line(stripped, line_num)
                if dep:
                    deps.append(dep)

        return deps

    def _parse_require_line(
        self, line: str, source_line: int | None = None
    ) -> dict[str, Any] | None:
        """Parse a single require line."""
        match = _REQUIRE_RE.match(line)
        if not match:
            return None

        module = match.group("module")
        version = match.group("version")
        comment = match.group("comment") or ""
        is_indirect = "indirect" in comment

        return self._make_dep(
            package_name=module,
            version_spec=version,
            dependency_type="runtime",
            is_direct=not is_indirect,
            source_line=source_line,
        )
