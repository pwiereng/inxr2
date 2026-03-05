"""Configuration service port interface."""

from abc import ABC, abstractmethod
from pathlib import Path

from ....domain.value_objects import AppConfig


class ConfigServicePort(ABC):
    """
    Port for configuration loading.

    Implementations will load config from YAML files.
    """

    @abstractmethod
    def load(self, config_path: Path) -> AppConfig:
        """
        Load configuration from a file.

        Args:
            config_path: Path to configuration file (YAML)

        Returns:
            Parsed AppConfig object

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        pass

    @abstractmethod
    def validate(self, config_path: Path) -> list[str]:
        """
        Validate a configuration file without loading it fully.

        Args:
            config_path: Path to configuration file

        Returns:
            List of validation errors (empty if valid)
        """
        pass
