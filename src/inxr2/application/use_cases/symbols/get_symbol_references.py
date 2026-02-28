"""Get symbol references use case.

Handles fetching references to a symbol with file path enrichment.
"""

from dataclasses import dataclass

from ....domain.entities import Reference
from ....domain.exceptions import SymbolNotFound
from ...ports.repositories import (
    CommitRepositoryPort,
    FileRepositoryPort,
    ReferenceRepositoryPort,
    SymbolRepositoryPort,
)


@dataclass
class ReferenceWithFilePath:
    """Reference enriched with source file path for display.

    Contains all reference data plus the source file path resolved from source_file_id.
    """

    reference: Reference
    source_file_path: str | None


@dataclass
class GetSymbolReferencesRequest:
    """Request to get symbol references.

    Args:
        symbol_id: The symbol ID to find references for
        by_name: If True, find all references matching the symbol name
                 (useful when multiple symbols share the same name)
        commit_hash: Optional commit hash for time travel
        branch: Optional branch name to filter references (only show refs from this branch)
        limit: Maximum results to return
    """

    symbol_id: int
    by_name: bool = True
    commit_hash: str | None = None
    branch: str | None = None
    limit: int = 100


@dataclass
class GetSymbolReferencesResponse:
    """Response containing symbol references.

    Args:
        references: List of references with file paths
        total: Total number of references
        symbol_name: Name of the symbol being referenced
    """

    references: list[ReferenceWithFilePath]
    total: int
    symbol_name: str


class GetSymbolReferencesUseCase:
    """Use case for finding references to a symbol.

    Fetches references either by symbol ID or by symbol name (for disambiguation
    when multiple symbols share the same name), and enriches with file paths.

    Handles:
    - Looking up the symbol
    - Decision logic for by_name vs by_id search
    - Commit resolution for time travel
    - Batch file path enrichment
    """

    def __init__(
        self,
        symbol_repo: SymbolRepositoryPort,
        reference_repo: ReferenceRepositoryPort,
        file_repo: FileRepositoryPort,
        commit_repo: CommitRepositoryPort | None = None,
    ) -> None:
        """Initialize use case with dependencies.

        Args:
            symbol_repo: Repository for accessing symbols
            reference_repo: Repository for accessing references
            file_repo: Repository for accessing files (for path enrichment)
            commit_repo: Optional repository for commit hash resolution
        """
        self._symbol_repo = symbol_repo
        self._reference_repo = reference_repo
        self._file_repo = file_repo
        self._commit_repo = commit_repo

    async def execute(
        self, request: GetSymbolReferencesRequest
    ) -> GetSymbolReferencesResponse:
        """Execute symbol references lookup.

        Args:
            request: Request parameters

        Returns:
            GetSymbolReferencesResponse with enriched references

        Raises:
            SymbolNotFound: If symbol_id doesn't exist
            ValueError: If commit_hash is provided but cannot be resolved
        """
        # Get the symbol first
        symbol = await self._symbol_repo.find_by_id(request.symbol_id)
        if not symbol:
            raise SymbolNotFound(str(request.symbol_id))

        # Resolve commit_id if commit_hash provided
        commit_id: int | None = None
        if request.commit_hash:
            if not self._commit_repo:
                raise ValueError(
                    "commit_hash was provided but commit repository is not available"
                )
            commit = await self._commit_repo.find_by_hash(
                symbol.repository_id, request.commit_hash
            )
            if not commit:
                raise ValueError(
                    f"Unknown commit hash for repository {symbol.repository_id}: "
                    f"{request.commit_hash}"
                )
            commit_id = commit.id

        # Get references - either by symbol ID or by name
        if request.by_name:
            # Find all references matching the symbol name (for disambiguation)
            references = await self._reference_repo.find_references_by_text(
                symbol.name,
                symbol.repository_id,
                limit=request.limit,
                commit_id=commit_id,
                branch=request.branch,
            )
        else:
            # Find only references pointing to this specific symbol
            references = await self._reference_repo.find_references_to_symbol(
                request.symbol_id,
                limit=request.limit,
                commit_id=commit_id,
                branch=request.branch,
                repository_id=symbol.repository_id,
            )

        # Batch fetch file paths
        enriched_references = await self._enrich_with_file_paths(references)

        return GetSymbolReferencesResponse(
            references=enriched_references,
            total=len(enriched_references),
            symbol_name=symbol.name,
        )

    async def _enrich_with_file_paths(
        self, references: list[Reference]
    ) -> list[ReferenceWithFilePath]:
        """Enrich references with source file paths using batch fetching.

        Args:
            references: List of references to enrich

        Returns:
            List of references with source file paths
        """
        # Collect unique source file IDs
        file_ids = list({r.source_file_id for r in references if r.source_file_id})

        # Batch fetch files
        files_by_id = await self._file_repo.find_by_ids(file_ids)

        # Build enriched results
        result = []
        for ref in references:
            source_file_path = None
            if ref.source_file_id:
                file = files_by_id.get(ref.source_file_id)
                if file:
                    source_file_path = file.path
            result.append(
                ReferenceWithFilePath(reference=ref, source_file_path=source_file_path)
            )
        return result
