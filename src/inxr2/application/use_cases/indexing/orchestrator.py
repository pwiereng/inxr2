"""
Indexing orchestrator DTOs — re-exported from application.dtos.indexing.

This module re-exports the DTOs for backward compatibility. New code should
import directly from ``inxr2.application.dtos.indexing``.
"""

from inxr2.application.dtos.indexing import (
    DBQueryStats,
    IndexRepositoryRequest,
    IndexRepositoryResponse,
)

__all__ = [
    "DBQueryStats",
    "IndexRepositoryRequest",
    "IndexRepositoryResponse",
]
