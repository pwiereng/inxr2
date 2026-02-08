"""
Optimize file indexing use case.

This use case implements the content-hash optimization that reuses
symbols and references from files with identical content, avoiding
redundant parsing.
"""

from dataclasses import dataclass

from ...ports.repositories import (
    FileRepositoryPort,
    ReferenceRepositoryPort,
    SymbolRepositoryPort,
)


@dataclass
class OptimizeFileIndexingRequest:
    """
    Request to optimize file indexing via content-hash reuse.

    Attributes:
        target_file_id: Database ID of the file being indexed
        target_commit_id: Commit ID where the file appears
        target_repository_id: Repository ID
        content_hash: SHA-1 hash of file content
        content_hash_cache: In-memory cache mapping content_hash -> file_id
    """

    target_file_id: int
    target_commit_id: int
    target_repository_id: int
    content_hash: str
    content_hash_cache: dict[str, int]


@dataclass
class OptimizationResult:
    """
    Result of content-hash optimization attempt.

    Attributes:
        optimization_applied: True if a donor file was found and used
        donor_file_id: Database ID of the donor file (None if not optimized)
        symbols_copied: Number of symbols copied from donor
        references_copied: Number of references copied from donor
    """

    optimization_applied: bool
    donor_file_id: int | None
    symbols_copied: int
    references_copied: int


class OptimizeFileIndexingUseCase:
    """
    Use case for optimizing file indexing via content-hash reuse.

    When indexing a file, this use case checks if another file with the
    same content_hash has already been indexed. If so, it copies the
    symbols and references instead of re-parsing the file.

    This is a significant performance optimization for repositories with:
    - Many unchanged files across commits
    - Generated or vendored code
    - Large binary commits with few actual changes

    Example:
        If file X in commit A has hash "abc123" and was already parsed,
        and file Y in commit B also has hash "abc123", we can copy X's
        symbols/references to Y without parsing.
    """

    def __init__(
        self,
        file_repository: FileRepositoryPort,
        symbol_repository: SymbolRepositoryPort,
        reference_repository: ReferenceRepositoryPort,
    ) -> None:
        """
        Initialize use case with repository dependencies.

        Args:
            file_repository: Repository for file operations
            symbol_repository: Repository for symbol operations
            reference_repository: Repository for reference operations
        """
        self._file_repository = file_repository
        self._symbol_repository = symbol_repository
        self._reference_repository = reference_repository

    async def execute(self, request: OptimizeFileIndexingRequest) -> OptimizationResult:
        """
        Try to optimize file indexing via content-hash reuse.

        This method checks the content-hash cache for a donor file with
        identical content. If found, it copies symbols and references
        from the donor to the target file.

        Args:
            request: Optimization request parameters

        Returns:
            OptimizationResult indicating whether optimization was applied
            and how many symbols/references were copied.

        Note:
            If no donor is found (content hash not in cache), this returns
            an OptimizationResult with optimization_applied=False, indicating
            that the caller should proceed with normal parsing.
        """
        # Look up donor file in cache (in-memory operation - fast)
        donor_file_id = request.content_hash_cache.get(request.content_hash)

        if donor_file_id is None:
            # No donor found - optimization not applicable
            return OptimizationResult(
                optimization_applied=False,
                donor_file_id=None,
                symbols_copied=0,
                references_copied=0,
            )

        # Donor found - copy symbols and references
        copy_result = await self._symbol_repository.copy_symbols_to_file(
            source_file_id=donor_file_id,
            target_file_id=request.target_file_id,
            target_commit_id=request.target_commit_id,
            target_repository_id=request.target_repository_id,
        )

        references_copied = await self._reference_repository.copy_references_to_file(
            source_file_id=donor_file_id,
            target_file_id=request.target_file_id,
            target_commit_id=request.target_commit_id,
            target_repository_id=request.target_repository_id,
            symbol_id_mapping=copy_result.id_mapping,
        )

        return OptimizationResult(
            optimization_applied=True,
            donor_file_id=donor_file_id,
            symbols_copied=copy_result.count,
            references_copied=references_copied,
        )
