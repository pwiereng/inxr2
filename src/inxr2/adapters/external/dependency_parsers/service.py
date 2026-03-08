"""Dependency parser service — dispatches to per-language parsers."""

import logging
from typing import Any

from ....application.ports.services import DependencyParserServicePort
from .base import BaseDependencyParser
from .csharp_deps import CSharpDependencyParser
from .java_deps import JavaDependencyParser
from .javascript_deps import JavaScriptDependencyParser
from .python_deps import PythonDependencyParser

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
            ]
        return self._parsers

    def supports_file(self, file_path: str) -> bool:
        """Check if any parser handles this file."""
        parsers = self._ensure_initialized()
        return any(p.supports_file(file_path) for p in parsers)

    def parse(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Parse a manifest/lock file, delegating to the appropriate parser."""
        parsers = self._ensure_initialized()

        for parser in parsers:
            if parser.supports_file(file_path):
                try:
                    return parser.parse(content, file_path)
                except Exception:
                    logger.exception(
                        "Failed to parse dependency file %s with %s",
                        file_path,
                        parser.__class__.__name__,
                    )
                    return []

        return []
