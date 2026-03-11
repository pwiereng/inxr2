"""Search dependencies use case.

Searches dependencies by package name with partial, case-insensitive matching,
with optional filtering by repository, language, dependency type, and directness.
"""

from dataclasses import dataclass, field

from ...ports.repositories import (
    DependencyRepositoryPort,
    FileRepositoryPort,
    RepositoryPort,
)


@dataclass(frozen=True)
class SearchDependenciesRequest:
    """Request to search dependencies by package name."""

    query: str
    repository_id: int | None = None
    language: str | None = None
    dependency_type: str | None = None
    is_direct: bool | None = None
    branch: str | None = None
    scope: str = "latest"
    limit: int = 20
    offset: int = 0


@dataclass
class SearchDependencyItem:
    """A single dependency search result."""

    id: int
    package_name: str
    language: str
    version_spec: str | None
    resolved_version: str | None
    dependency_type: str
    is_direct: bool
    file_id: int
    file_path: str | None
    repository_id: int
    repository_name: str


@dataclass
class SearchDependenciesResponse:
    """Response containing dependency search results."""

    results: list[SearchDependencyItem] = field(default_factory=list)
    total: int = 0
    query: str = ""
    limit: int = 20
    offset: int = 0


class SearchDependenciesUseCase:
    """Use case for searching dependencies by package name."""

    def __init__(
        self,
        dependency_repo: DependencyRepositoryPort,
        file_repo: FileRepositoryPort,
        repository_repo: RepositoryPort,
    ) -> None:
        self._dependency_repo = dependency_repo
        self._file_repo = file_repo
        self._repository_repo = repository_repo

    async def execute(
        self, request: SearchDependenciesRequest
    ) -> SearchDependenciesResponse:
        """Execute dependency search."""
        deps, total = await self._dependency_repo.search_by_package_name(
            query=request.query,
            repository_id=request.repository_id,
            language=request.language,
            dependency_type=request.dependency_type,
            is_direct=request.is_direct,
            branch=request.branch,
            scope=request.scope if request.repository_id is None else None,
            limit=request.limit,
            offset=request.offset,
        )

        if not deps:
            return SearchDependenciesResponse(
                results=[],
                total=total,
                query=request.query,
                limit=request.limit,
                offset=request.offset,
            )

        # Batch-fetch file paths
        file_ids = list({d.file_id for d in deps})
        file_entities = await self._file_repo.find_by_ids(file_ids)
        file_path_map = {fid: f.path for fid, f in file_entities.items()}

        # Batch-fetch repository names
        repo_ids = list({d.repository_id for d in deps})
        repositories = await self._repository_repo.find_by_ids(repo_ids)
        repo_map = {r.id: r.name for r in repositories if r.id is not None}

        items: list[SearchDependencyItem] = []
        for d in deps:
            if d.id is None:
                raise ValueError(
                    f"Persisted dependency missing id: {d.package_name}"
                )
            items.append(
                SearchDependencyItem(
                    id=d.id,
                    package_name=d.package_name,
                    language=d.language,
                    version_spec=d.version_spec,
                    resolved_version=d.resolved_version,
                    dependency_type=d.dependency_type,
                    is_direct=d.is_direct,
                    file_id=d.file_id,
                    file_path=file_path_map.get(d.file_id),
                    repository_id=d.repository_id,
                    repository_name=repo_map.get(d.repository_id, "unknown"),
                )
            )

        return SearchDependenciesResponse(
            results=items,
            total=total,
            query=request.query,
            limit=request.limit,
            offset=request.offset,
        )
