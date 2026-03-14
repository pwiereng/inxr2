"""Python dependency parser.

Handles: pyproject.toml, requirements.txt, poetry.lock, Pipfile.lock
"""

import json
import logging
import re
from typing import Any

from .base import BaseDependencyParser

logger = logging.getLogger(__name__)

# PEP 508 dependency specifier pattern
# Matches: package_name[extra1,extra2] (>=1.0,<2.0); python_version >= "3.8"
_PEP508_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][-A-Za-z0-9_.]*)"
    r"(?:\[(?P<extras>[^\]]+)\])?"
    r"\s*(?P<version>[^;#]*?)?"
    r"\s*(?:;(?P<markers>.*))?$"
)


class PythonDependencyParser(BaseDependencyParser):
    """Parser for Python dependency files."""

    @property
    def language(self) -> str:
        return "python"

    @property
    def supported_files(self) -> set[str]:
        return {
            "pyproject.toml",
            "requirements.txt",
            "requirements-dev.txt",
            "requirements_dev.txt",
            "dev-requirements.txt",
            "test-requirements.txt",
            "poetry.lock",
            "Pipfile.lock",
        }

    def parse(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Parse Python dependency file."""
        basename = file_path.rsplit("/", 1)[-1]

        if basename == "pyproject.toml":
            return self._parse_pyproject_toml(content)
        elif basename.endswith("requirements.txt") or basename.startswith(
            (
                "dev-requirements",
                "test-requirements",
                "requirements_dev",
                "requirements-dev",
            )
        ):
            dep_type = "dev" if "dev" in basename or "test" in basename else "runtime"
            return self._parse_requirements_txt(content, dep_type)
        elif basename == "poetry.lock":
            return self._parse_poetry_lock(content)
        elif basename == "Pipfile.lock":
            return self._parse_pipfile_lock(content)
        return []

    def _parse_pyproject_toml(self, content: str) -> list[dict[str, Any]]:
        """Parse pyproject.toml (PEP 621 and Poetry formats)."""
        import tomllib

        try:
            data = tomllib.loads(content)
        except Exception:
            logger.warning("Failed to parse pyproject.toml")
            return []

        deps: list[dict[str, Any]] = []
        lines = self._split_lines(content)

        # PEP 621: [project.dependencies]
        project = data.get("project", {})
        for dep_str in project.get("dependencies", []):
            dep = self._parse_pep508(dep_str, "runtime")
            if dep:
                dep["source_line"] = self._find_line(lines, dep["package_name"])
                deps.append(dep)

        # PEP 621: [project.optional-dependencies]
        optional = project.get("optional-dependencies", {})
        for group_name, group_deps in optional.items():
            dep_type = "dev" if group_name in ("dev", "test", "testing") else "optional"
            for dep_str in group_deps:
                dep = self._parse_pep508(dep_str, dep_type)
                if dep:
                    dep["source_line"] = self._find_line(lines, dep["package_name"])
                    if dep_type == "optional":
                        dep.setdefault("extras", {})["group"] = group_name
                    deps.append(dep)

        # Poetry: [tool.poetry.dependencies]
        poetry = data.get("tool", {}).get("poetry", {})
        if poetry:
            for name, spec in poetry.get("dependencies", {}).items():
                if name.lower() == "python":
                    continue
                dep = self._poetry_dep(name, spec, "runtime")
                dep["source_line"] = self._find_line(lines, name)
                deps.append(dep)

            for name, spec in poetry.get("dev-dependencies", {}).items():
                dep = self._poetry_dep(name, spec, "dev")
                dep["source_line"] = self._find_line(lines, name)
                deps.append(dep)

            # Poetry groups: [tool.poetry.group.dev.dependencies]
            for group_name, group_data in poetry.get("group", {}).items():
                dep_type = (
                    "dev" if group_name in ("dev", "test", "testing") else "optional"
                )
                for name, spec in group_data.get("dependencies", {}).items():
                    dep = self._poetry_dep(name, spec, dep_type)
                    dep["source_line"] = self._find_line(lines, name)
                    deps.append(dep)

        # Build system requirements
        build_system = data.get("build-system", {})
        for dep_str in build_system.get("requires", []):
            dep = self._parse_pep508(dep_str, "build")
            if dep:
                dep["source_line"] = self._find_line(lines, dep["package_name"])
                deps.append(dep)

        return deps

    def _parse_requirements_txt(
        self, content: str, default_type: str = "runtime"
    ) -> list[dict[str, Any]]:
        """Parse requirements.txt format."""
        deps: list[dict[str, Any]] = []

        for line_num, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            # Skip comments, empty lines, options, constraints files
            if not line or line.startswith(("#", "-", "--")):
                continue
            dep = self._parse_pep508(line, default_type)
            if dep:
                dep["source_line"] = line_num
                deps.append(dep)

        return deps

    def _parse_poetry_lock(self, content: str) -> list[dict[str, Any]]:
        """Parse poetry.lock (TOML format with full transitive tree)."""
        import tomllib

        try:
            data = tomllib.loads(content)
        except Exception:
            logger.warning("Failed to parse poetry.lock")
            return []

        deps: list[dict[str, Any]] = []
        for package in data.get("package", []):
            name = package.get("name", "")
            version = package.get("version", "")
            category = package.get("category", "main")
            is_optional = package.get("optional", False)

            if category == "dev":
                dep_type = "dev"
            elif is_optional:
                dep_type = "optional"
            else:
                dep_type = "runtime"

            deps.append(
                self._make_dep(
                    package_name=name,
                    resolved_version=version,
                    dependency_type=dep_type,
                    is_direct=False,  # Lock files list all transitives
                    extras={"source": package.get("source", {}).get("type")},
                )
            )

        return deps

    def _parse_pipfile_lock(self, content: str) -> list[dict[str, Any]]:
        """Parse Pipfile.lock (JSON format)."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse Pipfile.lock")
            return []

        deps: list[dict[str, Any]] = []

        for section, dep_type in [("default", "runtime"), ("develop", "dev")]:
            for name, info in data.get(section, {}).items():
                version = info.get("version", "")
                # Pipfile.lock versions start with "==" for pinned
                resolved = version.lstrip("=") if version.startswith("==") else None
                deps.append(
                    self._make_dep(
                        package_name=name,
                        version_spec=version if not version.startswith("==") else None,
                        resolved_version=resolved,
                        dependency_type=dep_type,
                        is_direct=False,  # Lock file — all transitives included
                    )
                )

        return deps

    def _parse_pep508(self, dep_str: str, dep_type: str) -> dict[str, Any] | None:
        """Parse a PEP 508 dependency string."""
        dep_str = dep_str.strip()
        if not dep_str:
            return None

        match = _PEP508_RE.match(dep_str)
        if not match:
            logger.debug("Could not parse PEP 508 dep: %s", dep_str)
            return None

        name = match.group("name")
        version = (match.group("version") or "").strip()
        extras_str = match.group("extras")
        markers = (match.group("markers") or "").strip()

        dep = self._make_dep(
            package_name=name,
            version_spec=version or None,
            dependency_type=dep_type,
        )

        extras: dict[str, Any] = {}
        if extras_str:
            extras["extras"] = [e.strip() for e in extras_str.split(",")]
        if markers:
            extras["markers"] = markers
        if extras:
            dep["extras"] = extras

        return dep

    def _poetry_dep(self, name: str, spec: Any, dep_type: str) -> dict[str, Any]:
        """Convert a Poetry dependency spec to a dep dict."""
        if isinstance(spec, str):
            return self._make_dep(
                package_name=name,
                version_spec=spec,
                dependency_type=dep_type,
            )
        elif isinstance(spec, dict):
            version = spec.get("version")
            extras: dict[str, Any] = {}
            if spec.get("optional"):
                dep_type = "optional"
            if spec.get("extras"):
                extras["extras"] = spec["extras"]
            if spec.get("markers"):
                extras["markers"] = spec["markers"]
            if spec.get("python"):
                extras["python"] = spec["python"]
            return self._make_dep(
                package_name=name,
                version_spec=version,
                dependency_type=dep_type,
                extras=extras or None,
            )
        return self._make_dep(package_name=name, dependency_type=dep_type)
