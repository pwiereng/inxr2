"""File search use case - search files by name or path pattern."""

from dataclasses import dataclass

from ....domain.exceptions import CommitNotFound, RepositoryNotFound
from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    RepositoryPort,
)


@dataclass(frozen=True)
class SearchFilesRequest:
    """Request to search files by name or path pattern.

    Attributes:
        query: Search query for file name/path
        repository_name: Optional repository name filter
        branch: Optional branch name filter
        commit_hash: Optional commit hash filter (for time travel)
        language: Optional programming language filter
        limit: Maximum results to return (default: 20)
    """

    query: str
    repository_name: str | None = None
    branch: str | None = None
    commit_hash: str | None = None
    language: str | None = None
    scope: str = "latest"
    limit: int = 20


@dataclass(frozen=True)
class SearchFilesResultItem:
    """A single file search result.

    Attributes:
        id: File ID
        path: Full file path
        name: Filename extracted from path
        language: Programming language
        repository_id: Repository ID
        repository_name: Repository name
        commit_id: Commit ID (set when search was scoped to a commit)
        commit_hash: Commit hash string (set when search was scoped to a commit)
    """

    id: int
    path: str
    name: str
    language: str | None
    repository_id: int
    repository_name: str
    commit_id: int | None = None
    commit_hash: str | None = None


@dataclass(frozen=True)
class SearchFilesResponse:
    """Response from file search.

    Attributes:
        files: List of matching files with metadata
        total_count: Number of files returned
    """

    files: list[SearchFilesResultItem]
    total_count: int


class SearchFilesUseCase:
    """Use case for searching files by name or path pattern.

    This use case orchestrates file search by:
    1. Validating request parameters (branch/commit_hash require repository)
    2. Resolving repository name to ID
    3. Resolving commit hash or branch to commit ID
    4. Calling file repository to search by name
    5. Hydrating results with repository names and commit hashes
    6. Returning enriched results
    """

    def __init__(
        self,
        file_repo: FileRepositoryPort,
        repository_repo: RepositoryPort,
        commit_repo: CommitRepositoryPort,
    ):
        self._file_repo = file_repo
        self._repository_repo = repository_repo
        self._commit_repo = commit_repo

    async def execute(self, request: SearchFilesRequest) -> SearchFilesResponse:
        """Execute file search.

        Args:
            request: Search request parameters

        Returns:
            Search response with enriched results

        Raises:
            ValueError: If branch/commit_hash specified without repository
            RepositoryNotFound: If specified repository doesn't exist
            CommitNotFound: If specified commit hash doesn't exist
        """
        # Validate: branch/commit_hash require repository to be specified
        if (request.branch or request.commit_hash) and not request.repository_name:
            raise ValueError(
                "repository parameter is required when using branch or commit_hash"
            )

        # Resolve repository ID from name if provided
        repository_id: int | None = None
        if request.repository_name:
            repo = await self._repository_repo.find_by_name(request.repository_name)
            if not repo:
                raise RepositoryNotFound(request.repository_name)
            repository_id = repo.id

        # Resolve commit ID from hash or branch
        commit_id: int | None = None
        if request.commit_hash and repository_id is not None:
            commit = await self._commit_repo.find_by_hash(
                repository_id, request.commit_hash
            )
            if not commit:
                raise CommitNotFound(commit_hash=request.commit_hash)
            commit_id = commit.id
        elif request.branch and repository_id is not None:
            commit = await self._commit_repo.find_latest_by_branch(
                repository_id, request.branch
            )
            if commit:
                commit_id = commit.id

        # Search files
        files = await self._file_repo.search_by_name(
            query=request.query,
            repository_id=repository_id,
            commit_id=commit_id,
            language=request.language,
            limit=request.limit,
            scope=request.scope if repository_id is None else None,
        )

        # Collect unique repo IDs for bulk lookup
        repo_ids = {f.repository_id for f in files if f.repository_id is not None}

        # Fetch repositories in bulk
        repositories = await self._repository_repo.find_by_ids(list(repo_ids))
        repo_map: dict[int, str] = {
            r.id: r.name for r in repositories if r.id is not None
        }

        # Resolve commit hash if we have a commit context
        resolved_commit_hash: str | None = None
        if commit_id is not None:
            commit = await self._commit_repo.find_by_id(commit_id)
            if commit is not None:
                resolved_commit_hash = commit.commit_hash.value

        # Build result items
        results: list[SearchFilesResultItem] = []
        for file in files:
            if file.id is None or file.repository_id is None:
                raise ValueError(
                    "File search returned incomplete data; "
                    "this indicates a data integrity issue."
                )

            if file.repository_id not in repo_map:
                raise ValueError(
                    "File references unknown repository; data integrity issue."
                )

            filename = file.path.rsplit("/", 1)[-1] if "/" in file.path else file.path

            results.append(
                SearchFilesResultItem(
                    id=file.id,
                    path=file.path,
                    name=filename,
                    language=file.language,
                    repository_id=file.repository_id,
                    repository_name=repo_map[file.repository_id],
                    commit_id=commit_id,
                    commit_hash=resolved_commit_hash,
                )
            )

        return SearchFilesResponse(files=results, total_count=len(results))
