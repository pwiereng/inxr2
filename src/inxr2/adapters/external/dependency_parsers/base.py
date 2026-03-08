"""Base class for language-specific dependency parsers."""

from abc import ABC, abstractmethod
from typing import Any


class BaseDependencyParser(ABC):
    """Abstract base for parsing manifest/lock files for one language ecosystem.

    Subclasses implement:
    - language: The ecosystem name (e.g., 'python', 'javascript')
    - supported_files: Set of recognized filenames
    - parse(): Extract dependencies from file content
    """

    @property
    @abstractmethod
    def language(self) -> str:
        """Language ecosystem name."""
        ...

    @property
    @abstractmethod
    def supported_files(self) -> set[str]:
        """Set of recognized manifest/lock filenames (basename only)."""
        ...

    def supports_file(self, file_path: str) -> bool:
        """Check if this parser handles the given file."""
        basename = file_path.rsplit("/", 1)[-1]
        return basename in self.supported_files

    @abstractmethod
    def parse(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Parse file content and return dependency dicts.

        Each dict must contain at minimum:
        - package_name: str
        - language: str

        Optional keys:
        - version_spec: str | None
        - resolved_version: str | None
        - dependency_type: str (default 'runtime')
        - is_direct: bool (default True)
        - extras: dict | None
        """
        ...

    def _make_dep(
        self,
        package_name: str,
        version_spec: str | None = None,
        resolved_version: str | None = None,
        dependency_type: str = "runtime",
        is_direct: bool = True,
        extras: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Helper to build a dependency dict with standard keys."""
        dep: dict[str, Any] = {
            "package_name": package_name,
            "language": self.language,
            "version_spec": version_spec,
            "resolved_version": resolved_version,
            "dependency_type": dependency_type,
            "is_direct": is_direct,
        }
        if extras:
            dep["extras"] = extras
        return dep
