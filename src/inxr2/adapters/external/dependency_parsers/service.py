"""Dependency parser service — dispatches to per-language parsers."""

import logging

from ....application.ports.services import DependencyParserServicePort, ParsedDependency
from .base import BaseDependencyParser
from .csharp_deps import CSharpDependencyParser
from .go_deps import GoDependencyParser
from .java_deps import JavaDependencyParser
from .javascript_deps import JavaScriptDependencyParser
from .python_deps import PythonDependencyParser
from .ruby_deps import RubyDependencyParser

logger = logging.getLogger(__name__)


class DependencyParserService(DependencyParserServicePort):
    """Dispatches dependency parsing to the appropriate language-specific parser.

    Lazily initializes parsers on first use.
    """

    def __init__(self) -> None:
        self._parsers: list[BaseDependencyParser] | None = None

    def _ensure_initialized(self) -> list[BaseDependencyParser]:
        """Lazy-initialize all language parsers."""
        if self._parsers is None:
            self._parsers = [
                PythonDependencyParser(),
                JavaScriptDependencyParser(),
                JavaDependencyParser(),
                CSharpDependencyParser(),
                GoDependencyParser(),
                RubyDependencyParser(),
            ]
        return self._parsers

    def supports_file(self, file_path: str) -> bool:
        """Check if any parser handles this file."""
        parsers = self._ensure_initialized()
        return any(p.supports_file(file_path) for p in parsers)

    def parse(self, content: str, file_path: str) -> list[ParsedDependency]:
        """Parse a manifest/lock file, delegating to the appropriate parser."""
        parsers = self._ensure_initialized()

        for parser in parsers:
            if parser.supports_file(file_path):
                try:
                    raw_deps = parser.parse(content, file_path)
                    return [
                        ParsedDependency(
                            package_name=d["package_name"],
                            language=d["language"],
                            version_spec=d.get("version_spec"),
                            resolved_version=d.get("resolved_version"),
                            dependency_type=d.get("dependency_type", "runtime"),
                            is_direct=d.get("is_direct", True),
                            extras=d.get("extras"),
                            source_line=d.get("source_line"),
                        )
                        for d in raw_deps
                    ]
                except Exception:
                    logger.exception(
                        "Failed to parse dependency file %s with %s",
                        file_path,
                        parser.__class__.__name__,
                    )
                    return []

        return []
