"""Symbol-related use cases."""

from .find_dead_code import (
    FindDeadCodeRequest,
    FindDeadCodeResponse,
    FindDeadCodeUseCase,
)
from .get_symbol_references import (
    GetSymbolReferencesRequest,
    GetSymbolReferencesResponse,
    GetSymbolReferencesUseCase,
    ReferenceWithFilePath,
)
from .get_symbol_tree import (
    GetSymbolTreeFilesResponse,
    GetSymbolTreeRequest,
    GetSymbolTreeSymbolsResponse,
    GetSymbolTreeUseCase,
    ResolvedInheritance,
    SymbolTreeFile,
    SymbolTreeNode,
)
from .search_symbols import (
    SearchSymbolsRequest,
    SearchSymbolsResponse,
    SearchSymbolsUseCase,
    SymbolWithFilePath,
)

__all__ = [
    "FindDeadCodeRequest",
    "FindDeadCodeResponse",
    "FindDeadCodeUseCase",
    "GetSymbolReferencesRequest",
    "GetSymbolReferencesResponse",
    "GetSymbolReferencesUseCase",
    "GetSymbolTreeFilesResponse",
    "GetSymbolTreeRequest",
    "GetSymbolTreeSymbolsResponse",
    "GetSymbolTreeUseCase",
    "ResolvedInheritance",
    "ReferenceWithFilePath",
    "SearchSymbolsRequest",
    "SearchSymbolsResponse",
    "SearchSymbolsUseCase",
    "SymbolTreeFile",
    "SymbolTreeNode",
    "SymbolWithFilePath",
]
