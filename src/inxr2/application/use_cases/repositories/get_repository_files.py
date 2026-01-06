"""Get repository files use case."""

from dataclasses import dataclass

from ....domain.entities import File
from ...ports.repositories import FileRepositoryPort, RepositoryPort


@dataclass
class GetRepositoryFilesRequest:
    """Request to get files for a repository."""

    repository_id: int


@dataclass
class GetRepositoryFilesResponse:
    """Response with repository files."""

    files: list[File]
    total_count: int


class GetRepositoryFilesUseCase:
    """Use case for getting all files in a repository."""

    def __init__(
        self, repository_repo: RepositoryPort, file_repo: FileRepositoryPort
    ) -> None:
        """
        Initialize use case.

        Args:
            repository_repo: Repository for accessing repositories
            file_repo: Repository for accessing files
        """
        self._repository_repo = repository_repo
        self._file_repo = file_repo

    async def execute(
        self, request: GetRepositoryFilesRequest
    ) -> GetRepositoryFilesResponse:
        """
        Execute file listing for repository.

        Args:
            request: Request with repository ID

        Returns:
            List of files in the repository
        """
        # Verify repository exists
        repository = await self._repository_repo.find_by_id(request.repository_id)
        if not repository:
            raise ValueError(f"Repository {request.repository_id} not found")

        # Get all files for this repository
        files = await self._file_repo.list_by_repository(request.repository_id)

        return GetRepositoryFilesResponse(files=files, total_count=len(files))
