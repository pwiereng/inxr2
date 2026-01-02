"""Pytest configuration and fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_repository_id() -> str:
    """Sample repository ID for testing."""
    return "repo-123"


@pytest.fixture
def sample_file_id() -> str:
    """Sample file ID for testing."""
    return "file-456"


@pytest.fixture
def sample_symbol_id() -> str:
    """Sample symbol ID for testing."""
    return "sym-789"


@pytest.fixture
def sample_file_path() -> Path:
    """Sample file path for testing."""
    return Path("src/example/module.py")
