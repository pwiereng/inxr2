"""Indexing orchestrator port interface."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ...dtos.indexing import ProgressCallback

if TYPE_CHECKING:
    from ...dtos.indexing import IndexRepositoryRequest, IndexRepositoryResponse


class IndexingOrchestratorPort(ABC):
    """
    Port for indexing orchestration.

    This port defines the interface for repository indexing operations,
    allowing different indexing strategies and implementations to be swapped.
    """

    @abstractmethod
    async def index_repository(
        self,
        request: "IndexRepositoryRequest",
        progress_callback: ProgressCallback | None = None,
    ) -> "IndexRepositoryResponse":
        """
        Index a repository with specified strategy.

        Args:
            request: Indexing request parameters
            progress_callback: Optional callback for progress updates

        Returns:
            Indexing results with statistics

        Raises:
            ValueError: If request parameters are invalid
            RuntimeError: If indexing fails critically
        """
        pass
