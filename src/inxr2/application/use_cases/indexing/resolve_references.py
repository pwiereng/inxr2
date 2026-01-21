"""Resolve references use case.

This use case handles the post-indexing step of matching references
to their target symbols in the codebase.
"""

from dataclasses import dataclass

from ...ports.repositories import ReferenceRepositoryPort


@dataclass
class ResolveReferencesRequest:
    """Request to resolve unlinked references in a repository.

    Args:
        repository_id: The repository ID to resolve references for
        commit_aware: If True, only match references to symbols from the
                     same commit (for time travel consistency). If False,
                     match across all commits in the repository.
    """

    repository_id: int
    commit_aware: bool = False


@dataclass
class ResolveReferencesResponse:
    """Response from resolving references.

    Args:
        resolved_count: Number of references that were resolved
    """

    resolved_count: int


class ResolveReferencesUseCase:
    """Use case for resolving references to their target symbols.

    After indexing, this use case matches reference_text to symbol names
    and updates the target_symbol_id for each reference. This enables
    "find usages" and "go to definition" functionality.

    Two modes are supported:
    - commit_aware=False: Match references to any symbol in the repository
      (useful for incremental indexing where symbols may exist in other commits)
    - commit_aware=True: Only match references to symbols from the same commit
      (ensures time travel navigation stays within a consistent version)

    Dependencies are injected via constructor.
    """

    def __init__(self, reference_repository: ReferenceRepositoryPort) -> None:
        """Initialize use case.

        Args:
            reference_repository: Repository for accessing references
        """
        self._reference_repository = reference_repository

    async def execute(
        self, request: ResolveReferencesRequest
    ) -> ResolveReferencesResponse:
        """Execute reference resolution.

        Args:
            request: Resolution request parameters

        Returns:
            Resolution results with count of resolved references
        """
        resolved_count = await self._reference_repository.resolve_unlinked_references(
            repository_id=request.repository_id,
            commit_aware=request.commit_aware,
        )

        return ResolveReferencesResponse(resolved_count=resolved_count)
