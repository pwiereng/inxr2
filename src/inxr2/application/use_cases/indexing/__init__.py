"""Indexing use cases."""

from inxr2.application.dtos.indexing import (
    IndexRepositoryRequest,
    IndexRepositoryResponse,
)

from .get_index_status import (
    GetIndexStatusRequest,
    GetIndexStatusResponse,
    GetIndexStatusUseCase,
)
from .process_commit import (
    ProcessCommitRequest,
    ProcessCommitResult,
    ProcessCommitUseCase,
)
from .process_file import (
    ProcessFileRequest,
    ProcessFileResult,
    ProcessFileUseCase,
)
from .resolve_references import (
    ResolveReferencesRequest,
    ResolveReferencesResponse,
    ResolveReferencesUseCase,
)

__all__ = [
    "GetIndexStatusRequest",
    "GetIndexStatusResponse",
    "GetIndexStatusUseCase",
    "IndexRepositoryRequest",
    "IndexRepositoryResponse",
    "ProcessCommitRequest",
    "ProcessCommitResult",
    "ProcessCommitUseCase",
    "ProcessFileRequest",
    "ProcessFileResult",
    "ProcessFileUseCase",
    "ResolveReferencesRequest",
    "ResolveReferencesResponse",
    "ResolveReferencesUseCase",
]
