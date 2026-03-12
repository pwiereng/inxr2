"""
Data Transfer Objects for application layer.

DTOs are used to transfer data between layers without coupling to domain entities.
"""

from .indexing import (
    DBQueryStats,
    IndexingProgress,
    IndexRepositoryRequest,
    IndexRepositoryResponse,
    ProgressCallback,
)

__all__ = [
    "DBQueryStats",
    "IndexingProgress",
    "IndexRepositoryRequest",
    "IndexRepositoryResponse",
    "ProgressCallback",
]
