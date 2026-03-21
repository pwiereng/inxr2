"""Shared fixtures for unit tests in tests/unit/application/.

Provides common InMemory repository and service fakes used across multiple
test modules in this directory.
"""

import pytest

from tests.fixtures.test_doubles import (
    FakeGitService,
    InMemoryCommitRepository,
    InMemoryFileRepository,
    InMemoryReferenceRepository,
    InMemorySymbolRepository,
    InMemoryTextContentRepository,
)


@pytest.fixture
def git_service() -> FakeGitService:
    """Create a fresh FakeGitService."""
    return FakeGitService()


@pytest.fixture
def commit_repo() -> InMemoryCommitRepository:
    """Create a fresh in-memory commit repository."""
    return InMemoryCommitRepository()


@pytest.fixture
def file_repo() -> InMemoryFileRepository:
    """Create a fresh in-memory file repository."""
    return InMemoryFileRepository()


@pytest.fixture
def symbol_repo() -> InMemorySymbolRepository:
    """Create a fresh in-memory symbol repository."""
    return InMemorySymbolRepository()


@pytest.fixture
def reference_repo(
    symbol_repo: InMemorySymbolRepository,
) -> InMemoryReferenceRepository:
    """Create a fresh in-memory reference repository."""
    return InMemoryReferenceRepository(symbol_repo=symbol_repo)


@pytest.fixture
def text_content_repo() -> InMemoryTextContentRepository:
    """Create a fresh in-memory text content repository."""
    return InMemoryTextContentRepository()
