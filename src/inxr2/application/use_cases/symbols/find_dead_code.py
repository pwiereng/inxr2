"""Find dead code use case.

Lists symbols that no reference uses, across every symbol in scope, with
file path enrichment and coverage counts.
"""

from dataclasses import dataclass

from ....domain.constants import QueryDefaults
from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    ReferenceRepositoryPort,
)
from .search_symbols import SymbolWithFilePath


@dataclass
class FindDeadCodeRequest:
    """Request to find unreferenced symbols.

    Args:
        repository_id: Repository to scan
        kind: Optional symbol kind filter (e.g., "function", "class")
        branch: Optional branch whose head is scanned (default branch if None)
        commit_hash: Optional commit to scan instead of a branch head.
            Raises ValueError if it cannot be resolved.
        limit: Page size
        offset: Page offset
    """

    repository_id: int
    kind: str | None = None
    branch: str | None = None
    commit_hash: str | None = None
    limit: int = QueryDefaults.SYMBOL_SEARCH_LIMIT
    offset: int = 0


@dataclass
class FindDeadCodeResponse:
    """One page of unreferenced symbols plus scan coverage.

    Args:
        symbols: Unreferenced symbols with file paths, one per name
        total: Unreferenced names across all pages
        scanned: Symbols checked (all symbols in scope matching the kind)
        entry_points_excluded: Unreferenced symbols left out because the
            runtime or a test runner invokes them (@main, tests, fixtures)
        limit: Limit used in request
        offset: Offset used in request
    """

    symbols: list[SymbolWithFilePath]
    total: int
    scanned: int
    entry_points_excluded: int
    limit: int
    offset: int


class FindDeadCodeUseCase:
    """Use case for finding symbols with no references (dead code).

    Handles:
    - Commit resolution for time travel
    - Delegating the whole-scope scan to the reference repository
    - Batch file path enrichment
    """

    def __init__(
        self,
        reference_repo: ReferenceRepositoryPort,
        file_repo: FileRepositoryPort,
        commit_repo: CommitRepositoryPort,
    ) -> None:
        self._reference_repo = reference_repo
        self._file_repo = file_repo
        self._commit_repo = commit_repo

    async def execute(self, request: FindDeadCodeRequest) -> FindDeadCodeResponse:
        """Execute the dead code scan.

        Raises:
            ValueError: If commit_hash is provided but cannot be resolved
        """
        commit_id: int | None = None
        if request.commit_hash:
            commit = await self._commit_repo.find_by_hash(
                request.repository_id, request.commit_hash
            )
            if not commit:
                raise ValueError(
                    f"Commit hash '{request.commit_hash}' not found "
                    f"for repository {request.repository_id}"
                )
            commit_id = commit.id

        page = await self._reference_repo.find_unreferenced_symbols(
            request.repository_id,
            kind=request.kind,
            branch=request.branch,
            commit_id=commit_id,
            limit=request.limit,
            offset=request.offset,
        )

        files_by_id = await self._file_repo.find_by_ids(
            list({s.file_id for s in page.symbols})
        )
        symbols = [
            SymbolWithFilePath(
                symbol=s,
                file_path=f.path if (f := files_by_id.get(s.file_id)) else None,
            )
            for s in page.symbols
        ]

        return FindDeadCodeResponse(
            symbols=symbols,
            total=page.total,
            scanned=page.scanned,
            entry_points_excluded=page.entry_points,
            limit=request.limit,
            offset=request.offset,
        )
