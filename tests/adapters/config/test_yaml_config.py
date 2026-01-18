"""Tests for YAML configuration service."""

import os
import tempfile
from pathlib import Path

import pytest

from inxr2.adapters.config.yaml_config import YamlConfigService
from inxr2.domain.value_objects import AppConfig, RepositoryConfig


class TestYamlConfigService:
    """Tests for YamlConfigService."""

    @pytest.fixture
    def config_service(self) -> YamlConfigService:
        """Create a config service instance."""
        return YamlConfigService()

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory with a fake git repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake .git directory
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            yield Path(tmpdir)

    def test_load_valid_config(
        self, config_service: YamlConfigService, temp_dir: Path
    ) -> None:
        """Test loading a valid configuration file."""
        config_content = f"""
repositories:
  - name: test-repo
    path: {temp_dir}
    branches:
      - main
    languages:
      - python

indexing:
  incremental: true
  max_commit_history: 500
"""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(config_content)

        config = config_service.load(config_path)

        assert isinstance(config, AppConfig)
        assert len(config.repositories) == 1
        assert config.repositories[0].name == "test-repo"
        assert config.repositories[0].path == str(temp_dir)
        assert config.repositories[0].branches == ["main"]
        assert config.repositories[0].languages == ["python"]
        assert config.indexing.incremental is True
        assert config.indexing.max_commit_history == 500

    def test_load_config_with_defaults(
        self, config_service: YamlConfigService, temp_dir: Path
    ) -> None:
        """Test that default values are applied."""
        config_content = f"""
repositories:
  - name: minimal-repo
    path: {temp_dir}
"""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(config_content)

        config = config_service.load(config_path)

        # Check defaults
        assert config.repositories[0].branches == ["main"]
        assert config.repositories[0].languages == [
            "python",
            "typescript",
            "javascript",
        ]
        assert config.indexing.incremental is True
        assert config.indexing.max_commit_history == 1000
        assert config.indexing.batch_size == 100
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 8000

    def test_load_config_file_not_found(
        self, config_service: YamlConfigService
    ) -> None:
        """Test error when config file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            config_service.load(Path("/nonexistent/config.yaml"))

    def test_load_invalid_yaml(
        self, config_service: YamlConfigService, temp_dir: Path
    ) -> None:
        """Test error on invalid YAML syntax."""
        config_content = """
repositories:
  - name: test
    path: /some/path
    invalid yaml here: [
"""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ValueError, match="Invalid YAML syntax"):
            config_service.load(config_path)

    def test_load_empty_config(
        self, config_service: YamlConfigService, temp_dir: Path
    ) -> None:
        """Test error on empty config file."""
        config_path = temp_dir / "config.yaml"
        config_path.write_text("")

        with pytest.raises(ValueError, match="Configuration file is empty"):
            config_service.load(config_path)

    def test_load_missing_repositories(
        self, config_service: YamlConfigService, temp_dir: Path
    ) -> None:
        """Test error when repositories field is missing."""
        config_content = """
indexing:
  incremental: true
"""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ValueError, match="repositories"):
            config_service.load(config_path)

    def test_load_config_path_not_exist(
        self, config_service: YamlConfigService, temp_dir: Path
    ) -> None:
        """Test error when repository path doesn't exist."""
        config_content = """
repositories:
  - name: test-repo
    path: /nonexistent/path
"""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ValueError, match="path does not exist"):
            config_service.load(config_path)

    def test_load_config_not_git_repo(
        self, config_service: YamlConfigService, temp_dir: Path
    ) -> None:
        """Test error when path is not a git repository."""
        # Create a directory without .git
        non_git_dir = temp_dir / "not-a-repo"
        non_git_dir.mkdir()

        config_content = f"""
repositories:
  - name: test-repo
    path: {non_git_dir}
"""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(config_content)

        with pytest.raises(ValueError, match="not a git repository"):
            config_service.load(config_path)


class TestEnvironmentVariableExpansion:
    """Tests for environment variable expansion."""

    @pytest.fixture
    def config_service(self) -> YamlConfigService:
        """Create a config service instance."""
        return YamlConfigService()

    def test_expand_simple_env_var(self, config_service: YamlConfigService) -> None:
        """Test expanding a simple environment variable."""
        os.environ["TEST_VAR"] = "test_value"
        try:
            content = "path: ${TEST_VAR}/subdir"
            result = config_service._expand_env_vars(content)
            assert result == "path: test_value/subdir"
        finally:
            del os.environ["TEST_VAR"]

    def test_expand_env_var_with_default(
        self, config_service: YamlConfigService
    ) -> None:
        """Test expanding env var with default value."""
        # Make sure var doesn't exist
        if "NONEXISTENT_VAR" in os.environ:
            del os.environ["NONEXISTENT_VAR"]

        content = "path: ${NONEXISTENT_VAR:-/default/path}"
        result = config_service._expand_env_vars(content)
        assert result == "path: /default/path"

    def test_expand_env_var_overrides_default(
        self, config_service: YamlConfigService
    ) -> None:
        """Test that env var value overrides default."""
        os.environ["MY_PATH"] = "/actual/path"
        try:
            content = "path: ${MY_PATH:-/default/path}"
            result = config_service._expand_env_vars(content)
            assert result == "path: /actual/path"
        finally:
            del os.environ["MY_PATH"]

    def test_expand_missing_env_var_no_default(
        self, config_service: YamlConfigService
    ) -> None:
        """Test that missing env var with no default becomes empty string."""
        if "MISSING_VAR" in os.environ:
            del os.environ["MISSING_VAR"]

        content = "path: ${MISSING_VAR}/subdir"
        result = config_service._expand_env_vars(content)
        assert result == "path: /subdir"

    def test_expand_multiple_env_vars(self, config_service: YamlConfigService) -> None:
        """Test expanding multiple env vars in same string."""
        os.environ["VAR1"] = "value1"
        os.environ["VAR2"] = "value2"
        try:
            content = "combined: ${VAR1}/${VAR2}"
            result = config_service._expand_env_vars(content)
            assert result == "combined: value1/value2"
        finally:
            del os.environ["VAR1"]
            del os.environ["VAR2"]


class TestConfigValidation:
    """Tests for config validation."""

    @pytest.fixture
    def config_service(self) -> YamlConfigService:
        """Create a config service instance."""
        return YamlConfigService()

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory with a fake git repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            yield Path(tmpdir)

    def test_validate_valid_config(
        self, config_service: YamlConfigService, temp_dir: Path
    ) -> None:
        """Test validating a valid config returns no errors."""
        config_content = f"""
repositories:
  - name: test-repo
    path: {temp_dir}
"""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(config_content)

        errors = config_service.validate(config_path)
        assert errors == []

    def test_validate_nonexistent_file(self, config_service: YamlConfigService) -> None:
        """Test validating nonexistent file returns error."""
        errors = config_service.validate(Path("/nonexistent/config.yaml"))
        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_validate_invalid_path(
        self, config_service: YamlConfigService, temp_dir: Path
    ) -> None:
        """Test validating config with invalid path returns error."""
        config_content = """
repositories:
  - name: test-repo
    path: /nonexistent/path
"""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(config_content)

        errors = config_service.validate(config_path)
        assert len(errors) == 1
        assert "does not exist" in errors[0]


class TestRepositoryConfigModel:
    """Tests for RepositoryConfig Pydantic model."""

    def test_repository_requires_path_or_url(self) -> None:
        """Test that either path or url must be provided."""
        with pytest.raises(
            ValueError, match="Either 'path' or 'url' must be specified"
        ):
            RepositoryConfig(name="test")

    def test_repository_with_path(self) -> None:
        """Test creating repository config with path."""
        repo = RepositoryConfig(name="test", path="/some/path")
        assert repo.name == "test"
        assert repo.path == "/some/path"
        assert repo.url is None

    def test_repository_with_url(self) -> None:
        """Test creating repository config with URL."""
        repo = RepositoryConfig(name="test", url="https://github.com/user/repo")
        assert repo.name == "test"
        assert repo.url == "https://github.com/user/repo"
        assert repo.path is None

    def test_repository_get_resolved_path(self) -> None:
        """Test resolving path with ~ expansion."""
        repo = RepositoryConfig(name="test", path="~/projects/test")
        resolved = repo.get_resolved_path()
        assert resolved is not None
        assert "~" not in str(resolved)
        assert resolved.is_absolute()

    def test_repository_get_resolved_path_none_for_url(self) -> None:
        """Test that resolved path is None for URL-based repos."""
        repo = RepositoryConfig(name="test", url="https://github.com/user/repo")
        assert repo.get_resolved_path() is None


class TestAppConfigModel:
    """Tests for AppConfig Pydantic model."""

    def test_get_repository_by_name(self) -> None:
        """Test getting repository by name."""
        config = AppConfig(
            repositories=[
                RepositoryConfig(name="repo1", path="/path1"),
                RepositoryConfig(name="repo2", path="/path2"),
            ]
        )

        repo1 = config.get_repository("repo1")
        assert repo1 is not None
        assert repo1.name == "repo1"

        repo2 = config.get_repository("repo2")
        assert repo2 is not None
        assert repo2.name == "repo2"

        nonexistent = config.get_repository("nonexistent")
        assert nonexistent is None

    def test_get_repository_names(self) -> None:
        """Test getting list of repository names."""
        config = AppConfig(
            repositories=[
                RepositoryConfig(name="repo1", path="/path1"),
                RepositoryConfig(name="repo2", path="/path2"),
            ]
        )

        names = config.get_repository_names()
        assert names == ["repo1", "repo2"]
