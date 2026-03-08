"""Dependency entity - represents a package dependency from a manifest file."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Dependency:
    """
    A package dependency extracted from a manifest or lock file.

    Domain entity (framework-agnostic). Separate from SQLAlchemy ORM model.
    Dependencies belong to a file version (content-addressable); commit context
    is provided through the commit_files junction table.

    Attributes:
        file_id: File version (manifest/lock file) containing this dependency
        repository_id: Repository containing this dependency
        package_name: Package/library name (e.g., 'fastapi', 'react')
        language: Programming language ecosystem (e.g., 'python', 'javascript')
        id: Database ID (None for new entities)
        version_spec: Version constraint from manifest (e.g., '^2.5.0', '>=1.0')
        resolved_version: Exact version from lock file (e.g., '2.5.3')
        dependency_type: Category (e.g., 'runtime', 'dev', 'optional', 'build')
        is_direct: True for direct dependencies, False for transitives
        parent_dependency_id: Parent dep ID for transitive dependency tree
        extras: Language-specific metadata (JSONB)
        indexed_at: When dependency was indexed
    """

    file_id: int
    repository_id: int
    package_name: str
    language: str
    id: int | None = None
    version_spec: str | None = None
    resolved_version: str | None = None
    dependency_type: str = "runtime"
    is_direct: bool = True
    parent_dependency_id: int | None = None
    extras: dict[str, Any] | None = None
    indexed_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate dependency entity."""
        if not self.package_name:
            raise ValueError("Package name cannot be empty")
        if not self.language:
            raise ValueError("Language cannot be empty")
        if self.dependency_type not in ("runtime", "dev", "optional", "build", "peer"):
            raise ValueError(
                f"Invalid dependency type: {self.dependency_type}. "
                "Must be one of: runtime, dev, optional, build, peer"
            )
