"""Service port interfaces - external service abstractions.

Each port is defined in its own module for easier navigation:
- git_service: GitServicePort, CommitInfo, ChangedFiles, RepositoryInfo, BlameLineInfo
- parser_service: ParserServicePort, PlaintextParserPort
- config_service: ConfigServicePort
- filesystem_service: FileSystemPort, FileStat
- text_search_service: TextSearchPort, TextSearchResult, TextSearchQuery
- indexing_orchestrator: IndexingOrchestratorPort, ProgressCallback
"""

from .config_service import ConfigServicePort
from .filesystem_service import FileStat, FileSystemPort
from .git_service import (
    BlameLineInfo,
    ChangedFiles,
    CommitInfo,
    GitServicePort,
    RepositoryInfo,
)
from .indexing_orchestrator import IndexingOrchestratorPort, ProgressCallback
from .parser_service import ParserServicePort, PlaintextParserPort
from .text_search_service import TextSearchPort, TextSearchQuery, TextSearchResult

__all__ = [
    "BlameLineInfo",
    "ChangedFiles",
    "CommitInfo",
    "ConfigServicePort",
    "FileStat",
    "FileSystemPort",
    "GitServicePort",
    "IndexingOrchestratorPort",
    "ParserServicePort",
    "PlaintextParserPort",
    "ProgressCallback",
    "RepositoryInfo",
    "TextSearchPort",
    "TextSearchQuery",
    "TextSearchResult",
]
