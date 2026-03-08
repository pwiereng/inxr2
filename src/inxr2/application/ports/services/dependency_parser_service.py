"""Dependency parser service port interface."""

from abc import ABC, abstractmethod
from typing import Any


class DependencyParserServicePort(ABC):
    """
    Port for dependency parsing service.

    Implementations parse manifest and lock file content to extract
    package dependency information. Each parser returns a list of
    dependency dicts that can be converted to Dependency entities.
    """

    @abstractmethod
    def supports_file(self, file_path: str) -> bool:
        """Check if the parser can handle this manifest/lock file.

        Args:
            file_path: Relative file path (e.g., 'pyproject.toml', 'frontend/package.json')

        Returns:
            True if this file is a recognized manifest/lock file
        """
        pass

    @abstractmethod
    def parse(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Parse manifest/lock file content and return dependency dicts.

        Args:
            content: File content as string
            file_path: Relative file path (for format detection)

        Returns:
            List of dependency dicts with keys:
            - package_name: str (required)
            - language: str (required, e.g., 'python', 'javascript')
            - version_spec: str | None (constraint from manifest)
            - resolved_version: str | None (exact version from lock file)
            - dependency_type: str (runtime, dev, optional, build, peer)
            - is_direct: bool (True for direct, False for transitive)
            - extras: dict | None (language-specific metadata)
        """
        pass
