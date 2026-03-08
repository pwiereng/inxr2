"""Repository implementations."""

from .base_repository import BaseSQLAlchemyRepository, MapperProtocol
from .commit_adapter import PostgresCommitRepository
from .dependency_adapter import PostgresDependencyRepository
from .file_adapter import PostgresFileRepository
from .file_search_adapter import PostgresFileSearchRepository
from .file_version_adapter import PostgresFileVersionRepository
from .index_status_adapter import PostgresIndexStatusRepository
from .postgres_text_search import PostgresTextSearch
from .reference_adapter import PostgresReferenceRepository
from .repository_adapter import PostgresRepositoryAdapter
from .symbol_adapter import PostgresSymbolRepository
from .text_content_adapter import PostgresTextContentRepository

__all__ = [
    "BaseSQLAlchemyRepository",
    "MapperProtocol",
    "PostgresCommitRepository",
    "PostgresDependencyRepository",
    "PostgresFileRepository",
    "PostgresFileSearchRepository",
    "PostgresFileVersionRepository",
    "PostgresIndexStatusRepository",
    "PostgresReferenceRepository",
    "PostgresRepositoryAdapter",
    "PostgresSymbolRepository",
    "PostgresTextContentRepository",
    "PostgresTextSearch",
]
