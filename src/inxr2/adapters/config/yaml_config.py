"""YAML configuration service implementation."""

import os
import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from ...application.ports.services import ConfigServicePort
from ...domain.value_objects import AppConfig
from .models import AppConfigModel


class YamlConfigService(ConfigServicePort):
    """
    YAML-based configuration service.

    Loads configuration from YAML files with support for:
    - Environment variable expansion (${VAR} or ${VAR:-default})
    - Path validation for local repositories
    """

    # Pattern for environment variable substitution: ${VAR} or ${VAR:-default}
    ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")

    def load(self, config_path: Path) -> AppConfig:
        """
        Load configuration from a YAML file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Parsed AppConfig object

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path) as f:
            raw_content = f.read()

        # Expand environment variables
        expanded_content = self._expand_env_vars(raw_content)

        # Parse YAML
        try:
            data = yaml.safe_load(expanded_content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML syntax: {e}") from e

        if not data:
            raise ValueError("Configuration file is empty")

        # Parse into Pydantic model for validation
        try:
            config_model = AppConfigModel(**data)
        except ValidationError as e:
            errors = []
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                errors.append(f"{loc}: {error['msg']}")
            raise ValueError(
                "Configuration validation failed:\n" + "\n".join(errors)
            ) from e

        # Convert to domain object
        config = config_model.to_domain()

        # Validate paths exist for local repositories
        self._validate_paths(config, config_path.parent)

        return config

    def validate(self, config_path: Path) -> list[str]:
        """
        Validate a configuration file without loading it fully.

        Args:
            config_path: Path to configuration file

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not config_path.exists():
            return [f"Configuration file not found: {config_path}"]

        try:
            with open(config_path) as f:
                raw_content = f.read()

            expanded_content = self._expand_env_vars(raw_content)
            data = yaml.safe_load(expanded_content)

            if not data:
                return ["Configuration file is empty"]

            # Try to parse and convert to domain
            config_model = AppConfigModel(**data)
            config = config_model.to_domain()

            # Check paths
            for repo in config.repositories:
                if repo.path:
                    resolved = self._resolve_path(repo.path, config_path.parent)
                    if not resolved.exists():
                        errors.append(
                            f"Repository '{repo.name}': path does not exist: {resolved}"
                        )
                    elif not (resolved / ".git").exists():
                        errors.append(
                            f"Repository '{repo.name}': not a git repository: {resolved}"
                        )

        except yaml.YAMLError as e:
            errors.append(f"Invalid YAML syntax: {e}")
        except ValidationError as e:
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                errors.append(f"{loc}: {error['msg']}")
        except (KeyError, TypeError, ValueError, OSError) as e:
            errors.append(f"Unexpected error: {e}")

        return errors

    def _expand_env_vars(self, content: str) -> str:
        """
        Expand environment variables in content.

        Supports:
        - ${VAR} - replaced with value of VAR
        - ${VAR:-default} - replaced with value of VAR, or 'default' if not set
        """

        def replace(match: re.Match[str]) -> str:
            var_name: str = match.group(1)
            default: str | None = match.group(2)
            value = os.environ.get(var_name)
            if value is not None:
                return value
            if default is not None:
                return default
            # Return empty string if not found and no default
            return ""

        return self.ENV_VAR_PATTERN.sub(replace, content)

    def _resolve_path(self, path_str: str, base_path: Path) -> Path:
        """Resolve a path, handling ~ and relative paths."""
        path = Path(path_str).expanduser()
        if not path.is_absolute():
            path = base_path / path
        return path.resolve()

    def _validate_paths(self, config: AppConfig, base_path: Path) -> None:
        """
        Validate that all local repository paths exist.

        Args:
            config: Parsed configuration
            base_path: Base path for resolving relative paths

        Raises:
            ValueError: If any path is invalid
        """
        errors = []

        for repo in config.repositories:
            if repo.path:
                resolved = self._resolve_path(repo.path, base_path)
                if not resolved.exists():
                    errors.append(
                        f"Repository '{repo.name}': path does not exist: {resolved}"
                    )
                elif not (resolved / ".git").exists():
                    errors.append(
                        f"Repository '{repo.name}': not a git repository: {resolved}"
                    )

        if errors:
            raise ValueError(
                "Configuration path validation failed:\n" + "\n".join(errors)
            )


def load_config(config_path: Path | str) -> AppConfig:
    """
    Convenience function to load configuration.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Parsed AppConfig object
    """
    service = YamlConfigService()
    return service.load(Path(config_path))
