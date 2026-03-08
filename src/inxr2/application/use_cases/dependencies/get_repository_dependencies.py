"""Get repository dependencies use case.

Retrieves dependencies for a repository at a specific commit or branch,
with optional filtering by language, dependency type, and direct/transitive.
"""

from dataclasses import dataclass, field

from ...ports.repositories import (
    CommitRepositoryPort,
    DependencyRepositoryPort,
    FileRepositoryPort,
    RepositoryPort,
)


@dataclass
class GetRepositoryDependenciesRequest:
    """Request to get dependencies for a repository."""

    repository_name: str | None = None
    repository_id: int | None = None
    commit_hash: str | None = None
    branch: str | None = None
    language: str | None = None
    dependency_type: str | None = None
    is_direct: bool | None = None

    def __post_init__(self) -> None:
        if self.repository_id is None and self.repository_name is None:
            raise ValueError("Either repository_id or repository_name must be provided")


@dataclass
class DependencyItem:
    """A dependency with its file context."""

    id: int
    package_name: str
    language: str
    version_spec: str | None
    resolved_version: str | None
    dependency_type: str
    is_direct: bool
    file_id: int
    file_path: str | None = None


@dataclass
class GetRepositoryDependenciesResponse:
    """Response containing repository dependencies."""

    repository_id: int
    repository_name: str
    commit_hash: str | None
    items: list[DependencyItem] = field(default_factory=list)
    total: int = 0


class GetRepositoryDependenciesUseCase:
    """Use case for getting dependencies at a specific commit/branch."""

    def __init__(
        self,
        repository_repo: RepositoryPort,
        dependency_repo: DependencyRepositoryPort,
        commit_repo: CommitRepositoryPort,
        file_repo: FileRepositoryPort,
    ) -> None:
        self._repository_repo = repository_repo
        self._dependency_repo = dependency_repo
        self._commit_repo = commit_repo
        self._file_repo = file_repo

    async def execute(
        self, request: GetRepositoryDependenciesRequest
    ) -> GetRepositoryDependenciesResponse:
        """Execute dependency retrieval."""
        # Resolve repository
        if request.repository_id is not None:
            repository = await self._repository_repo.find_by_id(request.repository_id)
        else:
            repository = await self._repository_repo.find_by_name(
                request.repository_name or ""
            )

        if not repository or repository.id is None:
            raise ValueError("Repository not found")

        repo_id = repository.id

        # Resolve commit: explicit hash > branch > latest on default branch
        commit_hash = request.commit_hash
        if commit_hash:
            commit = await self._commit_repo.find_by_hash(repo_id, commit_hash)
            if not commit or commit.id is None:
                raise ValueError(f"Commit not found: {commit_hash}")
            commit_id = commit.id
        elif request.branch:
            commit = await self._commit_repo.find_latest_by_branch(
                repo_id, request.branch
            )
            if not commit or commit.id is None:
                raise ValueError(
                    f"No indexed commits found for branch '{request.branch}'"
                )
            commit_id = commit.id
            commit_hash = commit.commit_hash.value
        else:
            # Default: latest commit on default branch
            branch = repository.default_branch or "main"
            commit = await self._commit_repo.find_latest_by_branch(repo_id, branch)
            if not commit or commit.id is None:
                raise ValueError("No indexed commits found")
            commit_id = commit.id
            commit_hash = commit.commit_hash.value

        # Query dependencies at this commit
        deps = await self._dependency_repo.find_by_commit(
            commit_id=commit_id,
            repository_id=repo_id,
            language=request.language,
            dependency_type=request.dependency_type,
            is_direct=request.is_direct,
        )

        # Batch-fetch file paths for all unique file_ids
        file_ids = list({d.file_id for d in deps})
        file_path_map: dict[int, str] = {}
        if file_ids:
            for fid in file_ids:
                file_entity = await self._file_repo.find_by_id(fid)
                if file_entity:
                    file_path_map[fid] = file_entity.path

        # Build response items
        items = [
            DependencyItem(
                id=d.id if d.id is not None else 0,
                package_name=d.package_name,
                language=d.language,
                version_spec=d.version_spec,
                resolved_version=d.resolved_version,
                dependency_type=d.dependency_type,
                is_direct=d.is_direct,
                file_id=d.file_id,
                file_path=file_path_map.get(d.file_id),
            )
            for d in deps
        ]

        return GetRepositoryDependenciesResponse(
            repository_id=repo_id,
            repository_name=repository.name,
            commit_hash=commit_hash,
            items=items,
            total=len(items),
        )
