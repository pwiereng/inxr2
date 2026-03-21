"""Dependency parser service port interface and typed return structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedDependency:
    """A package dependency extracted from a manifest or lock file."""

    package_name: str
    language: str
    version_spec: str | None = None
    resolved_version: str | None = None
    dependency_type: str = "runtime"
    is_direct: bool = True
    extras: dict[str, Any] | None = None
    source_line: int | None = None


class DependencyParserServicePort(ABC):
    """
    Port for dependency parsing service.

    Implementations parse manifest and lock file content to extract
    package dependency information.
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
    def parse(self, content: str, file_path: str) -> list[ParsedDependency]:
        """Parse manifest/lock file content and return dependencies.

        Args:
            content: File content as string
            file_path: Relative file path (for format detection)

        Returns:
            List of ParsedDependency with package_name, language, version_spec,
            resolved_version, dependency_type, is_direct, extras, source_line
        """
        pass
