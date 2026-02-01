"""Test data factories for creating domain entities."""

from datetime import UTC, datetime
from typing import Any

from inxr2.domain.entities import Commit, File, Repository, Symbol
from inxr2.domain.value_objects import CommitHash, SymbolKind


class RepositoryFactory:
    """Factory for creating test Repository entities."""

    @staticmethod
    def create(
        name: str = "test-repo",
        url: str = "https://github.com/test/repo.git",
        **kwargs: Any,
    ) -> Repository:
        """Create a test repository."""
        return Repository(
            name=name,
            url=url,
            description=kwargs.get("description", "Test repository"),
            default_branch=kwargs.get("default_branch", "main"),
            config=kwargs.get("config"),
            id=kwargs.get("id"),
            created_at=kwargs.get("created_at"),
            updated_at=kwargs.get("updated_at"),
        )


class CommitFactory:
    """Factory for creating test Commit entities."""

    @staticmethod
    def create(
        repository_id: int = 1,
        commit_hash: str = "a" * 40,
        **kwargs: Any,
    ) -> Commit:
        """Create a test commit.

        Note: Branch information is no longer stored on the Commit entity.
        Use CommitRepositoryPort.link_commit_to_branch() to associate commits with branches.

        Design note: Author info, message, and parent hashes are NOT stored.
        They are queried from git on-demand. See ARCHITECTURAL_REVIEW.md.
        """
        return Commit(
            repository_id=repository_id,
            commit_hash=CommitHash(value=commit_hash),
            author_date=kwargs.get(
                "author_date", datetime.now(UTC).replace(tzinfo=None)
            ),
            commit_date=kwargs.get(
                "commit_date", datetime.now(UTC).replace(tzinfo=None)
            ),
            id=kwargs.get("id"),
            indexed_at=kwargs.get("indexed_at"),
        )


class FileFactory:
    """Factory for creating test File entities."""

    @staticmethod
    def create(
        repository_id: int = 1,
        commit_id: int = 1,
        path: str = "src/test.py",
        **kwargs: Any,
    ) -> File:
        """Create a test file."""
        return File(
            repository_id=repository_id,
            commit_id=commit_id,
            path=path,
            content_hash=kwargs.get("content_hash", "b" * 40),
            size_bytes=kwargs.get("size_bytes", 1024),
            id=kwargs.get("id"),
            language=kwargs.get("language", "python"),
            encoding=kwargs.get("encoding", "utf-8"),
            is_binary=kwargs.get("is_binary", False),
            line_count=kwargs.get("line_count", 50),
            indexed_at=kwargs.get("indexed_at"),
        )


class SymbolFactory:
    """Factory for creating test Symbol entities."""

    @staticmethod
    def create(
        file_id: int = 1,
        repository_id: int = 1,
        commit_id: int = 1,
        name: str = "test_function",
        **kwargs: Any,
    ) -> Symbol:
        """Create a test symbol."""
        return Symbol(
            file_id=file_id,
            repository_id=repository_id,
            commit_id=commit_id,
            name=name,
            kind=kwargs.get("kind", SymbolKind.FUNCTION),
            start_line=kwargs.get("start_line", 10),
            start_column=kwargs.get("start_column", 0),
            end_line=kwargs.get("end_line", 20),
            end_column=kwargs.get("end_column", 0),
            id=kwargs.get("id"),
            qualified_name=kwargs.get("qualified_name"),
            parent_symbol_id=kwargs.get("parent_symbol_id"),
            scope=kwargs.get("scope"),
            signature=kwargs.get("signature"),
            docstring=kwargs.get("docstring"),
            metadata=kwargs.get("metadata"),
            indexed_at=kwargs.get("indexed_at"),
        )
