"""Repository port interfaces - data access abstractions.

These are Clean Architecture ports (interfaces) that define the contract
for data access. Implementations (adapters) will use specific persistence
mechanisms like PostgreSQL.
"""

from abc import ABC, abstractmethod

from ...domain.entities import Commit, File, IndexStatus, Reference, Repository, Symbol


class RepositoryPort(ABC):
    """Port for repository entity operations."""

    @abstractmethod
    async def save(self, repository: Repository) -> Repository:
        """Save or update a repository."""
        pass

    @abstractmethod
    async def find_by_id(self, repository_id: int) -> Repository | None:
        """Find repository by ID."""
        pass

    @abstractmethod
    async def find_by_name(self, name: str) -> Repository | None:
        """Find repository by unique name."""
        pass

    @abstractmethod
    async def list_all(self) -> list[Repository]:
        """List all repositories."""
        pass

    @abstractmethod
    async def delete(self, repository_id: int) -> bool:
        """Delete repository and all related data (CASCADE)."""
        pass


class CommitRepositoryPort(ABC):
    """Port for commit entity operations."""

    @abstractmethod
    async def save(self, commit: Commit) -> Commit:
        """Save or update a commit."""
        pass

    @abstractmethod
    async def save_many(self, commits: list[Commit]) -> list[Commit]:
        """Bulk save commits for performance."""
        pass

    @abstractmethod
    async def find_by_id(self, commit_id: int) -> Commit | None:
        """Find commit by ID."""
        pass

    @abstractmethod
    async def find_by_hash(
        self, repository_id: int, commit_hash: str
    ) -> Commit | None:
        """Find commit by repository and hash."""
        pass

    @abstractmethod
    async def list_by_repository(
        self, repository_id: int, branch: str | None = None, limit: int = 100
    ) -> list[Commit]:
        """List commits for a repository, optionally filtered by branch."""
        pass


class FileRepositoryPort(ABC):
    """Port for file entity operations."""

    @abstractmethod
    async def save(self, file: File) -> File:
        """Save or update a file."""
        pass

    @abstractmethod
    async def save_many(self, files: list[File]) -> list[File]:
        """Bulk save files for performance."""
        pass

    @abstractmethod
    async def find_by_id(self, file_id: int) -> File | None:
        """Find file by ID."""
        pass

    @abstractmethod
    async def find_by_path(
        self, repository_id: int, commit_id: int, path: str
    ) -> File | None:
        """Find file by repository, commit, and path (temporal query)."""
        pass

    @abstractmethod
    async def list_by_commit(self, commit_id: int) -> list[File]:
        """List all files at a specific commit."""
        pass

    @abstractmethod
    async def list_by_repository(self, repository_id: int) -> list[File]:
        """List all files for a repository (latest version)."""
        pass

    @abstractmethod
    async def find_by_content_hash(self, content_hash: str) -> list[File]:
        """Find files with matching content hash (deduplication)."""
        pass


class SymbolRepositoryPort(ABC):
    """Port for symbol entity operations."""

    @abstractmethod
    async def save(self, symbol: Symbol) -> Symbol:
        """Save or update a symbol."""
        pass

    @abstractmethod
    async def save_many(self, symbols: list[Symbol]) -> list[Symbol]:
        """Bulk save symbols for performance."""
        pass

    @abstractmethod
    async def find_by_id(self, symbol_id: int) -> Symbol | None:
        """Find symbol by ID."""
        pass

    @abstractmethod
    async def search_by_name(
        self,
        name: str,
        repository_id: int | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> list[Symbol]:
        """Search symbols by name (supports autocomplete)."""
        pass

    @abstractmethod
    async def find_by_qualified_name(
        self, repository_id: int, qualified_name: str
    ) -> list[Symbol]:
        """Find symbols by fully qualified name."""
        pass

    @abstractmethod
    async def list_by_file(self, file_id: int) -> list[Symbol]:
        """List all symbols in a file."""
        pass

    @abstractmethod
    async def delete_by_file(self, file_id: int) -> int:
        """Delete all symbols for a file (for re-indexing). Returns count deleted."""
        pass


class ReferenceRepositoryPort(ABC):
    """Port for reference entity operations."""

    @abstractmethod
    async def save(self, reference: Reference) -> Reference:
        """Save or update a reference."""
        pass

    @abstractmethod
    async def save_many(self, references: list[Reference]) -> list[Reference]:
        """Bulk save references for performance."""
        pass

    @abstractmethod
    async def find_by_id(self, reference_id: int) -> Reference | None:
        """Find reference by ID."""
        pass

    @abstractmethod
    async def find_references_to_symbol(
        self, symbol_id: int, limit: int = 100
    ) -> list[Reference]:
        """Find all references TO a symbol (find usages)."""
        pass

    @abstractmethod
    async def list_by_file(self, file_id: int) -> list[Reference]:
        """List all references in a file."""
        pass

    @abstractmethod
    async def delete_by_file(self, file_id: int) -> int:
        """Delete all references for a file (for re-indexing). Returns count deleted."""
        pass


class IndexStatusRepositoryPort(ABC):
    """Port for index status operations."""

    @abstractmethod
    async def save(self, status: IndexStatus) -> IndexStatus:
        """Save or update index status."""
        pass

    @abstractmethod
    async def find_by_repository_and_branch(
        self, repository_id: int, branch: str
    ) -> IndexStatus | None:
        """Find index status for a repository/branch combination."""
        pass

    @abstractmethod
    async def list_by_repository(self, repository_id: int) -> list[IndexStatus]:
        """List all index statuses for a repository (all branches)."""
        pass
