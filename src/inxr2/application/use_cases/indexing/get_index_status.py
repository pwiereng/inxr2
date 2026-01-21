"""Get index status use case.

This use case retrieves the indexing status for a repository,
including commit information and index counts.
"""

from dataclasses import dataclass
from datetime import datetime

from ...ports.repositories import IndexStatusRepositoryPort, RepositoryPort


@dataclass
class GetIndexStatusRequest:
    """Request to get index status for a repository.

    Args:
        repository_name: Name of the repository
        branch: Branch to check status for
        current_commit_hash: Current commit hash (from git) to compare against
    """

    repository_name: str
    branch: str
    current_commit_hash: str | None = None


@dataclass
class GetIndexStatusResponse:
    """Response containing index status information.

    Args:
        repository_name: Name of the repository
        branch: Branch being checked
        current_commit_hash: Current commit hash (from git)
        is_indexed: Whether the repository/branch has been indexed
        last_indexed_commit: Hash of last indexed commit (if indexed)
        last_indexed_at: Timestamp of last indexing (if indexed)
        total_files_indexed: Number of files indexed
        total_symbols_indexed: Number of symbols indexed
        total_references_indexed: Number of references indexed
        is_up_to_date: Whether index matches current commit
    """

    repository_name: str
    branch: str
    current_commit_hash: str | None
    is_indexed: bool
    last_indexed_commit: str | None = None
    last_indexed_at: datetime | None = None
    total_files_indexed: int = 0
    total_symbols_indexed: int = 0
    total_references_indexed: int = 0
    is_up_to_date: bool = False


class GetIndexStatusUseCase:
    """Use case for retrieving index status.

    This use case checks if a repository has been indexed and returns
    status information including counts and whether it's up to date.

    Dependencies are injected via constructor.
    """

    def __init__(
        self,
        repository_repo: RepositoryPort,
        index_status_repo: IndexStatusRepositoryPort,
    ) -> None:
        """Initialize use case.

        Args:
            repository_repo: Repository for accessing repository records
            index_status_repo: Repository for accessing index status records
        """
        self._repository_repo = repository_repo
        self._index_status_repo = index_status_repo

    async def execute(self, request: GetIndexStatusRequest) -> GetIndexStatusResponse:
        """Execute the get index status use case.

        Args:
            request: Request containing repository name and branch

        Returns:
            Response with index status information
        """
        # Find the repository
        db_repo = await self._repository_repo.find_by_name(request.repository_name)

        if not db_repo or db_repo.id is None:
            # Repository not in database - not indexed
            return GetIndexStatusResponse(
                repository_name=request.repository_name,
                branch=request.branch,
                current_commit_hash=request.current_commit_hash,
                is_indexed=False,
            )

        # Get index status for this branch
        index_status = await self._index_status_repo.find_by_repository_and_branch(
            db_repo.id, request.branch
        )

        if not index_status or not index_status.last_indexed_commit:
            # No index status found - not indexed for this branch
            return GetIndexStatusResponse(
                repository_name=request.repository_name,
                branch=request.branch,
                current_commit_hash=request.current_commit_hash,
                is_indexed=False,
            )

        # Determine if up to date
        is_up_to_date = (
            request.current_commit_hash is not None
            and index_status.last_indexed_commit == request.current_commit_hash
        )

        return GetIndexStatusResponse(
            repository_name=request.repository_name,
            branch=request.branch,
            current_commit_hash=request.current_commit_hash,
            is_indexed=True,
            last_indexed_commit=index_status.last_indexed_commit,
            last_indexed_at=index_status.last_indexed_at,
            total_files_indexed=index_status.total_files_indexed,
            total_symbols_indexed=index_status.total_symbols_indexed,
            total_references_indexed=index_status.total_references_indexed,
            is_up_to_date=is_up_to_date,
        )
