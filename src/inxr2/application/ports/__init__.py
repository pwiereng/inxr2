"""Application ports - interfaces for external dependencies."""

from .repositories import (
    FileRepositoryPort,
    SymbolRepositoryPort,
    TextContentRepositoryPort,
)
from .services import (
    ChangedFiles,
    CommitInfo,
    FileStat,
    FileSystemPort,
    GitServicePort,
    ParserServicePort,
    RepositoryInfo,
    TextSearchPort,
    TextSearchQuery,
    TextSearchResult,
)

__all__ = [
    "SymbolRepositoryPort",
    "FileRepositoryPort",
    "TextContentRepositoryPort",
    "ParserServicePort",
    "GitServicePort",
    "FileSystemPort",
    "FileStat",
    "CommitInfo",
    "ChangedFiles",
    "RepositoryInfo",
    "TextSearchPort",
    "TextSearchQuery",
    "TextSearchResult",
]
