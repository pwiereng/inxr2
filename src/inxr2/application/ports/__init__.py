"""Application ports - interfaces for external dependencies."""

from .repositories import (
    FileRepositoryPort,
    SymbolRepositoryPort,
    TextContentRepositoryPort,
)
from .services import (
    FileStat,
    FileSystemPort,
    GitServicePort,
    ParserServicePort,
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
    "TextSearchPort",
    "TextSearchQuery",
    "TextSearchResult",
]
