"""Repository port interfaces - data access abstractions.

These are Clean Architecture ports (interfaces) that define the contract
for data access. Implementations (adapters) will use specific persistence
mechanisms like PostgreSQL.

Each port is defined in its own module for easier navigation:
- repository_port: RepositoryPort
- commit_repository_port: CommitRepositoryPort
- file_repository_port: FileRepositoryPort, FileSearchPort, FileVersionPort
- symbol_repository_port: SymbolRepositoryPort
- reference_repository_port: ReferenceRepositoryPort
- index_status_repository_port: IndexStatusRepositoryPort
- text_content_repository_port: TextContentRepositoryPort
"""

from .commit_repository_port import CommitRepositoryPort
from .dependency_repository_port import DependencyRepositoryPort
from .file_rename_repository_port import FileRenameRepositoryPort
from .file_repository_port import FileRepositoryPort, FileSearchPort, FileVersionPort
from .index_status_repository_port import IndexStatusRepositoryPort
from .query_log_port import QueryLogEntry, QueryLogPort
from .reference_repository_port import ReferenceRepositoryPort
from .repository_port import RepositoryPort
from .symbol_repository_port import SymbolRepositoryPort
from .text_content_repository_port import TextContentRepositoryPort

__all__ = [
    "CommitRepositoryPort",
    "DependencyRepositoryPort",
    "FileRenameRepositoryPort",
    "FileRepositoryPort",
    "FileSearchPort",
    "FileVersionPort",
    "IndexStatusRepositoryPort",
    "QueryLogEntry",
    "QueryLogPort",
    "ReferenceRepositoryPort",
    "RepositoryPort",
    "SymbolRepositoryPort",
    "TextContentRepositoryPort",
]
