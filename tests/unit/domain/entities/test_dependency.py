"""Unit tests for Dependency domain entity."""

import pytest

from inxr2.domain.entities import Dependency


class TestDependencyCreation:
    """Test creating Dependency entities."""

    def test_create_minimal(self) -> None:
        """Create dependency with only required fields."""
        dep = Dependency(
            file_id=1,
            repository_id=1,
            package_name="fastapi",
            language="python",
        )
        assert dep.package_name == "fastapi"
        assert dep.language == "python"
        assert dep.dependency_type == "runtime"
        assert dep.is_direct is True
        assert dep.id is None
        assert dep.version_spec is None
        assert dep.resolved_version is None
        assert dep.parent_dependency_id is None
        assert dep.extras is None

    def test_create_full(self) -> None:
        """Create dependency with all fields."""
        dep = Dependency(
            file_id=1,
            repository_id=1,
            package_name="fastapi",
            language="python",
            id=42,
            version_spec="^0.109.0",
            resolved_version="0.109.1",
            dependency_type="runtime",
            is_direct=True,
            parent_dependency_id=None,
            extras={"python_version": ">=3.8"},
        )
        assert dep.id == 42
        assert dep.version_spec == "^0.109.0"
        assert dep.resolved_version == "0.109.1"
        assert dep.extras == {"python_version": ">=3.8"}

    def test_transitive_dependency(self) -> None:
        """Create a transitive dependency with parent."""
        dep = Dependency(
            file_id=1,
            repository_id=1,
            package_name="starlette",
            language="python",
            is_direct=False,
            parent_dependency_id=42,
        )
        assert dep.is_direct is False
        assert dep.parent_dependency_id == 42

    def test_frozen(self) -> None:
        """Dependency entity is immutable."""
        dep = Dependency(
            file_id=1,
            repository_id=1,
            package_name="fastapi",
            language="python",
        )
        with pytest.raises(AttributeError):
            dep.package_name = "other"  # type: ignore[misc]


class TestDependencyValidation:
    """Test Dependency entity validation."""

    def test_empty_package_name_raises(self) -> None:
        """Package name cannot be empty."""
        with pytest.raises(ValueError, match="Package name cannot be empty"):
            Dependency(
                file_id=1,
                repository_id=1,
                package_name="",
                language="python",
            )

    def test_empty_language_raises(self) -> None:
        """Language cannot be empty."""
        with pytest.raises(ValueError, match="Language cannot be empty"):
            Dependency(
                file_id=1,
                repository_id=1,
                package_name="fastapi",
                language="",
            )

    def test_invalid_dependency_type_raises(self) -> None:
        """Invalid dependency type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid dependency type"):
            Dependency(
                file_id=1,
                repository_id=1,
                package_name="fastapi",
                language="python",
                dependency_type="invalid",
            )

    @pytest.mark.parametrize(
        "dep_type", ["runtime", "dev", "optional", "build", "peer"]
    )
    def test_valid_dependency_types(self, dep_type: str) -> None:
        """All valid dependency types are accepted."""
        dep = Dependency(
            file_id=1,
            repository_id=1,
            package_name="fastapi",
            language="python",
            dependency_type=dep_type,
        )
        assert dep.dependency_type == dep_type


class TestDependencySourceLine:
    """Test source_line field on Dependency entity."""

    def test_source_line_defaults_to_none(self) -> None:
        dep = Dependency(
            file_id=1,
            repository_id=1,
            package_name="fastapi",
            language="python",
        )
        assert dep.source_line is None

    def test_source_line_set(self) -> None:
        dep = Dependency(
            file_id=1,
            repository_id=1,
            package_name="fastapi",
            language="python",
            source_line=42,
        )
        assert dep.source_line == 42
