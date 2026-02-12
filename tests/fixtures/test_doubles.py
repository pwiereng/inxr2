"""
Test doubles (fakes) for testing - implements ports for testing.

ARCHITECTURE PATTERN: Dependency Injection over Mocking
========================================================

This module provides fake implementations of ports (interfaces) for testing.
These are REAL implementations that follow the interface contract, not mocks.

Why use test doubles instead of mocking frameworks?
---------------------------------------------------
✅ More maintainable - tests don't break when implementation changes
✅ Clearer intent - explicit test data setup
✅ Faster - no mocking framework overhead
✅ Follows port/adapter pattern - respects the architecture
✅ Type-safe - real implementations catch interface changes

Example Usage:
--------------
```python
# DON'T: Use mocking framework
from unittest.mock import Mock
mock_repo = Mock(spec=SymbolRepositoryPort)
mock_repo.find_by_name.return_value = [...]

# DO: Use test double (fake)
from tests.fixtures.test_doubles import FakeSymbolRepository
fake_repo = FakeSymbolRepository()
fake_repo.add_test_symbol(Symbol(...))
```
"""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO

from inxr2.application.ports.repositories import (
    CommitRepositoryPort,
    CopySymbolsResult,
    FileRepositoryPort,
    IndexStatusRepositoryPort,
    ReferenceRepositoryPort,
    RepositoryPort,
    SymbolRepositoryPort,
    TextContentRepositoryPort,
)
from inxr2.application.ports.services import (
    ChangedFiles,
    CommitInfo,
    FileStat,
    FileSystemPort,
    GitServicePort,
    ParserServicePort,
    PlaintextParserPort,
    RepositoryInfo,
    TextSearchPort,
    TextSearchQuery,
    TextSearchResult,
)
from inxr2.domain.entities import (
    Commit,
    File,
    IndexStatus,
    Reference,
    Repository,
    Symbol,
    TextContent,
)

# ============================================================================
# Repository Test Doubles
# ============================================================================


class InMemorySymbolRepository(SymbolRepositoryPort):
    """
    In-memory implementation of SymbolRepositoryPort for testing.

    This is a test double (fake) that implements the port interface
    using in-memory storage instead of a database.

    Usage:
        repo = InMemorySymbolRepository()
        repo.add(Symbol(...))  # Add test data
        result = await repo.find_by_name("foo")  # Test
    """

    def __init__(self, file_repo: "InMemoryFileRepository | None" = None) -> None:
        """Initialize with empty storage.

        Args:
            file_repo: Optional file repository for latest-file-version filtering.
                      When provided, search/find methods filter to only symbols
                      from the latest version of each file (matching Postgres behavior).
        """
        self._symbols: dict[int, Symbol] = {}
        self._next_id = 1
        self._file_repo = file_repo

    async def save(self, symbol: Symbol) -> Symbol:
        """Save symbol to in-memory storage."""
        if symbol.id is None:
            # Assign a new ID
            symbol = Symbol(
                id=self._next_id,
                file_id=symbol.file_id,
                repository_id=symbol.repository_id,
                commit_id=symbol.commit_id,
                name=symbol.name,
                kind=symbol.kind,
                start_line=symbol.start_line,
                start_column=symbol.start_column,
                end_line=symbol.end_line,
                end_column=symbol.end_column,
                qualified_name=symbol.qualified_name,
                parent_symbol_id=symbol.parent_symbol_id,
                scope=symbol.scope,
                signature=symbol.signature,
                docstring=symbol.docstring,
                metadata=symbol.metadata,
                indexed_at=symbol.indexed_at,
            )
            self._next_id += 1
        else:
            # Update _next_id to avoid collisions when symbols with explicit IDs are inserted
            self._next_id = max(self._next_id, symbol.id + 1)
        assert symbol.id is not None, "Symbol must have an ID after assignment"
        self._symbols[symbol.id] = symbol
        return symbol

    async def find_by_id(self, symbol_id: int) -> Symbol | None:
        """Find symbol by ID."""
        return self._symbols.get(symbol_id)

    async def find_by_name(
        self, name: str, repository_id: int | None = None
    ) -> list[Symbol]:
        """Find symbols by name (case-insensitive)."""
        results = []
        for symbol in self._symbols.values():
            if name.lower() in symbol.name.lower():
                # Filter by repository if specified
                if repository_id is None or symbol.repository_id == repository_id:
                    results.append(symbol)
        return results

    async def save_many(self, symbols: list[Symbol]) -> list[Symbol]:
        """Bulk save symbols."""
        result = []
        for symbol in symbols:
            saved = await self.save(symbol)
            result.append(saved)
        return result

    async def search_by_name(
        self,
        name: str,
        repository_id: int | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> list[Symbol]:
        """Search symbols by name with optional filters.

        When repository_id is set and file_repo is available, filters to
        only symbols from the latest version of each file (matching Postgres).
        """
        # Compute latest file IDs for filtering (matches Postgres behavior)
        latest_file_ids: set[int] | None = None
        if repository_id is not None and self._file_repo is not None:
            latest_file_ids = self._file_repo._compute_latest_file_ids(repository_id)

        results = []
        for symbol in self._symbols.values():
            if name.lower() in symbol.name.lower():
                if repository_id is not None and symbol.repository_id != repository_id:
                    continue
                if kind is not None and symbol.kind.value != kind:
                    continue
                if (
                    latest_file_ids is not None
                    and symbol.file_id not in latest_file_ids
                ):
                    continue
                results.append(symbol)
        results.sort(key=lambda s: s.name)
        return results[:limit]

    async def find_by_qualified_name(
        self, repository_id: int, qualified_name: str
    ) -> list[Symbol]:
        """Find symbols by qualified name.

        Filters to only symbols from the latest version of each file
        when file_repo is available (matching Postgres behavior).
        """
        latest_file_ids: set[int] | None = None
        if self._file_repo is not None:
            latest_file_ids = self._file_repo._compute_latest_file_ids(repository_id)

        results = []
        for s in self._symbols.values():
            if s.repository_id == repository_id and s.qualified_name == qualified_name:
                if latest_file_ids is not None and s.file_id not in latest_file_ids:
                    continue
                results.append(s)
        return results

    async def list_by_file(self, file_id: int) -> list[Symbol]:
        """List all symbols in a file."""
        return [s for s in self._symbols.values() if s.file_id == file_id]

    async def find_by_exact_name(
        self,
        name: str,
        repository_id: int | None = None,
        commit_id: int | None = None,
        limit: int = 100,
    ) -> list[Symbol]:
        """Find symbols by exact name.

        When commit_id is None and repository_id is set with file_repo available,
        filters to only symbols from the latest version of each file
        (matching Postgres behavior).
        """
        # Compute latest file IDs when not in time-travel mode
        latest_file_ids: set[int] | None = None
        if (
            commit_id is None
            and repository_id is not None
            and self._file_repo is not None
        ):
            latest_file_ids = self._file_repo._compute_latest_file_ids(repository_id)

        results = []
        for symbol in self._symbols.values():
            if symbol.name == name:
                if repository_id is not None and symbol.repository_id != repository_id:
                    continue
                if commit_id is not None and symbol.commit_id != commit_id:
                    continue
                if (
                    latest_file_ids is not None
                    and symbol.file_id not in latest_file_ids
                ):
                    continue
                results.append(symbol)
        results.sort(key=lambda s: (s.qualified_name or "", s.id or 0))
        return results[:limit]

    async def count_by_repository(self, repository_id: int) -> int:
        """Count symbols in a repository."""
        return len(
            [s for s in self._symbols.values() if s.repository_id == repository_id]
        )

    async def delete_by_file(self, file_id: int) -> int:
        """Delete all symbols for a file."""
        to_delete = [sid for sid, s in self._symbols.items() if s.file_id == file_id]
        for sid in to_delete:
            del self._symbols[sid]
        return len(to_delete)

    async def copy_symbols_to_file(
        self,
        source_file_id: int,
        target_file_id: int,
        target_commit_id: int,
        target_repository_id: int,
    ) -> CopySymbolsResult:
        """Copy all symbols from source file to target file."""
        source_symbols = [
            s for s in self._symbols.values() if s.file_id == source_file_id
        ]
        if not source_symbols:
            return CopySymbolsResult(count=0, id_mapping={})

        # Map old symbol IDs to new ones for parent_symbol_id remapping
        old_to_new_id: dict[int, int] = {}

        for source in source_symbols:
            new_symbol = Symbol(
                id=self._next_id,
                file_id=target_file_id,
                repository_id=target_repository_id,
                commit_id=target_commit_id,
                name=source.name,
                kind=source.kind,
                start_line=source.start_line,
                start_column=source.start_column,
                end_line=source.end_line,
                end_column=source.end_column,
                qualified_name=source.qualified_name,
                scope=source.scope,
                signature=source.signature,
                docstring=source.docstring,
                metadata=source.metadata,
                parent_symbol_id=None,  # Will be remapped below
            )
            self._symbols[self._next_id] = new_symbol
            if source.id is not None:
                old_to_new_id[source.id] = self._next_id
            self._next_id += 1

        # Remap parent_symbol_id references
        for source in source_symbols:
            if source.parent_symbol_id is not None and source.id is not None:
                new_id = old_to_new_id.get(source.id)
                new_parent_id = old_to_new_id.get(source.parent_symbol_id)
                if new_id is not None and new_parent_id is not None:
                    old_symbol = self._symbols[new_id]
                    self._symbols[new_id] = Symbol(
                        id=old_symbol.id,
                        file_id=old_symbol.file_id,
                        repository_id=old_symbol.repository_id,
                        commit_id=old_symbol.commit_id,
                        name=old_symbol.name,
                        kind=old_symbol.kind,
                        start_line=old_symbol.start_line,
                        start_column=old_symbol.start_column,
                        end_line=old_symbol.end_line,
                        end_column=old_symbol.end_column,
                        qualified_name=old_symbol.qualified_name,
                        scope=old_symbol.scope,
                        signature=old_symbol.signature,
                        docstring=old_symbol.docstring,
                        metadata=old_symbol.metadata,
                        parent_symbol_id=new_parent_id,
                    )

        return CopySymbolsResult(count=len(source_symbols), id_mapping=old_to_new_id)

    # Test helper methods
    def add(self, symbol: Symbol) -> Symbol:
        """Add a symbol for testing (convenience method)."""
        if symbol.id is None:
            symbol = Symbol(
                id=self._next_id,
                file_id=symbol.file_id,
                repository_id=symbol.repository_id,
                commit_id=symbol.commit_id,
                name=symbol.name,
                kind=symbol.kind,
                start_line=symbol.start_line,
                start_column=symbol.start_column,
                end_line=symbol.end_line,
                end_column=symbol.end_column,
                qualified_name=symbol.qualified_name,
                parent_symbol_id=symbol.parent_symbol_id,
                scope=symbol.scope,
                signature=symbol.signature,
                docstring=symbol.docstring,
                metadata=symbol.metadata,
                indexed_at=symbol.indexed_at,
            )
            self._next_id += 1
        assert symbol.id is not None, "Symbol must have an ID after assignment"
        self._symbols[symbol.id] = symbol
        return symbol

    def clear(self) -> None:
        """Clear all symbols (for test isolation)."""
        self._symbols.clear()

    def count(self) -> int:
        """Get total symbol count (for assertions)."""
        return len(self._symbols)

    def get_all_symbols(self) -> list[Symbol]:
        """Get all symbols (for testing and internal use)."""
        return list(self._symbols.values())


class InMemoryFileRepository(FileRepositoryPort):
    """
    In-memory implementation of FileRepositoryPort for testing.

    Example:
        repo = InMemoryFileRepository()
        repo.add(File(...))
        file = await repo.find_by_id("file-1")

    For time travel testing, pass a commit repository:
        commit_repo = InMemoryCommitRepository()
        file_repo = InMemoryFileRepository(commit_repo=commit_repo)
    """

    def __init__(self, commit_repo: "InMemoryCommitRepository | None" = None) -> None:
        """Initialize with empty storage.

        Args:
            commit_repo: Optional commit repository for commit hash lookups
                         (required for find_by_repository_path_and_commit_hash)
        """
        self._files: dict[int, File] = {}
        self._next_id = 1
        self._commit_repo = commit_repo

    async def save(self, file: File) -> File:
        """Save file to in-memory storage."""
        if file.id is None:
            file = File(
                id=self._next_id,
                repository_id=file.repository_id,
                commit_id=file.commit_id,
                path=file.path,
                content_hash=file.content_hash,
                size_bytes=file.size_bytes,
                language=file.language,
                encoding=file.encoding,
                is_binary=file.is_binary,
                line_count=file.line_count,
                indexed_at=file.indexed_at,
            )
            self._next_id += 1
        assert file.id is not None, "File must have an ID after assignment"
        self._files[file.id] = file
        return file

    async def find_by_id(self, file_id: int) -> File | None:
        """Find file by ID."""
        return self._files.get(file_id)

    async def find_by_ids(self, file_ids: list[int]) -> dict[int, File]:
        """Find multiple files by IDs."""
        return {fid: self._files[fid] for fid in file_ids if fid in self._files}

    async def save_many(self, files: list[File]) -> list[File]:
        """Save multiple files."""
        saved_files = []
        for file in files:
            saved = await self.save(file)
            saved_files.append(saved)
        return saved_files

    async def list_by_repository(self, repository_id: int) -> list[File]:
        """List all files for a repository."""
        return [f for f in self._files.values() if f.repository_id == repository_id]

    async def find_by_path(
        self, repository_id: int, commit_id: int, path: str
    ) -> File | None:
        """Find file by path."""
        for file in self._files.values():
            if (
                file.repository_id == repository_id
                and file.commit_id == commit_id
                and file.path == path
            ):
                return file
        return None

    async def list_by_commit(self, commit_id: int) -> list[File]:
        """List files for a commit."""
        return [f for f in self._files.values() if f.commit_id == commit_id]

    async def list_at_or_before_commit(
        self, repository_id: int, commit_id: int
    ) -> list[File]:
        """List the latest version of each file at or before a specific commit.

        This requires commit_repo to be set for proper date-based filtering.
        """
        if self._commit_repo is None:
            # No commit repo - fall back to simple commit_id matching
            return [
                f
                for f in self._files.values()
                if f.repository_id == repository_id and f.commit_id == commit_id
            ]

        # Get target commit date
        target_commit = await self._commit_repo.find_by_id(commit_id)
        if target_commit is None:
            return []

        # Get all commits up to and including the target
        all_commits = self._commit_repo.get_all_commits()
        valid_commit_ids = {
            c.id
            for c in all_commits
            if c.repository_id == repository_id
            and c.id is not None
            and c.commit_date <= target_commit.commit_date
        }

        # Get all files from these commits, keeping only the latest per path
        path_to_file: dict[str, File] = {}
        for f in self._files.values():
            if f.repository_id == repository_id and f.commit_id in valid_commit_ids:
                # Get commit date for this file's commit
                file_commit = await self._commit_repo.find_by_id(f.commit_id)
                if file_commit is None:
                    continue

                existing = path_to_file.get(f.path)
                if existing is None:
                    path_to_file[f.path] = f
                else:
                    # Compare commit dates, keep the newer one
                    existing_commit = await self._commit_repo.find_by_id(
                        existing.commit_id
                    )
                    if (
                        existing_commit is not None
                        and file_commit.commit_date > existing_commit.commit_date
                    ):
                        path_to_file[f.path] = f

        return list(path_to_file.values())

    async def find_by_content_hash(self, content_hash: str) -> list[File]:
        """Find files by content hash."""
        return [f for f in self._files.values() if f.content_hash == content_hash]

    async def find_by_repository_and_path(
        self, repository_id: int, path: str
    ) -> File | None:
        """Find file by repository and path (latest version)."""
        for file in self._files.values():
            if file.repository_id == repository_id and file.path == path:
                return file
        return None

    async def list_versions_by_path(
        self, repository_id: int, path: str, branch: str | None = None
    ) -> list[File]:
        """List all versions of a file across commits (for time travel).

        Args:
            repository_id: The repository ID
            path: The file path
            branch: Optional branch to filter by (requires commit_repo with branch tracking)
        """
        files = [
            f
            for f in self._files.values()
            if f.repository_id == repository_id and f.path == path
        ]

        # If branch filter specified and we have a commit repo, filter by branch
        if branch is not None and self._commit_repo is not None:
            # Get commit IDs on this branch from the branch_commits mapping
            branch_commit_ids: set[int] = set()
            for (repo_id, b, cid), _ in self._commit_repo._branch_commits.items():
                if repo_id == repository_id and b == branch:
                    branch_commit_ids.add(cid)
            files = [f for f in files if f.commit_id in branch_commit_ids]

        return files

    async def find_by_repository_path_and_commit_hash(
        self, repository_id: int, path: str, commit_hash: str
    ) -> File | None:
        """Find file by repository, path, and commit hash (for time travel).

        Requires commit_repo to be set for proper commit hash lookups.
        """
        if self._commit_repo is None:
            # No commit repo - fall back to simple path matching (legacy behavior)
            for file in self._files.values():
                if file.repository_id == repository_id and file.path == path:
                    return file
            return None

        # Look up commit by hash
        commit = await self._commit_repo.find_by_hash(repository_id, commit_hash)
        if commit is None or commit.id is None:
            return None

        # Find file matching repository, path, and commit_id
        for file in self._files.values():
            if (
                file.repository_id == repository_id
                and file.path == path
                and file.commit_id == commit.id
            ):
                return file
        return None

    async def list_latest_by_branch(
        self, repository_id: int, branch: str
    ) -> list[File]:
        """List the latest version of each file on a branch.

        For delta-indexed repositories, this aggregates files across all commits
        on the branch, returning only the most recent version of each unique path.
        """
        if self._commit_repo is None:
            # No commit repo - return all files for repository
            return [f for f in self._files.values() if f.repository_id == repository_id]

        # Get commit IDs on this branch
        branch_commit_ids: set[int] = set()
        for (repo_id, b, cid), _ in self._commit_repo._branch_commits.items():
            if repo_id == repository_id and b == branch:
                branch_commit_ids.add(cid)

        # Get commits with dates for ordering
        commits_with_dates: dict[int, datetime] = {}
        for cid in branch_commit_ids:
            commit = self._commit_repo._commits.get(cid)
            if commit:
                commits_with_dates[cid] = commit.commit_date

        # Get all files on this branch
        branch_files = [
            f
            for f in self._files.values()
            if f.repository_id == repository_id and f.commit_id in branch_commit_ids
        ]

        # Group by path and keep only the latest (by commit date, then commit_id desc)
        latest_by_path: dict[str, File] = {}
        for file in branch_files:
            file_date = commits_with_dates.get(file.commit_id, datetime.min)
            if file.path not in latest_by_path:
                latest_by_path[file.path] = file
            else:
                existing_file = latest_by_path[file.path]
                existing_date = commits_with_dates.get(
                    existing_file.commit_id, datetime.min
                )
                if file_date > existing_date:
                    latest_by_path[file.path] = file
                elif file_date == existing_date:
                    # Tie-breaker: prefer higher commit_id (matches production behavior)
                    if (
                        file.commit_id is not None
                        and existing_file.commit_id is not None
                        and file.commit_id > existing_file.commit_id
                    ):
                        latest_by_path[file.path] = file

        # Return sorted by path
        return sorted(latest_by_path.values(), key=lambda f: f.path)

    async def list_changed_at_commit(
        self, repository_id: int, commit_id: int
    ) -> list[File]:
        """List only files that actually changed at a specific commit.

        Returns files where either:
        - The file is new (no prior version exists), OR
        - The file's content_hash differs from the most recent prior version

        Requires commit_repo to determine commit ordering.
        Mirrors the Postgres ROW_NUMBER() window function approach.
        """
        if self._commit_repo is None:
            # No commit repo - fall back to returning all files at commit
            return [
                f
                for f in self._files.values()
                if f.repository_id == repository_id and f.commit_id == commit_id
            ]

        # Get target commit to determine its date
        target_commit = await self._commit_repo.find_by_id(commit_id)
        if target_commit is None:
            return []

        # Get all files at the target commit
        files_at_commit = [
            f
            for f in self._files.values()
            if f.repository_id == repository_id and f.commit_id == commit_id
        ]

        if not files_at_commit:
            return []

        # Build commit_dates lookup: commit_id -> (commit_date, commit_id)
        # for all commits in this repo
        commit_dates: dict[int, tuple[datetime, int]] = {}
        for c in self._commit_repo._commits.values():
            if c.repository_id == repository_id and c.id is not None:
                commit_dates[c.id] = (c.commit_date, c.id)

        target_key = (target_commit.commit_date, commit_id)

        # Build prior_hashes: for each path, keep the content_hash from the
        # most recent commit strictly before the target commit.
        # "Most recent" = highest (commit_date, commit_id) that is < target_key.
        prior_hashes: dict[str, str] = {}
        prior_keys: dict[str, tuple[datetime, int]] = {}

        for f in self._files.values():
            if f.repository_id != repository_id:
                continue
            f_key = commit_dates.get(f.commit_id)
            if f_key is None or f_key >= target_key:
                continue
            # This file is from a prior commit
            existing_key = prior_keys.get(f.path)
            if existing_key is None or f_key > existing_key:
                prior_hashes[f.path] = f.content_hash or ""
                prior_keys[f.path] = f_key

        # Filter to only changed files
        changed_files = []
        for f in files_at_commit:
            prior_hash = prior_hashes.get(f.path)
            if prior_hash is None or prior_hash != f.content_hash:
                changed_files.append(f)

        return changed_files

    async def find_one_by_content_hash_in_repo(
        self, repository_id: int, content_hash: str
    ) -> File | None:
        """Find first file with matching content hash within a repository."""
        for file in self._files.values():
            if (
                file.repository_id == repository_id
                and file.content_hash == content_hash
            ):
                return file
        return None

    async def get_content_hash_to_file_id_map(
        self, repository_id: int
    ) -> dict[str, int]:
        """Load all content hashes for a repository into memory."""
        result: dict[str, int] = {}
        for file in self._files.values():
            if (
                file.repository_id == repository_id
                and file.content_hash
                and file.id is not None
                and file.content_hash not in result
            ):
                result[file.content_hash] = file.id
        return result

    async def search_by_name(
        self,
        query: str,
        repository_id: int | None = None,
        commit_id: int | None = None,
        language: str | None = None,
        limit: int = 20,
    ) -> list[File]:
        """Search files by name/path pattern.

        Uses case-insensitive pattern matching on file paths.
        When commit_id is None, deduplicates by (repository_id, path).
        """
        query_lower = query.lower()
        results = []

        for file in self._files.values():
            # Check if query matches path (case-insensitive)
            if query_lower not in file.path.lower():
                continue

            # Apply filters
            if repository_id is not None and file.repository_id != repository_id:
                continue

            if commit_id is not None and file.commit_id != commit_id:
                continue

            if language is not None and file.language != language:
                continue

            results.append(file)

        # When no commit_id, deduplicate by (repository_id, path) keeping latest
        if commit_id is None:
            if self._commit_repo is not None:
                # Use commit dates (matches Postgres ROW_NUMBER approach)
                commit_keys: dict[int, tuple[datetime, str]] = {}
                for c in self._commit_repo._commits.values():
                    if c.id is not None:
                        commit_keys[c.id] = (c.commit_date, c.commit_hash.value)

                latest_by_repo_path: dict[tuple[int | None, str], File] = {}
                latest_keys: dict[tuple[int | None, str], tuple[datetime, str]] = {}
                for f in results:
                    rp_key = (f.repository_id, f.path)
                    f_key = commit_keys.get(f.commit_id)
                    if f_key is None:
                        # No commit info — keep highest file.id among such candidates,
                        # but any entry with real commit data always wins.
                        existing = latest_by_repo_path.get(rp_key)
                        if existing is None:
                            latest_by_repo_path[rp_key] = f
                        elif rp_key not in latest_keys:
                            # Existing also has no commit info — prefer higher id
                            if f.id is not None and (
                                existing.id is None or f.id > existing.id
                            ):
                                latest_by_repo_path[rp_key] = f
                        continue
                    existing_key = latest_keys.get(rp_key)
                    if existing_key is None or f_key > existing_key:
                        latest_by_repo_path[rp_key] = f
                        latest_keys[rp_key] = f_key
                results = list(latest_by_repo_path.values())
            else:
                # Fallback: max(id) when no commit repo (backward compat)
                latest_by_repo_path_simple: dict[tuple[int | None, str], File] = {}
                for f in results:
                    key = (f.repository_id, f.path)
                    existing = latest_by_repo_path_simple.get(key)
                    if existing is None or (
                        f.id is not None and (existing.id is None or f.id > existing.id)
                    ):
                        latest_by_repo_path_simple[key] = f
                results = list(latest_by_repo_path_simple.values())

        # Sort by relevance (exact filename match first, then prefix, then contains)
        def relevance_key(f: File) -> tuple[int, str]:
            filename = (
                f.path.rsplit("/", 1)[-1].lower() if "/" in f.path else f.path.lower()
            )
            if filename == query_lower:
                return (1, f.path)
            elif filename.startswith(query_lower):
                return (2, f.path)
            else:
                return (3, f.path)

        results.sort(key=relevance_key)

        return results[:limit]

    def _compute_latest_file_ids(self, repository_id: int) -> set[int]:
        """Compute the latest file ID for each unique path in a repository.

        Mirrors the Postgres pattern: ROW_NUMBER() OVER (PARTITION BY path
        ORDER BY commit_date DESC, commit_hash DESC, file_id DESC) where rn=1.

        Uses commit dates from _commit_repo when available; falls back to
        max(id) when no commit repo is set (backward compat for tests that
        don't wire up commit_repo).
        """
        if self._commit_repo is None:
            # Fallback: max(id) per path (legacy behavior)
            latest_by_path: dict[str, int] = {}
            for file in self._files.values():
                if file.repository_id == repository_id and file.id is not None:
                    current = latest_by_path.get(file.path)
                    if current is None or file.id > current:
                        latest_by_path[file.path] = file.id
            return set(latest_by_path.values())

        # Build commit_id -> (commit_date, commit_hash) lookup
        commit_keys: dict[int, tuple[datetime, str]] = {}
        for c in self._commit_repo._commits.values():
            if c.repository_id == repository_id and c.id is not None:
                commit_keys[c.id] = (c.commit_date, c.commit_hash.value)

        # For each path, keep the file whose commit has the newest date
        latest_by_path_dated: dict[str, tuple[tuple[datetime, str], int]] = {}
        for file in self._files.values():
            if file.repository_id != repository_id or file.id is None:
                continue
            key = commit_keys.get(file.commit_id)
            if key is None:
                # Commit not in repo — fall back to max(id) for this path,
                # but real commits (date > datetime.min) always win.
                existing = latest_by_path_dated.get(file.path)
                if existing is None:
                    latest_by_path_dated[file.path] = (
                        (datetime.min, ""),
                        file.id,
                    )
                elif existing[0][0] == datetime.min and file.id > existing[1]:
                    latest_by_path_dated[file.path] = (
                        existing[0],
                        file.id,
                    )
                continue
            existing = latest_by_path_dated.get(file.path)
            if existing is None or key > existing[0]:
                latest_by_path_dated[file.path] = (key, file.id)

        return {file_id for _, file_id in latest_by_path_dated.values()}

    # Test helper methods
    def add(self, file: File) -> None:
        """Add a file for testing."""
        if file.id is None:
            raise ValueError("File must have an ID when using add()")
        self._files[file.id] = file

    def clear(self) -> None:
        """Clear all files."""
        self._files.clear()


class InMemoryRepositoryRepository(RepositoryPort):
    """In-memory implementation of RepositoryPort for testing."""

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._repositories: dict[int, Repository] = {}
        self._next_id = 1

    async def save(self, repository: Repository) -> Repository:
        """Save repository to in-memory storage."""
        if repository.id is None:
            repository = Repository(
                id=self._next_id,
                name=repository.name,
                url=repository.url,
                description=repository.description,
                default_branch=repository.default_branch,
                config=repository.config,
                created_at=repository.created_at,
                updated_at=repository.updated_at,
            )
            self._next_id += 1
        assert repository.id is not None, "Repository must have an ID after assignment"
        self._repositories[repository.id] = repository
        return repository

    async def find_by_id(self, repository_id: int) -> Repository | None:
        """Find repository by ID."""
        return self._repositories.get(repository_id)

    async def find_by_ids(self, repository_ids: list[int]) -> list[Repository]:
        """Find multiple repositories by IDs."""
        return [
            repo
            for rid in repository_ids
            if (repo := self._repositories.get(rid)) is not None
        ]

    async def find_by_name(self, name: str) -> Repository | None:
        """Find repository by name."""
        for repo in self._repositories.values():
            if repo.name == name:
                return repo
        return None

    async def list_all(self) -> list[Repository]:
        """List all repositories."""
        return list(self._repositories.values())

    async def update(self, repository: Repository) -> Repository:
        """Update repository."""
        if repository.id in self._repositories:
            self._repositories[repository.id] = repository
            return repository
        raise ValueError(f"Repository {repository.id} not found")

    async def delete(self, repository_id: int) -> bool:
        """Delete repository."""
        if repository_id in self._repositories:
            del self._repositories[repository_id]
            return True
        return False

    async def get_or_create(
        self,
        name: str,
        url: str | None = None,
        description: str | None = None,
        default_branch: str | None = None,
    ) -> tuple[Repository, bool]:
        """Get existing repository by name, or create if not exists."""
        # Check if exists
        existing = await self.find_by_name(name)
        if existing is not None:
            return existing, False

        # Create new (use defaults for required fields)
        new_repo = Repository(
            id=self._next_id,
            name=name,
            url=url or "",  # Repository requires non-None url
            description=description,
            default_branch=default_branch or "main",
        )
        self._repositories[self._next_id] = new_repo
        self._next_id += 1
        return new_repo, True

    def clear(self) -> None:
        """Clear all repositories."""
        self._repositories.clear()

    def add(self, repository: Repository) -> None:
        """Add a repository for testing (convenience method)."""
        if repository.id is not None:
            self._repositories[repository.id] = repository
        else:
            # Auto-assign ID
            new_repo = Repository(
                id=self._next_id,
                name=repository.name,
                url=repository.url,
                description=repository.description,
                default_branch=repository.default_branch,
                config=repository.config,
                created_at=repository.created_at,
                updated_at=repository.updated_at,
            )
            self._repositories[self._next_id] = new_repo
            self._next_id += 1


class InMemoryCommitRepository(CommitRepositoryPort):
    """In-memory implementation of CommitRepositoryPort for testing.

    Branch information is stored in a separate _branch_commits dict,
    matching the production junction table approach.
    """

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._commits: dict[int, Commit] = {}
        # branch_commits: maps (repository_id, branch, commit_id) -> True
        self._branch_commits: dict[tuple[int, str, int], bool] = {}
        self._next_id = 1

    async def save(self, commit: Commit) -> Commit:
        """Save commit to in-memory storage."""
        if commit.id is None:
            from inxr2.domain.value_objects import CommitHash

            # Design note: Only essential data is stored. Author info, message,
            # and parent hashes are queried from git on-demand.
            commit = Commit(
                id=self._next_id,
                repository_id=commit.repository_id,
                commit_hash=(
                    commit.commit_hash
                    if isinstance(commit.commit_hash, CommitHash)
                    else CommitHash(commit.commit_hash)
                ),
                author_date=commit.author_date,
                commit_date=commit.commit_date,
                indexed_at=commit.indexed_at,
            )
            self._next_id += 1
        assert commit.id is not None, "Commit must have an ID after assignment"
        self._commits[commit.id] = commit
        return commit

    async def save_many(self, commits: list[Commit]) -> list[Commit]:
        """Save multiple commits."""
        result = []
        for commit in commits:
            saved = await self.save(commit)
            result.append(saved)
        return result

    def add(self, commit: Commit) -> None:
        """Synchronous add for test setup (like InMemoryFileRepository.add)."""
        from inxr2.domain.value_objects import CommitHash

        if commit.id is None:
            commit = Commit(
                id=self._next_id,
                repository_id=commit.repository_id,
                commit_hash=(
                    commit.commit_hash
                    if isinstance(commit.commit_hash, CommitHash)
                    else CommitHash(commit.commit_hash)
                ),
                author_date=commit.author_date,
                commit_date=commit.commit_date,
                indexed_at=commit.indexed_at,
            )
            self._next_id += 1
        else:
            self._next_id = max(self._next_id, commit.id + 1)
        assert commit.id is not None
        self._commits[commit.id] = commit

    async def find_by_id(self, commit_id: int) -> Commit | None:
        """Find commit by ID."""
        return self._commits.get(commit_id)

    async def find_by_ids(self, commit_ids: list[int]) -> list[Commit]:
        """Find multiple commits by IDs."""
        return [
            commit
            for cid in commit_ids
            if (commit := self._commits.get(cid)) is not None
        ]

    async def find_by_hash(self, repository_id: int, commit_hash: str) -> Commit | None:
        """Find commit by repository and hash.

        Commits are unique per (repository_id, commit_hash).
        Supports short (prefix) commit hashes — when the provided hash
        is shorter than 40 characters, uses prefix matching.
        """
        is_prefix = len(commit_hash) < 40
        matches: list[Commit] = []
        for commit in self._commits.values():
            if commit.repository_id != repository_id:
                continue
            if is_prefix:
                if commit.commit_hash.value.startswith(commit_hash):
                    matches.append(commit)
            else:
                if commit.commit_hash.value == commit_hash:
                    return commit
        # For prefix matches, return only if exactly one match (ambiguous = None)
        if len(matches) == 1:
            return matches[0]
        return None

    async def link_commit_to_branch(
        self, repository_id: int, commit_id: int, branch: str
    ) -> None:
        """Link an existing commit to a branch.

        Idempotent - if the link already exists, does nothing.
        """
        key = (repository_id, branch, commit_id)
        self._branch_commits[key] = True

    async def link_commit_to_branches(
        self, repository_id: int, commit_id: int, branches: list[str]
    ) -> None:
        """Link an existing commit to multiple branches."""
        for branch in branches:
            await self.link_commit_to_branch(repository_id, commit_id, branch)

    async def get_branches_for_commit(self, commit_id: int) -> list[str]:
        """Get all branches that contain a specific commit."""
        branches = []
        for (_repo_id, branch, cid), _ in self._branch_commits.items():
            if cid == commit_id:
                branches.append(branch)
        return branches

    async def get_branches_for_commits(
        self, commit_ids: list[int]
    ) -> dict[int, list[str]]:
        """Get branches for multiple commits in a single query."""
        result: dict[int, list[str]] = {cid: [] for cid in commit_ids}
        for (_repo_id, branch, cid), _ in self._branch_commits.items():
            if cid in result:
                result[cid].append(branch)
        return result

    async def list_by_repository(
        self, repository_id: int, branch: str | None = None, limit: int = 100
    ) -> list[Commit]:
        """List commits for a repository, optionally filtered by branch."""
        commits = [
            c for c in self._commits.values() if c.repository_id == repository_id
        ]
        if branch:
            # Filter by branch via the branch_commits mapping
            branch_commit_ids = {
                cid
                for (repo_id, b, cid), _ in self._branch_commits.items()
                if repo_id == repository_id and b == branch
            }
            commits = [c for c in commits if c.id in branch_commit_ids]
        # Sort by commit date descending
        commits.sort(key=lambda c: c.commit_date, reverse=True)
        return commits[:limit]

    async def find_latest_by_branch(
        self, repository_id: int, branch: str
    ) -> Commit | None:
        """Find the latest indexed commit for a specific branch."""
        # Get commit IDs on this branch
        branch_commit_ids = {
            cid
            for (repo_id, b, cid), _ in self._branch_commits.items()
            if repo_id == repository_id and b == branch
        }

        commits = [
            c
            for c in self._commits.values()
            if c.repository_id == repository_id and c.id in branch_commit_ids
        ]
        if not commits:
            return None
        # Sort by commit date descending and return the first (latest)
        commits.sort(key=lambda c: c.commit_date, reverse=True)
        return commits[0]

    def clear(self) -> None:
        """Clear all commits and branch links."""
        self._commits.clear()
        self._branch_commits.clear()

    # Test helper methods
    def get_all_commits(self) -> list[Commit]:
        """Get all commits (for testing and internal use)."""
        return list(self._commits.values())


class InMemoryReferenceRepository(ReferenceRepositoryPort):
    """In-memory implementation of ReferenceRepositoryPort for testing.

    For resolve_unlinked_references, this fake requires a symbol_repository
    to be provided so it can match references to symbols.

    For branch filtering, this fake requires a commit_repo and file_repo
    to be provided.

    Example:
        symbol_repo = InMemorySymbolRepository()
        file_repo = InMemoryFileRepository()
        commit_repo = InMemoryCommitRepository()
        ref_repo = InMemoryReferenceRepository(
            symbol_repo=symbol_repo, file_repo=file_repo, commit_repo=commit_repo
        )
        ref_repo.add(Reference(...))
        count = await ref_repo.resolve_unlinked_references(repository_id=1)
    """

    def __init__(
        self,
        symbol_repo: "InMemorySymbolRepository | None" = None,
        file_repo: "InMemoryFileRepository | None" = None,
        commit_repo: "InMemoryCommitRepository | None" = None,
    ) -> None:
        """Initialize with empty storage.

        Args:
            symbol_repo: Optional symbol repository for resolving references.
                        Required for resolve_unlinked_references to work properly.
            file_repo: Optional file repository for language-aware resolution.
                      When provided, enables same-file and same-language priority.
            commit_repo: Optional commit repository for branch filtering.
                        Required for branch parameter to work in find_references_*.
        """
        self._references: dict[int, Reference] = {}
        self._next_id = 1
        self._symbol_repo = symbol_repo
        self._file_repo = file_repo
        self._commit_repo = commit_repo

    async def save(self, reference: Reference) -> Reference:
        """Save reference to in-memory storage."""
        if reference.id is None:
            # Create a new reference with an assigned ID
            # Since Reference is frozen, we need to create a new instance
            reference = Reference(
                id=self._next_id,
                repository_id=reference.repository_id,
                commit_id=reference.commit_id,
                source_file_id=reference.source_file_id,
                source_line=reference.source_line,
                source_column=reference.source_column,
                source_end_column=reference.source_end_column,
                reference_text=reference.reference_text,
                reference_type=reference.reference_type,
                target_symbol_id=reference.target_symbol_id,
                target_repository_id=reference.target_repository_id,
                is_definition=reference.is_definition,
                is_write=reference.is_write,
                resolution_confidence=reference.resolution_confidence,
                metadata=reference.metadata,
                indexed_at=reference.indexed_at,
            )
            self._next_id += 1
        assert reference.id is not None, "Reference must have an ID after assignment"
        self._references[reference.id] = reference
        return reference

    async def save_many(self, references: list[Reference]) -> list[Reference]:
        """Bulk save references."""
        result = []
        for ref in references:
            saved = await self.save(ref)
            result.append(saved)
        return result

    async def find_by_id(self, reference_id: int) -> Reference | None:
        """Find reference by ID."""
        return self._references.get(reference_id)

    async def find_references_to_symbol(
        self,
        symbol_id: int,
        limit: int = 100,
        commit_id: int | None = None,
        branch: str | None = None,
    ) -> list[Reference]:
        """Find all references to a symbol.

        Args:
            symbol_id: The target symbol ID
            limit: Maximum number of results
            commit_id: Filter by specific commit for time travel (optional)
            branch: Filter by branch name (only show refs from files on this branch)

        When commit_id and branch are both None and file_repo is available,
        filters to only refs from the latest version of each file
        (matching Postgres behavior).
        """
        refs = [r for r in self._references.values() if r.target_symbol_id == symbol_id]
        if commit_id is not None:
            refs = [r for r in refs if r.commit_id == commit_id]

        # Apply branch filter if specified
        if (
            branch is not None
            and self._commit_repo is not None
            and self._file_repo is not None
        ):
            # Get commit IDs on this branch
            branch_commit_ids: set[int] = set()
            for ref in refs:
                # Get repository_id from file
                file = self._file_repo._files.get(ref.source_file_id)
                if file is not None:
                    for (
                        repo_id,
                        b,
                        cid,
                    ), _ in self._commit_repo._branch_commits.items():
                        if repo_id == file.repository_id and b == branch:
                            branch_commit_ids.add(cid)
                    break  # Only need to get branch commits once

            # Filter refs to only those whose source file is on this branch
            filtered_refs = []
            for ref in refs:
                file = self._file_repo._files.get(ref.source_file_id)
                if file is not None and file.commit_id in branch_commit_ids:
                    filtered_refs.append(ref)
            refs = filtered_refs
        elif commit_id is None and self._file_repo is not None:
            # Default mode: filter to latest file versions (matches Postgres)
            inferred_repo_id = self._get_repo_id_from_refs(refs)
            if inferred_repo_id is not None:
                latest_ids = self._file_repo._compute_latest_file_ids(inferred_repo_id)
                refs = [r for r in refs if r.source_file_id in latest_ids]

        refs.sort(key=lambda r: (r.source_file_id, r.source_line))
        return refs[:limit]

    async def list_by_file(self, file_id: int) -> list[Reference]:
        """List all references in a file."""
        refs = [r for r in self._references.values() if r.source_file_id == file_id]
        refs.sort(key=lambda r: (r.source_line, r.source_column))
        return refs

    async def find_references_by_text(
        self,
        text: str,
        repository_id: int,
        limit: int = 100,
        commit_id: int | None = None,
        branch: str | None = None,
    ) -> list[Reference]:
        """Find references by text.

        Args:
            text: The reference text to match
            repository_id: Filter by repository
            limit: Maximum number of results
            commit_id: Filter by specific commit for time travel (optional)
            branch: Filter by branch name (only show refs from files on this branch)

        When commit_id and branch are both None and file_repo is available,
        filters to only refs from the latest version of each file
        (matching Postgres behavior).
        """
        refs = [
            r
            for r in self._references.values()
            if r.reference_text == text and r.repository_id == repository_id
        ]
        if commit_id is not None:
            refs = [r for r in refs if r.commit_id == commit_id]

        # Apply branch filter if specified
        if (
            branch is not None
            and self._commit_repo is not None
            and self._file_repo is not None
        ):
            # Get commit IDs on this branch
            branch_commit_ids: set[int] = set()
            for (repo_id, b, cid), _ in self._commit_repo._branch_commits.items():
                if repo_id == repository_id and b == branch:
                    branch_commit_ids.add(cid)

            # Filter refs to only those whose source file is on this branch
            filtered_refs = []
            for ref in refs:
                file = self._file_repo._files.get(ref.source_file_id)
                if file is not None and file.commit_id in branch_commit_ids:
                    filtered_refs.append(ref)
            refs = filtered_refs
        elif commit_id is None and self._file_repo is not None:
            # Default mode: filter to latest file versions (matches Postgres)
            latest_ids = self._file_repo._compute_latest_file_ids(repository_id)
            refs = [r for r in refs if r.source_file_id in latest_ids]

        refs.sort(key=lambda r: (r.source_file_id, r.source_line))
        return refs[:limit]

    async def count_by_repository(self, repository_id: int) -> int:
        """Count references for a repository."""
        return len(
            [r for r in self._references.values() if r.repository_id == repository_id]
        )

    async def delete_by_file(self, file_id: int) -> int:
        """Delete all references for a file."""
        to_delete = [
            ref_id
            for ref_id, ref in self._references.items()
            if ref.source_file_id == file_id
        ]
        for ref_id in to_delete:
            del self._references[ref_id]
        return len(to_delete)

    async def count_unresolved_references(self, repository_id: int) -> int:
        """Count references that don't have a target_symbol_id set."""
        return len(
            [
                r
                for r in self._references.values()
                if r.repository_id == repository_id and r.target_symbol_id is None
            ]
        )

    async def resolve_references_batch(
        self,
        repository_id: int,
        batch_size: int = 1000,
        commit_aware: bool = False,
    ) -> int:
        """Resolve a batch of unlinked references.

        Resolution priority (matches real implementation):
        1. Same file - most likely the correct local symbol
        2. Same language - cross-file but same language preferred
        3. Lowest symbol ID - deterministic tiebreaker for consistency

        This matches the real DB implementation which only selects refs
        that have a matching symbol (via JOIN), so batch_size limits
        the number of resolvable refs processed, not just examined.
        """
        if self._symbol_repo is None:
            return 0

        resolved_count = 0
        updated_refs: dict[int, Reference] = {}

        for ref_id, ref in self._references.items():
            # Stop when we've resolved batch_size refs
            if resolved_count >= batch_size:
                break

            # Skip if already resolved or wrong repository
            if ref.target_symbol_id is not None or ref.repository_id != repository_id:
                continue

            # Find all matching symbols
            candidates: list[Symbol] = []
            for symbol in self._symbol_repo.get_all_symbols():
                if (
                    symbol.repository_id == repository_id
                    and symbol.name == ref.reference_text
                ):
                    if commit_aware:
                        if symbol.commit_id == ref.commit_id:
                            candidates.append(symbol)
                    else:
                        candidates.append(symbol)

            if not candidates:
                continue

            # Pick best match using priority: same-file, same-language, lowest ID
            matching_symbol = self._pick_best_symbol(ref, candidates)

            if matching_symbol is not None and matching_symbol.id is not None:
                updated_refs[ref_id] = Reference(
                    id=ref.id,
                    repository_id=ref.repository_id,
                    commit_id=ref.commit_id,
                    source_file_id=ref.source_file_id,
                    source_line=ref.source_line,
                    source_column=ref.source_column,
                    source_end_column=ref.source_end_column,
                    reference_text=ref.reference_text,
                    reference_type=ref.reference_type,
                    target_symbol_id=matching_symbol.id,
                    target_repository_id=ref.target_repository_id,
                    is_definition=ref.is_definition,
                    is_write=ref.is_write,
                    resolution_confidence=ref.resolution_confidence,
                    metadata=ref.metadata,
                    indexed_at=ref.indexed_at,
                )
                resolved_count += 1

        self._references.update(updated_refs)
        return resolved_count

    def _get_repo_id_from_refs(self, refs: list[Reference]) -> int | None:
        """Get repository_id directly from references.

        Used by find_references_to_symbol which doesn't take repository_id directly.
        """
        if not refs:
            return None
        return refs[0].repository_id

    def _pick_best_symbol(
        self, ref: Reference, candidates: list[Symbol]
    ) -> Symbol | None:
        """Pick the best matching symbol using priority rules.

        Priority:
        1. Same file (file_id matches)
        2. Same language (requires file_repo)
        3. Lowest symbol ID (deterministic tiebreaker)
        """
        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0]

        # Get reference file language if file_repo is available
        ref_file_language: str | None = None
        if self._file_repo is not None:
            for file in self._file_repo._files.values():
                if file.id == ref.source_file_id:
                    ref_file_language = file.language
                    break

        def sort_key(symbol: Symbol) -> tuple[int, int, int]:
            # Lower values = higher priority
            same_file = 0 if symbol.file_id == ref.source_file_id else 1

            # Same language check (requires file_repo)
            same_language = 1  # Default: not same language
            if self._file_repo is not None and ref_file_language is not None:
                for file in self._file_repo._files.values():
                    if file.id == symbol.file_id:
                        if file.language == ref_file_language:
                            same_language = 0
                        break

            symbol_id = symbol.id if symbol.id is not None else 999999
            return (same_file, same_language, symbol_id)

        candidates.sort(key=sort_key)
        return candidates[0]

    async def resolve_unlinked_references(
        self, repository_id: int, commit_aware: bool = False
    ) -> int:
        """Resolve references to their target symbols.

        This fake implementation matches references to symbols by name.
        Requires symbol_repo to be set for proper functionality.

        Uses the same priority logic as resolve_references_batch:
        1. Same file - most likely the correct local symbol
        2. Same language - cross-file but same language preferred
        3. Lowest symbol ID - deterministic tiebreaker for consistency
        """
        if self._symbol_repo is None:
            # Without a symbol repo, we can't resolve anything
            return 0

        resolved_count = 0
        updated_refs: dict[int, Reference] = {}

        for ref_id, ref in self._references.items():
            # Skip if already resolved or wrong repository
            if ref.target_symbol_id is not None or ref.repository_id != repository_id:
                continue

            # Find all matching symbols
            candidates: list[Symbol] = []
            for symbol in self._symbol_repo.get_all_symbols():
                if (
                    symbol.repository_id == repository_id
                    and symbol.name == ref.reference_text
                ):
                    if commit_aware:
                        # Only match if same commit
                        if symbol.commit_id == ref.commit_id:
                            candidates.append(symbol)
                    else:
                        candidates.append(symbol)

            # Pick best match using priority: same-file, same-language, lowest ID
            matching_symbol = self._pick_best_symbol(ref, candidates)

            if matching_symbol is not None and matching_symbol.id is not None:
                # Create updated reference with target_symbol_id set
                updated_refs[ref_id] = Reference(
                    id=ref.id,
                    repository_id=ref.repository_id,
                    commit_id=ref.commit_id,
                    source_file_id=ref.source_file_id,
                    source_line=ref.source_line,
                    source_column=ref.source_column,
                    source_end_column=ref.source_end_column,
                    reference_text=ref.reference_text,
                    reference_type=ref.reference_type,
                    target_symbol_id=matching_symbol.id,
                    target_repository_id=ref.target_repository_id,
                    is_definition=ref.is_definition,
                    is_write=ref.is_write,
                    resolution_confidence=ref.resolution_confidence,
                    metadata=ref.metadata,
                    indexed_at=ref.indexed_at,
                )
                resolved_count += 1

        # Apply updates
        self._references.update(updated_refs)
        return resolved_count

    async def copy_references_to_file(
        self,
        source_file_id: int,
        target_file_id: int,
        target_commit_id: int,
        target_repository_id: int,
        symbol_id_mapping: dict[int, int] | None = None,
    ) -> int:
        """Copy all references from source file to target file."""
        source_refs = [
            r for r in self._references.values() if r.source_file_id == source_file_id
        ]
        if not source_refs:
            return 0

        for source in source_refs:
            # Remap target_symbol_id if mapping is available
            old_target = source.target_symbol_id
            if symbol_id_mapping and old_target and old_target in symbol_id_mapping:
                new_target_symbol_id = symbol_id_mapping[old_target]
            else:
                new_target_symbol_id = None

            new_ref = Reference(
                id=self._next_id,
                repository_id=target_repository_id,
                commit_id=target_commit_id,
                source_file_id=target_file_id,
                source_line=source.source_line,
                source_column=source.source_column,
                source_end_column=source.source_end_column,
                reference_text=source.reference_text,
                reference_type=source.reference_type,
                target_symbol_id=new_target_symbol_id,
                target_repository_id=None,
                is_definition=source.is_definition,
                is_write=source.is_write,
                resolution_confidence=source.resolution_confidence,
                metadata=source.metadata,
            )
            self._references[self._next_id] = new_ref
            self._next_id += 1

        return len(source_refs)

    # Test helper methods
    def add(self, reference: Reference) -> None:
        """Add a reference for testing."""
        if reference.id is not None:
            self._references[reference.id] = reference
        else:
            # Auto-assign ID
            new_ref = Reference(
                id=self._next_id,
                repository_id=reference.repository_id,
                commit_id=reference.commit_id,
                source_file_id=reference.source_file_id,
                source_line=reference.source_line,
                source_column=reference.source_column,
                source_end_column=reference.source_end_column,
                reference_text=reference.reference_text,
                reference_type=reference.reference_type,
                target_symbol_id=reference.target_symbol_id,
                target_repository_id=reference.target_repository_id,
                is_definition=reference.is_definition,
                is_write=reference.is_write,
                resolution_confidence=reference.resolution_confidence,
                metadata=reference.metadata,
                indexed_at=reference.indexed_at,
            )
            self._references[self._next_id] = new_ref
            self._next_id += 1

    def clear(self) -> None:
        """Clear all references."""
        self._references.clear()


class InMemoryTextContentRepository(TextContentRepositoryPort):
    """In-memory implementation of TextContentRepositoryPort for testing."""

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._text_contents: dict[int, TextContent] = {}
        self._next_id = 1

    async def save(self, text_content: TextContent) -> TextContent:
        """Save text content to in-memory storage."""
        if text_content.id is None:
            text_content = TextContent(
                id=self._next_id,
                repository_id=text_content.repository_id,
                commit_id=text_content.commit_id,
                source_type=text_content.source_type,
                content=text_content.content,
                source_file_id=text_content.source_file_id,
                source_line=text_content.source_line,
                source_end_line=text_content.source_end_line,
                language=text_content.language,
                content_type=text_content.content_type,
                indexed_at=text_content.indexed_at,
            )
            self._next_id += 1
        assert (
            text_content.id is not None
        ), "TextContent must have an ID after assignment"
        self._text_contents[text_content.id] = text_content
        return text_content

    async def save_batch(self, text_contents: list[TextContent]) -> list[TextContent]:
        """Bulk save text contents."""
        result = []
        for tc in text_contents:
            saved = await self.save(tc)
            result.append(saved)
        return result

    async def delete_by_commit(self, commit_id: int) -> int:
        """Delete all text contents for a commit."""
        to_delete = [
            tc_id
            for tc_id, tc in self._text_contents.items()
            if tc.commit_id == commit_id
        ]
        for tc_id in to_delete:
            del self._text_contents[tc_id]
        return len(to_delete)

    async def delete_by_file(self, file_id: int) -> int:
        """Delete all text contents for a file."""
        to_delete = [
            tc_id
            for tc_id, tc in self._text_contents.items()
            if tc.source_file_id == file_id
        ]
        for tc_id in to_delete:
            del self._text_contents[tc_id]
        return len(to_delete)

    # Test helper methods
    def get_all(self) -> list[TextContent]:
        """Get all text contents (for testing)."""
        return list(self._text_contents.values())

    def find_by_repository(self, repository_id: int) -> list[TextContent]:
        """Find text contents by repository (for testing)."""
        return [
            tc
            for tc in self._text_contents.values()
            if tc.repository_id == repository_id
        ]

    def clear(self) -> None:
        """Clear all text contents."""
        self._text_contents.clear()


class InMemoryIndexStatusRepository(IndexStatusRepositoryPort):
    """In-memory implementation of IndexStatusRepositoryPort for testing."""

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._statuses: dict[int, IndexStatus] = {}
        self._next_id = 1

    async def save(self, status: IndexStatus) -> IndexStatus:
        """Save index status to in-memory storage."""
        if status.id is None:
            status = IndexStatus(
                id=self._next_id,
                repository_id=status.repository_id,
                branch=status.branch,
                indexing_status=status.indexing_status,
                last_indexed_commit=status.last_indexed_commit,
                oldest_indexed_commit=status.oldest_indexed_commit,
                last_indexed_at=status.last_indexed_at,
                indexing_started_at=status.indexing_started_at,
                total_commits_indexed=status.total_commits_indexed,
                total_files_indexed=status.total_files_indexed,
                total_symbols_indexed=status.total_symbols_indexed,
                total_references_indexed=status.total_references_indexed,
                error_message=status.error_message,
                error_count=status.error_count,
                indexer_version=status.indexer_version,
                metadata=status.metadata,
                created_at=status.created_at,
                updated_at=status.updated_at,
            )
            self._next_id += 1
        assert status.id is not None, "IndexStatus must have an ID after assignment"
        self._statuses[status.id] = status
        return status

    async def find_by_repository_and_branch(
        self, repository_id: int, branch: str
    ) -> IndexStatus | None:
        """Find index status for a repository/branch combination."""
        for status in self._statuses.values():
            if status.repository_id == repository_id and status.branch == branch:
                return status
        return None

    async def list_by_repository(self, repository_id: int) -> list[IndexStatus]:
        """List all index statuses for a repository (all branches)."""
        return [s for s in self._statuses.values() if s.repository_id == repository_id]

    # Test helper methods
    def add(self, status: IndexStatus) -> None:
        """Add an index status for testing."""
        if status.id is not None:
            self._statuses[status.id] = status
        else:
            new_status = IndexStatus(
                id=self._next_id,
                repository_id=status.repository_id,
                branch=status.branch,
                indexing_status=status.indexing_status,
                last_indexed_commit=status.last_indexed_commit,
                oldest_indexed_commit=status.oldest_indexed_commit,
                last_indexed_at=status.last_indexed_at,
                indexing_started_at=status.indexing_started_at,
                total_commits_indexed=status.total_commits_indexed,
                total_files_indexed=status.total_files_indexed,
                total_symbols_indexed=status.total_symbols_indexed,
                total_references_indexed=status.total_references_indexed,
                error_message=status.error_message,
                error_count=status.error_count,
                indexer_version=status.indexer_version,
                metadata=status.metadata,
                created_at=status.created_at,
                updated_at=status.updated_at,
            )
            self._statuses[self._next_id] = new_status
            self._next_id += 1

    def clear(self) -> None:
        """Clear all statuses."""
        self._statuses.clear()


# ============================================================================
# Service Test Doubles
# ============================================================================


class FakeFileSystem(FileSystemPort):
    """
    In-memory file system implementation for testing.

    Allows tests to set up virtual files without touching the real file system.
    Useful for pure unit tests of use cases that depend on file I/O.

    Example:
        fs = FakeFileSystem()
        fs.add_file("/project/main.py", b"print('hello')")
        fs.add_file("/project/utils.py", b"def helper(): pass")
        content = fs.read_text("/project/main.py")
    """

    def __init__(self) -> None:
        """Initialize with empty virtual file system."""
        self._files: dict[str, bytes] = {}
        self._directories: set[str] = set()

    def walk_directory(
        self,
        path: str | Path,
        skip_dirs: set[str] | None = None,
        skip_hidden: bool = True,
    ) -> list[Path]:
        """Walk virtual directory and return file paths."""
        skip_dirs = skip_dirs or set()
        path_str = str(path).rstrip("/")
        result: list[Path] = []

        for file_path in self._files:
            # Check if file is under the given path (must be exact prefix + /)
            # This prevents /project from matching /project2/file.txt
            if not (file_path.startswith(path_str + "/") or file_path == path_str):
                continue

            # Get the relative part
            relative = file_path[len(path_str) :].lstrip("/")
            if not relative:
                continue

            # Check for skip conditions
            parts = relative.split("/")

            # Skip hidden files/dirs
            if skip_hidden and any(p.startswith(".") for p in parts):
                continue

            # Skip excluded directories
            skip = False
            for part in parts[:-1]:  # Exclude filename
                if part in skip_dirs:
                    skip = True
                    break
            if skip:
                continue

            result.append(Path(file_path))

        return result

    def stat(self, path: str | Path) -> FileStat:
        """Get file statistics for virtual file."""
        path_str = str(path)
        if path_str in self._files:
            return FileStat(
                size_bytes=len(self._files[path_str]),
                is_file=True,
                is_dir=False,
            )
        if path_str in self._directories:
            return FileStat(
                size_bytes=0,
                is_file=False,
                is_dir=True,
            )
        raise FileNotFoundError(f"No such file or directory: {path}")

    def read_bytes(self, path: str | Path) -> bytes:
        """Read virtual file as bytes."""
        path_str = str(path)
        if path_str not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        return self._files[path_str]

    def read_text(
        self, path: str | Path, encoding: str = "utf-8", errors: str = "strict"
    ) -> str:
        """Read virtual file as text."""
        content = self.read_bytes(path)
        return content.decode(encoding, errors=errors)

    def relative_path(self, path: str | Path, base: str | Path) -> str:
        """Get path relative to base."""
        path_str = str(path)
        base_str = str(base).rstrip("/")
        if path_str.startswith(base_str):
            rel = path_str[len(base_str) :].lstrip("/")
            return rel if rel else "."
        return path_str

    def exists(self, path: str | Path) -> bool:
        """Check if virtual path exists."""
        path_str = str(path)
        return path_str in self._files or path_str in self._directories

    @contextmanager
    def open_binary(self, path: str | Path) -> Iterator[BinaryIO]:
        """Open virtual file for binary reading as a context manager."""
        content = self.read_bytes(path)
        yield BytesIO(content)

    # Test helper methods
    def add_file(self, path: str, content: bytes | str) -> None:
        """Add a virtual file.

        Args:
            path: Absolute path for the virtual file
            content: File content (str will be encoded as UTF-8)
        """
        if isinstance(content, str):
            content = content.encode("utf-8")
        self._files[path] = content

        # Ensure parent directories exist
        parts = path.split("/")
        for i in range(1, len(parts)):
            dir_path = "/".join(parts[:i])
            if dir_path:
                self._directories.add(dir_path)

    def add_directory(self, path: str) -> None:
        """Add a virtual directory."""
        self._directories.add(path)

    def clear(self) -> None:
        """Clear all virtual files and directories."""
        self._files.clear()
        self._directories.clear()


class StubParserService(ParserServicePort):
    """
    Stub implementation of ParserServicePort for testing.

    A stub returns predefined responses. Useful when you need to
    control exactly what the parser returns in tests.

    Example:
        parser = StubParserService()
        parser.set_symbols_for_file("main.py", [Symbol(...), Symbol(...)])
        symbols = await parser.parse_file(Path("main.py"), "python")
    """

    def __init__(self) -> None:
        """Initialize with empty responses."""
        self._responses: dict[str, list[Symbol]] = {}

    async def parse_file(self, file_path: Path, language: str) -> list[Symbol]:
        """Return predefined symbols for the file."""
        key = str(file_path)
        return self._responses.get(key, [])

    # Test helper methods
    def set_symbols_for_file(self, file_path: str, symbols: list[Symbol]) -> None:
        """Set what symbols should be returned for a file."""
        self._responses[file_path] = symbols

    def clear(self) -> None:
        """Clear all predefined responses."""
        self._responses.clear()


class FakeGitService(GitServicePort):
    """
    Fake implementation of GitServicePort for testing.

    Provides configurable git operation responses with typed return values.

    Example:
        from inxr2.application.ports.services import CommitInfo, ChangedFiles

        git = FakeGitService()
        info = git.get_repository_info(Path("/repo"))
        assert info.current_branch == "main"
    """

    def __init__(self, commits: list[CommitInfo] | None = None) -> None:
        """Initialize with test commits.

        Args:
            commits: List of CommitInfo objects. If None, provides sensible defaults.
        """
        self.commits: list[CommitInfo] = (
            list(commits)
            if commits
            else [
                CommitInfo(
                    hash="abc123",
                    short_hash="abc123",
                    author_name="Test User",
                    author_email="test@example.com",
                    author_date=datetime(2024, 1, 1, 0, 0, 0),
                    committer_name="Test User",
                    committer_email="test@example.com",
                    commit_date=datetime(2024, 1, 1, 0, 0, 0),
                    message="Initial commit",
                    parent_hashes=[],
                ),
                CommitInfo(
                    hash="def456",
                    short_hash="def456",
                    author_name="Test User",
                    author_email="test@example.com",
                    author_date=datetime(2024, 1, 2, 0, 0, 0),
                    committer_name="Test User",
                    committer_email="test@example.com",
                    commit_date=datetime(2024, 1, 2, 0, 0, 0),
                    message="Add feature",
                    parent_hashes=["abc123"],
                ),
            ]
        )
        self.files_in_commit: dict[str, list[str]] = {
            "abc123": ["src/main.py", "src/utils.py"],
            "def456": ["src/main.py", "src/utils.py", "src/new_file.py"],
        }
        self.changed_files_in_commit: dict[str, ChangedFiles] = {
            "abc123": ChangedFiles(
                added=["src/main.py", "src/utils.py"],
                modified=[],
                deleted=[],
            ),
            "def456": ChangedFiles(
                added=["src/new_file.py"],
                modified=[],
                deleted=[],
            ),
        }
        self._file_contents: dict[tuple[str, str, str], str] = {}
        # Tracking for test verification
        self._list_branch_commits_called = False
        self._list_branch_commits_args: dict[str, str] = {}

    def get_repository_info(self, repo_path: Path) -> RepositoryInfo:
        return RepositoryInfo(
            name=repo_path.name,
            url=str(repo_path),
            current_branch="main",
            is_bare=False,
        )

    def get_current_commit(self, repo_path: Path, branch: str | None = None) -> str:
        commit_hash: str = self.commits[-1].hash
        return commit_hash

    def get_commit_info(self, repo_path: Path, commit_hash: str) -> CommitInfo:
        for commit in self.commits:
            if commit.hash == commit_hash:
                return commit
        return self.commits[-1]

    def list_commits(
        self,
        repo_path: Path,
        branch: str,
        max_count: int | None = 1000,
        since_days: int | None = None,
    ) -> list[CommitInfo]:
        commits = self.commits.copy()
        if max_count:
            commits = commits[:max_count]
        return commits

    def list_branch_commits(
        self,
        repo_path: Path,
        branch: str,
        base_branch: str,
        max_count: int | None = 1000,
        since_days: int | None = None,
    ) -> list[CommitInfo]:
        self._list_branch_commits_called = True
        self._list_branch_commits_args = {
            "branch": branch,
            "base_branch": base_branch,
        }
        if self.commits:
            return [self.commits[-1]]
        return []

    def list_files(
        self,
        repo_path: Path,
        commit_hash: str,
        patterns: list[str] | None = None,
    ) -> list[str]:
        return self.files_in_commit.get(commit_hash, [])

    def get_changed_files_in_commit(
        self, repo_path: Path, commit_hash: str
    ) -> ChangedFiles:
        return self.changed_files_in_commit.get(
            commit_hash,
            ChangedFiles(added=[], modified=[], deleted=[]),
        )

    def get_file_content(
        self, repo_path: Path, commit_hash: str, file_path: str
    ) -> str:
        key = (str(repo_path), commit_hash, file_path)
        if key in self._file_contents:
            return self._file_contents[key]
        return f"# Content of {file_path} at {commit_hash}\nprint('hello')"

    def list_branches(self, repo_path: Path) -> list[str]:
        return ["main"]

    # Test helper methods
    def set_file_content(
        self, repo_path: str, commit_hash: str, file_path: str, content: str
    ) -> None:
        """Set what content should be returned for a file."""
        key = (repo_path, commit_hash, file_path)
        self._file_contents[key] = content

    def clear(self) -> None:
        """Clear all predefined responses."""
        self._file_contents.clear()


class FakePlaintextParser(PlaintextParserPort):
    """Fake plaintext parser for testing.

    Supports a configurable set of file extensions and returns
    a single chunk containing the full content.

    Example:
        parser = FakePlaintextParser()
        assert parser.supports_file("README.md")
        chunks = parser.parse("hello world", "README.md")
        assert len(chunks) == 1
    """

    def __init__(self) -> None:
        """Initialize with default supported extensions."""
        self._supported_extensions: set[str] = {
            ".md",
            ".markdown",
            ".rst",
            ".txt",
            ".yaml",
            ".yml",
            ".toml",
            ".ini",
            ".cfg",
            ".json",
            ".xml",
        }
        self._supported_filenames: set[str] = {
            "Dockerfile",
            "README",
            "LICENSE",
        }

    def supports_file(self, file_path: str) -> bool:
        """Check if this parser supports the given file."""
        path = Path(file_path)
        name = path.name

        if name in self._supported_filenames:
            return True
        if path.suffix.lower() in self._supported_extensions:
            return True
        if "dockerfile" in name.lower():
            return True
        return False

    def parse(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Parse file content into a single chunk."""
        if not content or not content.strip():
            return []
        return [
            {
                "content": content,
                "content_type": "plain_text",
                "source_line": 1,
                "source_end_line": content.count("\n") + 1,
            }
        ]


class FakeTextSearch(TextSearchPort):
    """
    Fake implementation of TextSearchPort for testing.

    This fake performs simple in-memory text matching to simulate
    the behavior of a real text search engine without needing PostgreSQL.

    Example:
        text_search = FakeTextSearch(text_content_repo)
        results, total = await text_search.search(TextSearchQuery(query="TODO"))
    """

    # Regex validation constants (match production implementation)
    MAX_REGEX_LENGTH = 500
    DANGEROUS_REGEX_PATTERNS = [
        r"\(\.\*\)\+",  # (.*)+
        r"\(\.\+\)\+",  # (.+)+
        r"\([^)]*\+\)\+",  # (x+)+ pattern
        r"\([^)]*\*\)\+",  # (x*)+
        r"\([^)]*\+\)\*",  # (x+)*
        r"\([^)]*\*\)\*",  # (x*)*
    ]

    def __init__(self, text_content_repo: InMemoryTextContentRepository):
        """Initialize with a text content repository.

        Args:
            text_content_repo: Text content repository to search in
        """
        self._text_content_repo = text_content_repo

    def _validate_regex_pattern(self, pattern: str) -> None:
        """Validate regex pattern for safety (matches production behavior).

        Args:
            pattern: The regex pattern to validate

        Raises:
            ValueError: If pattern is invalid or potentially dangerous
        """
        if len(pattern) > self.MAX_REGEX_LENGTH:
            raise ValueError(
                f"Regex pattern too long: {len(pattern)} characters "
                f"(max {self.MAX_REGEX_LENGTH})"
            )

        for dangerous in self.DANGEROUS_REGEX_PATTERNS:
            if re.search(dangerous, pattern):
                raise ValueError(
                    "Regex pattern contains potentially dangerous nested quantifiers "
                    "that could cause performance issues"
                )

        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}") from None

    async def search(
        self, query: TextSearchQuery
    ) -> tuple[list[TextSearchResult], int]:
        """Execute text search using simple in-memory matching.

        Args:
            query: Search query parameters

        Returns:
            Tuple of (results, total_count)

        Raises:
            ValueError: If query is empty
        """
        if not query.query or not query.query.strip():
            raise ValueError("Search query cannot be empty")

        # Get all text contents
        all_contents = self._text_content_repo.get_all()

        # Apply filters
        filtered = []
        for tc in all_contents:
            # Repository filter
            if (
                query.repository_id is not None
                and tc.repository_id != query.repository_id
            ):
                continue

            # Commit filter
            if query.commit_id is not None and tc.commit_id != query.commit_id:
                continue

            # Source type filter
            if query.source_types and tc.source_type not in query.source_types:
                continue

            # Language filter
            if query.languages and tc.language not in query.languages:
                continue

            # Text matching based on mode
            if query.mode == "regex":
                # Validate regex pattern (matches production behavior)
                self._validate_regex_pattern(query.query)
                # Use actual regex matching
                try:
                    if re.search(query.query, tc.content, re.IGNORECASE):
                        filtered.append(tc)
                except re.error:
                    # Should not happen after validation, but be defensive
                    pass
            else:  # keyword or phrase
                # Simple contains match for testing
                if query.query.lower() in tc.content.lower():
                    filtered.append(tc)

        # Calculate total before pagination
        total = len(filtered)

        # Sort by a simple relevance score (count of query occurrences)
        # In real implementation, this would be ts_rank
        query_lower = query.query.lower()
        scored = [(tc, tc.content.lower().count(query_lower)) for tc in filtered]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Apply pagination
        paginated = scored[query.offset : query.offset + query.limit]

        # Convert to search results
        results = [
            TextSearchResult(
                text_content=tc,
                rank=float(score),
                headline=None,  # TODO: Add simple snippet generation
            )
            for tc, score in paginated
        ]

        return results, total


# ============================================================================
# Factory Functions for Common Test Scenarios
# ============================================================================


def create_populated_symbol_repository() -> InMemorySymbolRepository:
    """
    Create a symbol repository with common test data.

    Useful for tests that need realistic symbol data without
    setting it up manually each time.
    """
    from inxr2.domain.value_objects import SymbolKind

    repo = InMemorySymbolRepository()

    # Add some common test symbols
    repo.add(
        Symbol(
            id=1,
            file_id=1,
            repository_id=1,
            commit_id=1,
            name="calculate_total",
            kind=SymbolKind.FUNCTION,
            start_line=10,
            start_column=0,
            end_line=15,
            end_column=0,
            scope="module",
        )
    )
    repo.add(
        Symbol(
            id=2,
            file_id=1,
            repository_id=1,
            commit_id=1,
            name="Calculator",
            kind=SymbolKind.CLASS,
            start_line=20,
            start_column=0,
            end_line=50,
            end_column=0,
            scope="module",
        )
    )
    repo.add(
        Symbol(
            id=3,
            file_id=1,
            repository_id=1,
            commit_id=1,
            name="add",
            kind=SymbolKind.METHOD,
            start_line=25,
            start_column=4,
            end_line=30,
            end_column=4,
            scope="module.Calculator",
        )
    )

    return repo


# ============================================================================
# Documentation: When to Use Which Pattern
# ============================================================================
#
# Test Double Patterns (from "Test Double" by Gerard Meszaros):
#
# 1. **Dummy**: Passed but never used (e.g., fill parameter lists)
#    - Use when: Interface requires parameter you don't care about
#
# 2. **Stub**: Returns predefined responses
#    - Use when: Need to control what dependencies return
#    - Example: StubParserService
#
# 3. **Fake**: Real working implementation (simpler than production)
#    - Use when: Need realistic behavior without infrastructure
#    - Example: InMemorySymbolRepository
#
# 4. **Spy**: Records how it was called (for verification)
#    - Use when: Need to verify interactions happened
#    - Prefer real assertions over spy when possible
#
# 5. **Mock** (framework): Pre-programmed with expectations
#    - Use when: ...actually, try to avoid these!
#    - Prefer fakes/stubs for cleaner, more maintainable tests
#
# In this codebase, we PREFER:
# - Fakes (InMemoryRepository) for repositories
# - Stubs (StubService) for external services
# - Real implementations whenever possible
# - Avoid mocking frameworks (unittest.mock, pytest-mock)
# ============================================================================
